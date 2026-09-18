# Client

A Client sends requests to a [Service][] and receives replies. It can also subscribe to messages that are published by the [Service][].

```python
from msl.network import Client


def captured(data: bytes) -> None:
    """Handle image data that is published by the Service."""
    ...


with Client(host="192.168.1.25") as client:  # (1)!
    print(client.services())  # (2)!

    camera = client.link("Camera")  # (3)!
    print(camera.signatures())  # (4)!

    camera.subscribe(captured)  # (5)!

    camera.set_resolution(width=1280, height=720)  # (6)!
    resolution = camera.get_resolution()  # (7)!

    # do more stuff...
```

1. Connect to a Broker. By using a context manager (i.e., a [with][] statement), the connection is automatically closed after you are done using it. Otherwise, call [disconnect][msl.network.client.Client.disconnect].
2. Get the names of the [Service][]s that are available to [link][msl.network.client.Client.link] with.
3. Establish a [Link][] with a [Service][]. *Tip: The [Service][] does not actually need to be running in order to establish a [Link][]. The [Service][] only needs to be running when a request is sent in order to get a reply.*
4. Request what functions are available from the linked [Service][]. This will return a mapping of the function name to the input/output parameters that the function requires/returns.
5. [Subscribe][msl.network.client.Link.subscribe] to captured images that are published by the [Service][].
6. Send a request. No reply expected, but the [Service][] still sends `None` as a reply.
7. Send a request. Wait for reply.

::: msl.network.client.Client
    options:
        show_attribute_values: false
