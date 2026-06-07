# cSpell: ignore Unraisable
from __future__ import annotations

import threading
import time

import pytest

from msl.network import Flag, Worker


@pytest.mark.filterwarnings("error")
def test_del_is_clean(capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture) -> None:
    # If Worker.__del__ issues a pytest.PytestUnraisableExceptionWarning, this test fails
    _ = Worker()
    assert not caplog.records
    out, err = capsys.readouterr()
    assert not out
    assert not err


def test_connect_interrupt_disconnect(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("DEBUG")

    w = Worker()
    threading.Thread(target=w.connect, daemon=True).start()
    time.sleep(0.1)
    interrupter = w._interrupter  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
    assert interrupter is not None
    interrupter()
    time.sleep(0.1)

    r = caplog.records
    assert r[0].name == "asyncio"
    assert r[1].message == f"{interrupter.name} created"
    assert r[2].message == "Worker connected"
    assert r[3].message == "Worker registered"
    assert r[4].message == "Worker polling..."
    assert r[5].message == f"{interrupter.name} triggered"
    assert r[6].message == f"{interrupter.name} destroyed"
    assert r[7].message == "Worker disconnected"
    assert r[8].message == "Worker event loop closed"


def test_flags_at() -> None:
    w = Worker(flag=Flag.NONE)
    assert w.flag == Flag.NONE
    with w.flag_at(Flag.JSON):
        assert w.flag == Flag.JSON  # type: ignore[comparison-overlap]
    assert w.flag == Flag.NONE  # type: ignore[unreachable]
