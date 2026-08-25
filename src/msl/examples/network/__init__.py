"""Example services."""

from __future__ import annotations

from .echo import Echo
from .heartbeat import Heartbeat

__all__: list[str] = [
    "Echo",
    "Heartbeat",
]
