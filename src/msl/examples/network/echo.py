"""Example echo Service.

Returns the arguments and keyword arguments that were sent from a Client.
"""

from __future__ import annotations

from typing import Any

from msl.network import Service


class Echo(Service):
    """Example Service that echos the arguments of the request."""

    @staticmethod
    def echo(*args: Any, **kwargs: Any) -> tuple[tuple[Any, ...], dict[str, Any]]:
        """Returns the arguments and keyword arguments sent from a Client."""
        return args, kwargs


if __name__ == "__main__":
    echo = Echo()

    # Connect the Service to the Broker (runs the event loop "forever")
    echo.connect()
