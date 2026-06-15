"""Common stuff."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from logging import Logger
    from typing import Any, Final


logger: Final[Logger] = logging.getLogger(__package__)

BROKER_PORT: Final[int] = 1875

USER_DIR: Final[Path] = Path("~" + os.getenv("SUDO_USER", "")).expanduser()

HOME_DIR: Final[Path] = Path(os.getenv("MSL_NETWORK_HOME") or USER_DIR / ".msl") / "network"
"""[Path][pathlib.Path] &mdash; The default directory where all files used by msl-network are located.

Can be overwritten by specifying a `MSL_NETWORK_HOME` environment variable.
"""

logging.getLogger("asyncio").setLevel(logging.WARNING)


def run_event_loop(coroutine: Coroutine[Any, Any, None]) -> None:
    """Execute the coroutine and return the result."""
    less_than_3_12 = sys.version_info < (3, 12)

    if less_than_3_12 and sys.platform == "win32":
        # PyZMQ requires a SelectorEventLoop to have the `add_reader` method available
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined]  # pyright: ignore[reportDeprecated]

    kwargs = {} if less_than_3_12 else {"loop_factory": asyncio.SelectorEventLoop}
    return asyncio.run(coroutine, debug=False, **kwargs)


def get_logging_level(*, quiet: int, verbose: int) -> int:
    """Get the logging level from command-line flags.

    Args:
        quiet: The number of times the `--quiet` flag is specified.
        verbose: The number of times the `--verbose` flag is specified.

    Returns:
        The logging level.
    """
    level = 10 * (quiet - verbose) + logging.INFO
    return max(10, min(level, 50))
