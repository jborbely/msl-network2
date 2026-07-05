"""Command line interface for the `start` command."""

from __future__ import annotations

import logging
import socket
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from .broker import Broker
from .cli_argparse import add_argument_quiet, add_argument_verbose
from .utils import BROKER_PORT, get_logging_level, load_curves, load_devices, load_plain, logger, run_event_loop

if TYPE_CHECKING:
    from argparse import Namespace, _SubParsersAction  # pyright: ignore[reportPrivateUsage]

    from .cli_argparse import ArgumentParser
    from .utils import Curve

CONST = "~"


def add_parser_start(parser: _SubParsersAction[ArgumentParser]) -> None:
    """Add the `start` command to the `parser`."""
    p = parser.add_parser(
        "start",
        help="Start the broker.",
        description=(
            "Start a broker that allows for multiple clients and services to connect to it and "
            "it links a client's request to the appropriate service to handle the "
            "request and then sends the response from the service back to the client."
        ),
    )
    _ = p.add_argument(
        "--auth-curve",
        nargs="?",
        const=CONST,
        metavar="KEYS_DIR",
        help=(
            "Use authentication based on public and private CURVE keys. Specifying a value "
            "after this flag will use the files in the specified directory to load the key "
            "files. Specifying this flag without a value will use the default directory. "
            "See `msl-network curve` for more details."
        ),
    )
    _ = p.add_argument(
        "--auth-domain",
        default="*",
        help="The domain to use for PLAIN and CURVE authentication. Default is '*'.",
    )
    _ = p.add_argument(
        "--auth-device",
        nargs="*",
        metavar="DEVICE",
        help=(
            "Use authentication based on the IP address (or hostname) of devices that are "
            "allowed to connect. Specifying this flag without one or more values will use the"
            "values stored in the default file. See `msl-network device` for more details."
        ),
    )
    _ = p.add_argument(
        "--auth-plain",
        nargs="?",
        const=CONST,
        metavar="JSON_FILE",
        help=(
            "Use authentication based on usernames and passwords. Specifying a value after "
            "this flag will load that JSON file for the username to password mapping for the "
            "authentication parameters. Specifying this flag without a value will use the "
            "parameters in the default file. See `msl-network plain` for more details."
        ),
    )
    _ = p.add_argument(
        "-H",
        "--host",
        default="*",
        help="The network interface to run the Broker on. If unspecified, listen on all network interfaces.",
    )
    _ = p.add_argument(
        "-p",
        "--port",
        type=int,
        default=BROKER_PORT,
        help="The port number to use for the Broker. Default is %(default)s.",
    )
    add_argument_quiet(p)
    add_argument_verbose(p)
    p.set_defaults(func=execute)


class RunKwargs(TypedDict):
    """Keyword arguments for Broker.run()."""

    addresses: dict[str, str] | None
    curve: Curve | None
    debug: bool
    domain: str
    host: str
    plain: dict[str, str] | None
    port: int


def namespace_to_run_kwargs(ns: Namespace, *, debug: bool = False) -> RunKwargs:
    """Convert parsed command-line arguments to keyword argument for Broker.run()."""
    addresses: dict[str, str] | None = None
    if ns.auth_device is not None:
        if len(ns.auth_device) == 0:
            _, devices = load_devices()
        else:
            devices = ns.auth_device

        addresses = {}
        for device in devices:
            try:
                addresses[device] = socket.gethostbyname(device)
            except socket.gaierror:  # noqa: PERF203
                logger.error("Cannot determine IPv4 address of %r [skipping]", device)

    plain: dict[str, str] | None = None
    if ns.auth_plain is not None:
        file = None if ns.auth_plain == CONST else Path(ns.auth_plain)
        _, plain = load_plain(file)

    curve: Curve | None = None
    if ns.auth_curve is not None:
        home_dir = None if ns.auth_curve == CONST else Path(ns.auth_curve)
        curve = load_curves(home_dir, domain=ns.auth_domain)

    return {
        "host": ns.host,
        "port": ns.port,
        "domain": ns.auth_domain,
        "debug": debug,
        "addresses": addresses,
        "curve": curve,
        "plain": plain,
    }


def execute(ns: Namespace) -> None:
    """Run the Broker in an asyncio event loop."""
    level = get_logging_level(quiet=ns.quiet, verbose=ns.verbose)

    logging.basicConfig(
        level=level,
        format="%(asctime)s.%(msecs)03d [%(levelname)05s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    broker = Broker()
    try:
        run_event_loop(broker.run(**namespace_to_run_kwargs(ns, debug=level == logging.DEBUG)))
    except KeyboardInterrupt:
        pass
    finally:
        broker.destroy()
