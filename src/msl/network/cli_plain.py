"""Command line interface for the `plain` command."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from .cli_argparse import add_argument_quiet, add_argument_verbose
from .utils import get_logging_level, load_plain, logger

if TYPE_CHECKING:
    from argparse import Namespace, _SubParsersAction  # pyright: ignore[reportPrivateUsage]

    from .cli_argparse import ArgumentParser


def add_parser_plain(parser: _SubParsersAction[ArgumentParser]) -> None:
    """Add the `plain` command to the `parser`."""
    p = parser.add_parser(
        "plain",
        help="Edit usernames and passwords for PLAIN authentication.",
        description="Edit usernames and passwords for PLAIN authentication.",
    )
    _ = p.add_argument("action", choices=["add", "remove", "reset", "list"], help="The action to perform.")
    _ = p.add_argument("-u", "--username", help="The username to action.")
    _ = p.add_argument("-p", "--password", help="The password.")
    _ = p.add_argument("-f", "--file", help="The JSON file to use. If not specified, use the default file.")
    add_argument_quiet(p)
    add_argument_verbose(p)
    p.set_defaults(func=execute)


def execute(ns: Namespace) -> None:  # noqa: C901
    """Edit the PLAIN authentication file."""
    logging.basicConfig(
        level=get_logging_level(quiet=ns.quiet, verbose=ns.verbose),
        format="%(message)s",
    )

    path, auth = load_plain(ns.file)
    if auth is None:
        return  # reason already logged

    def dumps(obj: dict[str, str]) -> str:
        return json.dumps(obj, indent=2, ensure_ascii=False)

    if ns.action == "list":
        logger.info("%s", dumps(auth))
        return

    if ns.action == "reset":
        if ns.username is None and ns.password is None:
            _ = path.write_text("{}")
            logger.info("Removed all usernames and passwords")
        elif ns.username is not None and ns.password is not None:
            auth[ns.username] = ns.password
            _ = path.write_text(dumps(auth))
            logger.info("Reset authentication for only %r", ns.username)
        else:
            logger.info("Must specify both --username and --password or neither")
        return

    if ns.action == "remove":
        if ns.username is None:
            logger.info("Must specify --username to remove a user")
        elif ns.username not in auth:
            logger.info("User %r does not exist, cannot remove", ns.username)
        else:
            del auth[ns.username]
            _ = path.write_text(dumps(auth))
            logger.info("Removed authentication for %r", ns.username)
        return

    # must be action="add"
    if ns.username is not None and ns.password is not None:
        auth[ns.username] = ns.password
        _ = path.write_text(dumps(auth))
        logger.info("Added authentication for %r", ns.username)
    else:
        logger.info("Must specify both --username and --password to add a user")
