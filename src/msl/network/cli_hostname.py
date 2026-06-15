"""Command line interface for the `hostname` command.

To see the help documentation, run the following command in a terminal:

```console
msl-network hostname --help
```
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .cli_argparse import add_quiet_argument, add_verbose_argument
from .utils import HOME_DIR, get_logging_level, logger

if TYPE_CHECKING:
    from argparse import Namespace, _SubParsersAction  # pyright: ignore[reportPrivateUsage]

    from .cli_argparse import ArgumentParser


HELP = "Edit authorised hostnames (IP addresses)."

DESCRIPTION = (
    HELP
    + """

A Broker can be started with the option to use authorised devices, based on
the hostname (or IP address) of a connecting device, as the authorisation
mechanism for a client or service to be able to connect to the Broker.

To use authorised hostnames as the authentication check, start the Broker
with the `--auth-hostname` flag:

  msl-network start --auth-hostname

"""
)

EPILOG = """
Examples:

  # add 'TheHostname' as an authorised device
  msl-network hostname add TheHostname

  # add 'another-hostname' and '192.168.10.30' as authorised devices
  msl-network hostname add another-hostname 192.168.10.30

  # remove 'TheHostname' as an authorised device
  msl-network hostname remove TheHostname

  # reset the authorised hostnames to only be 'localhost'
  msl-network hostname reset

  # list all authorised hostnames
  msl-network hostname list

"""

assert __doc__  # noqa: S101
__doc__ += DESCRIPTION + EPILOG


def add_parser_hostname(parser: _SubParsersAction[ArgumentParser]) -> None:
    """Add the `hostname` command to the `parser`."""
    p = parser.add_parser(
        "hostname",
        help=HELP,
        description=DESCRIPTION,
        epilog=EPILOG,
    )
    _ = p.add_argument(
        "action",
        choices=["add", "remove", "reset", "list"],
        help=(
            "The action to perform:\n"
            "  add: Add one or more hostnames\n"
            "  remove: Remove one or more hostnames\n"
            "  reset: Reset to only allow '127.0.0.1'\n"
            "  list: Show the authorised hostnames"
        ),
    )
    _ = p.add_argument(
        "names",
        nargs="*",
        help="The hostname(s) or IP address(es) to action.",
    )
    add_quiet_argument(p)
    add_verbose_argument(p)
    p.set_defaults(func=execute)


def execute(ns: Namespace) -> None:
    """Executes the `hostname` command."""
    logging.basicConfig(
        level=get_logging_level(quiet=ns.quiet, verbose=ns.verbose),
        format="%(message)s",
    )

    path = HOME_DIR / "hostnames.txt"
    if not path.is_file():
        HOME_DIR.mkdir(parents=True, exist_ok=True)
        _ = path.write_text("127.0.0.1")

    hostnames = set(path.read_text().split(","))

    if ns.action == "list":
        logger.info("Authorised devices:\n  " + "\n  ".join(sorted(hostnames)))
        return

    if ns.action == "reset":
        logger.info("Reset to '127.0.0.1'")
        _ = path.write_text("127.0.0.1")
        return

    if not ns.names:
        logger.warning("Warning! You must specify at least one device to %s", ns.action)
        return

    if ns.action == "add":
        hostnames.update(ns.names)
        _ = path.write_text(",".join(hostnames))
        logger.info("Added: %s", ", ".join(ns.names))
        return

    # must be "remove"
    removed: list[str] = []
    for name in ns.names:
        if name not in hostnames:
            logger.warning("Cannot remove %r, it was not an authorised hostname", name)
        hostnames.remove(name)
        removed.append(name)
    logger.info("Removed: %s", ", ".join(removed))
