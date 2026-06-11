"""Custom type annotations."""

from __future__ import annotations

from concurrent.futures import Future  # noqa: TC003
from typing import Any, Literal, Protocol, overload


class FutureOrResult(Protocol):
    """The response from a request.

    Depending on the value of the `sync` keyword argument, the returned value is the
    result (`sync=True`) for a synchronous request or a [Future][concurrent.futures.Future]
    (`sync=False`) for an asynchronous request, which will eventually contain the
    [result][concurrent.futures.Future.result] of the request that the future represents.
    """

    @overload
    def __call__(self, *args: Any, sync: Literal[True], sync_timeout: float | None = ..., **kwargs: Any) -> Any: ...

    @overload
    def __call__(
        self, *args: Any, sync: Literal[False], sync_timeout: float | None = ..., **kwargs: Any
    ) -> Future[Any]: ...

    @overload
    def __call__(self, *args: Any, sync: bool = True, sync_timeout: float | None = None, **kwargs: Any) -> Any: ...
