"""ZeroMQ broker to forward requests and responses."""

from __future__ import annotations

import logging
from collections import deque
from contextlib import suppress
from typing import TYPE_CHECKING

import zmq
from zmq.asyncio import Context, Poller, Socket
from zmq.auth.base import Authenticator
from zmq.utils.win32 import allow_interrupt

from .interrupter import Interrupter
from .message import Flag, Request, Response
from .utils import logger

if TYPE_CHECKING:
    from .utils import Curve


class WorkerBalancer:
    """Evenly distribute requests to available Workers that have the same service name."""

    def __init__(self) -> None:
        """Evenly distribute requests to available Workers that have the same service name."""
        self._worker_ids: deque[bytes] = deque()  # Use a deque for fast pop/append
        self._unique_set: set[bytes] = set()  # Use a set for fast __contains__

    def __contains__(self, worker_id: bytes) -> bool:
        """Checks if `worker_id` is in the balancer."""
        return worker_id in self._unique_set

    def __len__(self) -> int:
        """Returns the number of Worker IDs in the balancer."""
        return len(self._worker_ids)

    def __next__(self) -> bytes:
        """Get the next Worker ID that should get the request."""
        item = self._worker_ids.pop()  # return and remove the rightmost item
        self._worker_ids.appendleft(item)  # add item to the left side
        return item

    def append(self, worker_id: bytes) -> None:
        """Maybe add `worker_id` to the right side of the deque.

        Checks if `worker_id` is not already in the deque, since a Worker
        might try to reconnect using the same ID.
        """
        if worker_id not in self._unique_set:
            self._worker_ids.append(worker_id)  # add item to the right side
            self._unique_set.add(worker_id)

    def remove(self, worker_id: bytes) -> None:
        """Remove `worker_id` from the balancer."""
        self._worker_ids.remove(worker_id)
        self._unique_set.remove(worker_id)


