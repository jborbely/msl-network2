"""Example echo service.

Returns the arguments and keyword arguments that were sent from a Client.
"""

from __future__ import annotations

from typing import Any

from msl.network import Worker


class Echo(Worker):
    """Example Worker that echos the arguments of the request."""

    @staticmethod
    def echo(*args: Any, **kwargs: Any) -> tuple[tuple[Any, ...], dict[str, Any]]:
        """Returns the arguments and keyword arguments sent from a Client."""
        return args, kwargs


if __name__ == "__main__":
    echo = Echo()

    # Connect the service to the Broker
    echo.connect()
