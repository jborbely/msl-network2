"""Custom type annotations."""

from __future__ import annotations

import os
from concurrent.futures import Future  # noqa: TC003
from typing import Any, Literal, Protocol, Union, overload  # pyright: ignore[reportDeprecated]


class FutureOrResult(Protocol):
    """The *response* from a *request*."""

    @overload
    def __call__(self, *args: Any, sync: Literal[True] = True, **kwargs: Any) -> Any: ...

    @overload
    def __call__(self, *args: Any, sync: Literal[False] = False, **kwargs: Any) -> Future[Any]: ...

    def __call__(self, *args: Any, sync: bool = True, **kwargs: Any) -> Any | Future[Any]:
        """Call a method of a [Worker][].

        Args:
            *args: The arguments that the method of the [Worker][] requires.
            sync: Whether to perform a synchronous request or an asynchronous request.
            **kwargs: The keyword arguments that the method of the [Worker][] requires.

        Returns:
            Depending on the value of the `sync` keyword argument, the returned value is the
                result (`sync=True`) for a synchronous request or a [Future][concurrent.futures.Future]
                (`sync=False`) for an asynchronous request, which will eventually contain the
                [result][concurrent.futures.Future.result] of the request that the future represents.
        """


PathLike = Union[str, bytes, os.PathLike[str], os.PathLike[bytes]]  # pyright: ignore[reportDeprecated]
"""A [path-like object][]."""
