# Service

To implement your own Service, just inherit from the [Service][msl.network.service.Service] class, create the methods/attributes that you want your Service to provide and then run your script.

!!! warning
    Your subclass cannot have method/attribute names that are the same as those found in the [Link][] class, otherwise a request will not be sent to your Service.

```python
import asyncio
from msl.network import Service


class Camera(Service):
    def __init__(self) -> None:
        """A Service that allows for a camera to be controllable via the network."""
        super().__init__()
        self._camera = ...  # (1)!
        self.version: str = "1.3"  # (2)!

    def get_resolution(self) -> tuple[int, int]:
        """Get the image resolution."""
        return self._camera.resolution

    def set_resolution(self, width: int, height: int) -> None:
        """Set the image resolution."""
        self._camera.resolution = (width, height)

    async def stream(self) -> None:
        """This coroutine is also run in the event loop."""
        while True:
            self.publish(self._camera.capture())
            await asyncio.sleep(1)


if __name__ == "__main__":
    c = Camera()
    c.add_tasks(c.stream())  # (3)!
    c.connect()  # (4)!
```

1. Access the camera interface.
2. A [Client][] can also send a request for an attribute value, not just callable methods.
3. Add the `stream` method to the event loop of the [Service][msl.network.service.Service] to publish images every second.
4. Connect to the [Broker][]. Runs the event loop *forever*.

::: msl.network.service.Service
