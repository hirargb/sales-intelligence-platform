"""Liveness and readiness.

Cloud Run needs a cheap endpoint that proves the process is up and can reach
its data. `/health` is liveness. `/ready` runs a trivial query through the pool.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app import __version__
from app.api.deps import get_repo
from app.models import Health
from app.repositories import CompaniesRepository

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Health)
def health() -> Health:
    return Health(status="ok", version=__version__)


@router.get("/ready", response_model=Health)
def ready(repo: CompaniesRepository = Depends(get_repo)) -> Health:
    # One cached, tiny read proves the pool and the Parquet are reachable.
    repo.stats()
    return Health(status="ready", version=__version__)
