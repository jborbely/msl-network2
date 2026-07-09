# cSpell: ignore Unraisable
from __future__ import annotations

import logging
import time
from concurrent import futures
from typing import TYPE_CHECKING

import pytest
import zmq

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

    # the order of ZMQ event-monitoring messages are unpredictable so ignore them
    r = [r.message for r in caplog.records if not r.message.startswith("Monitor")]
    assert r[0] == f"{interrupter_name} created"
    assert r[1] == f"{c} connecting..."
    assert r[2] == f"{interrupter_name} triggered"
    assert r[3] == f"{interrupter_name} terminated"
    assert r[4] == f"{c} disconnected"

    out, err = capsys.readouterr()
    assert not out
    assert not err


def test_link_string_representation() -> None:
    with Client(port=8715) as c:
        link = c.link("Missing")
        assert str(link) == "Link[Missing]"
        assert repr(link) == "Link[Missing]"


def test_services_timeout() -> None:
    c = Client(port=14909)
    with pytest.raises((TimeoutError, futures.TimeoutError)):
        _ = c.services(timeout=0.05)


def test_flag_at() -> None:
    c = Client(flag=Flag.PICKLE, port=52742)
    link = c.link("Any")
    assert c.flag == Flag.PICKLE

    with c.flag_at(Flag.JSON):
        assert c.flag == Flag.JSON  # type: ignore[comparison-overlap]
        _ = link.do_something(sync=False)  # type: ignore[unreachable]

    with link.flag_at(Flag.BZ2 | Flag.JSON):  # type: ignore[unreachable]
        assert c.flag == Flag.BZ2 | Flag.JSON
        _ = link.do_something(sync=False)

    assert c.flag == Flag.PICKLE
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
    port, *_ = broker.run()
    client = Client(port=port)
    assert client.services() == []

    foo = client.link("Foo")
    assert foo.timeout is None
    with pytest.raises(RuntimeError, match=r"Service 'Foo' is not available"):
        _ = foo.bar(sync=False).result()

    assert client.is_connected

    broker.stop()
    time.sleep(0.1)

    assert not client.is_connected  # should have received ZMQ_EVENT_DISCONNECTED from the broker stopping
    client.disconnect()  # type: ignore[unreachable]


def test_plain_and_curve() -> None:
    with pytest.raises(ValueError, match=r"Cannot use both PLAIN and CURVE"):
        _ = Client(curve=AuthCurve(b"a", b"b", b"c"), plain=AuthPlain("a", "b"))


def test_plain(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    c = Client(port=29501, plain=AuthPlain("hi", "hello"))
    assert c._async_client is not None  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
    interrupter_name = c._async_client.interrupter.name  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
    time.sleep(0.1)
    c.disconnect()

    # the order of ZMQ event-monitoring messages are unpredictable so ignore them
    r = [r.message for r in caplog.records if not r.message.startswith("Monitor")]
    assert r[0] == f"{interrupter_name} created"
    assert r[1] == "Using PLAIN authentication [domain:*]"
    assert r[2] == f"{c} connecting..."
    assert r[3] == f"{interrupter_name} triggered"
    assert r[4] == f"{interrupter_name} terminated"
    assert r[5] == f"{c} disconnected"


def test_curve(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    broker_public, _ = zmq.curve_keypair()
    client_public, client_secret = zmq.curve_keypair()

    c = Client(
        port=49162, curve=AuthCurve(public_key=client_public, secret_key=client_secret, broker_key=broker_public)
    )
    assert c._async_client is not None  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
    interrupter_name = c._async_client.interrupter.name  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
    time.sleep(0.1)
    c.disconnect()

    # the order of ZMQ event-monitoring messages are unpredictable so ignore them
    r = [r.message for r in caplog.records if not r.message.startswith("Monitor")]
    assert r[0] == f"{interrupter_name} created"
    assert r[1] == "Using CURVE authentication [domain:*]"
    assert r[2] == f"{c} connecting..."
    assert r[3] == f"{interrupter_name} triggered"
    assert r[4] == f"{interrupter_name} terminated"
    assert r[5] == f"{c} disconnected"
