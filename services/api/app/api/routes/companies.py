"""The ranked company list, filtered and paged."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_repo, rate_limit
from app.models import CompanyFilters, CompanyPage
from app.repositories import CompaniesRepository

router = APIRouter(tags=["companies"], dependencies=[Depends(rate_limit)])


@router.get("/companies", response_model=CompanyPage)
def list_companies(
    filters: CompanyFilters = Depends(),
    repo: CompaniesRepository = Depends(get_repo),
) -> CompanyPage:
    return CompanyPage(**repo.list_companies(filters))
