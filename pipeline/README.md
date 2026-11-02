# Ingestion pipeline

This pipeline turns raw Shodan scan files into a curated Parquet dataset. The
scoring step reads that dataset. The pipeline handles thousands of 20 GB files
each month.

## Bucket layout

    gs://<bucket>/inbox/                                   raw files, <name>.json.zst
    gs://<bucket>/curated/ingest_date=.../<name>.parquet   slim columns, one file each
    gs://<bucket>/manifest/ingested.jsonl                  one line for each ingested file

## How it scales

The pipeline has four properties.

1. Streaming. DuckDB reads each file from GCS. It never loads the full corpus at
   once.
2. Idempotent. The content hash (md5) is the key for each file. The worker skips
   a hash that the manifest already holds.
3. Incremental. The worker processes only files with a new hash. The curated
   dataset grows.
4. Resumable. The manifest is the checkpoint. A crash leaves a file without a
   manifest entry. The next run processes that file.

Each file is independent work. Therefore you scale by more workers, not by a
reprocess of the corpus.

## Run

Run the worker on a machine with GCS access. A GCE VM uses its service account.

    uv venv
    uv pip install -e .
    python ingest.py --bucket <bucket>

## Run targets

The same worker runs three ways. Cloud Build builds the image, so no Docker runs
on your machine.

1. Build the image.

    gcloud builds submit . --tag us-central1-docker.pkg.dev/<project>/shodan/ingest:v1

2. Small files and idempotency checks. Run the image as a Cloud Run Job. The job
   reads the inbox, applies the manifest, and skips files it already holds.

    gcloud run jobs create shodan-ingest --image <image> --args=--bucket,<bucket> --region us-central1
    gcloud run jobs execute shodan-ingest --region us-central1

3. Large files. A 20 GB file needs real disk for the download and the DuckDB
   spill. Cloud Run gives only memory-backed storage. Therefore run the same
   image on Cloud Batch or GKE with a mounted disk, and set INGEST_LOCAL to that
   disk.

A plain VM with uv and Python also runs the worker directly, without a container.

## Downstream

The scoring in ../sql reads the curated Parquet. Point it at
`gs://<bucket>/curated/**/*.parquet` to score the whole dataset.
