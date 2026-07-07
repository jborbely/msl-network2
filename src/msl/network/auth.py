"""Authentication tools for [Client][]s and [Worker][]s to connect to a [Broker][]."""

from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import TYPE_CHECKING

from zmq.auth import certs

from .utils import MSL_NETWORK_HOME, load_plain

if TYPE_CHECKING:
    from .typing import PathLike


def load_certificate(path: PathLike) -> tuple[bytes, bytes | None]:
    """Load public and secret keys from a ZeroMQ certificate file.

    Args:
        path: The path to a certificate file.

    Returns:
        The `(public, secret)` keys. The `secret` key can be `None` if it is not defined in the file.
    """
    path = Path(os.fsdecode(path))
    if not path.is_file():
        msg = f"File not found: {path}"  # prefer FileNotFoundError instead of pyzmq exception
        raise FileNotFoundError(msg)

    return certs.load_certificate(path)  # pyright: ignore[reportUnknownMemberType]


class AuthPlain:
    """PLAIN authentication credentials to connect to a [Broker][]."""

    def __init__(self, username: str | bytes, password: str | bytes) -> None:
        """PLAIN authentication credentials to connect to a [Broker][].

        Args:
            username: The username registered with the [Broker][].
            password: The password registered with the [Broker][].
        """
        self.username: bytes = username.encode() if isinstance(username, str) else username
        self.password: bytes = password.encode() if isinstance(password, str) else password

    @staticmethod
    def load(path: PathLike | None = None, sep: str | None = None) -> AuthPlain:
        """Load PLAIN authentication credentials from a file.

        Args:
            path: The path to load the credentials from. If the path has the `.json`
                extension, the file must contain a single *username* to *password*
                mapping. If `None`, loads the credentials that were created by running
                the `msl-network plain add` command.
            sep: If the `path` extension is not `.json`, the separator to use to split the
                first line in the file to get the `username, password` value.

        Returns:
            The PLAIN credentials.
        """
        default = MSL_NETWORK_HOME / "plain.json"
        file = default if path is None else Path(os.fsdecode(path))
        if not file.exists():
            msg = f"No such file: '{file}'"
            if file == default:
                msg += ", run `msl-network plain add` in a terminal"
            raise FileNotFoundError(msg)

        if file.suffix == ".json":
            _, auth = load_plain(file)
            if not auth:
                msg = "No PLAIN credentials found"
                if file == default:
                    msg += ", run `msl-network plain add` in a terminal"
                raise ValueError(msg)

            if len(auth) > 1:
                msg = (
                    "Too many PLAIN credentials found, run `msl-network plain remove` in a "
                    "terminal or specify a different file"
                )
                raise ValueError(msg)

            username = next(iter(auth))
            password = auth[username]
        else:
            u, p = file.read_text().split(sep)
            username = u.strip()
            password = p.strip()

        return AuthPlain(username=username, password=password)


class AuthCurve:
    """CURVE authentication credentials to connect to a [Broker][]."""

    def __init__(self, public_key: bytes, secret_key: bytes, broker_key: bytes) -> None:
        """CURVE authentication credentials to connect to a [Broker][].

        Args:
            public_key: The public key of the [Client][] or [Worker][].
            secret_key: The secret key of the [Client][] or [Worker][].
            broker_key: The public key of the [Broker][].
        """
        self.public_key: bytes = public_key
        self.secret_key: bytes = secret_key
        self.broker_key: bytes = broker_key

    @staticmethod
    def load(broker: PathLike, own: PathLike | None = None) -> AuthCurve:
        """Load CURVE authentication credentials from files.

        Args:
            broker: The path to the file that contains the [Broker][]'s public key.
            own: The path to the file that contains the public and secret keys of the
                client or worker that connects to the [Broker][]. If `None`, loads the
                credentials that were created by running the `msl-network curve` command.

        Returns:
            The CURVE credentials.
        """
        broker_public, _ = load_certificate(broker)

        default = MSL_NETWORK_HOME / f"{socket.gethostname()}.key_secret"
        file = default if own is None else os.fsdecode(own)
        own_public, own_secret = load_certificate(file)
        if own_secret is None:
            msg = f"No secret key found in {file}"
            raise ValueError(msg)

        return AuthCurve(public_key=own_public, secret_key=own_secret, broker_key=broker_public)
