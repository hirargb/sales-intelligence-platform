"""Request and response schemas.

These models are the API contract. FastAPI validates every query against
CompanyFilters and serializes every response through these models, so the
shape the frontend sees is fixed and documented in the OpenAPI schema.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SortKey(str, Enum):
    """Columns a client may sort on. A closed set stops query-string injection."""

    priority = "priority"
    need_score = "need_score"
    fit_score = "fit_score"
    exposed_ips = "exposed_ips"
    n_kev = "n_kev"


class SizeBand(str, Enum):
    """Surface-size bands, a rough proxy for company size by exposed hosts."""

    small = "small"
    medium = "medium"
    large = "large"
    xlarge = "xlarge"


class CompanyFilters(BaseModel):
    """Validated query parameters for the company list."""

    market: str | None = Field(default=None, description="Filter by country code.")
    q: str | None = Field(default=None, description="Case-insensitive name match.")
    min_need: float = Field(default=0, ge=0, le=100, description="Minimum need score.")
    high_confidence: bool = Field(
        default=False, description="Only companies identified by a certificate."
    )
    size: SizeBand | None = Field(
        default=None, description="Filter by surface-size band (exposed hosts)."
    )
    sort: SortKey = Field(default=SortKey.priority)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class Company(BaseModel):
    company: str
    need_score: float
    fit_score: float
    priority: float
    country: str | None
    exposed_ips: int
    distinct_ports: int
    n_kev: int
    worst_cvss: float
    n_db: int
    n_remote: int
    n_legacy: int
    n_eol: int
    n_compromised: int
    has_cert_identity: bool
    reasons: list[str]


class CompanyPage(BaseModel):
    total: int = Field(description="Total rows that match the filter.")
    items: list[Company]


class Stats(BaseModel):
    companies: int
    markets: int
    high_confidence: int


class Market(BaseModel):
    country: str
    companies: int


class Health(BaseModel):
    status: str
    version: str
