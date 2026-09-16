# Heartbeat

Example Service that publishes data to all subscribed Clients.

This example also shows how to add a task to the event loop of the Service.

## Start the `Broker` {: #heartbeat-broker }
Start the Broker by running the following command.

```console
msl-network start
```

## Start the `Heartbeat` Service  {: #heartbeat-service }
Open another terminal and start the service by running the following command.

```console
python -c "from msl.examples.network import Heartbeat; h = Heartbeat(); h.add_tasks(h.emit()); h.connect()"
```

The source code is:
<!-- fmt: off -->
```python
--8<-- "src/msl/examples/network/heartbeat.py"
```
<!-- fmt: on -->

## Run the `Client` {: #heartbeat-client }
Connect to the Broker as a Client, link with the Heartbeat service, subscribe to publications from the service and also send requests to the service.

```python
from msl.network import Client


def heartbeat_handler(counter: int) -> None:
    # Handles published data from the Heartbeat service
    print(f"Heartbeat {counter=} (Press ENTER to perform the next task)")


with Client() as client:
    link = client.link("Heartbeat")

    # You can also request what functions are available from the linked Service
    print(link.signatures())

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
