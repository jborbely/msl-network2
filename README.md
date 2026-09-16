# MSL-Network

[![CI Status](https://github.com/MSLNZ/msl-network/actions/workflows/ci.yml/badge.svg)](https://github.com/MSLNZ/msl-network/actions/workflows/ci.yml)
[![Docs Status](https://github.com/MSLNZ/msl-network/actions/workflows/docs.yml/badge.svg)](https://github.com/MSLNZ/msl-network/actions/workflows/docs.yml)
[![PyPI - Version](https://img.shields.io/pypi/v/msl-network?logo=pypi&logoColor=gold&label=PyPI&color=blue)](https://pypi.org/project/msl-network/)
[![PyPI - Python Versions](https://img.shields.io/pypi/pyversions/msl-network.svg?logo=python&label=Python&logoColor=gold)](https://pypi.org/project/msl-network/)

MSL-Network uses concurrency and asynchronous programming to transfer data across a network and it is composed of three objects &mdash; a [Broker], [Client]s and [Service]s.

The [Broker] allows for multiple [Client]s and [Service]s to connect to it and it links a [Client]'s request to the appropriate [Service] to execute the request and then the [Broker] sends the reply from the [Service] back to the [Client]. A [Broker] also distributes messages that are published by a [Service] to all [Client]s that have subscribed.

The [Broker] uses concurrency to handle requests from multiple [Client]s such that multiple requests start, run and complete in overlapping time periods and in no specific order. A [Client] can send requests synchronously or asynchronously to the Network [Broker] for a [Service] to execute. See [Concurrency and Asynchronous Programming] for more details.

## Install

`msl-network` is available for installation via the [Python Package Index](https://pypi.org/project/msl-network/)

```console
pip install msl-network
```

### Dependencies

* Python 3.8+
* PyZMQ

## Documentation

The documentation for `msl-network` can be found [here](https://mslnz.github.io/msl-network/latest/).

[Broker]:
[Client]:
[Service]:
[Concurrency and Asynchronous Programming]:
[PyZMQ]: https://pyzmq.readthedocs.io/en/latest/
