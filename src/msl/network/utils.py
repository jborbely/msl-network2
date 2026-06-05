"""Common stuff."""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from typing import Any


logger = logging.getLogger(__package__)


def run_event_loop(main: Coroutine[Any, Any, None]) -> None:
    """Execute the coroutine and return the result."""
    less_than_3_12 = sys.version_info < (3, 12)

    if less_than_3_12 and sys.platform == "win32":
        # PyZMQ requires a SelectorEventLoop to have the `add_reader` method available
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined]  # pyright: ignore[reportDeprecated]

    kwargs = {} if less_than_3_12 else {"loop_factory": asyncio.SelectorEventLoop}
    return asyncio.run(main, debug=False, **kwargs)
