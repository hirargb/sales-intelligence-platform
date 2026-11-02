"""Test fixtures.

Each client builds its own app so a test can tune settings, for example a tiny
rate-limit burst. The cache ttl is 0 in tests, so a read always hits DuckDB and
results stay deterministic.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

DATA = Path(__file__).resolve().parent.parent / "data" / "scored.parquet"


def _settings(**overrides) -> Settings:
    base = dict(
        environment="test",
        scored_parquet=str(DATA),
        pool_size=2,
        stats_cache_ttl=0,
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def client() -> TestClient:
    app = create_app(_settings())
    with TestClient(app) as c:
        yield c


@pytest.fixture
def strict_client() -> TestClient:
    # A shallow bucket that refills slowly, so the third call in a burst is 429.
    app = create_app(_settings(rate_limit_rpm=1, rate_limit_burst=2))
    with TestClient(app) as c:
        yield c
