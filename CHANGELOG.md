# Release Notes

---

## unreleased

***Added:***

- support for Python 3.12, 3.13 and 3.14
- the [Service.request][msl.network.service.Service.request] property
- `loads_kwargs` and `dumps_kwargs` keyword arguments to [use][msl.network.json.use]

***Fixed:***

- the `to_json()` method was not reliably called for an object, which resulted in the object not being JSON serializable

***Removed:***

- support for Python 3.6 and 3.7

## 1.0.0 (2023-06-16)

***Added:***

- a [Link][msl.network.client.Link] can create an exclusive or shared lock with a [Service][msl.network.service.Service]
- add [service_max_clients][msl.network.client.Link.service_max_clients] property to a [Link][msl.network.client.Link] and [LinkedClient][msl.network.client.LinkedClient]
- the [loop_thread_id][msl.network.network.Device.loop_thread_id] property for a [Service][msl.network.service.Service] and a [Client][msl.network.client.Client]
- the [emit_notification_threadsafe][msl.network.service.Service.emit_notification_threadsafe] method for a [Service][msl.network.service.Service]
- ability to specify the `host` to use when starting a [Manager][msl.network.manager.Manager]
- support for Python 3.9, 3.10 and 3.11
- [set_logging_level][msl.network.network.Network.set_logging_level] to be able to set the logging level at runtime
- ability to add tasks to the event loop via the [add_tasks][msl.network.network.Device.add_tasks] method
- the [shutdown_handler][msl.network.network.Device.shutdown_handler] method is called after the connection to the [Manager][msl.network.manager.Manager] is lost but before the event loop stops
- ability to use all [Database][msl.network.database.Database] classes as a context manager (i.e., using the `with` statement)
- the `--log-level` flag to the `start` command
- the `delete` command-line argument to delete files that are created by msl-network
- [orjson](https://pypi.org/project/orjson/) as a JSON backend to [Package][msl.network.json.Package]
- `JSON`, `UJSON`, `RAPIDJSON` and `SIMPLEJSON` are aliases for the JSON backends in [Package][msl.network.json.Package]
- the `read_limit` keyword arguments to [connect][msl.network.client.connect] and [start][msl.network.service.Service.start]
- the `auto_save` keyword argument to [connect][msl.network.client.connect] and [get_ssl_context][msl.network.cryptography.get_ssl_context]
- the `digest_size` keyword argument to [generate_certificate][msl.network.cryptography.generate_certificate] and [get_fingerprint][msl.network.cryptography.get_fingerprint]
- the `name` and `extensions` keyword arguments to [generate_certificate][msl.network.cryptography.generate_certificate]
- `**kwargs` to [get_ssl_context][msl.network.cryptography.get_ssl_context]

***Changed:***

- the `result` object that is returned by a [Service][msl.network.service.Service] response can implement a callable `to_json()` method
- the value of the `algorithm` keyword argument in [get_fingerprint][msl.network.cryptography.get_fingerprint] can now also be of type [str][]
- renamed `uuid` to be `uid` in the JSON format
- making an asynchronous request now returns a [Future][concurrent.futures.Future] instance instead of an [Future][asyncio.Future] instance
- [Client][msl.network.client.Client] and [Service][msl.network.service.Service] are subclasses of [Device][msl.network.network.Device]
- move the `utils.localhost_aliases` function to be defined as [LOCALHOST_ALIASES][msl.network.constants.LOCALHOST_ALIASES]
- renamed the `Client.manager` method to [identities][msl.network.client.Client.identities]
- renamed `certfile` to `cert_file` in [connect][msl.network.client.connect], [start][msl.network.service.Service.start] and [get_ssl_context][msl.network.cryptography.get_ssl_context]
- can now change which JSON backend to use during runtime by calling the [use][msl.network.json.use] function
- moved the `msl.network.constants.JSONPackage` class to [Package][msl.network.json.Package]
- renamed the command line arguments `--certfile` to `--cert-file`, `--keyfile` to `--key-file`, `--keyfile-password` to `--key-file-password`, and `--logfile` to `--log-file` for the `start` command
- use `T` as the separator between the date and time in a [ConnectionsTable][msl.network.database.ConnectionsTable]
- rename the keyword arguments `timestamp1` to `start` and `timestamp2` to `end` in [connections][msl.network.database.ConnectionsTable.connections]
- the default filename for the certificate and key files now use `'localhost'` instead of the value of `HOSTNAME`

***Fixed:***

- an `AttributeError` could be raised when generating the identity of a [Service][msl.network.service.Service]
- can now handle multiple requests/replies contained within the same network packet

***Removed:***

- support for Python 3.5
- the `MSLNetworkError` exception class (a [RuntimeError][] is raised instead)
- the `Service.set_debug` method
- the `termination` and `encoding` class attributes of [Network][msl.network.network.Network]
- the `send_pending_requests`, `raise_latest_error` and `wait` methods of a [Client][msl.network.client.Client]
- the `--debug` flag from the `start` command
- the `utils.new_selector_event_loop` function
- the `constants.JSON` attribute
- [YAJL](https://pypi.org/project/yajl/) as a JSON backend option

## 0.5.0 (2020-03-18)

***Added:***

- support for Python 3.8
- the `utils.new_selector_event_loop` function to create a new `asyncio.SelectorEventLoop`
- the `--logfile` command line argument for the `start` command
- a `Service` can emit notifications to all `Clients` that are linked with it
- a `Service` now accepts an `ignore_attributes` keyword argument when it is instantiated and also has an `ignore_attributes` method
- a `Link` can unlink from a `Service`
- the `LinkedClient.client` property
- `1.0.0.127.in-addr.arpa` as a localhost alias

***Changed:***

- use `__package__` as the logger name
- the `FileHandler` and `StreamHandler` that are added to the root logger now use a decimal point instead of a comma between the seconds and milliseconds values
- renamed the `disconnect_service` method for a `Link` and a `Service` (which was added in version 0.4.0) to be `shutdown_service`

***Removed:***

- the `Service._shutdown` method since it is no longer necessary to call this method from the `Service` subclass because shutting down happens automatically behind the scenes

## 0.4.1 (2019-07-23)

***Added:***

- `1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa` as a localhost alias

***Changed:***

- calling the `Client.manager(as_string=True)` method now prints the attributes analogous to how a `Client` would call the method of a `Service`

***Fixed:***

- the `timeout` value for creating a `LinkedClient` is now the total time that it takes to connect to the Network `Manager` plus the time required to link with the `Service` (this fixes a race condition when starting a `Service` on a remote computer and then trying to link to the same `Service`)

## 0.4.0 (2019-04-16)

***Added:***

- the `ssh` module
- a `LinkedClient` class
- the `run_forever` (to start the `Manager`) and the `run_services` (to start the `Manager` and then start the `Service`s) functions
- the `filter_service_start_kwargs`, `filter_run_forever_kwargs` and `filter_client_connect_kwargs` functions
- a `disconnect_service` method to `Link`
- shorter argument name options for some CLI parameters
- a `Service` now accepts `name` and `max_clients` as keyword arguments when it is instantiated

***Changed:***

- the following CLI changes to argument names for the `certgen` command

  + `--key-path` became `--keyfile`
  + `--key-password` became `--keyfile-password`

- the following CLI changes to argument names for the `keygen` command

  + `--path` became `--out`

- the following CLI changes to argument names for the `start` command

  + `--cert` became `--certfile`
  + `--key` became `--keyfile`
  + `--key-password` became `--keyfile-password`

- the `certificate` keyword argument for the `connect` and `get_ssl_context` functions and for the `Service.start` method was changed to `certfile`
- the `as_yaml` keyword argument for the `Client.manager` method was changed to `as_string`
- a `Client` can no longer request a private attribute -- i.e., an attribute that starts with a `_` (an underscore) -- from a `Service`
- the default `timeout` value for connecting to the `Manager` is now 10 seconds

***Fixed:***

- perform error handling if the `Manager` attempts to start on a port that is already in use
- issue [#7](https://github.com/MSLNZ/msl-network/issues/7) - a `Service` can now specify the maximum number of `Client`\s that can be linked with it
- issue [#6](https://github.com/MSLNZ/msl-network/issues/6) - the `password_manager` keyword argument is now used properly when starting a `Service`

***Removed:***

- the `name` class attribute for a `Service`
- the `send_request` method for a `Client` (must link with a `Service`)

## 0.3.0 (2019-01-06)

***Added:***

- every request from a `Client` can now specify a timeout value
- the docs now include an example for how to send requests to the `Echo` `Service`

***Changed:***

- the default `timeout` value for connecting to the `Manager` is now 10 seconds
- the `__repr__` method for a `Client` no longer includes the id as a hex number

***Fixed:***

- issue [#5](https://github.com/MSLNZ/msl-network/issues/5)
- issue [#4](https://github.com/MSLNZ/msl-network/issues/4)
- issue [#3](https://github.com/MSLNZ/msl-network/issues/3)
- issue [#2](https://github.com/MSLNZ/msl-network/issues/2)
- issue [#1](https://github.com/MSLNZ/msl-network/issues/1)

***Removed:***

- the `__repr__` method for a `Service`

## 0.2.0 (2018-08-24)

***Added:***

- a `wakeup()` Task in debug mode on Windows (see: https://bugs.python.org/issue23057)
- the `version_info` named tuple now includes a *releaselevel*
- example for creating a `Client` and a `Service` in LabVIEW
- the ability to establish a connection to the Network `Manager` without using TLS
- a `timeout` kwarg to `Service.start()`
- an `Echo` `Service` to the examples

***Changed:***

- rename 'async' kwarg to be 'asynchronous' (for Python 3.7 support)
- the termination bytes were changed from `\n` to `\r\n`

## 0.1.0 (2017-12-14)

Initial release
