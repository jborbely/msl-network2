# cSpell: ignore Unraisable

from __future__ import annotations

import threading
from concurrent import futures

import pytest

from msl.network import Client, Flag
from msl.network.broker import Broker
from msl.network.utils import run_event_loop


@pytest.mark.filterwarnings("error")
def test_del_is_clean(capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture) -> None:
    # If Client.__del__ issues a pytest.PytestUnraisableExceptionWarning, this test fails

    _ = Client()

    with Client() as _:
        pass

    assert not caplog.records
    out, err = capsys.readouterr()
    assert not out
    assert not err


def test_disconnect_multiple_times(capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture) -> None:
    c = Client()
    for _ in range(5):
        c.disconnect()
    assert not caplog.records
    out, err = capsys.readouterr()
    assert not out
    assert not err


def test_link_string_representation() -> None:
    with Client() as c:
        link = c.link("Missing")
        assert str(link) == "Link(service='Missing')"
        assert repr(link) == "Link(service='Missing')"


def test_services_timeout() -> None:
    c = Client()
    with pytest.raises((TimeoutError, futures.TimeoutError)):
        _ = c.services(timeout=0.05)


def test_flags_at() -> None:
    c = Client(flag=Flag.PICKLE)
    link = c.link("Any")
    assert c.flag == Flag.PICKLE
    with c.flag_at(Flag.JSON):
        assert c.flag == Flag.JSON  # type: ignore[comparison-overlap]
        _ = link.do_something(sync=False)  # type: ignore[unreachable]
    assert c.flag == Flag.PICKLE  # type: ignore[unreachable]
    _ = link.do_something(sync=False)


def test_request_after_disconnect() -> None:
    c = Client()
    c.disconnect()
    with pytest.raises(RuntimeError, match=r"Event loop not running, cannot send request"):
        _ = c.services()


def test_string_representation() -> None:
    class Custom(Client):
        pass

    c = Custom()
    expect = f"Custom(host='127.0.0.1', port=1875, id='{c._id}')"  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
    assert str(c) == expect
    assert repr(c) == expect


def test_result_ok_and_error() -> None:
    broker = Broker()
    thread = threading.Thread(target=run_event_loop, daemon=True, args=(broker.run(),))
    thread.start()

    _, port = broker.address.rsplit(":", 1)
    client = Client(port=int(port))
    assert client.services() == []

    foo = client.link("Foo")
    with pytest.raises(RuntimeError, match=r"Service 'Foo' is not available"):
        _ = foo.bar(sync=False).result()

    client.disconnect()
    broker.interrupter()
    thread.join()
