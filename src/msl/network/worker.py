"""A Worker handles requests from a Client."""

from __future__ import annotations

import inspect
import os
import traceback
from contextlib import contextmanager
from typing import TYPE_CHECKING

import zmq
from zmq.asyncio import Context, Poller, Socket
from zmq.utils.monitor import recv_monitor_message
from zmq.utils.win32 import allow_interrupt

from .interrupter import Interrupter
from .message import Flag, Request, Response
from .utils import BROKER_PORT, logger, run_event_loop

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

    from .auth import AuthCurve, AuthPlain


class Worker:
    """Base class for a Worker."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        name: str | None = None,
        host: str = "127.0.0.1",
        port: int = BROKER_PORT,
        flag: Flag = Flag.PICKLE,
        domain: str = "*",
        curve: AuthCurve | None = None,
        plain: AuthPlain | None = None,
        ignore_attributes: str | Iterable[str] | None = None,
    ) -> None:
        """Base class for a Worker.

        Args:
            name: The name of the service that a [Client][msl.network.client.Client] would use
                to [Link][msl.network.client.Link] with the [Worker][msl.network.client.Worker].
                If not specified, the class name is used.
            host: The hostname (or IP address) that the [Broker][] is running on.
            port: The network port that the [Broker][] is running on.
            flag: The serialisation and compression algorithms to apply to a response before
                sending the byte stream.
            domain: The domain to use for [CURVE](https://rfc.zeromq.org/spec/26/) or
                [PLAIN](https://rfc.zeromq.org/spec/24/) authentication.
            curve: The [CURVE](https://rfc.zeromq.org/spec/26/) authentication to use.
            plain: The [PLAIN](https://rfc.zeromq.org/spec/24/) authentication to use.
            ignore_attributes: The names of the attributes to not include in the
                [signatures][msl.network.worker.Worker.signatures]. See
                [ignore_attributes][msl.network.worker.Worker.ignore_attributes]
                for more details.
        """
        self.flag: Flag = flag
        """The serialisation and compression algorithms to apply to a response before sending the byte stream."""

        self._worker_id: bytes = f"Worker[{os.urandom(8).hex()}]".encode()
        self._service_name: str = name or self.__class__.__name__
        self._broker_address: str = f"tcp://{host}:{port}"
        self._context: Context = Context()
        self._poller: Poller = Poller()
        self._interrupter: Interrupter | None = None
        self._socket: Socket | None = None
        self._monitor_socket: Socket | None = None
        self._domain: bytes = domain.encode()
        self._curve: AuthCurve | None = curve
        self._plain: AuthPlain | None = plain

        if curve is not None and plain is not None:
            msg = "Cannot use both PLAIN and CURVE authentication, select only one authentication mechanism"
            raise ValueError(msg)

        self._ignore_attributes: set[str] = {
            "connect",
            "disconnect",
            "flag",
            "flag_at",
            "ignore_attributes",
            "signatures",
        }

        if ignore_attributes is not None:
            if isinstance(ignore_attributes, str):
                self.ignore_attributes(ignore_attributes)
            else:
                self.ignore_attributes(*ignore_attributes)

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
        if self._interrupter is None or self._socket is None or self._monitor_socket is None:
            return

        self._poller.unregister(self._socket)
        self._poller.unregister(self._interrupter.receiver)
        self._poller.unregister(self._monitor_socket)
        self._interrupter.close()
        self._monitor_socket.close(linger=0)
        self._socket.disable_monitor()
        self._socket.close(linger=0)
        self._interrupter = None
        self._socket = None
        self._monitor_socket = None
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
                    image: bytes = ...  # capture an image from the camera
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

    def ignore_attributes(self, *names: str) -> None:
        """Ignore attributes from being added to the [signature][msl.network.worker.Worker.signatures].

        There are a few reasons why you may want to call this method:

        * If you see warnings that the signature of an attribute cannot be found and you
          prefer not to see the warnings.
        * If you do not want an attribute to be made publicly known that it exists; however,
          a [Client][msl.network.client.Client] can still access ignored attributes.

        Private attributes (i.e., attributes that start with an underscore) are automatically
        ignored and cannot be accessed from a [Client][msl.network.client.Client] on the network.

        If you want to ignore any attributes then you must call this method before calling
        [connect][msl.network.worker.Worker.connect].

        Args:
            names: The names of the attributes to exclude from the
                [signatures][msl.network.worker.Worker.signatures] map.
        """
        self._ignore_attributes.update(names)

    def signatures(self) -> dict[str, str]:
        """Get the function signatures that the service provides.

        Returns:
            A mapping between the function (attribute) name and the
                function signature (attribute value).
        """
        signature_map: dict[str, str] = {}
        for name in dir(self):
            if name.startswith("_") or (name in self._ignore_attributes):
                continue

            try:
                attrib = getattr(self, name)
            except Exception as e:  # noqa: BLE001
                # This can happen if the Service is also a subclass of
                # another class (e.g., the PiCamera class) and the other
                # class defines some of its attributes using the builtin
                # property function, e.g., property(fget, fset, fdel, doc),
                # and defines fget=None or if the getattr() function
                # executes code, like PiCamera.frame does, which raises
                # a custom exception if the camera is not running.
                logger.warning("%s [attribute=%r]", e, name)
                continue

            try:
                signature_map[name] = str(inspect.signature(attrib)).replace("'", "")
            except TypeError:
                # Then the attribute is not a callable object
                signature_map[name] = f"() -> {attrib.__class__.__name__}"
            except ValueError as e:
                # Cannot get the signature of the callable object.
                # This can happen if the Worker is also a subclass of
                # some other object, for example a Qt class.
                logger.warning("%s [attribute=%r]", e, name)

        return signature_map

    async def _handle_disconnect(self) -> None:
        """Notify the Broker that this Worker is disconnecting."""
        if self._socket is None:
            return

        r = Request(id=0, service=self._service_name, attribute="WORKER_UNAVAILABLE", args=[], kwargs={})
        _ = await self._socket.send_multipart([b"Broker", r.to_bytes(self.flag)])  # pyright: ignore[reportUnknownMemberType]
        logger.debug("%s unregistered", self._service_name)

    async def _handle_requests(self) -> None:  # noqa: C901, PLR0915
        self._interrupter = Interrupter()
        self._socket = self._context.socket(zmq.DEALER)
        self._socket.setsockopt(zmq.ROUTING_ID, self._worker_id)

        if self._curve is not None:
            self._socket.setsockopt(zmq.CURVE_PUBLICKEY, self._curve.public_key)
            self._socket.setsockopt(zmq.CURVE_SECRETKEY, self._curve.secret_key)
            self._socket.setsockopt(zmq.CURVE_SERVERKEY, self._curve.broker_key)
            self._socket.setsockopt(zmq.ZAP_DOMAIN, self._domain)
            logger.debug("Using CURVE authentication [domain:%s]", self._domain.decode())
        elif self._plain is not None:
            self._socket.setsockopt(zmq.PLAIN_USERNAME, self._plain.username)
            self._socket.setsockopt(zmq.PLAIN_PASSWORD, self._plain.password)
            self._socket.setsockopt(zmq.ZAP_DOMAIN, self._domain)
            logger.debug("Using PLAIN authentication [domain:%s]", self._domain.decode())

        self._monitor_socket = self._socket.get_monitor_socket()

        self._poller.register(self._socket, zmq.POLLIN)
        self._poller.register(self._interrupter.receiver, zmq.POLLIN)
        self._poller.register(self._monitor_socket, zmq.POLLIN)

        _ = self._socket.connect(self._broker_address)

        # Register the service_name for this Worker with the Broker. DEALER
        # sockets add messages to a queue and deliver the message when the
        # destination socket is available. The Broker will receive this
        # service-name registration now or when the Broker runs later. Sending
        # this message now does not wait for the Broker to be ready to receive
        # it and is non-blocking.
        r = Request(id=0, service=self._service_name, attribute="WORKER_READY", args=[], kwargs={})
        _ = await self._socket.send_multipart([b"Broker", r.to_bytes(self.flag)])  # pyright: ignore[reportUnknownMemberType]
        logger.debug("%s registered", self._service_name)

        with allow_interrupt(self._interrupter):
            logger.debug("%s polling...", self._service_name)
            while True:
                event = dict(await self._poller.poll())
                if event.get(self._monitor_socket):
                    m = await recv_monitor_message(self._monitor_socket)
                    logger.debug("Monitor %r value=%d", m["event"], m["value"])
                    continue

                if event.get(self._interrupter.receiver):
                    break

                sender_id, message = await self._socket.recv_multipart()
                logger.debug("Request from %r", sender_id)

                request = Request.from_bytes(message)
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
                        response = Response(id=request.id, ok=False, result=traceback.format_exc())
                    else:
                        response = Response(id=request.id, ok=True, result=result)
                else:
                    response = Response(id=request.id, ok=True, result=attribute)

                _ = await self._socket.send_multipart([sender_id, response.to_bytes(self.flag)])  # pyright: ignore[reportUnknownMemberType]
