"""Company counts per market."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_repo, rate_limit
from app.models import Market
from app.repositories import CompaniesRepository

router = APIRouter(tags=["markets"], dependencies=[Depends(rate_limit)])


@router.get("/markets", response_model=list[Market])
def get_markets(repo: CompaniesRepository = Depends(get_repo)) -> list[Market]:
    return [Market(**row) for row in repo.markets()]
