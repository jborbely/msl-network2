"""Main entry way to the command-line interface."""

from __future__ import annotations

import sys

from .__about__ import __version__
from .cli_argparse import ArgumentParser
from .cli_hostname import add_parser_hostname
from .cli_start import add_parser_start

DESCRIPTION = """A concurrent and asynchronous Broker.

A Broker allows for multiple clients and services to connect to it
and it links a client's request to the appropriate service to handle
the request and then the broker sends the response from the service
back to the client.
"""


def configure_parser() -> ArgumentParser:
    """Returns the argument parser."""
    parser = ArgumentParser(description=DESCRIPTION)
    _ = parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"{__version__}",
        help="Show the version number and exit.",
    )
    command_parser = parser.add_subparsers(metavar="command", dest="cmd")
    command_parser.required = True
    add_parser_hostname(command_parser)
    add_parser_start(command_parser)
    return parser


def main(*args: str) -> None:
    """Main entry way to the command-line interface."""
    if not args:
        args = tuple(sys.argv[1:])
        if not args:
            args = ("--help",)
    parser = configure_parser()
    namespace = parser.parse_args(args)
    namespace.func(namespace)
