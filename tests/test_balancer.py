import pytest

from msl.network.broker import WorkerBalancer


def test_worker_balancer() -> None:
    wb = WorkerBalancer()
    assert not wb
    assert len(wb) == 0

    with pytest.raises(ValueError, match=r"not in deque"):
        wb.remove(b"missing")

    wb.append(b"a")
    assert len(wb) == 1
    wb.remove(b"a")
    assert len(wb) == 0

    wb.append(b"a")
    for _ in range(5):
        assert next(wb) == b"a"

    wb.append(b"b")
    assert len(wb) == 2
    wb.append(b"c")
    assert len(wb) == 3

    wb.append(b"c")
    assert len(wb) == 3

    assert b"a" in wb
    assert b"b" in wb
    assert b"c" in wb
    assert b"d" not in wb

    assert next(wb) == b"c"
    assert next(wb) == b"b"
    assert next(wb) == b"a"
    assert next(wb) == b"c"
    assert next(wb) == b"b"
    assert next(wb) == b"a"

    wb.remove(b"b")
    assert len(wb) == 2

    assert next(wb) == b"c"
    assert next(wb) == b"a"
    assert next(wb) == b"c"
    assert next(wb) == b"a"
    assert next(wb) == b"c"
    assert next(wb) == b"a"

    wb.remove(b"a")
    assert len(wb) == 1

    for _ in range(5):
        assert next(wb) == b"c"

    wb.remove(b"c")
    assert len(wb) == 0

    with pytest.raises(IndexError, match=r"empty deque"):
        _ = next(wb)
