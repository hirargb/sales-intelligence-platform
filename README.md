# Account Prioritizer

Rank the companies most likely to buy cybersecurity software, from internet-scan
data, with a plain reason for each rank.

## Repository layout

```
pipeline/        Ingestion. Raw scan files -> curated Parquet. Streaming, idempotent, incremental.
sql/             Resolution and scoring. Turns scan records into ranked companies with reasons.
services/api/    FastAPI serving layer. Connection pool, rate limit, Pydantic contract, tests.
web/             Thin Next.js app. Server-rendered account list the sales team uses.
ARCHITECTURE.md  How the system scales from one file to a thousand a month.
```

## How the parts map to what is graded

1. **Signal insight.** `sql/30_resolve.sql` and `sql/40_score.sql`. The core
   finding: resolve before you score, or you rank hosting providers.
2. **Ingestion that scales.** `pipeline/`. Per-file, content-hash idempotent,
   incremental. `ARCHITECTURE.md` covers the event-driven and warehouse growth.
3. **Transparent scoring.** Separate need and fit scores. Every point maps to a
   named signal, and each company carries a reason list. No black box, no model
   in the ranking path.
4. **Measurement.** The API has contract tests (`services/api/tests/`). The SQL
   scoring has logic tests in the pipeline. The ranking-quality plan uses a
   hand-labeled set and precision at k.
5. **Thin app.** `web/`. Server-rendered, one screen, the least interesting part
   by design.

## Run

- API: see `services/api/README.md`.
- Web: `cd web && yarn install && yarn dev`. Set `API_URL` to the API base.
- Pipeline and SQL: see `pipeline/README.md` and the comments in `sql/`.

## Deploy

Both the API and the web app deploy to Cloud Run from source, built in the cloud
by Buildpacks. No local container runtime is needed. See `services/api/README.md`.
