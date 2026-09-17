# MSL-Network

[![CI Status](https://github.com/MSLNZ/msl-network/actions/workflows/ci.yml/badge.svg)](https://github.com/MSLNZ/msl-network/actions/workflows/ci.yml)
[![Docs Status](https://github.com/MSLNZ/msl-network/actions/workflows/docs.yml/badge.svg)](https://github.com/MSLNZ/msl-network/actions/workflows/docs.yml)
[![PyPI - Version](https://img.shields.io/pypi/v/msl-network?logo=pypi&logoColor=gold&label=PyPI&color=blue)](https://pypi.org/project/msl-network/)
[![PyPI - Python Versions](https://img.shields.io/pypi/pyversions/msl-network.svg?logo=python&label=Python&logoColor=gold)](https://pypi.org/project/msl-network/)

`msl-network` uses concurrency and asynchronous programming to transfer messages across a network and it is composed of a [Broker], [Client]s and [Service]s with a [Link] established between a [Client] and a [Service].

A [Broker] uses concurrency to handle requests from multiple [Client]s such that multiple requests run in overlapping time periods and a reply is returned in no specific order. The [Broker] also distributes messages that are published by a [Service] to all [Client]s that are subscribed.

A [Client] can send requests synchronously or asynchronously for a [Service] to execute.

## Install

`msl-network` is available for installation via the [Python Package Index](https://pypi.org/project/msl-network/)

```console
pip install msl-network
```

### Dependencies

* Python 3.8+
* [PyZMQ]

## Documentation

The documentation for `msl-network` can be found [here](https://mslnz.github.io/msl-network/latest/).

[Broker]: https://mslnz.github.io/msl-network/latest/#broker
[Client]: https://mslnz.github.io/msl-network/latest/api/client/
[Service]: https://mslnz.github.io/msl-network/latest/api/service/
[Link]: https://mslnz.github.io/msl-network/latest/api/link/
[PyZMQ]: https://pyzmq.readthedocs.io/en/latest/
