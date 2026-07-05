"""Custom argument parser."""

from __future__ import annotations

import argparse
from typing import Any


class ArgumentParser(argparse.ArgumentParser):
    """A custom argument parser."""

    def __init__(self, **kwargs: Any) -> None:
        """A custom argument parser."""
        super().__init__(add_help=False, **kwargs)

        _ = self.add_argument(
            "-h",
            "--help",
            action="help",
            help="Show the help message and exit.",
            default=argparse.SUPPRESS,
        )


def add_argument_quiet(parser: ArgumentParser) -> None:
    """Add a `--quiet` flag to the parser."""
    _ = parser.add_argument(
        "-q",
        "--quiet",
        action="count",
        default=0,
        help="Give less output. Option is additive and can be used up to 3 times.",
    )


def add_argument_verbose(parser: ArgumentParser) -> None:
    """Add a `--verbose` flag to the parser."""
    _ = parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Give more output (DEBUG logging level).",
    )
