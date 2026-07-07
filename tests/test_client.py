# cSpell: ignore Unraisable
from __future__ import annotations

import logging
import time
from concurrent import futures
from typing import TYPE_CHECKING

import pytest

from msl.network import AuthCurve, AuthPlain, Client, Flag

if TYPE_CHECKING:
    from conftest import Broker


@pytest.mark.filterwarnings("error")
def test_del_is_clean(capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture) -> None:
    # If Client.__del__ issues a pytest.PytestUnraisableExceptionWarning, this test fails
    _ = Client(port=17777)

    with Client(port=17778) as _:
        pass

    c = Client(port=17779)
    c.__del__()
    c.__del__()

    assert not caplog.records
    out, err = capsys.readouterr()
    assert not out
    assert not err


def test_disconnect_multiple_times(capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("DEBUG")
    c = Client(port=9301)
    time.sleep(0.1)  # allow time for Client to be connected before Interrupt is triggered

    assert c._async_client is not None  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
    interrupter_name = c._async_client.interrupter.name  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001

    for _ in range(5):
        c.disconnect()

    assert caplog.record_tuples == [
        ("msl.network", logging.DEBUG, f"{interrupter_name} created"),
        ("msl.network", logging.DEBUG, f"{c} connected"),
        ("msl.network", logging.DEBUG, f"{interrupter_name} triggered"),
        ("msl.network", logging.DEBUG, f"{interrupter_name} destroyed"),
        ("msl.network", logging.DEBUG, f"{c} disconnected"),
    ]

    out, err = capsys.readouterr()
    assert not out
    assert not err


def test_link_string_representation() -> None:
    with Client(port=8715) as c:
        link = c.link("Missing")
        assert str(link) == "Link(service='Missing')"
        assert repr(link) == "Link(service='Missing')"


def test_services_timeout() -> None:
    c = Client(port=14909)
    with pytest.raises((TimeoutError, futures.TimeoutError)):
        _ = c.services(timeout=0.05)


def test_flags_at() -> None:
    c = Client(flag=Flag.PICKLE, port=52742)
    link = c.link("Any")
    assert c.flag == Flag.PICKLE
    with c.flag_at(Flag.JSON):
        assert c.flag == Flag.JSON  # type: ignore[comparison-overlap]
        _ = link.do_something(sync=False)  # type: ignore[unreachable]
    assert c.flag == Flag.PICKLE  # type: ignore[unreachable]
    _ = link.do_something(sync=False)


def test_request_after_disconnect() -> None:
    c = Client(port=26419)
    c.disconnect()
    with pytest.raises(RuntimeError, match=r"Event loop not running, cannot send request"):
        _ = c.services()


def test_string_representation() -> None:
    class Custom(Client):
        pass

    c = Custom(port=17590, flag=Flag.JSON | Flag.LZMA)
    _id = c._id  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
    assert str(c) == f"Custom[{_id}]"
    assert repr(c) == f"Custom(host='127.0.0.1', port=17590, flag='LZMA|JSON', id='{_id}')"


def test_result_ok_and_error(broker: Broker) -> None:
    port = broker.run()
    client = Client(port=port)
    assert client.services() == []

    foo = client.link("Foo")
    with pytest.raises(RuntimeError, match=r"Service 'Foo' is not available"):
        _ = foo.bar(sync=False).result()

    client.disconnect()
    broker.stop()


def test_plain_and_curve() -> None:
    with pytest.raises(ValueError, match=r"Cannot use both PLAIN and CURVE"):
        _ = Client(curve=AuthCurve(b"a", b"b", b"c"), plain=AuthPlain("a", "b"))
