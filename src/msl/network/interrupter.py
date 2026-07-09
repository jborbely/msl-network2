"""Interrupter to signal a `Ctrl+C` event on Windows."""

from __future__ import annotations

import os
import time

import zmq

from .utils import logger


class Interrupter:
    """Handle `Ctrl+C` on Windows by creating an interrupt event for the Poller.

    Creates an exclusive `PAIR` of sockets to handle a `Ctrl+C` event.
    """

    def __init__(self) -> None:
        """Handle `Ctrl+C` on Windows by creating an interrupt event for the Poller."""
        self.name: str = f"Interrupter[{os.urandom(8).hex()}]"
        self.context: zmq.Context[zmq.SyncSocket] = zmq.Context()
        self.sender: zmq.SyncSocket = self.context.socket(zmq.PAIR)
        self.receiver: zmq.SyncSocket = self.context.socket(zmq.PAIR)
        _ = self.sender.bind(f"inproc://{self.name}")
        _ = self.receiver.connect(f"inproc://{self.name}")
        logger.debug("%s created", self.name)

    def __call__(self) -> None:
        """Trigger `Ctrl+C` event."""
        logger.debug("%s triggered", self.name)
        self.sender.send(b"")
        time.sleep(0.01)  # avoids occasional asyncio.InvalidStateError from the Poller when shutting down on Windows

    def close(self) -> None:
        """Close the sockets and destroy the context."""
        self.sender.close(linger=0)
        self.receiver.close(linger=0)
        self.context.destroy(linger=0)
        logger.debug("%s terminated", self.name)
