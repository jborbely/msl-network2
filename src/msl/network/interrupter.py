"""Interrupter to handle Ctrl+C on Windows."""

from __future__ import annotations

import time

import zmq

from .utils import logger


class Interrupter:
    """Handles Ctrl+C on Windows."""

    def __init__(self, name: str) -> None:
        """Handles Ctrl+C on Windows.

        Args:
            name: The name to use for the *inproc* PUB-SUB pattern.
        """
        self.name: str = name
        self.context: zmq.Context[zmq.SyncSocket] = zmq.Context()

        self.publisher: zmq.SyncSocket = self.context.socket(zmq.PUB)
        _ = self.publisher.bind(f"inproc://{name}")

        self.subscriber: zmq.SyncSocket = self.context.socket(zmq.SUB)
        self.subscriber.setsockopt(zmq.SUBSCRIBE, b"")
        _ = self.subscriber.connect(f"inproc://{name}")

        logger.debug(f"Interrupter created for {name}")

    def __call__(self) -> None:
        """Publishes the notification."""
        self.publisher.send(b"")
        time.sleep(0.01)  # avoids occasional asyncio.InvalidStateError from the Poller when shutting down on Windows

    def shutdown(self) -> None:
        """Close the sockets and destroy the context."""
        self.publisher.close(linger=0)
        self.subscriber.close(linger=0)
        self.context.destroy()
        logger.debug(f"Interrupter destroyed for {self.name}")
