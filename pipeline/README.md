# Ingestion pipeline

Takes raw Shodan scan files landing in a GCS bucket and turns them into a curated,
partitioned Parquet dataset the scoring reads. Built to handle thousands of ~20 GB
files a month.

## Layout in the bucket

    gs://<bucket>/inbox/                 raw files land here (<name>.json.zst)
    gs://<bucket>/curated/ingest_date=.../<name>.parquet   slim columns, per file
    gs://<bucket>/manifest/ingested.jsonl                  one line per ingested file

## How it scales, and the four properties

- Streaming: DuckDB reads each file straight from GCS; the corpus is never loaded at once.
- Idempotent: each file is keyed by its GCS content hash (md5). A hash already in the
  manifest is skipped, so re-delivering the same bytes does nothing.
- Incremental: only files with a new hash are processed; the curated dataset grows.
- Resumable: the manifest is the checkpoint. A crash just leaves files without a
  manifest entry, which the next run picks up.

Each file is independent work, so scale is "run more workers", not "reprocess the corpus".

## Run

On a machine with GCS access (a GCE VM uses its service account automatically):

    uv venv
    uv pip install -e .
    python ingest.py --bucket <bucket>

## Run targets

The same worker runs three ways. The image is built by Cloud Build, so no Docker
runs on your machine.

1. Build the image.

    gcloud builds submit . --tag us-central1-docker.pkg.dev/<project>/shodan/ingest:v1

2. Small files and idempotency checks. Run the image as a Cloud Run Job. It reads
   the inbox, applies the manifest, and skips files it already has.

    gcloud run jobs create shodan-ingest --image <image> --args=--bucket,<bucket> --region us-central1
    gcloud run jobs execute shodan-ingest --region us-central1

3. Large files. A 20 GB file needs real disk for the download and the DuckDB spill.
   Cloud Run gives only memory-backed storage, so run the same image on Cloud Batch
   or GKE with a mounted disk, and set INGEST_LOCAL to that disk.

A plain VM with uv and Python also runs the worker directly, without a container.

## Downstream

The scoring in ../sql reads the curated Parquet. Point it at
`gs://<bucket>/curated/**/*.parquet` instead of the single local file to score the
whole accumulated dataset.
