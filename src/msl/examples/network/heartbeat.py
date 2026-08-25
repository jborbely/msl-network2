"""Example service that publishes data to all subscribed Clients.

This example also shows how to add a task to the event loop of the service.
"""

import asyncio

from msl.network import Worker


class Heartbeat(Worker):
    """A service that publishes a counter value."""

    def __init__(self) -> None:
        """A service that publishes a counter value."""
        super().__init__()
        self._sleep: float = 1.0
        self._counter: int = 0

    def reset(self) -> None:
        """Reset the heartbeat counter."""
        self._counter = 0

    def set_heart_rate(self, beats_per_second: int) -> None:
        """Change the rate that the value of the counter is published."""
        self._sleep = 1.0 / float(beats_per_second)

    async def emit(self) -> None:
        """This coroutine is also run in the event loop."""
        # Wait for the connection to the Broker to be established
        _ = await self.connected.wait()

        # Loop while connected to the Broker
        while self.connected.is_set():
            self.publish(self._counter)
            self._counter += 1
            await asyncio.sleep(self._sleep)


if __name__ == "__main__":
    heartbeat = Heartbeat()

    # Add a task to the event loop of the service
    heartbeat.add_tasks(heartbeat.emit())

    # Connect the service to the Broker
    heartbeat.connect()
