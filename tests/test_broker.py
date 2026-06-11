# cSpell: ignore creationflags capfd
from __future__ import annotations

import signal
import subprocess
import sys
import threading
import time

import pytest

from msl.network import Client, Worker
from msl.network.broker import Broker
from msl.network.utils import run_event_loop


def test_session() -> None:
    broker = Broker()
    broker_thread = threading.Thread(target=run_event_loop, daemon=True, args=(broker.run(),))
    broker_thread.start()

    port = int(broker.address.rsplit(":", 1)[1])

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

    future_issue = link.divide(1, 0, sync=False)  # Balancer calls service1
    with pytest.raises(RuntimeError, match=r"ZeroDivisionError"):
        _ = future_issue.result()

    assert link.num_requests() == 1  # Balancer calls service2
    assert link.num_requests() == 2  # Balancer calls service1

    t0 = time.perf_counter()
    assert link.sleep(0.1) is None
    assert link.sleep(0.1) is None
    assert time.perf_counter() - t0 > 0.19

    t0 = time.perf_counter()
    future1 = link.sleep(0.1, sync=False)
    future2 = link.sleep(0.1, sync=False)
    assert future1.result() is None
    assert future2.result() is None
    assert time.perf_counter() - t0 < 0.11

    interrupter1 = service1._interrupter  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
    interrupter2 = service2._interrupter  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
    assert interrupter1 is not None
    assert interrupter2 is not None
    interrupter1()
    interrupter2()
    service1_thread.join()
    service2_thread.join()

    with pytest.raises(RuntimeError, match=r"Service 'Foo' is not available"):
        _ = link.add(1, 2)

    client.disconnect()

    broker.interrupter()
    broker_thread.join()


def test_main(capfd: pytest.CaptureFixture[str]) -> None:
    command = ["msl-network"]

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
        assert "Broker running on 0.0.0.0:1875" in lines[1]
    else:
        assert len(lines) == 5
        assert "Interrupter" in lines[0]
        assert "created" in lines[0]
        assert "Broker running on 0.0.0.0:1875" in lines[1]
        assert lines[2] == "Broker shut down"
        assert "Interrupter" in lines[3]
        assert "destroyed" in lines[3]
        assert lines[4] == "Broker event loop closed"
