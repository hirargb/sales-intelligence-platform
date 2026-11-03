"""Contract tests for the scored data file.

The API tests cover the serving layer. These cover the artifact it serves:
data/scored.parquet, the output of the scoring step (sql/40_score.sql). They
read the Parquet directly, so a broken or mis-shaped scoring run fails here
before it can reach the API. They assert the invariants the scoring step
promises, not exact values, so they hold as the data is refreshed.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

DATA = Path(__file__).resolve().parent.parent / "data" / "scored.parquet"

# The columns the API contract depends on, with their expected DuckDB types.
_EXPECTED = {
    "company": "VARCHAR",
    "need_score": "DOUBLE",
    "fit_score": "DOUBLE",
    "priority": "DOUBLE",
    "country": "VARCHAR",
    "exposed_ips": "BIGINT",
    "distinct_ports": "BIGINT",
    "n_kev": "BIGINT",
    "worst_cvss": "DOUBLE",
    "n_db": "BIGINT",
    "n_remote": "BIGINT",
    "n_legacy": "BIGINT",
    "n_eol": "BIGINT",
    "n_compromised": "BIGINT",
    "has_cert_identity": "BOOLEAN",
    "reasons": "VARCHAR[]",
    "kev_cves": "VARCHAR[]",
    "worst_service": "VARCHAR",
    "db_services": "VARCHAR[]",
    "remote_services": "VARCHAR[]",
}


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect()
    c.execute(f"CREATE VIEW d AS SELECT * FROM read_parquet('{DATA}')")
    yield c
    c.close()


def _count(con, where: str) -> int:
    return con.execute(f"SELECT count(*) FROM d WHERE {where}").fetchone()[0]


def test_schema_matches_contract(con):
    got = {r[0]: r[1] for r in con.execute("DESCRIBE SELECT * FROM d").fetchall()}
    assert got == _EXPECTED


def test_has_companies(con):
    assert con.execute("SELECT count(*) FROM d").fetchone()[0] > 1000


def test_scores_are_in_range(con):
    assert _count(con, "need_score < 0 OR need_score > 100") == 0
    assert _count(con, "fit_score < 0 OR fit_score > 100") == 0
    assert _count(con, "worst_cvss < 0 OR worst_cvss > 10") == 0


def test_priority_never_exceeds_need(con):
    # Priority is need lifted by fit, so it can never beat need.
    assert _count(con, "priority > need_score + 1e-6") == 0


def test_priority_follows_the_formula(con):
    # priority = need * (0.5 + 0.5 * fit/100), within rounding.
    err = con.execute(
        "SELECT max(abs(priority - need_score * (0.5 + 0.5 * fit_score / 100))) FROM d"
    ).fetchone()[0]
    assert err < 0.1


def test_every_rank_has_a_reason(con):
    # The brief requires a reason for every rank.
    assert _count(con, "len(reasons) = 0") == 0


def test_evidence_columns_are_populated(con):
    # The evidence join is live: some companies carry named CVEs and services.
    assert _count(con, "len(kev_cves) > 0") > 0
    assert _count(con, "worst_service IS NOT NULL") > 0
    assert con.execute("SELECT max(len(kev_cves)) FROM d").fetchone()[0] <= 6


def test_no_junk_company_names(con):
    # Placeholder and IP-literal names must be filtered out by the scoring step.
    junk = _count(
        con,
        "lower(trim(company)) IN "
        "('company','certificate','localhost','default','none','null',"
        "'example','default company ltd','someorganization')",
    )
    assert junk == 0
    ip_literal = _count(con, r"regexp_full_match(company, '^\d{1,3}(\.\d{1,3}){3}$')")
    assert ip_literal == 0


def test_companies_are_distinct(con):
    total = con.execute("SELECT count(*) FROM d").fetchone()[0]
    distinct = con.execute("SELECT count(DISTINCT company) FROM d").fetchone()[0]
    assert total == distinct
