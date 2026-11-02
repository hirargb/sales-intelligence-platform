"""Read access to the scored companies.

The repository owns every SQL string and the connection pool. Routes call its
methods and never touch DuckDB, so the data access stays in one place and the
query shapes are easy to test. The two near-static reads are cached; the list
read is parameterized and sorted only on a validated column.
"""

from __future__ import annotations

from app.core.decorators import timed, ttl_cache
from app.db import DuckDBPool
from app.models import CompanyFilters

# Surface-size bands, keyed by exposed-host count. xlarge has no upper bound.
_SIZE_BANDS = {
    "small": (2, 9),
    "medium": (10, 49),
    "large": (50, 199),
    "xlarge": (200, None),
}

# Columns returned for each company. Kept explicit so the API contract does not
# drift when the scoring step adds a column.
_COMPANY_COLUMNS = """
    company, need_score, fit_score, priority, country,
    exposed_ips, distinct_ports, n_kev, worst_cvss, n_db,
    n_remote, n_legacy, n_eol, n_compromised,
    has_cert_identity, reasons,
    kev_cves, worst_service, db_services, remote_services
"""


class CompaniesRepository:
    def __init__(
        self, pool: DuckDBPool, stats_cache_ttl: float, fuzzy_threshold: float = 0.7
    ) -> None:
        self._pool = pool
        self._fuzzy_threshold = fuzzy_threshold
        # Bind the cache window from settings at construction time.
        self._stats_cached = ttl_cache(stats_cache_ttl)(self._stats_query)
        self._markets_cached = ttl_cache(stats_cache_ttl)(self._markets_query)

    def _fetch(self, sql: str, params: list) -> list[dict]:
        with self._pool.acquire() as con:
            cur = con.execute(sql, params)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def _scalar(self, sql: str, params: list):
        with self._pool.acquire() as con:
            return con.execute(sql, params).fetchone()[0]

    @timed("stats")
    def _stats_query(self) -> dict:
        return self._fetch(
            """
            SELECT count(*) AS companies,
                   count(DISTINCT country) AS markets,
                   count(*) FILTER (WHERE has_cert_identity) AS high_confidence
            FROM companies
            """,
            [],
        )[0]

    @timed("markets")
    def _markets_query(self) -> list[dict]:
        return self._fetch(
            """
            SELECT country, count(*) AS companies
            FROM companies
            WHERE country IS NOT NULL
            GROUP BY country
            ORDER BY companies DESC
            """,
            [],
        )

    def stats(self) -> dict:
        return self._stats_cached()

    def markets(self) -> list[dict]:
        return self._markets_cached()

    @timed("get_company")
    def get_company(self, name: str) -> dict | None:
        rows = self._fetch(
            f"SELECT {_COMPANY_COLUMNS} FROM companies WHERE company = ? LIMIT 1",
            [name],
        )
        return rows[0] if rows else None

    @timed("list_companies")
    def list_companies(self, f: CompanyFilters) -> dict:
        where = ["need_score >= ?"]
        params: list = [f.min_need]
        if f.market:
            where.append("country = ?")
            params.append(f.market)
        if f.high_confidence:
            where.append("has_cert_identity = true")
        if f.size:
            lo, hi = _SIZE_BANDS[f.size.value]
            where.append("exposed_ips >= ?")
            params.append(lo)
            if hi is not None:
                where.append("exposed_ips <= ?")
                params.append(hi)

        q = (f.q or "").strip()
        if q:
            # Fuzzy name match: a substring hit, or a high Jaro-Winkler
            # similarity, so a typo like "fortnet" still finds "Fortinet".
            where.append(
                "(company ILIKE ? "
                "OR jaro_winkler_similarity(lower(company), lower(?)) >= ?)"
            )
            params += [f"%{q}%", q, self._fuzzy_threshold]
        clause = " AND ".join(where)

        total = self._scalar(f"SELECT count(*) FROM companies WHERE {clause}", params)

        if q:
            # Rank by relevance first: a substring hit beats a fuzzy-only hit,
            # then the requested sort, then need.
            items = self._fetch(
                f"""
                WITH ranked AS (
                    SELECT {_COMPANY_COLUMNS},
                           GREATEST(
                             CASE WHEN company ILIKE ? THEN 1.0 ELSE 0.0 END,
                             jaro_winkler_similarity(lower(company), lower(?))
                           ) AS relevance
                    FROM companies
                    WHERE {clause}
                )
                SELECT {_COMPANY_COLUMNS}
                FROM ranked
                ORDER BY relevance DESC, {f.sort.value} DESC, need_score DESC
                LIMIT ? OFFSET ?
                """,
                [f"%{q}%", q] + params + [f.limit, f.offset],
            )
        else:
            items = self._fetch(
                f"""
                SELECT {_COMPANY_COLUMNS}
                FROM companies
                WHERE {clause}
                ORDER BY {f.sort.value} DESC, need_score DESC
                LIMIT ? OFFSET ?
                """,
                params + [f.limit, f.offset],
            )
        return {"total": total, "items": items}
