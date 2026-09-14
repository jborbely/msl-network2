# Overview

## Broker

## Security
There are five ways in which you can control the security of a device connecting to a [Broker][]. Since security is handle by ZeroMQ sockets, we use the same [mnemonic names](http://hintjens.com/blog:49) commonly used by the ZeroMQ community to illustrate the different ways you can use security in your application. You may also want to read [background information](https://rfc.zeromq.org/spec/27/) about the ZeroMQ Authentication Protocol.

| | Restrict IP addresses | Username/Password Authentication | CURVE Encryption | [Broker][] Verified | [Client][]/[Worker][] Verified |
| -------------- | :------: | :------: | :------: | :------: | :------: |
| [Grasslands][] | &#x274C; | &#x274C; | &#x274C; | &#x274C; | &#x274C; |
| [Strawhouse][] | &#x2705; | &#x274C; | &#x274C; | &#x274C; | &#x274C; |
| [Woodhouse][]  | &#x2705; | &#x2705; | &#x274C; | &#x274C; | &#x274C; |
| [Stonehouse][] | &#x2705; | &#x274C; | &#x2705; | &#x2705; | &#x274C; |
| [Ironhouse][]  | &#x2705; | &#x274C; | &#x2705; | &#x2705; | &#x2705; |

### Grasslands
No encryption. No security. This is the default mechanism.

Start a [Broker][] using,
```console
msl-network start
```

and use the default parameters for `curve` and `plain` when creating an instance of a [Client][]/[Worker][].

```python
from msl.network import Client

client = Client()
```

### Strawhouse
No encryption. The [Broker][] allows connections from only specific devices, based on the hostname or IP address of the device. This security layer is known as the [NULL](https://rfc.zeromq.org/spec/27/#the-null-mechanism) mechanism.

On the computer that you want to run the [Broker][] on, you can save the devices that are allowed to connect to the [Broker][] in a file,
```console
msl-network device add 192.168.1.10 lab-computer
```

and start a [Broker][] by reading the devices from the file.
```console
msl-network start --auth-device
```

Alternatively, you can specify the devices directly when starting the [Broker][] (which will not read the devices from the file).
```console
msl-network start --auth-device 192.168.1.32
```

Use the default parameters for `curve` and `plain` when creating an instance of a [Client][]/[Worker][].

```python
from msl.network import Client

client = Client()
```

Run `msl-network device --help` for more details about managing authorised devices.

### Woodhouse
No encryption. The [Broker][] requires a username and password for a device to connect. In addition, a [Broker][] may also allow connections from only specific devices (see [Strawhouse][]). This security layer is known as the [PLAIN](https://rfc.zeromq.org/spec/27/#the-plain-mechanism) mechanism.

!!! warning
    A username and password is sent in *plain* text through the network. Use this security mechanism only on trusted networks.

Save the usernames and passwords of authorised users to a file,
```console
msl-network plain add --username me --password secret
msl-network plain add --username you --password danger
```

and start a [Broker][] by reading the usernames and passwords from a file.
```console
msl-network start --auth-plain
```

Specify the `plain` parameter when creating an instance of a [Client][]/[Worker][].

```python
from msl.network import AuthPlain, Client

# Either specify the values directly in your code
auth = AuthPlain(username="me", password="secret")

# or you can load the values from a file
auth = AuthPlain.load("~/auth.txt")

client = Client(plain=auth)
```

Run `msl-network plain --help` for more details about managing usernames and passwords.

### Stonehouse
Messages are encrypted with [elliptic-curve](https://rfc.zeromq.org/spec/26/) cryptography. A [Client][]/[Worker][] verifies the public certificate of a [Broker][] (one-way verification). In addition, a [Broker][] may also allow connections from only specific devices (see [Strawhouse][]). This security layer is known as the [CURVE](https://rfc.zeromq.org/spec/27/#the-curve-mechanism) mechanism.

Create CURVE certificates on the computer running the [Broker][],
```console
msl-network curve
```

and start a [Broker][] by reading the certificates.
```console
msl-network start --auth-curve
```

Copy the [Broker][]'s public certificate to a computer connecting as a [Client][]/[Worker][] and specify the `curve` parameter when creating an instance of a [Client][]/[Worker][].

```python
from msl.network import AuthCurve, Client

# Load the public CURVE certificate of the Broker
auth = AuthCurve.load("~/.curve/broker.key")

client = Client(curve=auth)
```

Run `msl-network curve --help` for more details about creating CURVE certificates.

### Ironhouse
Messages are encrypted with [elliptic-curve](https://rfc.zeromq.org/spec/26/) cryptography. The [Broker][] verifies the public certificate of a [Client][]/[Worker][] and a [Client][]/[Worker][] verifies the public certificate of the [Broker][] (two-way verification). In addition, a [Broker][] may also allow connections from only specific devices (see [Strawhouse][]). This security layer is known as the [CURVE](https://rfc.zeromq.org/spec/27/#the-curve-mechanism) mechanism.

Create CURVE certificates on the computer running the [Broker][] and also on the computer connecting as a [Client][]/[Worker][].
```console
msl-network curve
```

Copy a [Client][]/[Worker][]'s public certificate to the `$HOME/.curve` directory on the computer running the [Broker][] and start a [Broker][] by reading the certificates.
```console
msl-network start --auth-curve
```

Copy the [Broker][]'s public certificate to a computer connecting as a [Client][]/[Worker][] and specify the `curve` parameter when creating an instance of a [Client][]/[Worker][].

```python
from msl.network import AuthCurve, Client

# Load the public CURVE certificate of the Broker
auth = AuthCurve.load("~/.curve/broker.key")

client = Client(curve=auth)
```

Run `msl-network curve --help` for more details about creating CURVE certificates.
