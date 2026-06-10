from __future__ import annotations

import sys
from array import array
from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np
import pytest

from msl.network import Flag
from msl.network.message import Request, Response, compress, decompress, deserialize, serialize

if TYPE_CHECKING:
    from collections.abc import Iterator

BAD_FLAGS = [
    Flag.JSON | Flag.PICKLE,
    Flag.JSON | Flag.ORJSON,
    Flag.PICKLE | Flag.ORJSON,
    Flag.BZ2 | Flag.LZMA,
    Flag.BZ2 | Flag.ZLIB,
    Flag.BZ2 | Flag.ZSTD,
    Flag.LZMA | Flag.ZLIB,
    Flag.LZMA | Flag.ZSTD,
    Flag.ZLIB | Flag.ZSTD,
]


@pytest.fixture
def temporarily_force_zstd_missing() -> Iterator[None]:
    from msl.network import message  # noqa: PLC0415

    original = message.has_zstd
    message.has_zstd = False
    yield
    message.has_zstd = original


@pytest.fixture
def temporarily_force_orjson_missing() -> Iterator[None]:
    from msl.network import message  # noqa: PLC0415

    original = message.has_orjson
    message.has_orjson = False
    yield
    message.has_orjson = original


def test_request_raw() -> None:
    # It does not make sense to use Flag.NONE for a request since int, str, tuple, nor dict
    # can be converted to a memoryview, which is then be converted to bytes
    r = Request(
        id=1,
        service="foo",
        attribute="bar",
        args=(1, 2),
        kwargs={"a": 0},
    )
    with pytest.raises(TypeError, match=r"memoryview"):
        _ = r.to_bytes(Flag.NONE)


def test_request_json() -> None:
    r = Request(
        id=1,
        service="a",
        attribute="b",
        args=[1, 2.3, None, True, "foo"],
        kwargs={"a": 0, "b": True},
    )

    serialised = r.to_bytes(Flag.JSON)
    assert serialised == b"\x00\x02" + b'[1,"a","b",[1,2.3,null,true,"foo"],{"a":0,"b":true}]'
    assert r == Request.from_bytes(serialised)


def test_request_orjson() -> None:
    r = Request(
        id=1,
        service="a",
        attribute="b",
        args=(1, 2.3, None, True, "foo", datetime(2020, 10, 25)),  # noqa: DTZ001
        kwargs={"a": 0, "b": True, "nd": np.array([[1.1, 2.2], [3.3, 4.4]])},
    )

    serialised = r.to_bytes(Flag.ORJSON)
    assert serialised == (
        b'\x00\x04[1,"a","b",[1,2.3,null,true,"foo","2020-10-25T00:00:00"],{"a":0,"b":true,"nd":[[1.1,2.2],[3.3,4.4]]}]'
    )
    r2 = Request.from_bytes(serialised)
    assert r2.id == r.id
    assert r2.service == r.service
    assert r2.attribute == r.attribute
    assert r2.args == [1, 2.3, None, True, "foo", "2020-10-25T00:00:00"]
    assert r2.kwargs == {"a": 0, "b": True, "nd": [[1.1, 2.2], [3.3, 4.4]]}


def test_request_pickle() -> None:
    r = Request(
        id=1,
        service="broker",
        attribute="something",
        args=(1, 2.3, None, True, "foo", b"bar", [], {1, 2, 3}),
        kwargs={"a": array("b", b"A"), "b": np.arange(10_000, dtype=float).reshape(100, 100)},
    )

    serialised = r.to_bytes(Flag.PICKLE)
    assert serialised.startswith(b"\x00\x01" + b"\x80\x05")
    r2 = Request.from_bytes(serialised)

    assert r.id == r2.id
    assert r.service == r2.service
    assert r.attribute == r2.attribute
    assert r.args == r2.args
    assert r.kwargs["a"] == r2.kwargs["a"]
    assert np.array_equal(r.kwargs["b"], r2.kwargs["b"])


def test_response_raw() -> None:
    r = Response(id=1, ok=False, result=b"data")
    raw = r.to_bytes(Flag.NONE)
    assert raw == b"\x00\x00" + b"\x01\x00\x00\x00\x00\x00\x00\x00" + b"\x00" + b"data"
    assert r == Response.from_bytes(raw)


def test_response_raw_invalid() -> None:
    r = Response(id=1, ok=False, result="data")
    with pytest.raises(TypeError, match=r"memoryview"):
        _ = r.to_bytes(Flag.NONE)


