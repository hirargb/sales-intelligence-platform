"""Exception handlers.

The handlers turn internal failures into clean JSON with the right status and
without leaking a stack trace to the client. The trace still reaches the logs.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.db import PoolTimeout

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(PoolTimeout)
    async def _pool_timeout(request: Request, exc: PoolTimeout) -> JSONResponse:
        logger.warning("pool timeout", extra={"path": request.url.path})
        return JSONResponse(
            status_code=503,
            content={"detail": "Service busy, retry shortly."},
            headers={"Retry-After": "1"},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error", extra={"path": request.url.path})
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})
