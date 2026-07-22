"""A Client."""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import Future
from contextlib import contextmanager
from threading import Event, Thread
from typing import TYPE_CHECKING

import zmq
from zmq.asyncio import Context, Poller, Socket
from zmq.utils.monitor import recv_monitor_message

from .interrupter import Interrupter
from .message import Flag, Request, Response
from .utils import BROKER_PORT, logger, run_event_loop

if TYPE_CHECKING:
    import sys
    from collections.abc import Callable, Generator
    from contextlib import AbstractContextManager
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
        xpub_port: int | None = None,
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
            xpub_port: The port on the [Broker][] that is publishing messages.
                Typically, this value is `port + 1` and does not need to be specified.
        """
        self.flag: Flag = flag
        """The serialisation and compression algorithms to apply to a request before sending the message."""

        self._host_port: tuple[str, int] = (host, port)
        self._xpub_port: int = xpub_port or port + 1  # Link connects via SUBscribe: SUB -> XPUB
        self._id: str = os.urandom(8).hex()
        self._transaction: int = 0
        self._async_client: _AsyncClient | None = None
        self._is_connected: Event = Event()
        self._links: list[Link] = []

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

    def _request(self, service_name: str, attr: str, *args: Any, **kwargs: Any) -> Future[Any]:
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

        for link in self._links:
            link.unlink()

        self._async_client.disconnect()
        self._is_connected.clear()
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

            with link.flag_at(Flag.JSON):
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

    @property
    def is_connected(self) -> bool:
        """[bool][] &mdash; Whether the client is connected to the [Broker][]."""
        return self._is_connected.is_set()

    def link(self, service_name: str) -> Link:
        """Link with a service.

        Args:
            service_name: The name of a service to create a [Link][msl.network.client.Link] with.

        Returns:
            The [Link][msl.network.client.Link] instance.
        """
        link = Link(self, service_name)
        self._links.append(link)
        return link

    def services(self, timeout: float | None = None) -> list[str]:
        """Request the names of the services that are available.

        Args:
            timeout: The maximum number of seconds to wait for the result.
                If `None`, there is no limit on the wait time.

        Returns:
            The names of the services that are available to be [link][..link]ed with.
        """
        return sorted(self._request("Broker", "SERVICES").result(timeout))


class Link:
    """A link with a service."""

    def __init__(self, client: Client, service_name: str) -> None:
        """A link with a service.

        !!! warning
            Do not instantiate directly. Use the [link][Client.link] method
            to create a [Link][] instance.
        """
        self.flag_at: Callable[[Flag], AbstractContextManager[None]] = client.flag_at
        """Reference to [flag_at][Client.flag_at]."""

        self.service_name: str = service_name
        """[str][] &mdash; The name of the service that the link is with."""

        self.timeout: float | None = None
        """[float][] or `None` &mdash; The number of seconds to wait for a response from a *synchronous* request.

        The value is always `None` for new links, which means that there is no limit on the wait time.
        """

        self._request: Callable[[str, str, Any, Any], Future[Any]] = client._request  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
        host, _ = client._host_port  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
        self._link_subscriber: _LinkSubscriber = _LinkSubscriber(service_name, host, client._xpub_port)  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
        self._client: Client = client

        self._thread: Thread = Thread(
            target=run_event_loop, daemon=True, args=(_create_async_subscriber(self._link_subscriber),)
        )
        self._thread.start()

        while self._link_subscriber.sub_socket is None:
            continue

    def __repr__(self) -> str:  # pyright: ignore[reportImplicitOverride]
        """Returns a string representation of the Link."""
        return f"Link[{self.service_name}]"

    def __getattr__(self, attr: str) -> FutureOrResult:
        """All undefined attributes are sent to the linked service to process.

        The internal wrapper function that is returned is essentially

        ```python
        def wrapper(*args: Any, sync: bool = True, **kwargs: Any) -> Any | Future[Any]:
            future = request(self.service_name, attr, *args, **kwargs)
            if sync:
                return future.result(self.timeout)
            return future
        return wrapper
        ```
        """

        def wrapper(*args: Any, sync: bool = True, **kwargs: Any) -> Any | Future[Any]:
            """Returns the result, if `sync=True`, otherwise a future that will eventually contain the result."""
            future = self._request(self.service_name, attr, *args, **kwargs)
            if sync:
                return future.result(self.timeout)
            return future

        return wrapper

    def subscribe(self, callback: Callable[[Any], None]) -> None:
        """Subscribe to publications from the linked service.

        Args:
            callback: The callback function to receive the published *result*. The callback
                receives a single argument, the published *result*, and the returned value is ignored.
        """
        if self._link_subscriber.sub_socket is None:
            msg = f"Cannot subscribe to {self.service_name!r}, unlinked from the service"
            raise RuntimeError(msg)

        self._link_subscriber.sub_socket.setsockopt(zmq.SUBSCRIBE, self.service_name.encode())
        self._link_subscriber.callback = callback

    def unsubscribe(self) -> None:
        """Unsubscribe from receiving publications from the linked service."""
        self._link_subscriber.callback = None
        if self._link_subscriber.sub_socket is not None:
            self._link_subscriber.sub_socket.setsockopt(zmq.UNSUBSCRIBE, self.service_name.encode())

    def unlink(self) -> None:
        """Unlink from the service."""
        if self._link_subscriber.interrupter is not None:
            self.unsubscribe()
            self._link_subscriber.interrupter()
            self._client._links.remove(self)  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
            self._thread.join()
            logger.debug("%s unlinked", self)


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

        self.is_connected: Event = client._is_connected  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
        self.endpoint: str = f"tcp://{host}:{port}"

        self.futures: dict[int, Future[Any]] = {}
        self.queue: asyncio.Queue[tuple[bytes, bytes]] = asyncio.Queue()
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

        self.monitor_socket: Socket = self.dealer.get_monitor_socket()

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
        self.poller.register(self.monitor_socket, zmq.POLLIN)

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
        self.poller.unregister(self.monitor_socket)
        self.interrupter.close()
        self.dealer.disable_monitor()
        self.dealer.close(linger=0)
        self.wakeup_receiver.close(linger=0)
        self.wakeup_sender.close(linger=0)
        self.context.destroy(linger=0)

    async def handle_messages(self) -> None:
        """Poll for events to handle messages."""
        logger.debug("%s connecting...", self)
        _ = self.dealer.connect(self.endpoint)
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
            elif event.get(self.monitor_socket):  # ZMQ monitoring
                m = await recv_monitor_message(self.monitor_socket)
                if m["event"] == zmq.EVENT_CONNECTED:
                    self.is_connected.set()
                elif m["event"] == zmq.EVENT_DISCONNECTED:
                    self.is_connected.clear()
                logger.debug("Monitor %r value=%d", m["event"], m["value"])
            else:  # Interrupter
                await self.queue.put((b"", b""))
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
            if not request:
                self.queue.task_done()
                break
            _ = await self.wakeup_sender.send_multipart((worker_id, request))  # pyright: ignore[reportUnknownMemberType]
            self.queue.task_done()


class _LinkSubscriber:
    """Handle publications from a Worker."""

    def __init__(self, service_name: str, host: str, xpub_port: int) -> None:
        """Handle publications from a Worker.

        Args:
            service_name: The name of the service that publishes messages.
            host: The hostname (or IP address) that the Broker is running on.
            xpub_port: The XPUB port that is running on the Broker.
        """
        self.callback: Callable[[Any], None] | None = None
        self.service_name: str = service_name
        self.endpoint: str = f"tcp://{host}:{xpub_port}"
        self.interrupter: Interrupter | None = None
        self.sub_socket: Socket | None = None

    async def handle_publications(self) -> None:
        """Poll for publications from a Worker."""
        context: Context = Context()

        # For Ctrl+C to work on Windows and to signal the while loop below to break
        self.interrupter = Interrupter()

        self.sub_socket = context.socket(zmq.SUB)
        _ = self.sub_socket.connect(self.endpoint)

        # Polls for events on the asyncio event loop
        poller: Poller = Poller()
        poller.register(self.sub_socket, zmq.POLLIN)
        poller.register(self.interrupter.receiver, zmq.POLLIN)

        logger.debug("Link[%s] publication polling...", self.service_name)
        while True:
            event = dict(await poller.poll())
            if event.get(self.sub_socket):  # Publication received
                _, data = await self.sub_socket.recv_multipart()
                if self.callback is not None:
                    self.callback(Response.from_bytes(data).result)
            else:  # Interrupter
                break

        poller.unregister(self.sub_socket)
        poller.unregister(self.interrupter.receiver)
        self.sub_socket.close(linger=0)
        self.interrupter.close()
        self.interrupter = None
        self.sub_socket = None
        context.destroy()
        logger.debug("Link[%s] stopped publication polling", self.service_name)


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


async def _create_async_subscriber(link_subscriber: _LinkSubscriber) -> None:
    """Create the async subscriber and run it in an event loop."""
    _ = await asyncio.gather(link_subscriber.handle_publications())
