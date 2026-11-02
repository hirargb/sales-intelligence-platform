"""Incremental, idempotent ingestion of Shodan scan files from GCS.

Design (the four words the brief asks for):

  streaming    DuckDB reads each file straight from GCS and streams it through;
               the whole corpus is never loaded at once.
  idempotent   each source file is keyed by its GCS content hash (md5). A hash
               already in the manifest is skipped, so re-delivery is a no-op.
  incremental  only files whose hash is new are processed; the curated dataset
               grows, it is never rebuilt.
  resumable    the manifest is the checkpoint. A crash mid-run just means the
               next run reprocesses whatever has no manifest entry yet.

Each source file becomes one Parquet file under curated/ingest_date=YYYY-MM-DD/,
holding the slim scoring columns. Per-file independence is what lets this scale
to thousands of files a month: add more workers, nothing reprocesses the corpus.

Run on a machine with GCS access (a GCE VM uses its service account):

    python ingest.py --bucket ushered-shodan-ingest

Flags:
    --once        process the current inbox and exit (default)
    --reset       ignore the manifest and reprocess everything (for testing)
"""

import argparse
import datetime as dt
import json
import os

import duckdb
from google.cloud import storage

# Scratch directory for the download and DuckDB spill. Override with INGEST_LOCAL
# so the same image can point at a mounted disk on Cloud Batch or GKE.
LOCAL = os.environ.get("INGEST_LOCAL", "/var/tmp/duckdb")

INBOX = "inbox/"
CURATED = "curated/"
MANIFEST = "manifest/ingested.jsonl"

# The slim projection. Identical to sql/10_build_parquet.sql, parameterized on
# the source path so it can read any single file from GCS.
SLIM_SELECT = """
  SELECT
    ip_str, org, isp, asn, domains, hostnames,
    ssl.cert.subject.O    AS cert_subject_o,
    ssl.cert.subject.CN   AS cert_subject_cn,
    ssl.cert.issuer.O     AS cert_issuer_o,
    location.country_code AS country_code,
    location.country_name AS country,
    location.city         AS city,
    cloud.provider        AS cloud_provider,
    port, transport,
    _shodan.module        AS module,
    product, version, cpe23 AS cpe, os, devicetype,
    map_keys(vulns)       AS vuln_cves,
    len(map_keys(vulns))  AS vuln_count,
    list_max(list_transform(map_values(vulns), lambda x: x.cvss)) AS max_cvss,
    coalesce(list_aggr(list_transform(map_values(vulns), lambda x: x.kev),
                       'bool_or'), false) AS any_kev,
    tags,
    ssl.versions          AS ssl_versions,
    ssl.cipher.name       AS ssl_cipher_name,
    ssl.cipher.bits       AS ssl_cipher_bits,
    ssl.cert.expired      AS ssl_cert_expired,
    ssl.cert.expires      AS ssl_cert_expires,
    http.title            AS http_title,
    http.server           AS http_server,
    http.waf              AS http_waf,
    map_keys(http.components) AS http_components,
    timestamp             AS ts
  FROM read_json_auto('{src}',
         maximum_object_size=33554432, format='newline_delimited',
         ignore_errors=true)
"""


def load_manifest(bucket):
    """Return the set of content hashes already ingested."""
    blob = bucket.blob(MANIFEST)
    if not blob.exists():
        return set(), []
    lines = blob.download_as_text().splitlines()
    records = [json.loads(line) for line in lines if line.strip()]
    return {r["md5"] for r in records}, records


def append_manifest(bucket, records, new_record):
    records = records + [new_record]
    body = "\n".join(json.dumps(r) for r in records) + "\n"
    bucket.blob(MANIFEST).upload_from_string(body, content_type="application/x-ndjson")


def new_duckdb():
    con = duckdb.connect()
    con.execute(f"SET temp_directory='{LOCAL}';")
    con.execute("SET memory_limit='12GB';")
    return con


def process_file(con, bucket, blob, ingest_date):
    """Download the file locally, transform with DuckDB, upload the Parquet.

    DuckDB never talks to GCS; the Google client uses the machine's credentials
    for the download and upload, which avoids GCS interoperability keys.
    """
    stem = blob.name.split("/")[-1].replace(".json.zst", "").replace(".json", "")
    local_src = os.path.join(LOCAL, f"{stem}.json.zst")
    local_out = os.path.join(LOCAL, f"{stem}.parquet")
    blob.download_to_filename(local_src)
    con.execute(
        f"COPY ({SLIM_SELECT.format(src=local_src)}) TO '{local_out}' "
        f"(FORMAT parquet, COMPRESSION zstd)"
    )
    rows = con.execute(f"SELECT count(*) FROM read_parquet('{local_out}')").fetchone()[0]
    # Deterministic output name: a reprocess overwrites rather than duplicates.
    out_name = f"{CURATED}ingest_date={ingest_date}/{stem}.parquet"
    bucket.blob(out_name).upload_from_filename(local_out)
    os.remove(local_src)
    os.remove(local_out)
    return f"gs://{bucket.name}/{out_name}", rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()

    client = storage.Client()
    bucket = client.bucket(args.bucket)

    done, records = (set(), []) if args.reset else load_manifest(bucket)
    ingest_date = dt.date.today().isoformat()

    inbox = [b for b in bucket.list_blobs(prefix=INBOX) if not b.name.endswith("/")]
    print(f"inbox: {len(inbox)} file(s); already ingested: {len(done)}")

    con = new_duckdb()
    processed = 0
    for blob in inbox:
        if blob.md5_hash in done:
            print(f"skip (already ingested): {blob.name}")
            continue
        print(f"ingest: {blob.name} ({blob.size/1e9:.1f} GB)")
        out, rows = process_file(con, bucket, blob, ingest_date)
        record = {
            "name": blob.name,
            "md5": blob.md5_hash,
            "size": blob.size,
            "rows": rows,
            "output": out,
            "ingested_at": dt.datetime.utcnow().isoformat() + "Z",
        }
        append_manifest(bucket, records, record)
        records.append(record)
        done.add(blob.md5_hash)
        processed += 1
        print(f"  wrote {rows:,} rows -> {out}")

    print(f"done. processed {processed} new file(s).")


if __name__ == "__main__":
    main()
