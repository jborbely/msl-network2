"""Command line interface for the `device` command."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .cli_argparse import add_argument_quiet, add_argument_verbose
from .utils import get_logging_level, load_devices, logger

if TYPE_CHECKING:
    from argparse import Namespace, _SubParsersAction  # pyright: ignore[reportPrivateUsage]

    from .cli_argparse import ArgumentParser


ABOUT = "Edit authorised devices (by hostname or IP address)."


def add_parser_device(parser: _SubParsersAction[ArgumentParser]) -> None:
    """Add the `device` command to the `parser`."""
    p = parser.add_parser("device", help=ABOUT, description=ABOUT)
    _ = p.add_argument(
        "action", choices=["add", "remove", "reset", "list"], help="The action to perform with the specified device(s)"
    )
    _ = p.add_argument(
        "devices",
        nargs="*",
        help="The hostname(s) or IP address(es) to action.",
    )
    add_argument_quiet(p)
    add_argument_verbose(p)
    p.set_defaults(func=execute)


def execute(ns: Namespace) -> None:
    """Executes the `hostname` command."""
    logging.basicConfig(
        level=get_logging_level(quiet=ns.quiet, verbose=ns.verbose),
        format="%(message)s",
    )

    path, devices = load_devices()

    if ns.action == "list":
        if devices:
            logger.info("Authorised devices:\n  %s", "\n  ".join(sorted(devices)))
        else:
            logger.info("There are no authorised devices")
        return

    if ns.action == "reset":
        names = ns.devices or ["localhost"]
        logger.info("Authorised devices:\n  %s", "\n  ".join(names))
        _ = path.write_text("\n".join(names))
        return

    if not ns.devices:
        logger.warning("Warning! You must specify at least one device to %s", ns.action)
        return

    if ns.action == "add":
        devices.update(ns.devices)
        _ = path.write_text("\n".join(devices))
        logger.info("Added: %s", ", ".join(ns.devices))
        return

    # must be "remove"
    removed: list[str] = []
    for device in ns.devices:
        try:
            devices.remove(device)
            removed.append(device)
        except KeyError:  # noqa: PERF203
            logger.warning("Warning! Cannot remove %r, it is not an authorised device", device)

    _ = path.write_text("\n".join(devices))
    logger.info("Removed: %s", ", ".join(removed))
