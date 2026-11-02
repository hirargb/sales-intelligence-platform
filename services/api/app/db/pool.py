"""A small connection pool for DuckDB.

DuckDB has no network server and one connection is not safe for concurrent
queries, so the API keeps a fixed set of in-memory connections. Each one holds
a read-only view over the scored Parquet. A request borrows a connection,
queries it, and returns it. The pool bounds concurrency and removes the
per-request cost of opening a connection and re-creating the view.
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
    """Raised when no connection became free within the acquire timeout."""


class DuckDBPool:
    def __init__(self, parquet_path: str, size: int, acquire_timeout: float) -> None:
        if size < 1:
            raise ValueError("pool size must be at least 1")
        self._parquet_path = parquet_path
        self._acquire_timeout = acquire_timeout
        self._pool: queue.Queue[duckdb.DuckDBPyConnection] = queue.Queue(maxsize=size)
        self._all: list[duckdb.DuckDBPyConnection] = []
        self._closed = False
        self._lock = threading.Lock()
        for _ in range(size):
            con = self._new_connection()
            self._all.append(con)
            self._pool.put(con)
        logger.info("duckdb pool ready", extra={"pool_size": size})

    def _new_connection(self) -> duckdb.DuckDBPyConnection:
        con = duckdb.connect(database=":memory:")
        # DuckDB forbids a bound parameter in CREATE VIEW, so the path is
        # inlined with single quotes escaped. It comes from config, not a user.
        safe = self._parquet_path.replace("'", "''")
        con.execute(f"CREATE VIEW companies AS SELECT * FROM read_parquet('{safe}')")
        return con

    @contextmanager
    def acquire(self) -> Iterator[duckdb.DuckDBPyConnection]:
        """Borrow a connection for the duration of the block."""
        if self._closed:
            raise PoolTimeout("pool is closed")
        try:
            con = self._pool.get(timeout=self._acquire_timeout)
        except queue.Empty as exc:
            raise PoolTimeout("no free connection within timeout") from exc
        try:
            yield con
        finally:
            # Always return the connection, even after a query error.
            self._pool.put(con)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for con in self._all:
                try:
                    con.close()
                except Exception:  # noqa: BLE001 - best effort on shutdown
                    pass
            self._all.clear()
        logger.info("duckdb pool closed")
