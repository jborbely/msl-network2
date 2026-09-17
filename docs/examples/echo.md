# Echo
Example of an Echo [Service][].

The Echo [Service][] returns the arguments and keyword arguments that were sent from a [Client][].

## Start the `Broker` {: #echo-broker }
Start the [Broker][] by running the following command.

```console
msl-network start
```

## Start the `Echo` Service  {: #echo-service }
Open another terminal and start the Echo [Service][] by running the following command.

```console
python -c "from msl.examples.network import run_echo; run_echo()"
```

The source code of the Echo [Service][] is:
<!-- fmt: off -->
```python
--8<-- "src/msl/examples/network/echo.py"
```
<!-- fmt: on -->

## Run the `Client` {: #echo-client }
Connect to the [Broker][] as a [Client][], [link][msl.network.client.Client.link] with the Echo [Service][] and send requests.

```python
from msl.network import Client

with Client() as client:
    link = client.link("Echo")
    print(link.echo())
    print(link.echo(1, "hi", x=9.1))
```
