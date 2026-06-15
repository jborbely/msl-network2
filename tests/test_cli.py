# cSpell: ignore creationflags capfd
from __future__ import annotations

import logging
import signal
import subprocess
import sys
import time

import pytest

from msl.network.utils import get_logging_level


def test_cli_start(capfd: pytest.CaptureFixture[str]) -> None:
    command = ["msl-network", "start", "--verbose"]

    is_windows = sys.platform == "win32"
    if is_windows:
        sig = signal.CTRL_BREAK_EVENT
        p = subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)  # noqa: S603
    else:
        sig = signal.SIGINT
        p = subprocess.Popen(command, start_new_session=True)  # noqa: S603

    time.sleep(0.5)
    p.send_signal(sig)
    _ = p.wait()

    out, err = capfd.readouterr()
    assert not out

    lines = err.splitlines()
    if is_windows:
        assert len(lines) == 2
        assert "Interrupter" in lines[0]
        assert "created" in lines[0]
        assert lines[1].endswith("Broker running on 0.0.0.0:1875")
    else:
        assert len(lines) == 4
        assert "Interrupter" in lines[0]
        assert "created" in lines[0]
        assert lines[1].endswith("Broker running on 0.0.0.0:1875")
        assert "Interrupter" in lines[2]
        assert "destroyed" in lines[2]
        assert lines[3].endswith("Broker has shut down")


@pytest.mark.parametrize(
    ("quiet", "verbose", "expected"),
    [
        (0, 0, logging.INFO),
        (1, 0, logging.WARNING),
        (2, 0, logging.ERROR),
        (3, 0, logging.CRITICAL),
        (4, 0, logging.CRITICAL),
        (10, 0, logging.CRITICAL),
        (0, 1, logging.DEBUG),
        (0, 2, logging.DEBUG),
        (0, 10, logging.DEBUG),
        (1, 1, logging.INFO),
        (8, 6, logging.ERROR),
        (5, 6, logging.DEBUG),
    ],
)
def test_get_logging_level(quiet: int, verbose: int, expected: int) -> None:
    assert get_logging_level(quiet=quiet, verbose=verbose) == expected
