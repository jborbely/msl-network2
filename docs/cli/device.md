# msl-network device

Edit authorised devices (by hostname or IP address).

The default directory to save the file is in `~/.msl/network`, which may also be set by an `MSL_NETWORK_HOME` environment variable.

## Usage

```console
msl-network device {add,remove,reset,list} [devices ...] [-h] [-q] [-v]
```

## Arguments

### add {: #device-add .cli-header }
Add the specified device(s).

Add a single device.
```console
msl-network device add 10.9.102.17
```

Add multiple devices.
```console
msl-network device add 10.9.102.50 msl-lab
```

### remove {: #device-remove .cli-header }
Remove the specified device(s).

Remove a single device.
```console
msl-network device remove 10.9.102.17
```

Remove multiple devices.
```console
msl-network device remove 10.9.102.50 msl-lab
```

### reset {: #device-reset .cli-header }
Reset to the specified device(s).

If no devices are specified, resets to only `localhost`.
```console
msl-network device reset
```

Otherwise, you can reset to the specified devices.
```console
msl-network device reset localhost 10.9.102.17 msl-lab
```

### list {: #device-list .cli-header }
List the authorised devices.
```console
msl-network device list
```

## Options

### -h, --help {: #device-help .cli-header }
Show the help message and exit.

### -q, --quiet {: #device-quiet .cli-header }
Give less output. Option is additive and can be used up to 3 times.

For example,

* `-q` &mdash; Silence INFO (and below) logging level
* `-qq` &mdash; Silence WARNING (and below) logging level
* `-qqq` &mdash; Silence ERROR (and below) logging level

### -v, --verbose {: #device-verbose .cli-header }
Give more output (DEBUG logging level).
