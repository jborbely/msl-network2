from __future__ import annotations

import asyncio
from threading import Thread
from time import sleep
from typing import TYPE_CHECKING

from msl.network import Client, Worker

if TYPE_CHECKING:
    from conftest import Broker


def test_publish(broker: Broker) -> None:
    port, xpub, xsub = broker.run()

    class Heartbeat(Worker):
        def __init__(self) -> None:
            super().__init__(port=port, xsub_port=xsub)
            self.counter: int = 0

        async def pulse(self) -> None:
            _ = await self.connected.wait()
            while self.connected.is_set():
                self.counter += 1
                self.publish(self.counter)
                await asyncio.sleep(0.05)

    c = Client(port=port, xpub_port=xpub)

    pulses: list[int] = []

    def append_pulse(value: int) -> None:
        pulses.append(value)

    link = c.link("Heartbeat")
    link.subscribe(append_pulse)

    h = Heartbeat()
    h.add_tasks(h.pulse())
    thread = Thread(target=h.connect, daemon=True)
    thread.start()

    sleep(0.5)
    link.unsubscribe()
    sleep(0.5)

    assert c.services() == ["Heartbeat"]
    assert link.counter() > 5

    c.disconnect()
    h.disconnect()
    broker.stop()
    thread.join()

    assert len(pulses) > 5


def test_publish_threadsafe(broker: Broker) -> None:
    port, xpub, xsub = broker.run()

    class Heartbeat(Worker):
        def __init__(self) -> None:
            super().__init__(port=port, xsub_port=xsub)
            self.counter: int = 0
            self.run: bool = True

        def pulse(self) -> None:
            while self.run:
                self.counter += 1
                self.publish(self.counter)
                sleep(0.05)

    c = Client(port=port, xpub_port=xpub)

    pulses: list[int] = []

    def append_pulse(value: int) -> None:
        pulses.append(value)

    link = c.link("Heartbeat")
    link.subscribe(append_pulse)

    h = Heartbeat()
    thread1 = Thread(target=h.connect, daemon=True)
    thread1.start()

    while not h.connected.is_set():
        sleep(0.01)

    thread2 = Thread(target=h.pulse, daemon=True)
    thread2.start()

    sleep(1)

    assert c.services() == ["Heartbeat"]
    assert link.counter() > 5

    broker.stop()

    h.run = False
    c.disconnect()
    h.disconnect()
    thread2.join()
    thread1.join()

    assert len(pulses) > 5
