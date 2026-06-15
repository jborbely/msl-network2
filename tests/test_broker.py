from __future__ import annotations

import logging
import threading
import time

import pytest
import zmq

from msl.network import Client, Worker
from msl.network.broker import Broker
from msl.network.message import Flag, Request
from msl.network.utils import run_event_loop


def test_session() -> None:  # noqa: PLR0915
    broker = Broker()
    broker_thread = threading.Thread(target=run_event_loop, daemon=True, args=(broker.run(),))
    broker_thread.start()

    port = int(broker.endpoint.rsplit(":", 1)[1])

    class Foo(Worker):
        def __init__(self) -> None:
            super().__init__(port=port)
            self.num_requests: int = 0

        def add(self, x: float, y: float) -> float:
            self.num_requests += 1
            return x + y

        def divide(self, x: float, y: float) -> float:
            self.num_requests += 1
            return x / y

        def sleep(self, duration: float) -> None:
            time.sleep(duration)

    service1 = Foo()
    service1_thread = threading.Thread(target=service1.connect, daemon=True)
    service1_thread.start()

    service2 = Foo()
    service2_thread = threading.Thread(target=service2.connect, daemon=True)
    service2_thread.start()

    time.sleep(0.1)

    client = Client(port=port)
    assert client.services() == ["Foo"]

    link = client.link("Foo")
    assert link.add(1, 2) == 3  # Balancer calls service1
    assert link.add(-1, 1, sync=False).result() == 0  # Balancer calls service2

    future1 = link.add(10, 1, sync=False)  # Balancer calls service1
    future2 = link.add(99, 1, sync=False)  # Balancer calls service2
    assert future2.result() == 100
    assert future1.result() == 11

    future_issue = link.divide(1, 0, sync=False)  # Balancer calls service1
    with pytest.raises(RuntimeError, match=r"ZeroDivisionError"):
        _ = future_issue.result()

    assert link.num_requests() == 2  # Balancer calls service2
    assert link.num_requests() == 3  # Balancer calls service1

    t0 = time.perf_counter()
    assert link.sleep(1) is None
    assert link.sleep(1) is None
    assert time.perf_counter() - t0 > 2.0

    t0 = time.perf_counter()
    future1 = link.sleep(1.0, sync=False)
    future2 = link.sleep(1.0, sync=False)
    assert future1.result() is None
    assert future2.result() is None
    assert time.perf_counter() - t0 < 1.5

    interrupter1 = service1._interrupter  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
    interrupter2 = service2._interrupter  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
    assert interrupter1 is not None
    assert interrupter2 is not None
    interrupter1()
    service1_thread.join()

    assert link.add(11, 22) == 33  # service2 still available

    interrupter2()
    service2_thread.join()

    with pytest.raises(RuntimeError, match=r"Service 'Foo' is not available"):
        _ = link.add(1, 2)

    with pytest.raises(RuntimeError, match=r"Unsupported broker request: 'WHATEVER'"):
        _ = client._create_future("Broker", "WHATEVER").result()  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001

    client.disconnect()

    broker.interrupter()
    broker_thread.join()


def test_worker_disconnects_without_notifying() -> None:
    broker = Broker()
    broker_thread = threading.Thread(target=run_event_loop, daemon=True, args=(broker.run(),))
    broker_thread.start()

    port = int(broker.endpoint.rsplit(":", 1)[1])

    class Foo(Worker):
        def add(self, x: float, y: float) -> float:
            return x + y

        async def _handle_disconnect(self) -> None:  # pyright: ignore[reportImplicitOverride]
            """Don't notify the Broker that this Worker is disconnecting."""
            return

    foo = Foo(port=port)
    foo_thread = threading.Thread(target=foo.connect, daemon=True)
    foo_thread.start()

    time.sleep(0.1)

    client = Client(port=port)
    assert client.services() == ["Foo"]

    link = client.link("Foo")
    assert link.add(1, 2) == 3

    interrupter1 = foo._interrupter  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
    assert interrupter1 is not None
    interrupter1()
    foo_thread.join()

    with pytest.raises(RuntimeError, match=r"Service 'Foo' is not available"):
        _ = link.add(1, 2)

    client.disconnect()

    broker.interrupter()
    broker.destroy()  # can call multiple times
    broker.destroy()
    broker.destroy()
    broker.destroy()
    broker_thread.join()


def test_worker_sends_bad_messages(caplog: pytest.LogCaptureFixture) -> None:
    # Tests that an unsupported message gets logged from a Worker and when
    # WORKER_UNAVAILABLE is sent with a service name that does not exist, the
    # request get silently ignored by the "is None" check on the broker
    caplog.set_level("DEBUG")

    broker = Broker()
    broker_thread = threading.Thread(target=run_event_loop, daemon=True, args=(broker.run(),))
    broker_thread.start()

    port = int(broker.endpoint.rsplit(":", 1)[1])

    context = zmq.Context()
    worker = context.socket(zmq.DEALER)
    worker.setsockopt(zmq.IDENTITY, b"Worker[1]")
    _ = worker.connect(f"tcp://localhost:{port}")

    r = Request(id=0, service="ignored", attribute="gets_logged", args=[], kwargs={})
    _ = worker.send_multipart([b"Broker", r.to_bytes(Flag.JSON)])  # pyright: ignore[reportUnknownMemberType]

    r = Request(id=0, service="UnknownServiceName", attribute="WORKER_UNAVAILABLE", args=[], kwargs={})
    _ = worker.send_multipart([b"Broker", r.to_bytes(Flag.JSON)])  # pyright: ignore[reportUnknownMemberType]
    time.sleep(0.1)

    worker.close()
    context.destroy()

    broker.interrupter()
    broker_thread.join()

    assert caplog.record_tuples == [
        ("msl.network", logging.DEBUG, f"{broker.interrupter.name} created"),
        ("msl.network", logging.INFO, f"Broker running on 0.0.0.0:{port}"),
        ("msl.network", logging.INFO, "b'Worker[1]' -> b'Broker'"),
        ("msl.network", logging.ERROR, "Unsupported broker request 'gets_logged' from b'Worker[1]'"),
        ("msl.network", logging.INFO, "b'Worker[1]' -> b'Broker'"),
        ("msl.network", logging.DEBUG, f"{broker.interrupter.name} triggered"),
        ("msl.network", logging.DEBUG, f"{broker.interrupter.name} destroyed"),
        ("msl.network", logging.DEBUG, "Broker has shut down"),
    ]
