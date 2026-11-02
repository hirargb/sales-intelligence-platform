"""A token-bucket rate limiter.

Each client gets a bucket that holds up to `burst` tokens and refills at
`rpm` tokens per minute. A request spends one token. An empty bucket returns
HTTP 429 with a Retry-After hint. The state is in process, which is the right
scope for one Cloud Run instance; a multi-instance deployment would move this
to a shared store such as Redis.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


class TokenBucketLimiter:
    def __init__(self, rpm: int, burst: int) -> None:
        self._refill_per_sec = rpm / 60.0
        self._capacity = float(burst)
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, float]:
        """Try to spend one token for `key`.

        Return (allowed, retry_after_seconds). retry_after is 0 when allowed.
        """
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(tokens=self._capacity, last_refill=now)
                self._buckets[key] = bucket
            elapsed = now - bucket.last_refill
            bucket.tokens = min(self._capacity, bucket.tokens + elapsed * self._refill_per_sec)
            bucket.last_refill = now
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True, 0.0
            deficit = 1.0 - bucket.tokens
            retry_after = deficit / self._refill_per_sec if self._refill_per_sec else 1.0
            return False, retry_after
