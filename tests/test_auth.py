from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from msl.network import AuthCurve, AuthPlain
from msl.network.cli import main
from msl.network.utils import load_curves

if TYPE_CHECKING:
    from pathlib import Path


def test_auth_plain_default_not_exists(home_dir: Path) -> None:
    home_dir.mkdir()  # so that it can be removed by the fixture
    with pytest.raises(FileNotFoundError, match=r"run `msl-network plain add` in a terminal$"):
        _ = AuthPlain.load()


@pytest.mark.parametrize("ext", ["json", "txt"])
def test_auth_plain_custom_not_exist(ext: str) -> None:
    path = f"missing.{ext}"
    with pytest.raises(FileNotFoundError, match=rf"'{path}'$"):
        _ = AuthPlain.load(path=path)


def test_auth_plain_default_exists_empty(home_dir: Path) -> None:
    home_dir.mkdir()
    _ = (home_dir / "plain.json").write_text("{}")
    with pytest.raises(ValueError, match=r"^No PLAIN credentials found, run `msl-network plain add` in a terminal$"):
        _ = AuthPlain.load()


def test_auth_plain_custom_exists_empty(tmp_path: Path) -> None:
    path = tmp_path / "plain.json"
    _ = path.write_text("{}")
    with pytest.raises(ValueError, match=r"^No PLAIN credentials found$"):
        _ = AuthPlain.load(path=path)


def test_auth_plain_default_exists(home_dir: Path) -> None:
    main("plain", "add", "-u", "msl", "-p", "anything")
    auth = AuthPlain.load()
    assert auth.username == "msl"
    assert auth.password == "anything"  # noqa: S105
    assert (home_dir / "plain.json").read_text() == '{\n  "msl": "anything"\n}'


def test_auth_plain_default_exists_multiple(home_dir: Path) -> None:
    main("plain", "add", "-u", "msl", "-p", "anything")
    main("plain", "add", "-u", "a", "-p", "b")
    with pytest.raises(ValueError, match=r"^Too many PLAIN credentials found"):
        _ = AuthPlain.load()
    assert (home_dir / "plain.json").read_text() == '{\n  "msl": "anything",\n  "a": "b"\n}'


def test_auth_plain_custom_text_empty(tmp_path: Path) -> None:
    path = tmp_path / "plain.txt"
    _ = path.write_text("")
    with pytest.raises(ValueError, match=r"not enough values to unpack"):
        _ = AuthPlain.load(path=path)


def test_auth_plain_custom_text_default_sep_none(tmp_path: Path) -> None:
    path = tmp_path / "plain.txt"
    _ = path.write_text("uname pass")
    auth = AuthPlain.load(path=path)
    assert auth.username == "uname"
    assert auth.password == "pass"  # noqa: S105


def test_auth_plain_custom_text_default_sep_equals(tmp_path: Path) -> None:
    path = tmp_path / "plain.txt"
    _ = path.write_text("uname = pass")
    auth = AuthPlain.load(path=path, sep="=")
    assert auth.username == "uname"
    assert auth.password == "pass"  # noqa: S105


def test_auth_curve_broker_missing() -> None:
    with pytest.raises(FileNotFoundError):
        _ = AuthCurve.load("missing.key")


def test_auth_curve_default(home_dir: Path, tmp_path: Path) -> None:
    broker = tmp_path / "broker.key"
    _ = broker.write_text("public-key = abc")

    main("curve")
    assert home_dir.exists()
    curve = load_curves()
    assert curve is not None

    auth = AuthCurve.load(broker=broker)
    assert auth.public_key == curve.public_key
    assert auth.secret_key == curve.secret_key
    assert auth.broker_key == b"abc"


def test_auth_curve_no_public_key(tmp_path: Path) -> None:
    broker = tmp_path / "broker.key"
    _ = broker.write_text("public-key = abc")

    client = tmp_path / "client.key"
    _ = broker.write_text("does not contain a public key")

    with pytest.raises(ValueError, match=r"No public key found in"):
        _ = AuthCurve.load(broker=broker, own=client)


def test_auth_curve_no_secret_key(tmp_path: Path) -> None:
    broker = tmp_path / "broker.key"
    _ = broker.write_text("public-key = abc")

    client = tmp_path / "client.key"
    _ = client.write_text("public-key = xyz")

    with pytest.raises(ValueError, match=r"No secret key found in"):
        _ = AuthCurve.load(broker=broker, own=client)
