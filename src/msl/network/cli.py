"""Main entry way to the command-line interface."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from .__about__ import __version__
from .cli_argparse import ArgumentParser
from .cli_curve import add_parser_curve
from .cli_device import add_parser_device
from .cli_plain import add_parser_plain
from .cli_start import add_parser_start

if TYPE_CHECKING:
    from argparse import Namespace


def configure_parser() -> ArgumentParser:
    """Returns the argument parser."""
    parser = ArgumentParser(prog="msl-network", description="Exchange concurrent and asynchronous messages.")
    _ = parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"{__version__}",
        help="Show the version number and exit.",
    )
    sub_parser = parser.add_subparsers(metavar="command", dest="cmd")
    sub_parser.required = True
    add_parser_curve(sub_parser)
    add_parser_device(sub_parser)
    add_parser_plain(sub_parser)
    add_parser_start(sub_parser)
    return parser


def parse_args(*args: str) -> Namespace:
    """Parse command-line arguments."""
    args = tuple(args or sys.argv[1:] or ["--help"])
    parser = configure_parser()
    return parser.parse_args(args)


def main(*args: str) -> None:
    """Main entry way to the command-line interface."""
    namespace = parse_args(*args)
    namespace.func(namespace)
