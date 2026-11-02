"""FastAPI dependencies.

The pool, the repository, and the limiter are built once at startup and held on
app.state. These getters hand them to routes, which keeps the routes free of
globals and makes them easy to override in a test.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from app.core.rate_limit import TokenBucketLimiter
from app.repositories import CompaniesRepository


def get_repo(request: Request) -> CompaniesRepository:
    return request.app.state.repo


def get_limiter(request: Request) -> TokenBucketLimiter:
    return request.app.state.limiter


def _client_key(request: Request) -> str:
    # Cloud Run and other proxies set X-Forwarded-For: "client, proxy, ...".
    # The first entry is the real client.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(
    request: Request,
    limiter: TokenBucketLimiter = Depends(get_limiter),
) -> None:
    """Spend one token for the caller, or reject with 429."""
    allowed, retry_after = limiter.check(_client_key(request))
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded.",
            headers={"Retry-After": str(max(1, round(retry_after)))},
        )
