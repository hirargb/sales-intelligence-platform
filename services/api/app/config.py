"""Application settings.

Settings load from the environment once at startup and are validated by
Pydantic, so a bad value fails fast instead of surfacing deep in a request.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_PARQUET = str(Path(__file__).resolve().parent.parent / "data" / "scored.parquet")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    environment: str = Field(default="local")
    log_level: str = Field(default="INFO")

    # Data source the repository reads. DuckDB queries the Parquet directly.
    scored_parquet: str = Field(default=_DEFAULT_PARQUET)

    # Connection pool. Each connection holds one DuckDB session over the Parquet.
    pool_size: int = Field(default=4, ge=1, le=32)
    pool_acquire_timeout: float = Field(default=5.0, gt=0)

    # Rate limit, token bucket per client. rpm is the steady rate, burst the depth.
    rate_limit_rpm: int = Field(default=120, ge=1)
    rate_limit_burst: int = Field(default=40, ge=1)

    # Response cache for the two near-static endpoints.
    stats_cache_ttl: float = Field(default=30.0, ge=0)

    # Minimum Jaro-Winkler similarity for a fuzzy company-name match.
    search_fuzzy_threshold: float = Field(default=0.7, ge=0, le=1)

    # Browsers that may call the API directly. The web app calls it server side,
    # so this matters only for a direct browser client.
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])


@lru_cache
def get_settings() -> Settings:
    """Return the one settings instance for the process."""
    return Settings()
