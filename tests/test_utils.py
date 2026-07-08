from __future__ import annotations

import json
import logging
import socket
from pathlib import Path

import pytest
from zmq.auth import certs

from msl.network.utils import USER_DIR, Curve, get_logging_level, load_curves, load_devices, load_plain


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


def test_load_devices_default_home_dir(home_dir: Path) -> None:
    assert not home_dir.exists()
    path, hosts = load_devices()
    assert home_dir.exists()
    assert path == home_dir / "devices.txt"
    assert hosts == {"localhost"}
    assert path.read_text() == "localhost"


def test_load_devices(tmp_path: Path) -> None:
    assert tmp_path.exists()
    path, hosts = load_devices(tmp_path)
    assert path == tmp_path / "devices.txt"
    assert hosts == {"localhost"}
    assert path.read_text() == "localhost"

    _ = path.write_text("127.0.0.1\n10.11.12.13\nMSL-Device")
    path2, hosts = load_devices(tmp_path)
    assert path == path2
    assert hosts == {"127.0.0.1", "10.11.12.13", "MSL-Device"}


def test_curve_callback_invalid_domain() -> None:
    curve = Curve(keys={b"1", b"2", b"3"}, domain="msl")
    assert not curve.callback("*", b"1")


def test_curve_callback_keys_empty() -> None:
    curve = Curve()
    assert curve.callback(curve.domain, b"key ignored")


def test_curve_callback_invalid_key() -> None:
    curve = Curve(keys={b"1", b"2", b"3"}, domain="msl")
    assert not curve.callback(curve.domain, b"4")


def test_curve_callback_valid_key() -> None:
    curve = Curve(keys={b"1", b"2", b"3"}, domain="*")
    assert curve.callback(curve.domain, b"2")


def test_load_plain_default_path(home_dir: Path) -> None:
    expected_path = home_dir / "plain.json"
    assert not expected_path.is_file()

    path, data = load_plain()
    assert path == expected_path
    assert data == {}

    assert expected_path.is_file()

    path, data = load_plain()
    assert path == expected_path
    assert data == {}


