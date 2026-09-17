# Heartbeat
Example [Service][] that publishes data to all subscribed [Client][]s.

This example shows how to add a task to the [event loop][asyncio-event-loop] of the [Service][].

## Start the `Broker` {: #heartbeat-broker }
Start the [Broker][] by running the following command.

```console
msl-network start
```

## Start the `Heartbeat` Service  {: #heartbeat-service }
Open another terminal and start the Heartbeat [Service][] by running the following command.

```console
python -c "from msl.examples.network import run_heartbeat; run_heartbeat()"
```

The source code of the Heartbeat [Service][] is:
<!-- fmt: off -->
```python
--8<-- "src/msl/examples/network/heartbeat.py"
```
<!-- fmt: on -->

## Run the `Client` {: #heartbeat-client }
Connect to the [Broker][] as a [Client][], [link][msl.network.client.Client.link] with the Heartbeat [Service][], [subscribe][msl.network.client.Link.subscribe] to publications from the [Service][] and also send requests to the [Service][].

```python
from msl.network import Client


def heartbeat_handler(counter: int) -> None:
    """Handles published data from the Heartbeat Service."""
    print(f"Heartbeat {counter=} (Press ENTER to perform the next task)")


with Client() as client:
    link = client.link("Heartbeat")

    # Subscribe to publications with a function that will be called with the published data
    link.subscribe(heartbeat_handler)

    # Wait until ENTER is pressed to reset the counter
    _ = input()
    link.reset()

    # Wait until ENTER is pressed to change the rate that data is published
    _ = input()
    link.set_heart_rate(10)

    # Wait until ENTER is pressed to end the script
    _ = input()
```
