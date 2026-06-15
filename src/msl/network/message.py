"""Request and response message structures."""

from __future__ import annotations

import bz2
import json
import lzma
import pickle
import zlib
from enum import IntFlag
from struct import pack, unpack
from typing import TYPE_CHECKING, NamedTuple

try:
    from compression import zstd
except ModuleNotFoundError:
    has_zstd = False
else:
    has_zstd = True

try:
    import orjson
except ModuleNotFoundError:
    has_orjson = False
else:
    has_orjson = True

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import Any


class Request(NamedTuple):
    """A request."""

    id: int
    """The message ID.

    Used by a client to keep track of which response corresponds to which
    request when sending asynchronous requests to multiple Workers.
    """

    service: str
    """The name of the service to send the request to."""

    attribute: str
    """The name of the attribute (method) on the Worker to call."""

    args: Sequence[Any]
    """The arguments that the Worker's method requires."""

    kwargs: dict[str, Any]
    """The keyword arguments that the Worker's method requires."""

    def to_bytes(self, flag: Flag) -> bytes:
        """Convert the request to bytes.

        !!! note
            It does not make sense to use Flag.NONE for a request since serialisation must occur.
            Neither int, str, tuple, nor dict can be converted to a memoryview, which would then be converted to bytes.
        """
        return flag.to_bytes(2, "little") + compress[flag & COMPRESS](serialize[flag & SERIALIZE](tuple(self)))

    @classmethod
    def from_bytes(cls, data: bytes) -> Request:
        """Create a request from bytes."""
        (flag,) = unpack("<H", data[:2])
        data = decompress[flag & DECOMPRESS](data[2:])
        return Request(*deserialize[flag & DESERIALIZE](data))


class Response(NamedTuple):
    """A response."""

    id: int
    """The message ID from the client (return unaltered)."""

    ok: bool
    """Whether the result of a Worker processing the request was successful.

    If `False`, the `result` is the exception traceback (as bytes).
    """

    result: Any
    """The result of the request."""

    def to_bytes(self, flag: Flag) -> bytes:
        """Convert the response to bytes.

        Only the `result` is used during serialisation and compression. The packed
        size of (id, ok) is only 9 bytes anyway, and flag cannot be compressed
        (otherwise we would not know how to decompress the bytes).
        """
        return pack("<HQ?", flag, self.id, self.ok) + compress[flag & COMPRESS](
            serialize[flag & SERIALIZE](self.result)
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> Response:
        """Create a response from bytes."""
        flag, _id, ok = unpack("<HQ?", data[:11])
        data = decompress[flag & DECOMPRESS](data[11:])
        return Response(id=_id, ok=ok, result=deserialize[flag & DESERIALIZE](data))


class Flag(IntFlag):
    """Message flags for compression and serialisation.

    You may use a single flag or take a bitwise union of one (de)serialisation
    flag with one (de)compression flag, e.g.,

    * `Flag.JSON` &mdash; JSON (de)serialisation, no (de)compression
    * `Flag.ZLIB` &mdash; No (de)serialisation, ZLIB (de)compression
    * `Flag.PICKLE | Flag.ZSTD` &mdash; Pickle (de)serialisation, ZSTD (de)compression

    A [KeyError][] will be raised when you use a flag that is a union of more than
    one serialisation flag or more than one compression flag when a *request* or a
    *response* is sent.

    Attributes:
        NONE (int): Do not apply (de)serialisation nor (de)compression. This flag
            is only useful if a method of a [Worker][msl.network.worker.Worker]
            returns an object that supports the [buffer protocol][buffer-protocol].
            As such, this flag is only applicable for a *response* and cannot be
            used for a *request*.
        BZ2 (int): bz2 (de)compression using the [bz2][module-bz2] module.
        LZMA (int): lzma (de)compression using the [lzma][module-lzma] module.
        ZLIB (int): zlib (de)compression using the [zlib][module-zlib] module.
        ZSTD (int): zstd (de)compression using the [zstd][module-compression.zstd] module.
        PICKLE (int): (De)serialisation using the [pickle][] module.
        JSON (int): (De)serialisation using the builtin [json][] module.
        ORJSON (int): (De)serialisation using the [orjson][https://pypi.org/project/orjson/]
            package. Includes the option `OPT_SERIALIZE_NUMPY` when serialising.
    """

    NONE = 0

    # (De)Compression
    BZ2 = 1 << 0
    LZMA = 1 << 1
    ZLIB = 1 << 2
    ZSTD = 1 << 3

    # (De)Serialisation (reserve space for a few more compression options)
    PICKLE = 1 << 8
    JSON = 1 << 9
    ORJSON = 1 << 10


COMPRESS = Flag.BZ2 | Flag.LZMA | Flag.ZLIB | Flag.ZSTD
DECOMPRESS = COMPRESS
SERIALIZE = Flag.PICKLE | Flag.JSON | Flag.ORJSON
DESERIALIZE = SERIALIZE


def _default(obj: Any) -> Any:
    """Used as the callable function in json.dumps()."""
    try:
        return obj.to_json()
    except AttributeError:
        pass

    name = obj.__class__.__name__
    msg = (
        f"Object of type {name} is not JSON serializable. "
        f"You can implement a {name}.to_json() method that returns an object that is JSON serializable"
    )
    raise TypeError(msg)


def _memoryview_to_bytes(obj: Any) -> bytes:
    if isinstance(obj, bytes):
        return obj
    return memoryview(obj).tobytes()


def _pickle_dumps(obj: Any) -> bytes:
    return pickle.dumps(obj, protocol=5)


def _json_dumps(obj: Any) -> bytes:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False, default=_default).encode()


