"""Corpus-level counts for the dashboard header."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_repo, rate_limit
from app.models import Stats
from app.repositories import CompaniesRepository

router = APIRouter(tags=["stats"], dependencies=[Depends(rate_limit)])


@router.get("/stats", response_model=Stats)
def get_stats(repo: CompaniesRepository = Depends(get_repo)) -> Stats:
    return Stats(**repo.stats())
