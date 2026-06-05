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

if TYPE_CHECKING:
    from typing import Any, Callable


class Request(NamedTuple):
    """A request."""

    id: int
    """The message ID.

    Used by a client to keep track of which response corresponds to which
    request when sending asynchronous requests to multiple workers.
    """

    worker: str
    """The name of the worker to send the request to."""

    attribute: str
    """The name of the attribute (method) on the worker to call."""

    args: tuple[Any, ...]
    """The arguments that the worker's method requires."""

    kwargs: dict[str, Any]
    """The keyword arguments that the worker's method requires."""

    def to_bytes(self, flag: Flag) -> bytes:
        """Convert the request to bytes."""
        return flag.to_bytes(2, "little") + compress[flag & Flag.COMPRESS](serialize[flag & Flag.SERIALIZE](self))

    @classmethod
    def from_bytes(cls, data: bytes) -> Request:
        """Create a request from bytes."""
        (flag,) = unpack("<H", data[:2])
        data = decompress[flag & Flag.DECOMPRESS](data[2:])
        return Request(*deserialize[flag & Flag.DESERIALIZE](data))


class Response(NamedTuple):
    """A response."""

    id: int
    """The message ID from the client (return unaltered)."""

    ok: bool
    """Whether the result of a worker processing the request was successful.

    If `False`, the `result` is the exception traceback (as [bytes][]) otherwise the result.
    """

    result: Any
    """The result of the request."""

    def to_bytes(self, flag: Flag) -> bytes:
        """Convert the response to bytes."""
        return pack("<Q?H", self.id, self.ok, flag) + compress[flag & Flag.COMPRESS](
            serialize[flag & Flag.SERIALIZE](self.result)
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> Response:
        """Create a response from bytes."""
        _id, ok, flag = unpack("<Q?H", data[:11])
        data = decompress[flag & Flag.DECOMPRESS](data[11:])
        return Response(id=_id, ok=ok, result=deserialize[flag & Flag.DESERIALIZE](data))


class Flag(IntFlag):
    """Message flags for compression and serialization."""

    NONE = 0

    # Compression and decompression
    BZ2 = 1 << 0
    LZMA = 1 << 1
    ZLIB = 1 << 2
    ZSTD = 1 << 3
    COMPRESS = BZ2 | LZMA | ZLIB | ZSTD
    DECOMPRESS = COMPRESS

    # Serialize and deserialize (reserve space for a few more compression options)
    PICKLE = 1 << 8
    JSON = 1 << 9
    SERIALIZE = PICKLE | JSON
    DESERIALIZE = SERIALIZE


def _memoryview_to_bytes(obj: Any) -> bytes:
    return memoryview(obj).tobytes()


def _pickle_dumps(obj: Any) -> bytes:
    return pickle.dumps(obj, protocol=5)


def _json_dumps(obj: Any) -> bytes:
    return json.dumps(obj, separators=(",", ":")).encode()


def _noop(obj: bytes) -> bytes:
    return obj


def _pickle_loads(obj: bytes) -> Any:
    return pickle.loads(obj)  # noqa: S301


def _json_loads(obj: bytes) -> Any:
    return json.loads(obj)


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
}

deserialize: dict[Flag, Callable[[bytes], Any]] = {
    Flag.NONE: _noop,
    Flag.PICKLE: _pickle_loads,
    Flag.JSON: _json_loads,
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
