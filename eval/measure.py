"""Measure the ranking quality over the scored companies.

Read-only and reproducible. It reports:
  1. Precision at k for a concrete, sellable problem, and the lift over the base
     rate in the whole population.
  2. The certificate-identity rate at the top, which shows why the identity
     filter exists.
  3. Each signal's Spearman rank correlation with the final priority, which shows
     how much each signal moves the ranking.
  4. A reason-consistency check: each reason text must match the row's columns.

Run from the repo root: python eval/measure.py
"""

from __future__ import annotations

from pathlib import Path

import duckdb

PARQUET = (
    Path(__file__).resolve().parent.parent
    / "services"
    / "api"
    / "data"
    / "scored.parquet"
)


def main() -> None:
    c = duckdb.connect()
    c.execute(
        f"""
        CREATE VIEW s AS
        SELECT *, (n_kev > 0 OR n_db > 0 OR n_compromised > 0) AS concrete
        FROM read_parquet('{PARQUET}')
        """
    )

    n = c.execute("SELECT count(*) FROM s").fetchone()[0]
    base_concrete = c.execute("SELECT avg(concrete::INT) FROM s").fetchone()[0]
    base_hc = c.execute("SELECT avg(has_cert_identity::INT) FROM s").fetchone()[0]
    print(f"population = {n}")
    print(f"base concrete-problem rate = {base_concrete:.3f}")
    print(f"base certificate-identity rate = {base_hc:.3f}\n")

    print("precision@k by priority:")
    print(f"{'k':>5} {'concrete':>9} {'lift':>6} {'cert-id':>9}")
    for k in (20, 50, 100, 500):
        p_con, p_hc = c.execute(
            f"""
            WITH t AS (SELECT * FROM s ORDER BY priority DESC, need_score DESC LIMIT {k})
            SELECT avg(concrete::INT), avg(has_cert_identity::INT) FROM t
            """
        ).fetchone()
        print(f"{k:>5} {p_con:>9.3f} {p_con / base_concrete:>6.2f} {p_hc:>9.3f}")

    print("\nsignal contribution, Spearman(signal, priority):")
    for comp in (
        "worst_cvss",
        "n_kev",
        "n_eol",
        "exposed_ips",
        "n_remote",
        "n_db",
        "distinct_ports",
        "n_legacy",
        "n_compromised",
    ):
        rho = c.execute(
            f"""
            WITH r AS (
              SELECT rank() OVER (ORDER BY {comp}) rc, rank() OVER (ORDER BY priority) rp
              FROM s
            )
            SELECT corr(rc, rp) FROM r
            """
        ).fetchone()[0]
        print(f"  {comp:>15}: {rho:+.3f}")

    bad = c.execute(
        """
        WITH t AS (SELECT * FROM s ORDER BY priority DESC LIMIT 200)
        SELECT count(*) FROM t
        WHERE list_last(reasons) NOT LIKE
          '%' || exposed_ips || ' internet-exposed host(s) across ' || distinct_ports || ' port(s)'
        """
    ).fetchone()[0]
    print(f"\nreason-consistency (top 200): {200 - bad}/200 match exactly")


if __name__ == "__main__":
    main()
