"""Reusable decorators for the service layer.

`timed` records how long a call took, as a structured log field. `ttl_cache`
memoizes a function result for a short window, which suits the two endpoints
whose answer changes only when a new scoring run lands.
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from typing import Callable, TypeVar

logger = logging.getLogger("app.timing")

T = TypeVar("T")


def timed(name: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Log the duration of each call under `name`."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: object, **kwargs: object) -> T:
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                ms = (time.perf_counter() - start) * 1000
                logger.info("call timed", extra={"operation": name, "duration_ms": round(ms, 2)})

        return wrapper

    return decorator


def ttl_cache(ttl_seconds: float) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Cache the result per argument tuple for `ttl_seconds`.

    Thread-safe. A ttl of 0 disables the cache, which keeps tests deterministic.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        store: dict[tuple, tuple[float, T]] = {}
        lock = threading.Lock()

        @functools.wraps(func)
        def wrapper(*args: object, **kwargs: object) -> T:
            if ttl_seconds <= 0:
                return func(*args, **kwargs)
            key = (args, tuple(sorted(kwargs.items())))
            now = time.monotonic()
            with lock:
                hit = store.get(key)
                if hit is not None and now - hit[0] < ttl_seconds:
                    return hit[1]
            value = func(*args, **kwargs)
            with lock:
                store[key] = (now, value)
            return value

        return wrapper

    return decorator
