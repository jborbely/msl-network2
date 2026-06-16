# cSpell: ignore Unraisable
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import TYPE_CHECKING

import pytest
import zmq

from msl.network import Flag, Worker
from msl.network.message import Request, Response

if TYPE_CHECKING:
    from collections.abc import Iterable


@pytest.mark.filterwarnings("error")
def test_del_is_clean(capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture) -> None:
    # If Worker.__del__ issues a pytest.PytestUnraisableExceptionWarning, this test fails
    _ = Worker(port=30001)
    assert not caplog.records
    out, err = capsys.readouterr()
    assert not out
    assert not err


def test_connect_interrupt_disconnect(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("DEBUG")

    w = Worker(port=32845)
    thread = threading.Thread(target=w.connect, daemon=True)
    thread.start()

    time.sleep(0.1)
    interrupter = w._interrupter  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
    assert interrupter is not None
    interrupter()
    time.sleep(0.1)

    r = caplog.records
    assert r[0].message == f"{interrupter.name} created"
    assert r[1].message == "Worker connected"
    assert r[2].message == "Worker registered"
    assert r[3].message == "Worker polling..."
    assert r[4].message == f"{interrupter.name} triggered"
    assert r[5].message == "Worker unregistered"
    assert r[6].message == f"{interrupter.name} destroyed"
    assert r[7].message == "Worker disconnected"
    assert r[8].message == "Worker event loop closed"

    thread.join()


def test_flags_at() -> None:
    w = Worker(flag=Flag.NONE, port=11008)
    assert w.flag == Flag.NONE
    with w.flag_at(Flag.JSON):
        assert w.flag == Flag.JSON  # type: ignore[comparison-overlap]
    assert w.flag == Flag.NONE  # type: ignore[unreachable]


def test_session() -> None:  # noqa: PLR0915
    context = zmq.Context()
    broker = context.socket(zmq.ROUTER)
    broker.setsockopt(zmq.IDENTITY, b"Broker")
    port = broker.bind_to_random_port("tcp://localhost")

    class ServiceName(Worker):
        def division(self, a: float, b: float) -> float:
            return a / b

    sn = ServiceName(port=port)
    thread = threading.Thread(target=sn.connect, daemon=True)
    thread.start()

    # The service name gets registered with the Broker
    worker_id, destination_id, message = broker.recv_multipart()
    request = Request.from_bytes(message)
    assert worker_id.startswith(b"Worker[")
    assert destination_id == b"Broker"
    assert request.attribute == "WORKER_READY"
    assert request.service == "ServiceName"

    # Request private attribute
    request = Request(id=1, service="ServiceName", attribute="_socket", args=(), kwargs={})
    _ = broker.send_multipart((worker_id, b"Broker", request.to_bytes(Flag.PICKLE)))  # pyright: ignore[reportUnknownMemberType]
    _, _, message = broker.recv_multipart()
    response = Response.from_bytes(message)
    assert response.result == "PermissionError: Cannot request a private attribute"

    # Request invalid attribute
    request = Request(id=2, service="ServiceName", attribute="missing", args=(), kwargs={})
    _ = broker.send_multipart((worker_id, b"Broker", request.to_bytes(Flag.PICKLE)))  # pyright: ignore[reportUnknownMemberType]
    _, _, message = broker.recv_multipart()
    response = Response.from_bytes(message)
    assert response.id == 2
    assert not response.ok
    assert response.result == "'ServiceName' object has no attribute 'missing'"

    # Request non-callable attribute
    request = Request(id=3, service="ServiceName", attribute="flag", args=(), kwargs={})
    _ = broker.send_multipart((worker_id, b"Broker", request.to_bytes(Flag.PICKLE)))  # pyright: ignore[reportUnknownMemberType]
    _, _, message = broker.recv_multipart()
    response = Response.from_bytes(message)
    assert response.id == 3
    assert response.ok
    assert response.result == Flag.PICKLE

    # Request valid callable attribute
    request = Request(id=4, service="ServiceName", attribute="division", args=(10, 2), kwargs={})
    _ = broker.send_multipart((worker_id, b"Broker", request.to_bytes(Flag.PICKLE)))  # pyright: ignore[reportUnknownMemberType]
    _, _, message = broker.recv_multipart()
    response = Response.from_bytes(message)
    assert response.id == 4
    assert response.ok
    assert response.result == 5

    # Request valid callable attribute raises
    request = Request(id=5, service="ServiceName", attribute="division", args=(10, 0), kwargs={})
    _ = broker.send_multipart((worker_id, b"Broker", request.to_bytes(Flag.PICKLE)))  # pyright: ignore[reportUnknownMemberType]
    _, _, message = broker.recv_multipart()
    response = Response.from_bytes(message)
    assert response.id == 5
    assert not response.ok
    assert response.result.startswith("Traceback (most recent call last):\n")
    assert response.result.endswith("ZeroDivisionError: division by zero\n")

    assert sn._interrupter is not None  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
    sn._interrupter()  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
    thread.join()

    broker.close(linger=0)
    context.destroy(linger=0)

    # Worker._handle_disconnect() can be called multiple times
    asyncio.run(sn._handle_disconnect())  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
    asyncio.run(sn._handle_disconnect())  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001


def test_signatures() -> None:
    class Foo(Worker):
        def __init__(self, ignore_attributes: str | Iterable[str] | None = None) -> None:
            super().__init__(ignore_attributes=ignore_attributes)
            self.count: int = 0

        def add(self, x: float, y: float) -> float:
            return x + y

        def types(self, *, a: bool, b: int, c: float, d: str = "hi", e: list[str] | None = None) -> bytes:
            _ = a, b, c, d, e
            return b""

        @property
        def greet(self) -> str:
            return "hi"

    foo = Foo()
    assert foo.signatures() == {
        "add": "(x: float, y: float) -> float",
        "count": "() -> int",
        "greet": "() -> str",
        "types": "(*, a: bool, b: int, c: float, d: str = hi, e: list[str] | None = None) -> bytes",
    }
    foo.disconnect()

    foo = Foo()
    foo.ignore_attributes("count", "greet")
    assert foo.signatures() == {
        "add": "(x: float, y: float) -> float",
        "types": "(*, a: bool, b: int, c: float, d: str = hi, e: list[str] | None = None) -> bytes",
    }
    foo.disconnect()

    foo = Foo("count")
    assert foo.signatures() == {
        "add": "(x: float, y: float) -> float",
        "greet": "() -> str",
        "types": "(*, a: bool, b: int, c: float, d: str = hi, e: list[str] | None = None) -> bytes",
    }
    foo.disconnect()

    foo = Foo(("types", "add"))
    assert foo.signatures() == {
        "count": "() -> int",
        "greet": "() -> str",
    }
    foo.disconnect()


def test_signatures_warnings(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("DEBUG")

    class Warner(Worker):
        def __init__(self) -> None:
            super().__init__()
            self._price: int = 0
            self.zzz: type[RuntimeError] = RuntimeError

        def set_price(self, value: int) -> None:
            self._price = value

        price: property = property(fget=None, fset=set_price, fdel=None, doc=None)

    w = Warner()
    assert w.signatures() == {"set_price": "(value: int) -> None"}
    del w

    assert caplog.record_tuples == [
        (
            "msl.network",
            logging.WARNING,
            "property 'price' of 'test_signatures_warnings.<locals>.Warner' object has no getter [attribute='price']",
        ),
        (
            "msl.network",
            logging.WARNING,
            "no signature found for builtin type <class 'RuntimeError'> [attribute='zzz']",
        ),
    ]
