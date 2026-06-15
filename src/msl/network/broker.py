"""ZeroMQ broker to forward requests and responses."""

from __future__ import annotations

from collections import deque
from contextlib import suppress

import zmq
from zmq.asyncio import Context, Poller, Socket
from zmq.utils.win32 import allow_interrupt

from .interrupter import Interrupter
from .message import Flag, Request, Response
from .utils import logger


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

    def __init__(self, host: str = "*", port: int = 0) -> None:
        """ZeroMQ broker to forward requests and responses.

        Args:
            host: The network interface to run the Broker on.
            port: The port number to run the Broker on. If `0`, use a random port.
        """
        self.context: Context = Context()
        self.router: Socket = self.context.socket(zmq.ROUTER)

        # Check for Errno.EHOSTUNREACH when a message cannot be routed (must be set before `bind`)
        self.router.setsockopt(zmq.ROUTER_MANDATORY, 1)
        _ = self.router.bind(f"tcp://{host}:{port}")
        self.endpoint: str = self.router.getsockopt_string(zmq.LAST_ENDPOINT)

        self.interrupter: Interrupter = Interrupter()

        self.poller: Poller = Poller()
        self.poller.register(self.router, zmq.POLLIN)
        self.poller.register(self.interrupter.receiver, zmq.POLLIN)

        # key: service name
        self.workers: dict[str, WorkerBalancer] = {}

    def remove_worker(self, worker_id: bytes, service_name: str, balancer: WorkerBalancer) -> None:
        """Worker is no longer available, remove it."""
        logger.info("Unregistered %r with service name %r", worker_id, service_name)
        balancer.remove(worker_id)
        if len(balancer) == 0:
            del self.workers[service_name]
            logger.info("No Workers are available any more for service name %r", service_name)

    def destroy(self) -> None:
        """Close all sockets and destroy the context."""
        if self.context.closed:
            return

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

    async def run(self) -> None:
        """Run the broker."""
        logger.info("Broker running on %s", self.endpoint[6:])
        with allow_interrupt(self.interrupter):
            while True:
                socket: dict[Socket, int] = dict(await self.poller.poll())
                if socket.get(self.router) is None:  # must be from Interrupter
                    break

                sender_id, destination_id, message = await self.router.recv_multipart()
                logger.info("%s -> %s", sender_id, destination_id)
                if destination_id == b"Broker":
                    await self.request_for_broker(sender_id, message)
                elif sender_id.startswith(b"Client"):
                    await self.request_for_worker(sender_id, destination_id, message)
                else:
                    # A response from a Worker to be sent to a Client
                    # Silently ignore all errors if the Client is no longer available
                    with suppress(zmq.error.ZMQError):
                        _ = await self.router.send_multipart((destination_id, sender_id, message))  # pyright: ignore[reportUnknownMemberType]

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
