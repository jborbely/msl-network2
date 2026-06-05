"""A Worker."""

from __future__ import annotations

import traceback
from contextlib import suppress

import zmq
from zmq.asyncio import Context, Poller, Socket
from zmq.utils.win32 import allow_interrupt

from .interrupter import Interrupter
from .message import Flag, Request, Response
from .utils import logger, run_event_loop


class Worker:
    """A Worker."""

    def __init__(
        self, *, name: str | None = None, host: str = "127.0.0.1", port: int = 1875, flags: Flag = Flag.PICKLE
    ) -> None:
        """A Worker.

        Args:
            name: The name of the Worker that a [Client][msl.network.client.Client]
                will use to create a [Link][msl.network.client.Link] with the Worker.
                If not specified, the class name is used.
            host: The hostname (or IP address) that the broker is running on.
            port: The network port that the broker is running on.
            flags: The serialization and compression algorithms to apply to a
                response before sending the byte stream.
        """
        self.flags: Flag = flags
        """The serialization and compression algorithms to apply to a response before sending the byte stream."""

        self._name: str = name or self.__class__.__name__

        self._interrupter: Interrupter = Interrupter(f"{self._name}[{hex(id(self))}]")
        self._context: Context = Context()
        self._socket: Socket = self._context.socket(zmq.DEALER)
        self._socket.setsockopt(zmq.IDENTITY, self._name.encode())
        _ = self._socket.connect(f"tcp://{host}:{port}")

        self._poller: Poller = Poller()
        self._poller.register(self._socket, zmq.POLLIN)
        self._poller.register(self._interrupter.subscriber, zmq.POLLIN)

    def __del__(self) -> None:
        """Stop the Worker."""
        self.stop()

    async def _handle_requests(self) -> None:
        logger.debug("%s started", self._name)

        # Register this Worker with the Broker
        _ = await self._socket.send_multipart([b"broker", b""])  # pyright: ignore[reportUnknownMemberType]

        poller = self._poller
        socket = self._socket
        num_requests = 0
        with allow_interrupt(self._interrupter):
            while True:
                event = dict(await poller.poll())
                mask = event.get(socket)
                if mask is None:
                    break

                num_requests += 1
                client_id, message = await socket.recv_multipart()
                request = Request.from_bytes(message)
                logger.debug("Request from %r (%d in total)", client_id, num_requests)

                if request.attribute.startswith("_"):
                    result = "PermissionError: Cannot request a private attribute"
                    response = Response(id=request.id, ok=False, result=result)
                    _ = await socket.send_multipart([client_id, response.to_bytes(self.flags)])  # pyright: ignore[reportUnknownMemberType]
                    continue

                try:
                    attribute = getattr(self, request.attribute)
                except AttributeError as e:
                    response = Response(id=request.id, ok=False, result=str(e))
                    _ = await socket.send_multipart([client_id, response.to_bytes(self.flags)])  # pyright: ignore[reportUnknownMemberType]
                    continue

                if callable(attribute):
                    try:
                        result = attribute(*request.args, **request.kwargs)
                    except Exception:  # noqa: BLE001
                        response = Response(id=request.id, ok=False, result=traceback.format_exc().encode())
                    else:
                        response = Response(id=request.id, ok=True, result=result)
                    _ = await socket.send_multipart([client_id, response.to_bytes(self.flags)])  # pyright: ignore[reportUnknownMemberType]
                else:
                    response = Response(id=request.id, ok=True, result=attribute)
                    _ = await socket.send_multipart([client_id, response.to_bytes(self.flags)])  # pyright: ignore[reportUnknownMemberType]

    def stop(self) -> None:
        """Stop the Worker.

        Close the socket and destroy the context.
        """
        if self._socket.closed:
            return

        self._interrupter.shutdown()
        self._poller.unregister(self._socket)
        self._poller.unregister(self._interrupter.subscriber)
        self._socket.close(linger=0)
        self._context.destroy()
        logger.debug("%s stopped", self._name)

    def start(self) -> None:
        """Start the Worker."""
        with suppress(KeyboardInterrupt):
            run_event_loop(self._handle_requests())
