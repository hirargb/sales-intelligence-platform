# Account Prioritizer API

FastAPI service that serves the ranked companies from the scored Parquet. DuckDB
reads the Parquet directly, so there is no database to run and queries return in
milliseconds.

## Structure

```
app/
  main.py              App factory. Builds the pool, repo, limiter; wires routes.
  config.py            Pydantic settings, loaded and validated from the environment.
  logging.py           Structured JSON logs for Cloud Run.
  db/pool.py           Bounded DuckDB connection pool with a borrow/return context.
  models/schemas.py    Request and response models. The API contract.
  core/rate_limit.py   Token-bucket limiter, per client.
  core/decorators.py   timed() and ttl_cache() for the service layer.
  core/errors.py       Exception handlers; clean JSON, no leaked traces.
  repositories/        Data access. Owns every SQL string and the pool.
  api/routes/          Typed endpoints: health, stats, markets, companies.
tests/                 Contract tests over the real scored Parquet.
```

## Design notes

- **Connection pool.** One DuckDB connection is not safe for concurrent queries.
  The pool holds a fixed set of connections, each with a read-only view over the
  Parquet. A request borrows one and returns it. The pool bounds concurrency and
  removes the per-request cost of opening a connection.
- **Rate limit.** A token bucket per client, in process. The right scope for one
  Cloud Run instance; a multi-instance deployment moves this to a shared store.
- **Caching.** The two near-static reads are cached for a short window, so a
  burst of dashboard loads does not re-run the same aggregate.
- **Validation.** Every query is validated against a Pydantic model, so a bad
  parameter is a 422, not a surprise deep in a query. Sort is a closed enum, so
  the sort column cannot inject SQL.

## Run locally

```
uv venv
uv pip install -e ".[test]"
uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000/docs for the OpenAPI UI.

## Test

```
uv pip install -e ".[test]"
pytest
```

## Configuration

All settings take the `APP_` prefix, for example `APP_POOL_SIZE=8`.

| Variable                   | Default              | Meaning                              |
| -------------------------- | -------------------- | ------------------------------------ |
| `APP_SCORED_PARQUET`       | `data/scored.parquet`| Path to the scored companies.        |
| `APP_POOL_SIZE`            | `4`                  | DuckDB connections in the pool.      |
| `APP_RATE_LIMIT_RPM`       | `120`                | Steady request rate per client.      |
| `APP_RATE_LIMIT_BURST`     | `40`                 | Bucket depth per client.             |
| `APP_STATS_CACHE_TTL`      | `30`                 | Cache window for stats and markets.  |
| `APP_CORS_ORIGINS`         | `["*"]`              | Browser origins allowed to call.     |

## Deploy to Cloud Run

```
gcloud run deploy account-prioritizer-api --source . \
  --region us-central1 --allow-unauthenticated --memory 1Gi
```

Buildpacks read `requirements.txt` and the `Procfile`, so no Dockerfile is needed.