def test_load_plain_file_not_found(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    file = Path("missing/file.json")
    path, data = load_plain(file)
    assert path == file
    assert data is None

    assert caplog.record_tuples == [
        ("msl.network", logging.DEBUG, f"Loading PLAIN authentication data from '{file}'"),
        ("msl.network", logging.ERROR, f"File not found: {file}"),
    ]


def test_load_plain_bad_json(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    file = tmp_path / "plain.json"
    _ = file.write_text("user=pass")

    path, data = load_plain(file)
    assert path == file
    assert data is None

    assert caplog.record_tuples == [
        ("msl.network", logging.DEBUG, f"Loading PLAIN authentication data from '{file}'"),
        ("msl.network", logging.ERROR, f"Invalid JSON file for PLAIN authentication: {file}"),
    ]


def test_load_plain_invalid_dict(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    file = tmp_path / "plain.json"
    _ = file.write_text(json.dumps([("user1", "pw1"), ("user2", "pw2")]))

    path, data = load_plain(file)
    assert path == file
    assert data is None

    assert caplog.record_tuples == [
        ("msl.network", logging.DEBUG, f"Loading PLAIN authentication data from '{file}'"),
        ("msl.network", logging.ERROR, 'The PLAIN authentication file must be a {"username": "password"} mapping'),
    ]


def test_load_plain_key_and_value_not_str(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    file = tmp_path / "plain.json"
    _ = file.write_text(json.dumps({123: "pw1", "user2": 456}))

    path, data = load_plain(file)
    assert path == file
    assert data == {"123": "pw1", "user2": "456"}

    # ZMQ event-monitoring messages can appear in this test so ignore them
    r = [r for r in caplog.records if not r.message.startswith("Monitor")]
    assert r[0].levelname == "DEBUG"
    assert r[0].message == f"Loading PLAIN authentication data from '{file}'"
    assert len(r) == 1


def test_load_curve_default_path(home_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    hostname = socket.gethostname()

    curves_dir = home_dir / "curves"
    secret_file = home_dir / f"{hostname}.key_secret"
    public_file = home_dir / f"{hostname}.key"

    assert not home_dir.is_dir()
    assert not curves_dir.is_dir()

    curve = load_curves()
    assert home_dir.is_dir()
    assert curves_dir.is_dir()
    assert secret_file.is_file()
    assert public_file.is_file()

    assert curve is not None

    public_key, secret_key = certs.load_certificate(secret_file)  # pyright: ignore[reportUnknownMemberType]
    assert curve.public_key == public_key
    assert curve.secret_key == secret_key

    public_key, secret_key = certs.load_certificate(public_file)  # pyright: ignore[reportUnknownMemberType]
    assert curve.public_key == public_key
    assert secret_key is None

    assert curve.domain == "*"
    assert len(curve.keys) == 0  # assumes there are no *.key files in $HOME/.curve

    assert curve.callback("*", b"whatever")
    assert not curve.callback("a", b"whatever")

    user_dir = USER_DIR / ".curve"
    assert not user_dir.exists()  # assumption for test

    # ZMQ event-monitoring messages can appear in this test so ignore them
    r = [r for r in caplog.records if not r.message.startswith("Monitor")]
    assert r[0].levelname == "INFO"
    assert r[0].message == "IMPORTANT! Created new CURVE authentication certificates"
    assert r[1].levelname == "INFO"
    assert r[1].message == f"IMPORTANT! Copy '{public_file}' to a device that connects as a client or service"
    assert r[2].levelname == "DEBUG"
    assert r[2].message == f"Loading CURVE authentication certificates from '{secret_file}'"
    assert r[3].levelname == "DEBUG"
    assert r[3].message == f"Loaded 0 CURVE certificates from '{curves_dir}'"
    assert r[4].levelname == "DEBUG"
    assert r[4].message == f"Skipping CURVE certificates in '{user_dir}' [directory does not exist]"
    assert len(r) == 5

    caplog.clear()

    curve = load_curves()
    assert caplog.record_tuples == [
        ("msl.network", logging.DEBUG, f"Loading CURVE authentication certificates from '{secret_file}'"),
        ("msl.network", logging.DEBUG, f"Loaded 0 CURVE certificates from '{curves_dir}'"),
        ("msl.network", logging.DEBUG, f"Skipping CURVE certificates in '{user_dir}' [directory does not exist]"),
    ]


def test_load_curve_invalid_directory(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    curve = load_curves(Path("missing"))
    assert curve is None

    assert caplog.record_tuples == [
        ("msl.network", logging.ERROR, "Cannot create broker certificates, the 'missing' directory does not exist"),
    ]


def test_load_curve_non_default_directory_empty(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    hostname = socket.gethostname()

    curves_dir = tmp_path / "curves"
    secret_file = tmp_path / f"{hostname}.key_secret"
    public_file = tmp_path / f"{hostname}.key"

    assert not curves_dir.is_dir()
    assert not secret_file.is_file()
    assert not public_file.is_file()

    curve = load_curves(tmp_path)

    assert not curves_dir.is_dir()  # does not get created
    assert secret_file.is_file()
    assert public_file.is_file()

    assert curve is not None

    user_dir = USER_DIR / ".curve"
    assert not user_dir.exists()  # assumption for test

    assert caplog.record_tuples == [
        ("msl.network", logging.INFO, "IMPORTANT! Created new CURVE authentication certificates"),
        (
            "msl.network",
            logging.INFO,
            f"IMPORTANT! Copy '{public_file}' to a device that connects as a client or service",
        ),
        ("msl.network", logging.DEBUG, f"Loading CURVE authentication certificates from '{secret_file}'"),
        ("msl.network", logging.DEBUG, f"Skipping CURVE certificates in '{curves_dir}' [directory does not exist]"),
        ("msl.network", logging.DEBUG, f"Skipping CURVE certificates in '{user_dir}' [directory does not exist]"),
    ]


def test_load_curve_no_public_key(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    secret_file = tmp_path / "new.key_secret"
    _ = secret_file.write_text("# does not contain a public key\nwhatever\n")

    curve = load_curves(tmp_path)
    assert curve is None

    assert caplog.record_tuples == [
        ("msl.network", logging.DEBUG, f"Loading CURVE authentication certificates from '{secret_file}'"),
        ("msl.network", logging.ERROR, f"No public key found in {secret_file}"),
    ]


def test_load_curve_no_secret_key(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    secret_file = tmp_path / "new.key_secret"
    _ = secret_file.write_text("# does not contain a secret key\n  public-key = abcd\n")

    curve = load_curves(tmp_path)
    assert curve is None

    assert caplog.record_tuples == [
        ("msl.network", logging.DEBUG, f"Loading CURVE authentication certificates from '{secret_file}'"),
        ("msl.network", logging.ERROR, f"No secret key found in '{secret_file}'"),
    ]


def test_load_curve_no_client_public_key(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    curves_dir = tmp_path / "curves"
    curves_dir.mkdir()

    secret_file = tmp_path / "broker.key_secret"
    _ = secret_file.write_text("public-key = abc\nsecret-key = def")

    client_file = curves_dir / "client.key"
    _ = client_file.write_text("# does not contain a public key\nwhatever\n")

    curve = load_curves(tmp_path)
    assert curve is not None

    user_dir = USER_DIR / ".curve"
    assert not user_dir.exists()  # assumption for test

    assert caplog.record_tuples == [
        ("msl.network", logging.DEBUG, f"Loading CURVE authentication certificates from '{secret_file}'"),
        (
            "msl.network",
            logging.ERROR,
            f"Skipping all CURVE certificates in '{curves_dir}' [No public key found in {client_file}]",
        ),
        ("msl.network", logging.DEBUG, f"Skipping CURVE certificates in '{user_dir}' [directory does not exist]"),
    ]
