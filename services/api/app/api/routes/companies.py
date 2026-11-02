"""The ranked company list, and one company's detail."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_repo, rate_limit
from app.models import Company, CompanyFilters, CompanyPage
from app.repositories import CompaniesRepository

router = APIRouter(tags=["companies"], dependencies=[Depends(rate_limit)])


@router.get("/companies", response_model=CompanyPage)
def list_companies(
    filters: CompanyFilters = Depends(),
    repo: CompaniesRepository = Depends(get_repo),
) -> CompanyPage:
    return CompanyPage(**repo.list_companies(filters))


@router.get("/company", response_model=Company)
def get_company(
    name: str = Query(..., description="Exact company name."),
    repo: CompaniesRepository = Depends(get_repo),
) -> Company:
    row = repo.get_company(name)
    if row is None:
        raise HTTPException(status_code=404, detail="Company not found.")
    return Company(**row)
