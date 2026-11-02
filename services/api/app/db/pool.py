"""The DuckDB serving layer: one indexed in-memory table, a pool of cursors.

DuckDB is an in-process analytical engine, so it serves this read-only ranked
list without a separate database server. At startup the Parquet is loaded once
into an in-memory table and indexed. The pool hands out cursors over that one
table, so every connection shares the same data and indexes, with no per-request
load and no duplicated memory. This is why the serving layer does not need
Postgres at this scale: DuckDB scans millions of rows fast, uses a Top-N
operator for ORDER BY ... LIMIT, keeps min/max zonemaps per row group, and the
indexes below cover the equality and range filters.
"""

from __future__ import annotations

import logging
import queue
import threading
from contextlib import contextmanager
from typing import Iterator

import duckdb

logger = logging.getLogger(__name__)


class PoolTimeout(Exception):
    """Raised when no cursor became free within the acquire timeout."""


class DuckDBPool:
    def __init__(self, parquet_path: str, size: int, acquire_timeout: float) -> None:
        if size < 1:
            raise ValueError("pool size must be at least 1")
        self._acquire_timeout = acquire_timeout
        self._closed = False
        self._lock = threading.Lock()

        # One base connection owns the table and the indexes. The path comes
        # from config, not a user, so it is inlined with quotes escaped.
        self._base = duckdb.connect(database=":memory:")
        safe = parquet_path.replace("'", "''")
        self._base.execute(
            f"CREATE TABLE companies AS SELECT * FROM read_parquet('{safe}')"
        )
        # Indexes for the filter and lookup paths. company for the detail
        # lookup, country for the market filter, need_score for the range filter.
        self._base.execute("CREATE INDEX idx_company ON companies(company)")
        self._base.execute("CREATE INDEX idx_country ON companies(country)")
        self._base.execute("CREATE INDEX idx_need ON companies(need_score)")

        # A cursor is a thread-usable handle onto the same database. The pool
        # bounds how many queries run at once.
        self._pool: queue.Queue = queue.Queue(maxsize=size)
        self._all = []
        for _ in range(size):
            cur = self._base.cursor()
            self._all.append(cur)
            self._pool.put(cur)
        rows = self._base.execute("SELECT count(*) FROM companies").fetchone()[0]
        logger.info("duckdb table ready", extra={"pool_size": size, "rows": rows})

    @contextmanager
    def acquire(self) -> Iterator[duckdb.DuckDBPyConnection]:
        """Borrow a cursor for the duration of the block."""
        if self._closed:
            raise PoolTimeout("pool is closed")
        try:
            cur = self._pool.get(timeout=self._acquire_timeout)
        except queue.Empty as exc:
            raise PoolTimeout("no free cursor within timeout") from exc
        try:
            yield cur
        finally:
            self._pool.put(cur)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for cur in self._all:
                try:
                    cur.close()
                except Exception:  # noqa: BLE001 - best effort on shutdown
                    pass
            try:
                self._base.close()
            except Exception:  # noqa: BLE001
                pass
            self._all.clear()
        logger.info("duckdb pool closed")
