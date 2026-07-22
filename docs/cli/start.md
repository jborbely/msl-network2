# msl-network start

Start the [Broker][] as a message proxy.

## Usage

```console
msl-network start [--auth-curve [KEYS_DIR]] [--auth-curve-allow-any] [--auth-domain DOMAIN] [--auth-device [DEVICE ...]] [--auth-plain [JSON_FILE]] [-H HOST] [-p PORT] [-m] [-h] [-q] [-v]
```

## Options

### --auth-curve [KEYS_DIR] {: #start-auth-curve .cli-header }
Use authentication based on public and private [CURVE] keys.

Specifying a value after this flag will use the specified directory to load the key files.
```console
msl-network start --auth-curve path/to/curve/keys
```

Specifying this flag without a value will use all keys that are located in the directories `~/.curve` and `~/.msl/network/curves` (the `~/.msl/network` part may also be set by an `MSL_NETWORK_HOME` environment variable).
```console
msl-network start --auth-curve
```

See [msl-network curve][] for more details.

### --auth-curve-allow-any {: #start-auth-curve-allow-any .cli-header }
Allow [CURVE] keys from any device. Enabled by default if no public key files are found.

### --auth-domain DOMAIN {: #start-auth-domain .cli-header }
The domain to use for [PLAIN] or [CURVE] authentication. Default is `*`.

### --auth-device [DEVICE ...] {: #start-auth-device .cli-header }
Use authentication based on the IP address (or hostname) of devices that are allowed to connect.

Specifying this flag without additional values will use the devices stored in the default file. See [msl-network device][] for more details.
```console
msl-network start --auth-device
```

Specifying this flag with one or more values will use the specified devices and ignore the list of devices stored in the default file.
```console
msl-network start --auth-device 10.9.102.80 msl-lab-computer
```

### --auth-plain [JSON_FILE] {: #start-auth-plain .cli-header }
Use authentication based on usernames and passwords.

Specifying a value after this flag will load that JSON file for the username to password mapping for the authentication parameters.
```console
msl-network start --auth-plain path/to/credentials.json
```

Specifying this flag without a value will use the parameters in the default file. The default file is in the `~/.msl/network` directory, which may also be set by an `MSL_NETWORK_HOME` environment variable. See [msl-network plain][] for more details.
```console
msl-network start --auth-plain
```

### -H, --host HOST {: #start-host .cli-header }
The network interface to run the [Broker][] on. If unspecified, listen on all network interfaces.

### -p, --port PORT {: #start-port .cli-header }
The port number to use for the [Broker][]. Default is 1875.

### -m, --monitor {: #start-monitor .cli-header }
Whether to allow [ZeroMQ event monitoring] (as INFO log messages).

### -h, --help {: #start-help .cli-header }
Show the help message and exit.

### -q, --quiet {: #start-quiet .cli-header }
Give less output. Option is additive and can be used up to 3 times.

For example,

* `-q` &mdash; Silence INFO (and below) logging level
* `-qq` &mdash; Silence WARNING (and below) logging level
* `-qqq` &mdash; Silence ERROR (and below) logging level

### -v, --verbose {: #start-verbose .cli-header }
Give more output (DEBUG logging level).


[CURVE]: https://rfc.zeromq.org/spec/26/
[PLAIN]: https://rfc.zeromq.org/spec/24/
[ZeroMQ event monitoring]: http://api.zeromq.org/4-2:zmq-socket-monitor
