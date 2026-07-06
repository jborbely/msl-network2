"""Command line interface for the `curve` command."""

from __future__ import annotations

import logging
import socket
from typing import TYPE_CHECKING

from zmq.auth import certs

from .cli_argparse import add_argument_quiet, add_argument_verbose
from .utils import MSL_NETWORK_HOME, get_logging_level, logger

if TYPE_CHECKING:
    from argparse import Namespace, _SubParsersAction  # pyright: ignore[reportPrivateUsage]

    from .cli_argparse import ArgumentParser


def add_parser_curve(parser: _SubParsersAction[ArgumentParser]) -> None:
    """Add the `curve` command to the `parser`."""
    p = parser.add_parser(
        "curve",
        help="Create CURVE certificates.",
        description="Create CURVE certificates.",
    )
    _ = p.add_argument(
        "-d",
        "--dir",
        help="The directory to save the certificate files to.",
    )
    _ = p.add_argument(
        "-n",
        "--name",
        help="The name (without the extension) to use for the files. Default is the computer's hostname.",
    )
    add_argument_quiet(p)
    add_argument_verbose(p)
    p.set_defaults(func=execute)


def execute(ns: Namespace) -> None:
    """Edit the CURVE authentication file."""
    logging.basicConfig(
        level=get_logging_level(quiet=ns.quiet, verbose=ns.verbose),
        format="%(message)s",
    )

    if ns.dir is None:
        key_dir = MSL_NETWORK_HOME
        key_dir.mkdir(parents=True, exist_ok=True)
    else:
        key_dir = ns.dir

    name = socket.gethostname() if ns.name is None else ns.name

    try:
        public_file, secret_file = certs.create_certificates(key_dir=key_dir, name=name)  # pyright: ignore[reportUnknownMemberType]
    except OSError:
        logger.error("Cannot create certificates, does '%s' directory exist?", key_dir)
    else:
        logger.info("Created secret certificate %s", secret_file)
        logger.info("Created public certificate %s", public_file)
        logger.info("Copy the public certificate to the $HOME/.curve directory on the computer running the broker")
