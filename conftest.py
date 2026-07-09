"""pytest configuration file."""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

# MSL_NETWORK_HOME must be defined before importing msl.network
home = Path(tempfile.gettempdir()) / ".msl"
os.environ["MSL_NETWORK_HOME"] = str(home)

from msl.network import utils  # noqa: E402
from msl.network.broker import Broker as _Broker  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import Any


class Broker:
    """Helper class to run and stop a Broker."""

    def __init__(self) -> None:
        """Helper class to run and stop a Broker."""
        self.broker: _Broker = _Broker()
        self.thread: threading.Thread | None = None
        self.interrupter_name: str = ""

    def run(self, **kwargs: Any) -> tuple[int, int, int]:
        """Run the broker and return the port, XPUB, XSUB numbers that the broker is using."""
        self.thread = threading.Thread(target=utils.run_event_loop, daemon=True, args=(self.broker.run(**kwargs),))
        self.thread.start()
        while (not self.broker.running) or (self.broker.xsub_port == -1):
            continue
        self.interrupter_name = self.broker.interrupter.name
        port = int(self.broker.endpoint.rsplit(":", 1)[1])
        return port, self.broker.xpub_port, self.broker.xsub_port

    def stop(self) -> None:
        """Stop the broker."""
        if self.thread is None:
            return

        self.broker.interrupter()
        self.thread.join()
        self.thread = None

        # okay to call again
        self.broker.destroy()


@pytest.fixture
def home_dir() -> Iterator[Path]:
    """Fixture to clean and yield the MSL_NETWORK_HOME path."""
    shutil.rmtree(home, ignore_errors=True)
    yield home
    shutil.rmtree(home)


@pytest.fixture
def broker() -> Broker:
    """Fixture to create a Broker."""
    return Broker()
