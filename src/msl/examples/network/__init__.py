"""Example services."""

from __future__ import annotations

from .echo import Echo
from .heartbeat import Heartbeat

__all__: list[str] = [
    "Echo",
    "Heartbeat",
]


def run_echo() -> None:
    echo = Echo()
    echo.connect()


def run_heartbeat() -> None:
    heartbeat = Heartbeat()
    heartbeat.add_tasks(heartbeat.emit())
    heartbeat.connect()
