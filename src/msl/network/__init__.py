"""Concurrent and asynchronous network I/O."""

from __future__ import annotations

from .__about__ import __author__, __copyright__, __version__, version_tuple
from .auth import AuthCurve, AuthPlain, load_certificate
from .client import Client
from .message import Flag
from .worker import Worker

__all__: list[str] = [
    "AuthCurve",
    "AuthPlain",
    "Client",
    "Flag",
    "Worker",
    "__author__",
    "__copyright__",
    "__version__",
    "load_certificate",
    "version_tuple",
]
