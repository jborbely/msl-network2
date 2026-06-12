"""Main entry way to the command-line interface."""

from __future__ import annotations

import logging

from .broker import Broker
from .utils import BROKER_PORT, logger, run_event_loop


def main(host: str = "*", port: int = BROKER_PORT, level: int = logging.DEBUG) -> None:
    """Run the Broker in an asyncio event loop."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s.%(msecs)03d [%(levelname)05s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    broker = Broker(host=host, port=port)

    try:
        run_event_loop(broker.run())
    except KeyboardInterrupt:
        pass
    finally:
        logger.debug("Broker shutting down")
        broker.poller.unregister(broker.router)
        broker.poller.unregister(broker.interrupter.receiver)
        broker.interrupter.close()
        broker.router.close(linger=0)
        broker.context.destroy()
        logger.debug("Broker event loop closed")
