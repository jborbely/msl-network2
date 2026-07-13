"""Common constants, functions and classes."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from zmq.auth import certs

if TYPE_CHECKING:
    from collections.abc import Coroutine
    from logging import Logger
    from typing import Any, Final


logger: Final[Logger] = logging.getLogger(__package__)

BROKER_PORT: Final[int] = 1875

USER_DIR: Final[Path] = Path("~" + os.getenv("SUDO_USER", "")).expanduser()

MSL_NETWORK_HOME: Final[Path] = Path(os.getenv("MSL_NETWORK_HOME", default=USER_DIR / ".msl" / "network"))

logging.getLogger("asyncio").setLevel(logging.WARNING)


class Curve:
    """Information for CURVE authentication."""

    def __init__(
        self, *, public_key: bytes = b"", secret_key: bytes = b"", keys: set[bytes] | None = None, domain: str = "*"
    ) -> None:
        """Information for CURVE authentication.

        Args:
            public_key: Public key to use for the Broker.
            secret_key: Secret key to use for the Broker.
            keys: A set of public z85 keys of devices that are allowed to connect to the Broker.
            domain: The ZAP domain that the Broker is using.
        """
        self.public_key: bytes = public_key
        self.secret_key: bytes = secret_key
        self.keys: set[bytes] = keys or set()
        self.domain: str = domain

    def callback(self, domain: str, key: bytes) -> bool:
        """Called during ZAP authentication when a device connects to the Broker.

        Args:
            domain: The domain specified by the device during ZAP.
            key: The z85 key of the connecting device.

        Returns:
            Whether the device can connect.
        """
        return (domain == self.domain) and ((not self.keys) or (key in self.keys))


def get_logging_level(*, quiet: int, verbose: int) -> int:
    """Get the logging level from command-line flags.

    Args:
        quiet: The number of times the `--quiet` flag is specified.
        verbose: The number of times the `--verbose` flag is specified.

    Returns:
        The logging level.
    """
    level = 10 * (quiet - verbose) + logging.INFO
    return max(10, min(level, 50))


def load_curves(home_dir: Path | None = None, domain: str = "*") -> Curve | None:  # noqa: C901
    """Load the CURVE authentication certificates."""
    root = home_dir or MSL_NETWORK_HOME

    secret_file = next(root.glob("*.key_secret"), None)
    if secret_file is None:
        if home_dir is None and not root.exists():
            root.mkdir(parents=True, exist_ok=True)
        elif not root.exists():
            logger.error("Cannot create broker certificates, the '%s' directory does not exist", root)
            return None

        public_cert, secret_cert = certs.create_certificates(root, socket.gethostname())  # pyright: ignore[reportUnknownMemberType]
        secret_file = Path(secret_cert)
        logger.info("IMPORTANT! Created new CURVE authentication certificates")
        logger.info("IMPORTANT! Copy '%s' to a device that connects as a client or service", public_cert)

    logger.debug("Loading CURVE authentication certificates from '%s'", secret_file)
    try:
        public_key, secret_key = certs.load_certificate(secret_file)  # pyright: ignore[reportUnknownMemberType]
    except ValueError as e:  # public_key is None
        logger.error("%s", e)  # noqa: TRY400
        return None

    if secret_key is None:
        logger.error("No secret key found in '%s'", secret_file)
        return None

    curves_dir = root / "curves"
    if home_dir is None and not curves_dir.exists():
        curves_dir.mkdir(parents=True, exist_ok=True)

    keys: set[bytes] = set()
    for directory in (curves_dir, USER_DIR / ".curve"):
        if not directory.is_dir():
            logger.debug("Skipping CURVE certificates in '%s' [directory does not exist]", directory)
            continue

        try:
            loaded = certs.load_certificates(directory)  # pyright: ignore[reportUnknownMemberType]
        except (OSError, ValueError) as e:
            logger.error("Skipping all CURVE certificates in '%s' [%s]", directory, e)  # noqa: TRY400
        else:
            keys.update(loaded)
            logger.debug("Loaded %d CURVE certificates from '%s'", len(loaded), directory)

    return Curve(public_key=public_key, secret_key=secret_key, keys=keys, domain=domain)


def load_devices(home_dir: Path | None = None) -> tuple[Path, set[str]]:
    """Load the devices.txt file.

    If the file does not exist, create it with "localhost" as the only value.
    """
    root = home_dir or MSL_NETWORK_HOME
    path = root / "devices.txt"
    logger.debug("Loading authorised device addresses from '%s'", path)
    try:
        return path, set(path.read_text().splitlines())
    except FileNotFoundError:
        root.mkdir(parents=True, exist_ok=True)
        _ = path.write_text("localhost")
        return path, {"localhost"}


def load_plain(path: str | Path | None = None) -> tuple[Path, dict[str, str] | None]:
    """Load a JSON file containing the PLAIN username to password mapping.

    The mapping is `None` if the file does not exist or contains invalid JSON data.
    """
    if path is None:
        path = MSL_NETWORK_HOME / "plain.json"
        if not path.is_file():
            MSL_NETWORK_HOME.mkdir(parents=True, exist_ok=True)
            _ = path.write_text("{}")

    path = Path(path)
    logger.debug("Loading PLAIN authentication data from '%s'", path)

    try:
        contents = path.read_bytes()
    except FileNotFoundError:
        logger.error("File not found: %s", path)  # noqa: TRY400
        return path, None

    try:
        data = json.loads(contents)
    except json.JSONDecodeError:
        logger.error("Invalid JSON file for PLAIN authentication: %s", path)  # noqa: TRY400
        return path, None

    if not isinstance(data, dict):
        logger.error('The PLAIN authentication file must be a {"username": "password"} mapping')
        return path, None

    # make sure every value is a string, valid JSON forces each key to be a string
    plain: dict[str, str] = {k: str(v) for k, v in data.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    return path, plain


def run_event_loop(coroutine: Coroutine[Any, Any, None]) -> None:
    """Execute the coroutine and return the result."""
    less_than_3_12 = sys.version_info < (3, 12)

    if less_than_3_12 and sys.platform == "win32":
        # PyZMQ requires a SelectorEventLoop to have the `add_reader` method available
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # pyright: ignore[reportDeprecated]

    kwargs = {} if less_than_3_12 else {"loop_factory": asyncio.SelectorEventLoop}
    return asyncio.run(coroutine, debug=False, **kwargs)