def test_response_json() -> None:
    r = Response(id=9, ok=True, result=[1, 2.3, None, True, "foo", [-1, 0, 1]])
    serialised = r.to_bytes(Flag.JSON)
    assert serialised == (
        b"\x00\x02" + b"\x09\x00\x00\x00\x00\x00\x00\x00" + b"\x01" + b'[1,2.3,null,true,"foo",[-1,0,1]]'
    )
    assert r == Response.from_bytes(serialised)


def test_response_orjson() -> None:
    r = Response(id=9, ok=True, result=[1, 2.3, None, True, "foo", [-1, 0, 1]])
    serialised = r.to_bytes(Flag.ORJSON)
    assert serialised == (
        b"\x00\x04" + b"\x09\x00\x00\x00\x00\x00\x00\x00" + b"\x01" + b'[1,2.3,null,true,"foo",[-1,0,1]]'
    )
    assert r == Response.from_bytes(serialised)


def test_response_pickle() -> None:
    r = Response(id=2, ok=True, result=(1, 2.3, None, True, b"foo", {-1, 0, 1}))
    serialised = r.to_bytes(Flag.PICKLE)
    assert serialised == (
        b"\x00\x01"
        b"\x02\x00\x00\x00\x00\x00\x00\x00"
        b"\x01"
        b"\x80\x05\x95$\x00\x00\x00\x00\x00\x00\x00(K\x01G@\x02ffffffN\x88C\x03foo\x94\x8f\x94(K\x00K\x01J\xff\xff\xff\xff\x90t\x94."
    )
    assert r == Response.from_bytes(serialised)


def test_response_json_bz2() -> None:
    r = Response(id=1, ok=False, result="X" * 50)
    data = r.to_bytes(Flag.JSON | Flag.BZ2)
    assert data == (
        b"\x01\x02"
        b"\x01\x00\x00\x00\x00\x00\x00\x00"
        b"\x00"
        b"BZh91AY&SY\xa95\xcaR\x00\x00\x00\x92\x00\x10\x01\x00@ \x000\xcc\t4\xcb\xc1\x85\xdc\x91N\x14$*Mr\x94\x80"
    )
    assert r == Response.from_bytes(data)


def test_response_json_lzma() -> None:
    r = Response(id=10, ok=True, result="X" * 50)
    data = r.to_bytes(Flag.JSON | Flag.LZMA)
    assert data == (
        b"\x02\x02"
        b"\x0a\x00\x00\x00\x00\x00\x00\x00"
        b"\x01"
        b"\xfd7zXZ\x00\x00\x04\xe6\xd6\xb4F\x02\x00!\x01\x16\x00\x00\x00t/\xe5\xa3\xe0\x00"
        b"3\x00\t]\x00\x11\x163\x1f\x11\x00\x00\x00\x00\x00\x00\x00\x00\xea\x8c\xe2\xde\xdf"
        b'R\xff"\x00\x01%4y\x91\xc1\xe9\x1f\xb6\xf3}\x01\x00\x00\x00\x00\x04YZ'
    )
    assert r == Response.from_bytes(data)


def test_request_json_bz2() -> None:
    r = Request(id=4, service="a", attribute="b", args=[2], kwargs={"foo": "bar"})
    data = r.to_bytes(Flag.JSON | Flag.BZ2)
    assert data == (
        b"\x01\x02"
        b"BZh91AY&SY5\x98\tR\x00\x00\x08\x1b\x80\x10\x04\x14\x10\x00\n1\x00\x90\n \x001\x00\x00"
        b"\x08\x83\xd2yG\xa2\x15\xe1\x06\xab\xaa\x1b\x8d\x1d\xbb\x0f8wh|]\xc9\x14\xe1B@\xd6`%H"
    )
    assert r == Request.from_bytes(data)


def test_request_pickle_zlib() -> None:
    r = Request(id=4, service="a", attribute="b", args=(2,), kwargs={"foo": "bar"})
    data = r.to_bytes(Flag.PICKLE | Flag.ZLIB)

    # ZLIB compression output can very depending on the default settings of the zlib version
    # bundled with the Python version, so just check some of the beginning bytes
    assert data.startswith(b"\x04\x01" + b"x\x9ck`\x9d\xaa\xc8\x00\x01\x1a\xde")
    assert r == Request.from_bytes(data)


