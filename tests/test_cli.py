# cSpell: ignore creationflags capfd
from __future__ import annotations

import logging
import signal
import subprocess
import sys
import time
from typing import TYPE_CHECKING

import pytest
from zmq.auth import certs

from msl.network.cli import main, parse_args
from msl.network.cli_start import namespace_to_run_kwargs
from msl.network.utils import BROKER_PORT

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


def test_cli_device(home_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")

    main("device", "list")
    assert caplog.record_tuples == [("msl.network", logging.INFO, "Authorised devices:\n  localhost")]
    caplog.clear()

    main("device", "add", "msl-device", "192.168.1.100")
    assert caplog.record_tuples == [("msl.network", logging.INFO, "Added: msl-device, 192.168.1.100")]
    caplog.clear()

    main("device", "remove", "localhost")
    assert caplog.record_tuples == [("msl.network", logging.INFO, "Removed: localhost")]
    caplog.clear()

    main("device", "list")
    assert caplog.record_tuples == [("msl.network", logging.INFO, "Authorised devices:\n  192.168.1.100\n  msl-device")]
    caplog.clear()

    main("device", "add")
    assert caplog.record_tuples == [
        ("msl.network", logging.WARNING, "Warning! You must specify at least one device to add")
    ]
    caplog.clear()

    main("device", "remove")
    assert caplog.record_tuples == [
        ("msl.network", logging.WARNING, "Warning! You must specify at least one device to remove")
    ]
    caplog.clear()

    main("device", "remove", "missing", "192.168.1.100")
    assert caplog.record_tuples == [
        ("msl.network", logging.WARNING, "Warning! Cannot remove 'missing', it is not an authorised device"),
        ("msl.network", logging.INFO, "Removed: 192.168.1.100"),
    ]
    caplog.clear()

    main("device", "add", "192.168.1.50")
    assert caplog.record_tuples == [("msl.network", logging.INFO, "Added: 192.168.1.50")]
    caplog.clear()

    main("device", "reset")
    assert caplog.record_tuples == [("msl.network", logging.INFO, "Authorised devices:\n  localhost")]
    caplog.clear()

    main("device", "reset", "a", "b")
    assert caplog.record_tuples == [("msl.network", logging.INFO, "Authorised devices:\n  a\n  b")]
    caplog.clear()

    main("device", "list")
    assert caplog.record_tuples == [("msl.network", logging.INFO, "Authorised devices:\n  a\n  b")]
    caplog.clear()

    assert (home_dir / "devices.txt").read_text() == "a\nb"


@pytest.mark.parametrize("command", [["-h"], ["--help"]])
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


def test_cli_start_args() -> None:
    ns = parse_args("start")
    assert ns.cmd == "start"
    assert ns.auth_plain is None  # do not use PLAIN authentication
    assert ns.auth_device is None  # do not use IP address authentication
    assert ns.auth_curve is None  # do not use CURVE authentication
    assert ns.auth_domain == "*"
    assert ns.host == "*"
    assert ns.port == BROKER_PORT
    assert ns.quiet == 0
    assert ns.verbose == 0

    ns = parse_args("start", "--auth-device")
    assert ns.auth_plain is None  # do not use PLAIN authentication
    assert ns.auth_device == []  # empty list means to load from file
    assert ns.auth_curve is None  # do not use CURVE authentication
    assert ns.auth_domain == "*"

    ns = parse_args("start", "--auth-device", "a")
    assert ns.auth_plain is None  # do not use PLAIN authentication
    assert ns.auth_device == ["a"]  # a non-empty list takes precedence over the file
    assert ns.auth_curve is None  # do not use CURVE authentication
    assert ns.auth_domain == "*"

    ns = parse_args("start", "--auth-device", "a", "--port", "5555", "--auth-domain", "msl")
    assert ns.auth_plain is None  # do not use PLAIN authentication
    assert ns.auth_device == ["a"]
    assert ns.auth_curve is None  # do not use CURVE authentication
    assert ns.auth_domain == "msl"
    assert ns.port == 5555

    ns = parse_args(
        "start", "--quiet", "--auth-device", "192.168.1.100", "msl-hostname", "--quiet", "--host", "127.0.0.1"
    )
    assert ns.auth_plain is None  # do not use PLAIN authentication
    assert ns.auth_device == ["192.168.1.100", "msl-hostname"]
    assert ns.auth_curve is None  # do not use CURVE authentication
    assert ns.host == "127.0.0.1"
    assert ns.quiet == 2

    ns = parse_args("start", "--auth-plain", "--auth-device")
    assert ns.auth_plain == "~"  # load from default file
    assert ns.auth_device == []
    assert ns.auth_curve is None  # do not use CURVE authentication

    ns = parse_args("start", "--auth-plain", "path/to/file.json", "--auth-device", "1")
    assert ns.auth_plain == "path/to/file.json"  # load from user-defined file
    assert ns.auth_device == ["1"]
    assert ns.auth_curve is None  # do not use CURVE authentication

    ns = parse_args("start", "--auth-curve")
    assert ns.auth_plain is None
    assert ns.auth_device is None
    assert ns.auth_curve == "~"  # load from default path


@pytest.mark.parametrize("debug", [True, False])
def test_namespace_to_run_kwargs_debug(debug: bool) -> None:  # noqa: FBT001
    ns = parse_args("start")
    kwargs = namespace_to_run_kwargs(ns, debug=debug)
    assert kwargs == {
        "host": "*",
        "port": BROKER_PORT,
        "domain": "*",
        "debug": debug,
        "addresses": None,
        "curve": None,
        "plain": None,
    }


def test_namespace_to_run_kwargs_auth_device_default(home_dir: Path) -> None:
    assert not home_dir.exists()
    ns = parse_args("start", "--auth-device")
    kwargs = namespace_to_run_kwargs(ns)
    assert kwargs == {
        "host": "*",
        "port": BROKER_PORT,
        "domain": "*",
        "debug": False,
        "addresses": {"localhost": "127.0.0.1"},
        "curve": None,
        "plain": None,
    }


def test_namespace_to_run_kwargs_auth_device_specified() -> None:
    ns = parse_args("start", "--auth-device", "127.0.0.1", "localhost")
    kwargs = namespace_to_run_kwargs(ns)
    assert kwargs == {
        "host": "*",
        "port": BROKER_PORT,
        "domain": "*",
        "debug": False,
        "addresses": {"127.0.0.1": "127.0.0.1", "localhost": "127.0.0.1"},
        "curve": None,
        "plain": None,
    }


def test_namespace_to_run_kwargs_auth_device_gaierror(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("DEBUG")

    ns = parse_args("start", "--auth-device", "invalid-hostname", "localhost")
    kwargs = namespace_to_run_kwargs(ns)
    assert kwargs == {
        "host": "*",
        "port": BROKER_PORT,
        "domain": "*",
        "debug": False,
        "addresses": {"localhost": "127.0.0.1"},
        "curve": None,
        "plain": None,
    }

    assert caplog.record_tuples == [
        ("msl.network", logging.ERROR, "Cannot determine IPv4 address of 'invalid-hostname' [skipping]")
    ]


def test_namespace_to_run_kwargs_auth_plain_default(home_dir: Path) -> None:
    assert not home_dir.exists()
    ns = parse_args("start", "--auth-plain")
    kwargs = namespace_to_run_kwargs(ns)
    assert kwargs == {
        "host": "*",
        "port": BROKER_PORT,
        "domain": "*",
        "debug": False,
        "addresses": None,
        "curve": None,
        "plain": {},
    }


def test_namespace_to_run_kwargs_auth_plain_custom(tmp_path: Path) -> None:
    file = tmp_path / "plain.json"
    _ = file.write_text('{"a":"b"}')

    ns = parse_args("start", "--auth-plain", str(file))
    kwargs = namespace_to_run_kwargs(ns)
    assert kwargs == {
        "host": "*",
        "port": BROKER_PORT,
        "domain": "*",
        "debug": False,
        "addresses": None,
        "curve": None,
        "plain": {"a": "b"},
    }


def test_namespace_to_run_kwargs_auth_curve_default(home_dir: Path) -> None:
    assert not home_dir.exists()

    ns = parse_args("start", "--auth-curve")
    kwargs = namespace_to_run_kwargs(ns)

    file = next(home_dir.glob("*.key_secret"))

    public, secret = certs.load_certificate(file)  # pyright: ignore[reportUnknownMemberType]
    assert secret is not None

    curve = kwargs["curve"]
    assert curve is not None
    assert curve.public_key == public
    assert curve.secret_key == secret
    assert curve.keys == set()
    assert curve.domain == "*"


def test_namespace_to_run_kwargs_auth_curve_custom_domain(tmp_path: Path) -> None:
    ns = parse_args("start", "--auth-curve", str(tmp_path), "--auth-domain", "msl")
    kwargs = namespace_to_run_kwargs(ns)

    file = next(tmp_path.glob("*.key_secret"))

    public, secret = certs.load_certificate(file)  # pyright: ignore[reportUnknownMemberType]

    curve = kwargs["curve"]
    assert curve is not None
    assert curve.public_key == public
    assert secret is not None
    assert curve.secret_key == secret
    assert curve.keys == set()
    assert curve.domain == "msl"
