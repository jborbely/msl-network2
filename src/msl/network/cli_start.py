"""Command line interface for the `start` command.

To see the help documentation, run the following command in a terminal:

```console
msl-network start --help
```
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .cli_argparse import add_quiet_argument, add_verbose_argument
from .utils import BROKER_PORT, get_logging_level, run_event_loop

if TYPE_CHECKING:
    from argparse import Namespace, _SubParsersAction  # pyright: ignore[reportPrivateUsage]

    from .cli_argparse import ArgumentParser


HELP = "Start the Broker."

DESCRIPTION = HELP

EPILOG = """
Examples::

  # start the Broker using the default settings (no authorisation)
  msl-network start

  # start the Broker on port 8326
  msl-network start --port 8326

  # only authorised hostnames (IP addresses) can connect to the Broker
  msl-network start --auth-hostnames

See Also::

  msl-network hostname

"""

assert __doc__  # noqa: S101
__doc__ += DESCRIPTION + EPILOG


def add_parser_start(parser: _SubParsersAction[ArgumentParser]) -> None:
    """Add the `start` command to the `parser`."""
    p = parser.add_parser(
        "start",
        help=HELP,
        description=DESCRIPTION,
        epilog=EPILOG,
    )
    _ = p.add_argument(
        "--auth-hostname",
        action="store_true",
        default=False,
        help="Only connections from authorised devices are allowed.\nSee also: msl-network hostname",
    )
    _ = p.add_argument(
        "-H",
        "--host",
        default="*",
        help="The network interface to run the Broker on.\nIf unspecified, listen on all network interfaces.",
    )
    _ = p.add_argument(
        "-p",
        "--port",
        default=BROKER_PORT,
        help="The port number to use for the Broker.\nDefault is %(default)s.",
    )
    add_quiet_argument(p)
    add_verbose_argument(p)
    p.set_defaults(func=execute)


def execute(ns: Namespace) -> None:
    """Run the Broker in an asyncio event loop."""
    from .broker import Broker  # noqa: PLC0415

    logging.basicConfig(
        level=get_logging_level(quiet=ns.quiet, verbose=ns.verbose),
        format="%(asctime)s.%(msecs)03d [%(levelname)05s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    broker = Broker(host=ns.host, port=ns.port)
    try:
        run_event_loop(broker.run())
    except KeyboardInterrupt:
        pass
    finally:
        broker.destroy()
