"""Concurrent and asynchronous network I/O."""

from __future__ import annotations

from .__about__ import __author__, __copyright__, __version__, version_tuple
from .client import Client
from .message import Flag
from .worker import Worker

__all__: list[str] = [
    "Client",
    "Flag",
    "Worker",
    "__author__",
    "__copyright__",
    "__version__",
    "version_tuple",
]
