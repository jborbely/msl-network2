# msl-network plain

Edit usernames and passwords for [PLAIN](https://rfc.zeromq.org/spec/24/) authentication.

The file structure is a JSON-object mapping between a username and a password.
```json
{
    "username1": "password1",
    "username2": "password2"
}
```

!!! warning
    The credentials are saved in plain text in the file that is created. You should set the file permissions provided by your operating system to ensure that your credentials are safe.

## Usage

```console
msl-network plain {add,remove,reset,list} [-u USERNAME] [-p PASSWORD] [-f FILE] [-h] [-q] [-v]
```

## Arguments

### add {: #plain-add .cli-header }
Add a user.

```console
msl-network plain add -u name -p password
```

### remove {: #plain-remove .cli-header }
Remove a user.

```console
msl-network plain remove -u name
```

### reset {: #plain-reset .cli-header }
Reset to either no users or a single user.

Clears all users if a username and password is not specified.
```console
msl-network plain reset
```

Otherwise, you can reset to only the specified username and password.
```console
msl-network plain reset -u name -p password
```

### list {: #plain-list .cli-header }
List the authorised users.
```console
msl-network plain list
```

## Options

### -u, --username USERNAME {: #plain-username .cli-header }
The username to action.

### -p, --password PASSWORD {: #plain-password .cli-header }
The password.

### -f, --file FILE {: #plain-file .cli-header }
The JSON file to use. If not specified, use the default file.

The default directory to save the JSON file is in `~/.msl/network`, which may also be set by an `MSL_NETWORK_HOME` environment variable.

### -h, --help {: #plain-help .cli-header }
Show the help message and exit.

### -q, --quiet {: #plain-quiet .cli-header }
Give less output. Option is additive and can be used up to 3 times.

For example,

* `-q` &mdash; Silence INFO (and below) logging level
* `-qq` &mdash; Silence WARNING (and below) logging level
* `-qqq` &mdash; Silence ERROR (and below) logging level

### -v, --verbose {: #plain-verbose .cli-header }
Give more output (DEBUG logging level).
