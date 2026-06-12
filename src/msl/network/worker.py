"""A Worker handles requests from a Client."""

from __future__ import annotations

import os
import traceback
from contextlib import contextmanager
from typing import TYPE_CHECKING

import zmq
from zmq.asyncio import Context, Poller, Socket
from zmq.utils.win32 import allow_interrupt

from .interrupter import Interrupter
from .message import Flag, Request, Response
from .utils import BROKER_PORT, logger, run_event_loop

if TYPE_CHECKING:
    from collections.abc import Generator


class Worker:
    """Base class for a Worker."""

    def __init__(
        self, *, name: str | None = None, host: str = "127.0.0.1", port: int = BROKER_PORT, flag: Flag = Flag.PICKLE
    ) -> None:
        """Base class for a Worker.

        Args:
            name: The name of the service that a [Client][msl.network.client.Client] would use
                to [Link][msl.network.client.Link] with the [Worker][msl.network.client.Worker].
                If not specified, the class name is used.
            host: The hostname (or IP address) that the [Broker][] is running on.
            port: The network port that the [Broker][] is running on.
            flag: The serialization and compression algorithms to apply to a response before
                sending the byte stream.
        """
        self.flag: Flag = flag
        """The serialization and compression algorithms to apply to a response before sending the byte stream."""

        self._worker_id: bytes = f"Worker[{os.urandom(8).hex()}]".encode()
        self._service_name: str = name or self.__class__.__name__
        self._broker_address: str = f"tcp://{host}:{port}"
        self._context: Context = Context()
        self._poller: Poller = Poller()
        self._interrupter: Interrupter | None = None
        self._socket: Socket | None = None

    def __del__(self) -> None:
        """Calls `disconnect` then destroys the context."""
        self.disconnect()
        self._context.destroy(linger=0)

    def connect(self) -> None:
        """Connect (or reconnect) to the [Broker][]."""
        try:
            run_event_loop(self._handle_requests())
        except KeyboardInterrupt:  # pragma: no cover
            pass
        finally:
            run_event_loop(self._handle_disconnect())
            self.disconnect()
            logger.debug("%s event loop closed", self._service_name)

    def disconnect(self) -> None:
        """Disconnect from the [Broker][].

        Unregister from the poller, close the interrupter and close the socket.
        """
        if self._interrupter is None or self._socket is None:
            return

        self._poller.unregister(self._socket)
        self._poller.unregister(self._interrupter.receiver)
        self._interrupter.close()
        self._socket.close(linger=0)
        self._interrupter = None
        self._socket = None
        logger.debug("%s disconnected", self._service_name)

    @contextmanager
    def flag_at(self, flag: Flag) -> Generator[None, None, None]:
        """Use as a context manager to temporarily change the [flag][..flag] value.

        !!! example
            ```python
            from msl.network import Flag, Worker

            class Camera(Worker):

                def __init__(self) -> None:
                    \"\"\"By default, use JSON to serialise all responses (no compression).\"\"\"
                    super().__init__(flag=Flag.JSON)

                def resolution(self) -> tuple[int, int]:
                    \"\"\"Returns the (width, height) of a captured image.

                    The response is serialised using JSON without compression.
                    \"\"\"
                    return 1600, 1200

                def capture(self) -> bytes:
                    \"\"\"Capture an image and return the image bytes.

                    In this method, compressed bytes without serialisation is returned.
                    \"\"\"
                    image = ...  # capture an image from the camera
                    with self.flag_at(Flag.ZLIB):
                        return image
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

    async def _handle_disconnect(self) -> None:
        """Notify the Broker that this Worker is disconnecting."""
        if self._socket is None:
            return

        r = Request(id=0, service=self._service_name, attribute="DISCONNECT", args=[], kwargs={})
        _ = await self._socket.send_multipart([b"Broker", r.to_bytes(self.flag)])  # pyright: ignore[reportUnknownMemberType]
        logger.debug("%s unregistered", self._service_name)

    async def _handle_requests(self) -> None:
        self._interrupter = Interrupter()
        self._socket = self._context.socket(zmq.DEALER)
        self._socket.setsockopt(zmq.IDENTITY, self._worker_id)
        self._poller.register(self._socket, zmq.POLLIN)
        self._poller.register(self._interrupter.receiver, zmq.POLLIN)
        _ = self._socket.connect(self._broker_address)
        logger.debug("%s connected", self._service_name)

        # Register the service_name for this Worker with the Broker. DEALER
        # sockets add messages to a queue and deliver the message when the
        # destination socket is available. The Broker will receive this
        # service-name registration now or when the Broker runs later. Sending
        # this message now does not wait for the Broker to be ready to receive
        # it and is non-blocking.
        r = Request(id=0, service=self._service_name, attribute="READY", args=[], kwargs={})
        _ = await self._socket.send_multipart([b"Broker", r.to_bytes(self.flag)])  # pyright: ignore[reportUnknownMemberType]
        logger.debug("%s registered", self._service_name)

        with allow_interrupt(self._interrupter):
            logger.debug("%s polling...", self._service_name)
            while True:
                event = dict(await self._poller.poll())
                mask = event.get(self._socket)
                if mask is None:  # event must be from self._interrupter.receiver
                    break

                sender_id, message = await self._socket.recv_multipart()
                request = Request.from_bytes(message)
                logger.debug("Request from %r", sender_id)

                if request.attribute.startswith("_"):
                    result = "PermissionError: Cannot request a private attribute"
                    response = Response(id=request.id, ok=False, result=result)
                    _ = await self._socket.send_multipart([sender_id, response.to_bytes(self.flag)])  # pyright: ignore[reportUnknownMemberType]
                    continue

                try:
                    attribute = getattr(self, request.attribute)
                except AttributeError as e:
                    response = Response(id=request.id, ok=False, result=str(e))
                    _ = await self._socket.send_multipart([sender_id, response.to_bytes(self.flag)])  # pyright: ignore[reportUnknownMemberType]
                    continue

                if callable(attribute):
                    try:
                        result = attribute(*request.args, **request.kwargs)
                    except Exception:  # noqa: BLE001
                        response = Response(id=request.id, ok=False, result=traceback.format_exc().encode())
                    else:
                        response = Response(id=request.id, ok=True, result=result)
                    _ = await self._socket.send_multipart([sender_id, response.to_bytes(self.flag)])  # pyright: ignore[reportUnknownMemberType]
                else:
                    response = Response(id=request.id, ok=True, result=attribute)
                    _ = await self._socket.send_multipart([sender_id, response.to_bytes(self.flag)])  # pyright: ignore[reportUnknownMemberType]