def _orjson_dumps(obj: Any) -> bytes:
    if has_orjson:
        return orjson.dumps(obj, option=orjson.OPT_SERIALIZE_NUMPY, default=_default)  # pyright: ignore[reportPossiblyUnboundVariable]

    msg = "The orjson package is not installed"
    raise ModuleNotFoundError(msg)


def _noop(obj: bytes) -> bytes:
    return obj


def _orjson_loads(obj: bytes) -> Any:
    if has_orjson:
        return orjson.loads(obj)  # pyright: ignore[reportPossiblyUnboundVariable]

    msg = "The orjson package is not installed"
    raise ModuleNotFoundError(msg)


def _zstd_compress(obj: bytes) -> bytes:
    if has_zstd:
        return zstd.compress(obj)  # pyright: ignore[reportPossiblyUnboundVariable]

    msg = "The zstd module is not available"
    raise ModuleNotFoundError(msg)


def _zstd_decompress(obj: bytes) -> bytes:
    if has_zstd:
        return zstd.decompress(obj)  # pyright: ignore[reportPossiblyUnboundVariable]

    msg = "The zstd module is not available"
    raise ModuleNotFoundError(msg)


serialize: dict[Flag, Callable[[Any], bytes]] = {
    Flag.NONE: _memoryview_to_bytes,
    Flag.PICKLE: _pickle_dumps,
    Flag.JSON: _json_dumps,
    Flag.ORJSON: _orjson_dumps,
}

deserialize: dict[Flag, Callable[[bytes], Any]] = {
    Flag.NONE: _noop,
    Flag.PICKLE: pickle.loads,
    Flag.JSON: json.loads,
    Flag.ORJSON: _orjson_loads,
}

compress: dict[Flag, Callable[[bytes], bytes]] = {
    Flag.NONE: _noop,
    Flag.BZ2: bz2.compress,
    Flag.LZMA: lzma.compress,
    Flag.ZLIB: zlib.compress,
    Flag.ZSTD: _zstd_compress,
}

decompress: dict[Flag, Callable[[bytes], bytes]] = {
    Flag.NONE: _noop,
    Flag.BZ2: bz2.decompress,
    Flag.LZMA: lzma.decompress,
    Flag.ZLIB: zlib.decompress,
    Flag.ZSTD: _zstd_decompress,
}
