from __future__ import annotations

import logging
import socket
import threading
import time
from typing import TYPE_CHECKING

import pytest
import zmq

from msl.network import AuthCurve, AuthPlain, Client, Worker
from msl.network.cli import main
from msl.network.message import Flag, Request
from msl.network.utils import Curve

if TYPE_CHECKING:
    from conftest import Broker

# when a test succeeds this value is large enough, when it fails a TimeoutError should be raised
TIMEOUT = 0.1


def test_session(broker: Broker) -> None:
    port, *_ = broker.run()

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

    broker.stop()


def test_worker_disconnects_without_notifying(broker: Broker) -> None:
    port, *_ = broker.run()

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

    assert link.signatures() == {"add": "(x: float, y: float) -> float"}

    interrupter1 = foo._interrupter  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
    assert interrupter1 is not None
    interrupter1()
    foo_thread.join()

    with pytest.raises(RuntimeError, match=r"Service 'Foo' is not available"):
        _ = link.add(1, 2)

    client.disconnect()
    broker.stop()


def test_worker_sends_bad_messages(broker: Broker, caplog: pytest.LogCaptureFixture) -> None:
    # Tests that an unsupported message gets logged from a Worker and when
    # WORKER_UNAVAILABLE is sent with a service name that does not exist, the
    # request get silently ignored by the "is None" check on the broker
    caplog.set_level("DEBUG")

    port, xpub, xsub = broker.run()

    context = zmq.Context()
    worker = context.socket(zmq.DEALER)
    worker.setsockopt(zmq.ROUTING_ID, b"Worker[1]")
    _ = worker.connect(f"tcp://localhost:{port}")

    r = Request(id=0, service="ignored", attribute="gets_logged", args=[], kwargs={})
    _ = worker.send_multipart([b"Broker", r.to_bytes(Flag.JSON)])  # pyright: ignore[reportUnknownMemberType]

    r = Request(id=0, service="UnknownServiceName", attribute="WORKER_UNAVAILABLE", args=[], kwargs={})
    _ = worker.send_multipart([b"Broker", r.to_bytes(Flag.JSON)])  # pyright: ignore[reportUnknownMemberType]
    time.sleep(0.1)

    worker.close()
    context.destroy()

    broker.stop()

    assert caplog.record_tuples == [
        ("msl.network", logging.DEBUG, f"{broker.interrupter_name} created"),
        ("msl.network", logging.INFO, f"Broker running on 0.0.0.0:{port}"),
        ("msl.network", logging.INFO, broker.proxy_init_message(port, xpub, xsub)),
        ("msl.network", logging.DEBUG, "b'Worker[1]' -> b'Broker'"),
        ("msl.network", logging.ERROR, "Unsupported broker request 'gets_logged' from b'Worker[1]'"),
        ("msl.network", logging.DEBUG, "b'Worker[1]' -> b'Broker'"),
        ("msl.network", logging.DEBUG, f"{broker.interrupter_name} triggered"),
        ("msl.network", logging.DEBUG, "XPUB/XSUB terminated"),
        ("msl.network", logging.DEBUG, f"{broker.interrupter_name} terminated"),
        ("msl.network", logging.DEBUG, "Broker terminated"),
    ]


def test_allow_localhost(broker: Broker, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)

    port, xpub, xsub = broker.run(addresses={"localhost": "127.0.0.1"})
    client = Client(port=port)
    assert client.services(timeout=TIMEOUT) == []
    client.disconnect()
    broker.stop()

    assert caplog.record_tuples == [
        ("msl.network", logging.INFO, "ZAP allowed devices: localhost"),
        ("msl.network", logging.INFO, "Using NULL authentication [domain:*]"),
        ("msl.network", logging.INFO, f"Broker running on 0.0.0.0:{port}"),
        ("msl.network", logging.INFO, broker.proxy_init_message(port, xpub, xsub)),
    ]


def test_plain_ok(broker: Broker, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)

    port, xpub, xsub = broker.run(plain={"msl": "uncertainty"})
    client = Client(port=port, plain=AuthPlain("msl", "uncertainty"))
    assert client.services(timeout=TIMEOUT) == []
    client.disconnect()
    broker.stop()

    assert caplog.record_tuples == [
        ("msl.network", logging.INFO, "Using PLAIN authentication for user msl [domain:*]"),
        ("msl.network", logging.INFO, f"Broker running on 0.0.0.0:{port}"),
        ("msl.network", logging.INFO, broker.proxy_init_message(port, xpub, xsub)),
    ]