class Broker:
    """ZeroMQ broker to forward requests and responses."""

    def __init__(self) -> None:
        """ZeroMQ broker to forward requests and responses."""
        self.auth: Authenticator | None = None
        self.endpoint: str = ""
        self.running: bool = False

        # key: service name
        self.workers: dict[str, WorkerBalancer] = {}

        self.interrupter: Interrupter
        self.context: Context
        self.router: Socket
        self.poller: Poller

    def remove_worker(self, worker_id: bytes, service_name: str, balancer: WorkerBalancer) -> None:
        """Worker is no longer available, remove it."""
        logger.info("Unregistered %r with service name %r", worker_id, service_name)
        balancer.remove(worker_id)
        if len(balancer) == 0:
            del self.workers[service_name]
            logger.info("No Workers are available for service name %r", service_name)

    def destroy(self) -> None:
        """Close all sockets and destroy the context."""
        self.running = False
        if self.context.closed:
            return

        if self.auth is not None:
            self.poller.unregister(self.auth.zap_socket)  # pyright: ignore[reportUnknownMemberType]
            self.auth.log.setLevel(logging.WARNING)
            self.auth.stop()
            self.auth = None

        self.poller.unregister(self.router)
        self.poller.unregister(self.interrupter.receiver)
        self.interrupter.close()
        self.router.close(linger=0)
        self.context.destroy(linger=0)
        logger.debug("Broker has shut down")

    async def request_for_broker(self, sender_id: bytes, message: bytes) -> None:
        """Process a request that is destined for the Broker.

        Args:
            sender_id: Either starts with `Client` or `Worker`.
            message: The message for the Broker.
        """
        request = Request.from_bytes(message)
        service_name, attribute = request.service, request.attribute
        if attribute == "SERVICES":
            response = Response(id=request.id, ok=True, result=list(self.workers)).to_bytes(Flag.JSON)
            _ = await self.router.send_multipart((sender_id, b"Broker", response))  # pyright: ignore[reportUnknownMemberType]
        elif attribute == "WORKER_READY":
            logger.info("Registered %r with service name %r", sender_id, service_name)
            if service_name not in self.workers:
                self.workers[service_name] = WorkerBalancer()
            self.workers[service_name].append(sender_id)
        elif attribute == "WORKER_UNAVAILABLE":
            balancer = self.workers.get(service_name)
            if balancer is not None:
                self.remove_worker(sender_id, service_name, balancer)
        elif sender_id.startswith(b"Client"):
            response = Response(
                id=request.id,
                ok=False,
                result=f"Unsupported broker request: {attribute!r}",
            ).to_bytes(Flag.JSON)
            _ = await self.router.send_multipart((sender_id, b"Broker", response))  # pyright: ignore[reportUnknownMemberType]
        else:
            logger.error("Unsupported broker request %r from %r", attribute, sender_id)

    async def request_for_worker(self, sender_id: bytes, service_name: bytes, message: bytes) -> None:
        """Send a request from a Client to any Worker that is handling requests for the *service*.

        Args:
            sender_id: Client ID.
            service_name: The name of the service.
            message: Original client message.
        """
        balancer = self.workers.get(service_name.decode())
        if balancer is None:
            await self.send_worker_unavailable(sender_id, service_name, message)
            return

        worker_id = next(balancer)
        try:
            _ = await self.router.send_multipart((worker_id, sender_id, message))  # pyright: ignore[reportUnknownMemberType]
        except zmq.error.ZMQError as e:
            if e.errno == zmq.EHOSTUNREACH:
                self.remove_worker(worker_id, service_name.decode(), balancer)
                await self.send_worker_unavailable(sender_id, service_name, message)
            else:
                logger.exception(e)

    async def run(  # noqa: PLR0913, PLR0915
        self,
        *,
        addresses: dict[str, str] | None = None,
        curve: Curve | None = None,
        debug: bool = False,
        domain: str = "*",
        host: str = "*",
        plain: dict[str, str] | None = None,
        port: int = 0,
    ) -> None:
        """Run the broker.

        Args:
            addresses: A hostname/address to IPv4 address mapping of devices that are allowed to connect to the broker.
                If not specified, all devices can connect to proceed to PLAIN or CURVE authentication (if used).
            curve: The information required for [CURVE](https://rfc.zeromq.org/spec/26/) authentication.
            debug: Whether to allow DEBUG log messages during [ZAP](https://rfc.zeromq.org/spec/27/) authentication.
            domain: The domain to use for [ZAP](https://rfc.zeromq.org/spec/27/) authentication.
            host: The network interface to run the Broker on.
            plain: A username to password mapping to use for [PLAIN](https://rfc.zeromq.org/spec/24/) authentication.
            port: The port number to run the Broker on. If `0`, use a random port.
        """
        self.interrupter = Interrupter()

        self.context = Context()
        self.router = self.context.socket(zmq.ROUTER)

        self.poller = Poller()
        self.poller.register(self.router, zmq.POLLIN)
        self.poller.register(self.interrupter.receiver, zmq.POLLIN)

        # must configure Authenticator and the ROUTER socket before binding the socket
        if addresses or curve or plain:
            self.auth = Authenticator(self.context)
            self.auth.log.setLevel(logging.WARNING)
            if addresses:
                self.auth.allow(*addresses.values())
                logger.info("ZAP allowed devices: %s", ", ".join(addresses))

            if curve:
                self.auth.configure_curve_callback(domain=domain, credentials_provider=curve)
                self.router.setsockopt(zmq.CURVE_PUBLICKEY, curve.public_key)
                self.router.setsockopt(zmq.CURVE_SECRETKEY, curve.secret_key)
                self.router.setsockopt(zmq.CURVE_SERVER, 1)
                n = len(curve.keys)
                text = {0: "all keys", 1: "1 key"}.get(n, f"{n} keys")
                logger.info("Using CURVE authentication with %s allowed [domain:%s]", text, domain)
            elif plain:
                self.auth.configure_plain(domain=domain, passwords=plain)
                self.router.setsockopt(zmq.PLAIN_SERVER, 1)
                s = "" if len(plain) == 1 else "s"
                logger.info("Using PLAIN authentication for user%s %s [domain:%s]", s, ", ".join(plain), domain)
            else:
                self.router.setsockopt(zmq.ZAP_DOMAIN, domain.encode())
                logger.info("Using NULL authentication [domain:%s]", domain)

            self.auth.start()
            self.poller.register(self.auth.zap_socket, zmq.POLLIN)  # pyright: ignore[reportUnknownMemberType]
            self.auth.log.setLevel(logging.DEBUG if debug else logging.WARNING)

        # Check for Errno.EHOSTUNREACH when a message cannot be routed (must be set before `bind`)
        self.router.setsockopt(zmq.ROUTER_MANDATORY, 1)

        _ = self.router.bind(f"tcp://{host}:{port}")
        self.endpoint = self.router.getsockopt_string(zmq.LAST_ENDPOINT)

        logger.info("Broker running on %s", self.endpoint[6:])
        with allow_interrupt(self.interrupter):
            self.running = True
            while True:
                event = dict(await self.poller.poll())
                if event.get(self.router):
                    sender_id, destination_id, message = await self.router.recv_multipart()
                    logger.debug("%s -> %s", sender_id, destination_id)
                    if destination_id == b"Broker":
                        await self.request_for_broker(sender_id, message)
                    elif sender_id.startswith(b"Client"):
                        await self.request_for_worker(sender_id, destination_id, message)
                    else:
                        # A response from a Worker to be sent to a Client
                        # Silently ignore all errors if the Client is no longer available
                        with suppress(zmq.error.ZMQError):
                            _ = await self.router.send_multipart((destination_id, sender_id, message))  # pyright: ignore[reportUnknownMemberType]
                elif self.auth is not None and event.get(self.auth.zap_socket):  # pyright: ignore[reportUnknownMemberType]
                    self.auth.log.debug("ZAP request initiated...")
                    await self.auth.handle_zap_message(self.auth.zap_socket.recv_multipart())  # pyright: ignore[reportUnknownMemberType]
                else:
                    break  # event must be from self.interrupter.receiver

        self.destroy()

    async def send_worker_unavailable(self, sender_id: bytes, service_name: bytes, message: bytes) -> None:
        """Send a response that there are no Workers available for the specified service.

        Args:
            sender_id: Client ID.
            service_name: The name of the service.
            message: Original client message.
        """
        request = Request.from_bytes(message)
        response = Response(
            id=request.id,
            ok=False,
            result=f"Service {request.service!r} is not available",
        ).to_bytes(Flag.JSON)
        _ = await self.router.send_multipart([sender_id, service_name, response])  # pyright: ignore[reportUnknownMemberType]
