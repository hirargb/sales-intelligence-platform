# Worker image for the ingestion pipeline. Built by Cloud Build, not locally.
FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir duckdb==2.0.0 "google-cloud-storage>=2.18"
COPY ingest.py .

# Scratch path for the download and the DuckDB spill. On a disk-backed runtime
# (Cloud Batch, GKE) mount a volume here and set INGEST_LOCAL to it.
ENV INGEST_LOCAL=/var/tmp/duckdb

ENTRYPOINT ["python", "ingest.py"]
