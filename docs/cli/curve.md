# msl-network curve

Create [CURVE](https://rfc.zeromq.org/spec/26/) certificates.

## Usage

```console
msl-network curve [-d DIR] [-n NAME] [-h] [-q] [-v]
```

## Options

### -d, --dir DIR {: #curve-dir .cli-header }
The directory to save the certificate files to.

The default directory is `~/.msl/network`, which may also be set by an `MSL_NETWORK_HOME` environment variable.

### -n, --name NAME {: #curve-name .cli-header }
The name (without the extension) to use for the files. Default is the computer's hostname.

### -h, --help {: #curve-help .cli-header }
Show the help message and exit.

### -q, --quiet {: #curve-quiet .cli-header }
Give less output. Option is additive and can be used up to 3 times.

For example,

* `-q` &mdash; Silence INFO (and below) logging level
* `-qq` &mdash; Silence WARNING (and below) logging level
* `-qqq` &mdash; Silence ERROR (and below) logging level

### -v, --verbose {: #curve-verbose .cli-header }
Give more output (DEBUG logging level).
