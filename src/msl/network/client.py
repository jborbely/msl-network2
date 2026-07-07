"""A Client."""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import Future
from contextlib import contextmanager
from threading import Thread
from typing import TYPE_CHECKING

import zmq
from zmq.asyncio import Context, Poller, Socket

from .interrupter import Interrupter
from .message import Flag, Request, Response
from .utils import BROKER_PORT, logger, run_event_loop

if TYPE_CHECKING:
    import sys
    from collections.abc import Callable, Generator
    from typing import Any

    # the Self type was added in Python 3.11 (PEP 673)
    # using TypeVar is equivalent for < 3.11
    if sys.version_info >= (3, 11):
        from typing import Self
    else:
        from typing import TypeVar

        Self = TypeVar("Self", bound="Client")  # pyright: ignore[reportUnreachable]

    from .auth import AuthCurve, AuthPlain
    from .typing import FutureOrResult


class Client:
    """A Client."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        host: str = "127.0.0.1",
        port: int = BROKER_PORT,
        flag: Flag = Flag.PICKLE,
        domain: str = "*",
        curve: AuthCurve | None = None,
        plain: AuthPlain | None = None,
    ) -> None:
        """A Client.

        Args:
            host: The hostname (or IP address) that the [Broker][] is running on.
            port: The network port that the [Broker][] is running on.
            flag: The serialisation and compression algorithms to apply to a
                request before sending the byte stream.
            domain: The domain to use for [CURVE](https://rfc.zeromq.org/spec/26/) or
                [PLAIN](https://rfc.zeromq.org/spec/24/) authentication.
            curve: The [CURVE](https://rfc.zeromq.org/spec/26/) authentication to use.
            plain: The [PLAIN](https://rfc.zeromq.org/spec/24/) authentication to use.
        """
        self.flag: Flag = flag
        """The serialisation and compression algorithms to apply to a request before sending the byte stream."""

        self._host_port: tuple[str, int] = (host, port)
        self._id: str = os.urandom(8).hex()
        self._transaction: int = 0
        self._async_client: _AsyncClient | None = None

        if curve is not None and plain is not None:
            msg = "Cannot use both PLAIN and CURVE authentication, select only one authentication mechanism"
            raise ValueError(msg)

        self._thread: Thread = Thread(
            target=run_event_loop, daemon=True, args=(_create_async_client(self, domain.encode(), curve, plain),)
        )
        self._thread.start()

        while self._async_client is None:
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
        """Returns the string representation."""
        host, port = self._host_port
        flag = "|".join(f.name or "" for f in Flag if self.flag & f)
        return f"{self.__class__.__name__}(host={host!r}, port={port}, flag={flag!r}, id={self._id!r})"

    def __str__(self) -> str:  # pyright: ignore[reportImplicitOverride]
        """Returns the string representation with only the ID."""
        return f"{self.__class__.__name__}[{self._id}]"

    def _create_future(self, service_name: str, attr: str, *args: Any, **kwargs: Any) -> Future[Any]:
        if self._async_client is None:
            msg = "Event loop not running, cannot send request"
            raise RuntimeError(msg)

        self._transaction += 1
        request = Request(
            id=self._transaction,
            service=service_name,
            attribute=attr,
            args=args,
            kwargs=kwargs,
        ).to_bytes(self.flag)

        return self._async_client.put_nowait(self._transaction, (service_name.encode(), request))

    def disconnect(self) -> None:
        """Close the connection."""
        if self._async_client is None:
            return

        self._async_client.disconnect()
        self._async_client = None
        self._thread.join()
        logger.debug("%s disconnected", self)

    @contextmanager
    def flag_at(self, flag: Flag) -> Generator[None, None, None]:
        """Use as a context manager to temporarily change the [flag][..flag] value.

        !!! example
            ```python
            from msl.network import Client, Flag

            client = Client(flag=Flag.PICKLE)
            link = client.link("Something")

            # uses PICKLE to serialise the request
            link.do_something()

            with client.flag_at(Flag.JSON):
                # uses JSON to serialise the request
                link.do_something_else()

            # uses PICKLE to serialise the request
            link.do_something()
        ```

        Args:
            flag: The temporary flag to use while within the context. Once the
                context exits, the value is set to the original value.
        """
        original = self.flag
        self.flag = flag
        try:
            yield
        finally:
            self.flag = original

    def link(self, service_name: str) -> Link:
        """Link with a service.

        Args:
            service_name: The name of a service to create a [Link][msl.network.client.Link] with.
        """
        return Link(self._create_future, service_name)

    def services(self, timeout: float | None = None) -> list[str]:
        """Request the names of the services that are available.

        Args:
            timeout: The maximum number of seconds to wait for the result.
                If `None`, there is no limit on the wait time.

        Returns:
            The names of the services that are available to be [Link][msl.network.client.Link]ed with.
        """
        return sorted(self._create_future("Broker", "SERVICES").result(timeout))


class Link:
    """A link with a service."""

    def __init__(self, create_future: Callable[..., Future[Any]], service_name: str) -> None:
        """A link with a service."""
        self._create_future: Callable[..., Future[Any]] = create_future

        self.service_name: str = service_name
        """The name of the service that the link is with."""

    def __repr__(self) -> str:  # pyright: ignore[reportImplicitOverride]
        """Returns a string representation of the Link."""
        return f"Link(service={self.service_name!r})"

    def __getattr__(self, attr: str) -> FutureOrResult:
        """Send a request to the linked service."""

        def wrapper(
            *args: Any, sync: bool = True, sync_timeout: float | None = None, **kwargs: Any
        ) -> Any | Future[Any]:
            """Returns the result, if `sync=True`, otherwise a future that will eventually contain the result."""
            future = self._create_future(self.service_name, attr, *args, **kwargs)
            if sync:
                return future.result(sync_timeout)
            return future

        return wrapper


class _AsyncClient:
    """An asynchronous client."""

    def __init__(
        self,
        client: Client,
        domain: bytes = b"*",
        curve: AuthCurve | None = None,
        plain: AuthPlain | None = None,
    ) -> None:
        """An asynchronous client."""
        (host, port), _id = client._host_port, client._id  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
        self._str: str = str(client)

        self.futures: dict[int, Future[Any]] = {}
        self.queue: asyncio.Queue[tuple[bytes, bytes] | tuple[None, None]] = asyncio.Queue()
        self.context: Context = Context()

        # For Ctrl+C to work on Windows and to signal handle_messages() to break
        self.interrupter: Interrupter = Interrupter()

        # For sending/receiving messages to/from the Broker
        self.dealer: Socket = self.context.socket(zmq.DEALER)
        self.dealer.setsockopt(zmq.ROUTING_ID, f"Client[{_id}]".encode())

        if curve is not None:
            self.dealer.setsockopt(zmq.CURVE_PUBLICKEY, curve.public_key)
            self.dealer.setsockopt(zmq.CURVE_SECRETKEY, curve.secret_key)
            self.dealer.setsockopt(zmq.CURVE_SERVERKEY, curve.broker_key)
            self.dealer.setsockopt(zmq.ZAP_DOMAIN, domain)
            logger.debug("Using CURVE authentication [domain:%s]", domain.decode())
        elif plain is not None:
            self.dealer.setsockopt(zmq.PLAIN_USERNAME, plain.username)
            self.dealer.setsockopt(zmq.PLAIN_PASSWORD, plain.password)
            self.dealer.setsockopt(zmq.ZAP_DOMAIN, domain)
            logger.debug("Using PLAIN authentication [domain:%s]", domain.decode())

        _ = self.dealer.connect(f"tcp://{host}:{port}")

        # For waking up the Poller to send another request
        self.wakeup_sender: Socket = self.context.socket(zmq.PAIR)
        self.wakeup_receiver: Socket = self.context.socket(zmq.PAIR)
        _ = self.wakeup_receiver.bind(f"inproc://wakeup-{_id}")
        _ = self.wakeup_sender.connect(f"inproc://wakeup-{_id}")

        # Polls for events on the asyncio event loop
        self.poller: Poller = Poller()
        self.poller.register(self.dealer, zmq.POLLIN)
        self.poller.register(self.interrupter.receiver, zmq.POLLIN)
        self.poller.register(self.wakeup_receiver, zmq.POLLIN)

        self.loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

    def __str__(self) -> str:  # pyright: ignore[reportImplicitOverride]
        """Returns the string representation of the Client."""
        return self._str

    def disconnect(self) -> None:
        """Triggers the interrupter, closes all sockets and destroys the context."""
        self.interrupter()
        self.poller.unregister(self.dealer)
        self.poller.unregister(self.interrupter.receiver)
        self.poller.unregister(self.wakeup_receiver)
        self.interrupter.close()
        self.dealer.close(linger=0)
        self.wakeup_receiver.close(linger=0)
        self.wakeup_sender.close(linger=0)
        self.context.destroy(linger=0)

    async def handle_messages(self) -> None:
        """Poll for events to handle messages."""
        logger.debug("%s connected", self)
        while True:
            event = dict(await self.poller.poll())
            if event.get(self.wakeup_receiver):  # Send request
                worker_id, request = await self.wakeup_receiver.recv_multipart()
                logger.debug("%s sent request to %r", self, worker_id)
                _ = await self.dealer.send_multipart((worker_id, request))  # pyright: ignore[reportUnknownMemberType]
            elif event.get(self.dealer):  # Handle reply
                worker_id, response = await self.dealer.recv_multipart()
                logger.debug("%s received response from %r", self, worker_id)
                r = Response.from_bytes(response)
                future = self.futures.pop(r.id)
                if r.ok:
                    future.set_result(r.result)
                else:
                    future.set_exception(RuntimeError(r.result))
            else:  # Shutdown
                await self.queue.put((None, None))
                _ = await asyncio.gather(self.queue.join())
                break

    def put_nowait(self, transaction: int, item: tuple[bytes, bytes]) -> Future[Any]:
        """Put a new request into the request queue without blocking."""
        future: Future[Any] = Future()
        self.futures[transaction] = future
        _ = self.loop.call_soon_threadsafe(self.queue.put_nowait, item)
        return future

    async def wakeup_event(self) -> None:
        """Wake up the Poller to handle a request."""
        while True:
            worker_id, request = await self.queue.get()
            if request is None:
                self.queue.task_done()
                break
            _ = await self.wakeup_sender.send_multipart((worker_id, request))  # pyright: ignore[reportUnknownMemberType]
            self.queue.task_done()


async def _create_async_client(
    client: Client,
    domain: bytes = b"*",
    curve: AuthCurve | None = None,
    plain: AuthPlain | None = None,
) -> None:
    """Create the async client and run it in an event loop."""
    async_client = _AsyncClient(client, domain, curve, plain)
    client._async_client = async_client  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
    _ = await asyncio.gather(async_client.handle_messages(), async_client.wakeup_event())
