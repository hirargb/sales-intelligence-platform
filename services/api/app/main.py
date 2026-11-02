"""Application factory and wiring.

create_app builds the pool, the repository, and the limiter once, attaches them
to app.state, and registers the routes, the CORS policy, and the error handlers.
A lifespan context closes the pool on shutdown.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import api_router
from app.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.rate_limit import TokenBucketLimiter
from app.db import DuckDBPool
from app.logging import configure_logging
from app.repositories import CompaniesRepository

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    pool = DuckDBPool(
        parquet_path=settings.scored_parquet,
        size=settings.pool_size,
        acquire_timeout=settings.pool_acquire_timeout,
    )
    repo = CompaniesRepository(
        pool,
        stats_cache_ttl=settings.stats_cache_ttl,
        fuzzy_threshold=settings.search_fuzzy_threshold,
    )
    limiter = TokenBucketLimiter(rpm=settings.rate_limit_rpm, burst=settings.rate_limit_burst)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("api starting", extra={"environment": settings.environment})
        yield
        pool.close()

    app = FastAPI(
        title="Sales Intelligence API",
        version=__version__,
        summary="Ranked companies most likely to buy cybersecurity software.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.pool = pool
    app.state.repo = repo
    app.state.limiter = limiter

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
