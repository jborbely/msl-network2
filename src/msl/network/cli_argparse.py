"""Custom argument parser."""

from __future__ import annotations

import argparse
from typing import Any


class ArgumentParser(argparse.ArgumentParser):
    """A custom argument parser."""

    def __init__(self, **kwargs: Any) -> None:
        """A custom argument parser."""
        kwargs["add_help"] = False  # use a custom help message (see below)
        kwargs["formatter_class"] = argparse.RawTextHelpFormatter
        super().__init__(**kwargs)

        _ = self.add_argument(
            "-h",
            "--help",
            action="help",
            help="Show this help message and exit.",
            default=argparse.SUPPRESS,
        )


def add_quiet_argument(parser: ArgumentParser) -> None:
    """Add a `--quiet` flag to the parser."""
    _ = parser.add_argument(
        "-q",
        "--quiet",
        action="count",
        default=0,
        help=(
            "Give less output. Option is additive and can be used up to 3 times,\n"
            "corresponds to silencing the INFO, WARNING and ERROR logging level."
        ),
    )


def add_verbose_argument(parser: ArgumentParser) -> None:
    """Add a `--verbose` flag to the parser."""
    _ = parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Give more output (DEBUG logging level).",
    )
