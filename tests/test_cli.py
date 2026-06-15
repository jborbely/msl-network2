# cSpell: ignore creationflags capfd
from __future__ import annotations

import logging
import signal
import subprocess
import sys
import time
from typing import TYPE_CHECKING

import pytest

from msl.network.cli import main
from msl.network.utils import get_logging_level

if TYPE_CHECKING:
    from pathlib import Path


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


def test_hostname_list(home_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("DEBUG")
    assert not home_dir.is_dir()

    main("hostname", "list")

    assert home_dir.is_dir()
    assert caplog.record_tuples == [("msl.network", logging.INFO, "Authorised devices:\n  127.0.0.1")]


def test_hostname(home_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("DEBUG")

    main("hostname", "list")
    assert caplog.record_tuples == [("msl.network", logging.INFO, "Authorised devices:\n  127.0.0.1")]
    caplog.clear()

    main("hostname", "add", "msl-device", "192.168.1.100")
    assert caplog.record_tuples == [("msl.network", logging.INFO, "Added: msl-device, 192.168.1.100")]
    caplog.clear()

    main("hostname", "remove", "127.0.0.1")
    assert caplog.record_tuples == [("msl.network", logging.INFO, "Removed: 127.0.0.1")]
    caplog.clear()

    main("hostname", "list")
    assert caplog.record_tuples == [("msl.network", logging.INFO, "Authorised devices:\n  192.168.1.100\n  msl-device")]
    caplog.clear()

    main("hostname", "add")
    assert caplog.record_tuples == [
        ("msl.network", logging.WARNING, "Warning! You must specify at least one device to add")
    ]
    caplog.clear()

    main("hostname", "remove")
    assert caplog.record_tuples == [
        ("msl.network", logging.WARNING, "Warning! You must specify at least one device to remove")
    ]
    caplog.clear()

    main("hostname", "remove", "missing", "192.168.1.100")
    assert caplog.record_tuples == [
        ("msl.network", logging.WARNING, "Warning! Cannot remove 'missing', it is not an authorised device"),
        ("msl.network", logging.INFO, "Removed: 192.168.1.100"),
    ]
    caplog.clear()

    main("hostname", "add", "192.168.1.50")
    assert caplog.record_tuples == [("msl.network", logging.INFO, "Added: 192.168.1.50")]
    caplog.clear()

    main("hostname", "reset")
    assert caplog.record_tuples == [("msl.network", logging.INFO, "Reset to only '127.0.0.1' (localhost)")]
    caplog.clear()

    main("hostname", "list")
    assert caplog.record_tuples == [("msl.network", logging.INFO, "Authorised devices:\n  127.0.0.1")]
    caplog.clear()

    assert (home_dir / "network" / "hostnames.txt").read_text() == "127.0.0.1"


@pytest.mark.parametrize("command", [[], ["--help"]])
def test_help(command: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(*command)

    out, err = capsys.readouterr()
    assert not err
    assert out.startswith("usage:")
    assert out.endswith("Show the version number and exit.\n")


def test_help_unknown_command(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main("unknown")

    out, err = capsys.readouterr()
    assert not out
    assert "invalid choice: 'unknown' (choose from" in err