def test_curve_all_keys(broker: Broker, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)

    broker_public, broker_secret = zmq.curve_keypair()
    client_public, client_secret = zmq.curve_keypair()
    curve = Curve(public_key=broker_public, secret_key=broker_secret)
    auth_curve = AuthCurve(public_key=client_public, secret_key=client_secret, broker_key=broker_public)

    port, xpub, xsub = broker.run(curve=curve)
    client = Client(port=port, curve=auth_curve)
    assert client.services(timeout=TIMEOUT) == []
    client.disconnect()
    broker.stop()

    assert caplog.record_tuples == [
        ("msl.network", logging.INFO, "Using CURVE authentication with all keys allowed [domain:*]"),
        ("msl.network", logging.INFO, f"Broker running on 0.0.0.0:{port}"),
        ("msl.network", logging.INFO, broker.proxy_init_message(port, xpub, xsub)),
    ]


def test_curve_valid_key(broker: Broker, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)

    broker_public, broker_secret = zmq.curve_keypair()
    client_public, client_secret = zmq.curve_keypair()
    curve = Curve(public_key=broker_public, secret_key=broker_secret, keys={client_public})
    auth_curve = AuthCurve(public_key=client_public, secret_key=client_secret, broker_key=broker_public)

    port, xpub, xsub = broker.run(curve=curve)
    client = Client(port=port, curve=auth_curve)
    assert client.services(timeout=TIMEOUT) == []
    client.disconnect()
    broker.stop()

    assert caplog.record_tuples == [
        ("msl.network", logging.INFO, "Using CURVE authentication with 1 key allowed [domain:*]"),
        ("msl.network", logging.INFO, f"Broker running on 0.0.0.0:{port}"),
        ("msl.network", logging.INFO, broker.proxy_init_message(port, xpub, xsub)),
    ]


def test_curve_valid_multiple_keys(broker: Broker, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)

    broker_public, broker_secret = zmq.curve_keypair()
    client_public, client_secret = zmq.curve_keypair()
    client2_public, _ = zmq.curve_keypair()
    curve = Curve(public_key=broker_public, secret_key=broker_secret, keys={client_public, client2_public})
    auth_curve = AuthCurve(public_key=client_public, secret_key=client_secret, broker_key=broker_public)

    port, xpub, xsub = broker.run(curve=curve)
    client = Client(port=port, curve=auth_curve)
    assert client.services(timeout=TIMEOUT) == []
    client.disconnect()
    broker.stop()

    assert caplog.record_tuples == [
        ("msl.network", logging.INFO, "Using CURVE authentication with 2 keys allowed [domain:*]"),
        ("msl.network", logging.INFO, f"Broker running on 0.0.0.0:{port}"),
        ("msl.network", logging.INFO, broker.proxy_init_message(port, xpub, xsub)),
    ]


