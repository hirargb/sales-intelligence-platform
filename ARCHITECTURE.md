# Architecture

How this system is built, and how it grows from one scan file to a thousand a
month without reprocessing the corpus.

## The problem shapes the design

The task ranks companies by how likely they are to buy cybersecurity software,
from internet-scan data. One fact drives every decision that follows:

> The strongest signals are global aggregates, not per-record facts.

Resolution is the clearest case. The rule "a domain that appears on more than
500 distinct IPs is hosting, not a company" can only be computed across the
whole corpus. The same holds for several scoring features. So a single file
cannot be fully scored on its own. This is the real reason the system has two
lanes. It is not latency. It is aggregation scope.

A naive pipeline hands the file to an LLM and ranks by vulnerability count. That
ranks hosting providers, because hosts carry the most banners and the most
CVEs. The resolution layer exists to remove them.

## Layers (medallion)

```
bronze (raw)   ->  silver (facts)   ->  gold (entities + scores)  ->  serving
GCS objects        per-file Parquet     resolution + scoring          API + web
immutable          parallel, keyed      global, scheduled             small table
```

1. **Bronze, raw.** Each scan file lands in GCS unchanged, partitioned by scan
   date, moved to colder storage after a retention window. This is the source
   of truth and is never mutated. A backfill is a replay of bronze.
2. **Silver, facts.** One banner becomes one typed row with the slim projected
   columns. The step is per file and embarrassingly parallel. It is triggered
   on object-finalize and is idempotent by content hash. Output is a columnar
   table in a format that allows schema evolution and safe appends (Iceberg, or
   BigQuery native).
3. **Gold, entities and scores.** Resolution, feature aggregation, and the
   deterministic score run over the whole corpus. Output is a small table of
   tens of thousands of ranked companies, each with a plain-language reason list.
4. **Serving.** The API reads the gold table from a fast store. The app never
   queries the lake directly.

## Fast lane and slow lane, stated honestly

- **Fast lane (speed layer).** On a new file, ingest to silver within minutes
  and compute a provisional score for the entities that file touched, using the
  last known global aggregates. Serve the provisional deltas, marked as such.
- **Slow lane (batch layer).** On a cadence, recompute the global aggregates and
  the authoritative scores across the full corpus, then overwrite the provisional
  scores.
- **Serving layer.** The app merges authoritative gold with provisional deltas.

This is Lambda architecture. It is justified here by the global-aggregate
dependency, not by a demand for sub-second freshness.

## Engine choices

| Layer   | Engine                         | Why                                                        |
| ------- | ------------------------------ | ---------------------------------------------------------- |
| silver  | DuckDB, one worker per file    | A 20 GB file fits one large worker; DuckDB is very fast    |
| gold    | BigQuery or Spark / Dataflow   | Global joins and aggregates at terabyte scale              |
| serving | DuckDB over a small Parquet    | Tens of thousands of rows; millisecond reads, no DB to run |

Right tool per layer, rather than one engine everywhere.

## Operational properties

- **Ingestion that scales.** Event-driven silver (GCS finalize -> Pub/Sub ->
  worker) makes each file independent work, so scale is "run more workers," not
  "reprocess the corpus." Idempotency is by content hash. Incremental: only new
  hashes are processed.
- **Orchestration.** A DAG tool (Cloud Composer or Cloud Workflows) owns the
  gold run with retries and SLAs. The orchestrator state plus an idempotent sink
  replaces a hand-rolled manifest at real scale.
- **Data quality.** Malformed records go to a quarantine table, not a silent
  drop, and an alert fires on quarantine volume. Gates check row counts, null
  rates, and score ranges before gold is published.
- **Reproducibility.** The scoring function is deterministic and versioned. Each
  gold row carries its score version, so any run can be reproduced.
- **Cost.** Storage tiers on bronze; compute runs only on new data; the LLM is
  kept out of the ranking path, so the score is cheap and auditable.

## What this repo ships

A runnable slice of the design: the batch pipeline (`pipeline/`), the resolution
and scoring SQL (`sql/`), a properly structured serving API (`services/api/`),
and a thin web app (`web/`). The fast lane, the orchestrator, and the warehouse
engines are described here and are the next build, not simulated.

## What I deliberately did not build

- No Kafka and no always-on Spark cluster for this scale.
- No streaming for its own sake. Daily batch meets a sales team's freshness need.
- Each lane is earned: batch first, event-driven silver when freshness demands
  it, the speed layer only for aggregate reconciliation.