@pytest.mark.skipif(sys.version_info < (3, 14), reason="zstd added in Python 3.14")
def test_zstd() -> None:
    r = Response(id=10, ok=True, result=array("d", (1, 2, 3)))
    data = r.to_bytes(Flag.ZSTD)
    assert data == (
        b"\x08\x00"
        b"\x0a\x00\x00\x00\x00\x00\x00\x00"
        b"\x01"
        b"(\xb5/\xfd \x18\xad\x00\x00p\x00\x00\xf0?\x00@\x00\x00\x00\x00\x00\x00\x08@\x02\x00`F\x00\xb0"
    )

    r2 = Response.from_bytes(data)
    assert r2.id == r.id
    assert r2.ok is True

    # Did not use JSON nor PICKLE serialisation, so when reading back the result is in uncompressed bytes
    assert r2.result == b"\x00\x00\x00\x00\x00\x00\xf0?\x00\x00\x00\x00\x00\x00\x00@\x00\x00\x00\x00\x00\x00\x08@"
    assert array("d", r2.result) == r.result


def test_zstd_missing(temporarily_force_zstd_missing: None) -> None:
    assert temporarily_force_zstd_missing is None
    with pytest.raises(ModuleNotFoundError):
        _ = Response(id=10, ok=True, result=b"hi").to_bytes(Flag.ZSTD)

    with pytest.raises(ModuleNotFoundError):
        _ = Request.from_bytes(Flag.ZSTD.to_bytes(2, "little") + b"foo")


def test_noop() -> None:
    data = b"foo"
    assert compress[Flag.NONE](data) is data
    assert decompress[Flag.NONE](data) is data
    assert serialize[Flag.NONE](data) is data
    assert deserialize[Flag.NONE](data) is data

    ba = bytearray(b"bar")
    assert serialize[Flag.NONE](ba) is not ba
    assert serialize[Flag.NONE](ba) == b"bar"


@pytest.mark.parametrize("flag", BAD_FLAGS)
def test_response_invalid_bitwise_flags(flag: Flag) -> None:
    response = Response(id=1, ok=True, result=None)
    with pytest.raises(KeyError):
        _ = response.to_bytes(flag)


@pytest.mark.parametrize("flag", BAD_FLAGS)
def test_request_invalid_bitwise_flags(flag: Flag) -> None:
    request = Request(id=1, service="", attribute="", args=(), kwargs={})
    with pytest.raises(KeyError):
        _ = request.to_bytes(flag)


@pytest.mark.parametrize("flag", [Flag.JSON, Flag.ORJSON])
def test_json_orjson_default(flag: Flag) -> None:

    class Nope:
        def __init__(self) -> None:
            self.a: int = 1
            self.b: bool = True

    request = Request(1, "a", "b", (Nope(),), {})
    with pytest.raises(TypeError, match=r"not JSON serializable"):
        _ = request.to_bytes(flag)

    class JSONable:
        def __init__(self) -> None:
            self.a: int = 1
            self.b: bool = True

        def to_json(self) -> dict[str, int | bool]:
            return {"a": self.a, "b": self.b}

    request = Request(1, "a", "b", (JSONable(),), {})
    serialised = request.to_bytes(flag)
    assert serialised == flag.to_bytes(2, "little") + b'[1,"a","b",[{"a":1,"b":true}],{}]'


def test_tuple_is_named_tuple() -> None:
    # Verifies that tuple(NamedTuple) does not copy data

    r = Request(
        id=1,
        service="hello",
        attribute="world",
        args=(1, 2.3, None, True, "foo", b"bar", [9, 8, 7], {1, 2, 3}),
        kwargs={"a": array("b", b"A"), "b": np.arange(1000, dtype=float)},
    )

    tr = tuple(r)
    assert tr[0] is r.id
    assert tr[0] is r[0]
    assert tr[1] is r.service
    assert tr[1] is r[1]
    assert tr[2] is r.attribute
    assert tr[2] is r[2]
    assert tr[3] is r.args
    assert tr[3] is r[3]
    assert tr[4] is r.kwargs
    assert tr[4] is r[4]


def test_orjson_missing(temporarily_force_orjson_missing: None) -> None:
    assert temporarily_force_orjson_missing is None
    with pytest.raises(ModuleNotFoundError):
        _ = Response(id=10, ok=True, result=b"hi").to_bytes(Flag.ORJSON)

    with pytest.raises(ModuleNotFoundError):
        _ = Request.from_bytes(Flag.ORJSON.to_bytes(2, "little") + b"foo")