def test_monitor_tcp_socket(broker: Broker, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    port, xpub, xsub = broker.run(monitor=True)

    with socket.socket() as s:
        s.connect(("127.0.0.1", port))

    broker.stop()

    records = caplog.records
    assert len(records) == 5
    assert records[0].levelname == "INFO"
    assert records[0].message == f"Broker running on 0.0.0.0:{port}"
    assert records[1].levelname == "INFO"
    assert records[1].message == broker.proxy_init_message(port, xpub, xsub)
    assert records[2].levelname == "INFO"
    assert records[2].message.startswith("Monitor <Event.ACCEPTED: 32>")
    assert records[3].levelname == "INFO"
    assert records[3].message.startswith("Monitor <Event.HANDSHAKE_FAILED_NO_DETAIL: 2048>")
    assert records[4].levelname == "INFO"
    assert records[4].message.startswith("Monitor <Event.DISCONNECTED: 512>")


def test_bad_client_request(broker: Broker, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    port, xpub, xsub = broker.run()

    ctx = zmq.Context()
    socket = ctx.socket(zmq.REQ)  # use REQ instead of DEALER
    socket.setsockopt(zmq.ROUTING_ID, b"Client[123]")
    _ = socket.connect(f"tcp://127.0.0.1:{port}")
    socket.send(b"invalid")
    time.sleep(0.05)
    socket.close(linger=0)
    ctx.destroy(linger=0)

    broker.stop()

    assert caplog.record_tuples == [
        ("msl.network", logging.INFO, f"Broker running on 0.0.0.0:{port}"),
        ("msl.network", logging.INFO, broker.proxy_init_message(port, xpub, xsub)),
        ("msl.network", logging.ERROR, "Bad client request b'invalid'"),
    ]


def test_no_destination_id(broker: Broker, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    port, xpub, xsub = broker.run()

    ctx = zmq.Context()
    socket = ctx.socket(zmq.REQ)  # use REQ instead of DEALER
    _ = socket.connect(f"tcp://127.0.0.1:{port}")
    socket.send(b"hi")
    time.sleep(0.05)
    socket.close()
    ctx.destroy()

    broker.stop()

    records = caplog.records
    assert len(records) == 9
    assert records[0].levelname == "DEBUG"
    assert records[0].message == f"{broker.interrupter_name} created"
    assert records[1].levelname == "INFO"
    assert records[1].message == f"Broker running on 0.0.0.0:{port}"
    assert records[2].levelname == "INFO"
    assert records[2].message == broker.proxy_init_message(port, xpub, xsub)
    assert records[3].levelname == "DEBUG"
    assert records[3].message.endswith("' -> b''")  # Ignore default source_id since it is platform dependant
    assert records[4].levelname == "DEBUG"
    assert records[4].message == "Undefined destination ID, ignoring message b'hi'"
    assert records[5].levelname == "DEBUG"
    assert records[5].message == f"{broker.interrupter_name} triggered"
    assert records[6].levelname == "DEBUG"
    assert records[6].message == "XPUB/XSUB terminated"
    assert records[7].levelname == "DEBUG"
    assert records[7].message == f"{broker.interrupter_name} terminated"
    assert records[8].levelname == "DEBUG"
    assert records[8].message == "Broker terminated"


def test_broker_port_in_use(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("DEBUG")

    port = 18750

    s = socket.socket()
    s.bind(("0.0.0.0", port))  # noqa: S104

    main("start", "--verbose", "--port", str(port))

    s.close()

    r = caplog.records
    assert len(r) == 4
    assert r[0].levelname == "DEBUG"
    assert r[0].message.startswith("Interrupter")
    assert r[0].message.endswith("created")
    assert r[1].levelname == "ERROR"
    assert r[1].message.endswith(f"in use (addr='tcp://*:{port}')")
    assert r[2].levelname == "DEBUG"
    assert r[2].message.startswith("Interrupter")
    assert r[2].message.endswith("terminated")
    assert r[3].levelname == "DEBUG"
    assert r[3].message == "Broker terminated"


def test_xpub_port_in_use(broker: Broker, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    mocked_broker_port = 9371

    s = socket.socket()
    s.bind(("127.0.0.1", mocked_broker_port + 1))

    xpub, xsub = broker.run_proxy(mocked_broker_port)
    broker.kill_proxy()

    assert xpub != mocked_broker_port + 1
    assert xsub == mocked_broker_port + 2
    assert caplog.record_tuples == [
        ("msl.network", logging.INFO, f"XPUB/XSUB bound to ports {xpub}/{xsub} [ATTENTION! using non-default ports]"),
        ("msl.network", logging.DEBUG, "XPUB/XSUB terminated"),
    ]

    s.close()


def test_xsub_port_in_use(broker: Broker, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    mocked_broker_port = 47482

    s = socket.socket()
    s.bind(("127.0.0.1", mocked_broker_port + 2))

    xpub, xsub = broker.run_proxy(mocked_broker_port)
    broker.kill_proxy()

    assert xpub == mocked_broker_port + 1
    assert xsub != mocked_broker_port + 2
    assert caplog.record_tuples == [
        ("msl.network", logging.INFO, f"XPUB/XSUB bound to ports {xpub}/{xsub} [ATTENTION! using non-default ports]"),
        ("msl.network", logging.DEBUG, "XPUB/XSUB terminated"),
    ]

    s.close()
