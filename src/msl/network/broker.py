"""ZeroMQ broker to forward requests and responses."""

from __future__ import annotations

import contextlib
import logging

import zmq
from zmq.asyncio import Context, Poller, Socket
from zmq.utils.win32 import allow_interrupt

from .interrupter import Interrupter
from .message import Flag, Request, Response
from .utils import BROKER_PORT, logger, run_event_loop


async def run(port: int = BROKER_PORT) -> None:
    """Run the broker.

    Args:
        port: The network port to run the broker on.
    """
    with Context() as c, c.socket(zmq.ROUTER) as router:

        async def send(*msg_parts: bytes) -> None:
            try:
                _ = await router.send_multipart(msg_parts)  # pyright: ignore[reportUnknownMemberType]
            except zmq.error.ZMQError as e:
                if e.errno == zmq.EHOSTUNREACH and not destination_id.startswith(b"client"):
                    # Send a response to the Client that the Worker is not available
                    with contextlib.suppress(KeyError):  # maybe the Worker never existed
                        worker_names.remove(destination_id)

                    request = Request.from_bytes(message)
                    response = Response(
                        id=request.id,
                        ok=False,
                        result=f"Worker {request.service!r} is not available",
                    ).to_bytes(Flag.JSON)

                    _ = await router.send_multipart([sender_id, destination_id, response])  # pyright: ignore[reportUnknownMemberType]

        # want to check for Errno.EHOSTUNREACH when a message cannot be routed, must be set before `bind`
        router.setsockopt(zmq.ROUTER_MANDATORY, 1)
        _ = router.bind(f"tcp://*:{port}")
        address = router.getsockopt_string(zmq.LAST_ENDPOINT)
        logger.info("Broker running on %s", address)

        interrupter = Interrupter()

        poller = Poller()
        poller.register(router, zmq.POLLIN)
        poller.register(interrupter.receiver, zmq.POLLIN)

        worker_names: set[bytes] = set()

        with allow_interrupt(interrupter):
            while True:
                socket: dict[Socket, int] = dict(await poller.poll())
                if socket.get(router) is None:
                    break

                sender_id, destination_id, message = await router.recv_multipart()
                logger.info("%s -> %s", sender_id, destination_id)
                if destination_id == b"broker":
                    if sender_id.startswith(b"client"):
                        request = Request.from_bytes(message)
                        response = Response(
                            id=request.id,
                            ok=True,
                            result=[wn.decode() for wn in worker_names],
                        ).to_bytes(Flag.JSON)
                        _ = await router.send_multipart((sender_id, b"broker", response))  # pyright: ignore[reportUnknownMemberType]
                    else:
                        logger.info("Registered Worker: %s", sender_id)
                        worker_names.add(sender_id)
                else:
                    await send(destination_id, sender_id, message)

        poller.unregister(router)
        poller.unregister(interrupter.receiver)
        interrupter.close()


def main(port: int = BROKER_PORT, level: int = logging.DEBUG) -> None:
    """Run the asyncio event loop."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s.%(msecs)03d [%(levelname)05s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    with contextlib.suppress(KeyboardInterrupt):
        run_event_loop(run(port=port))


if __name__ == "__main__":
    main()
