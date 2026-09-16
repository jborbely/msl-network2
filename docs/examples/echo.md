# Echo

Example of an echo Service.

The echo Service returns the arguments and keyword arguments that were sent from a Client.

## Start the `Broker` {: #echo-broker }
Start the Broker by running the following command.

```console
msl-network start
```

## Start the `Echo` Service  {: #echo-service }
Open another terminal and start the service by running the following command.

```console
python -c "from msl.examples.network import Echo; Echo().connect()"
```

The source code is:
<!-- fmt: off -->
```python
--8<-- "src/msl/examples/network/echo.py"
```
<!-- fmt: on -->

## Run the `Client` {: #echo-client }
Connect to the Broker as a Client, link with the Echo service and then send requests.

```python
from msl.network import Client

with Client() as client:
    link = client.link("Echo")
    print(link.echo(1, "hi", x=9.1))

    # You can also request what functions are available from the linked Service
    print(link.signatures())
```
