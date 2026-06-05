"""A Client."""

from __future__ import annotations

import asyncio
import os
import threading
from concurrent.futures import Future
from typing import TYPE_CHECKING

import zmq
from zmq.asyncio import Context, Poller, Socket

from .interrupter import Interrupter
from .message import Flag, Request, Response
from .utils import logger, run_event_loop

if TYPE_CHECKING:
    import sys
    from typing import Any, Callable

    # the Self type was added in Python 3.11 (PEP 673)
    # using TypeVar is equivalent for < 3.11
    if sys.version_info >= (3, 11):
        from typing import Self
    else:
        from typing import TypeVar

        Self = TypeVar("Self", bound="Client")  # pyright: ignore[reportUnreachable]


class Client:
    """A Client."""

    def __init__(self, *, host: str = "127.0.0.1", port: int = 1875, flags: Flag = Flag.PICKLE) -> None:
        """A Client.

        Args:
            host: The hostname (or IP address) that the broker is running on.
            port: The network port that the broker is running on.
            flags: The serialization and compression algorithms to apply to a
                request before sending the byte stream.
        """
        self.flags: Flag = flags
        """The serialization and compression algorithms to apply to a request before sending the byte stream."""

        self._id: str = hex(id(self))
        self._transaction: int = 0
        self._futures: dict[int, Future[Any]] = {}
        self._context: Context = Context()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue[tuple[bytes, bytes] | tuple[None, None]] = asyncio.Queue()

        # For Ctrl+C to work on Windows
        self._interrupter: Interrupter = Interrupter(f"Client[{self._id}]")

        # For sending/receiving messages to/from the Broker
        self._socket: Socket = self._context.socket(zmq.DEALER)
        self._socket.setsockopt(zmq.IDENTITY, b"client" + os.urandom(8))
        _ = self._socket.connect(f"tcp://{host}:{port}")

        # For waking up the Poller to send another request
        self._wakeup_sender: Socket = self._context.socket(zmq.PAIR)
        self._wakeup_receiver: Socket = self._context.socket(zmq.PAIR)
        _ = self._wakeup_sender.connect(f"inproc://wakeup[{self._id}]")
        _ = self._wakeup_receiver.bind(f"inproc://wakeup[{self._id}]")

        # Polls for events on the asyncio event loop
        self._poller: Poller = Poller()
        self._poller.register(self._socket, zmq.POLLIN)
        self._poller.register(self._interrupter.subscriber, zmq.POLLIN)
        self._poller.register(self._wakeup_receiver, zmq.POLLIN)

        # Must run the asyncio event loop in a separate thread
        async def tasks() -> None:
            _ = await asyncio.gather(self._handle_messages(), self._wakeup_event())

        threading.Thread(target=run_event_loop, daemon=True, args=(tasks(),)).start()
        while not self._loop:
            continue

    def __del__(self) -> None:
        """Close the socket and destroy the context."""
        self.disconnect()

    def __enter__(self: Self) -> Self:  # noqa: PYI019
        """Enter a context manager."""
        return self

    def __exit__(self, *_: object) -> None:
        """Exit the context manager."""
        self.disconnect()

    def __repr__(self) -> str:  # pyright: ignore[reportImplicitOverride]
        """Returns the class name and the network address of the Client."""
        return f"{self.__class__.__name__}[{self._id}]"

    def _create_future(self, worker_name: str, attr: str, *args: Any, **kwargs: Any) -> Future[Any]:
        if self._loop is None:
            msg = "Event loop not running, cannot send request"
            raise RuntimeError(msg)

        self._transaction += 1
        future: Future[Any] = Future()
        self._futures[self._transaction] = future

        request = Request(
            id=self._transaction,
            worker=worker_name,
            attribute=attr,
            args=args,
            kwargs=kwargs,
        ).to_bytes(self.flags)

        _ = self._loop.call_soon_threadsafe(self._queue.put_nowait, (worker_name.encode(), request))
        return future

    async def _wakeup_event(self) -> None:
        while True:
            worker, request = await self._queue.get()
            if request is None:
                self._queue.task_done()
                break

            _ = await self._wakeup_sender.send_multipart((worker, request))  # pyright: ignore[reportUnknownMemberType]

    async def _handle_messages(self) -> None:
        poller = self._poller
        socket = self._socket
        wakeup = self._wakeup_receiver
        self._loop = asyncio.get_running_loop()
        logger.debug("%s connected", self)
        while True:
            event = dict(await poller.poll())

            if event.get(wakeup):  # Send request
                worker, request = await wakeup.recv_multipart()
                logger.debug("%s sent request to %r", self, worker)
                _ = await socket.send_multipart((worker, request))  # pyright: ignore[reportUnknownMemberType]
            elif event.get(socket):  # Handle reply
                worker, response = await socket.recv_multipart()
                logger.debug("%s received response from %r", self, worker)
                r = Response.from_bytes(response)
                future = self._futures.pop(r.id)
                if r.ok:
                    future.set_result(r.result)
                else:
                    future.set_exception(RuntimeError(r.result))

            else:  # Shutdown
                _ = self._loop.call_soon_threadsafe(self._queue.put_nowait, (None, None))
                break

    def disconnect(self) -> None:
        """Close the socket and destroy the context."""
        if self._loop is None:
            return

        self._interrupter()
        self._interrupter.shutdown()
        self._poller.unregister(self._socket)
        self._poller.unregister(self._interrupter.subscriber)
        self._poller.unregister(self._wakeup_receiver)
        self._socket.close(linger=0)
        self._wakeup_receiver.close(linger=0)
        self._wakeup_sender.close(linger=0)
        self._context.destroy()
        self._loop = None
        logger.debug("%s disconnected", self)

    def link(self, worker_name: str) -> Link:
        """Link with a worker.

        Args:
            worker_name: The name of a [Worker][msl.network.worker.Worker] to create a link with.
        """
        return Link(self._create_future, worker_name)

    def workers(self, timeout: float | None = None) -> list[str]:
        """Request the names of the [Worker][msl.network.worker.Worker]s that are available.

        Args:
            timeout: The number of seconds to wait for the result if the future
                isn't done. If None, then there is no limit on the wait time.

        Returns:
            The names of the [Worker][msl.network.worker.Worker]s that are available
                to be [Link][msl.network.client.Link]ed with.
        """
        return sorted(self._create_future("broker", "").result(timeout))


class Link:
    """A link with a Worker."""

    def __init__(self, create_future: Callable[..., Future[Any]], worker_name: str) -> None:
        """A link with a Worker."""
        self._worker_name: str = worker_name
        self._create_future: Callable[..., Future[Any]] = create_future

    def __repr__(self) -> str:  # pyright: ignore[reportImplicitOverride]
        """Returns a string representation of the Worker that the Client is linked with."""
        return f"{self.__class__.__name__}(worker={self._worker_name})"

    def __getattr__(self, attr: str) -> Callable[..., Future[Any]]:
        """Send a request to the linked Worker."""

        def wrapper(*args: Any, **kwargs: Any) -> Future[Any]:
            return self._create_future(self._worker_name, attr, *args, **kwargs)

        return wrapper
