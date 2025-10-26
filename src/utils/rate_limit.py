from asyncio import sleep
from collections.abc import Awaitable, Callable, Iterable
from time import time
from typing import ParamSpec, TypeVar

from limits.aio.strategies import RateLimiter

from limits import RateLimitItem
from src.constants import DEFAULT_LIMITER, DEFAULT_RATE_LIMIT

T = TypeVar("T")
P = ParamSpec("P")


class RateLimitError(Exception):
    pass


def rate_limit(
    strategy: RateLimiter = DEFAULT_LIMITER,
    limit: RateLimitItem = DEFAULT_RATE_LIMIT,
    reschedule: bool = True,
    identifiers: Iterable[str] = tuple(),
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator for rate_limiting function calls.

    Args:
        strategy: Limiting strategy.
        limit: The limit, e.g., 10 calls per second.
        reschedule: How long to sleep in seconds before reattempting. Pass 0 to raise `RateLimitError` instead when limit is exceeded.
        identifier: Identifiers that can be used to separate this limit from oters.
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        async def wrapper(*args: P.args, **kwargs: P.kwargs):
            if reschedule:
                while not await strategy.hit(limit, *identifiers):
                    window = await strategy.get_window_stats(limit, *identifiers)
                    await sleep(window.reset_time - time())
            elif not await strategy.hit(limit, *identifiers):
                raise RateLimitError(f"Limit exceeded for '{identifiers}' '{limit}'")
            return await func(*args, **kwargs)

        return wrapper

    return decorator
