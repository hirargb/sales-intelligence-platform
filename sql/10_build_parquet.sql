-- 10_build_parquet.sql
-- Materialize the slim scoring Parquet from the full Shodan dataset.
--
-- This is the verified build. It was run on the box with:
--   /root/bin/duckdb < build_slim.sql
-- in an in-memory session that reads the compressed file directly. That path
-- avoids the write lock held by the running DuckDB UI, and never touches the
-- shodan.duckdb database file or the live UI.
--
-- Schema facts confirmed against the real file (not assumed):
--   - Nested fields are typed STRUCTs, so access is by dot, not json_extract.
--   - vulns is MAP(cve -> struct(cvss, kev, epss, ...)), so the CVE ids come
--     from map_keys(vulns), and severity comes from the map values.
--   - DuckDB 2.0 lambda syntax is `lambda x: expr`, not `x -> expr`.
--   - Top-level list fields (domains, hostnames, tags, cpe23) are native lists.

COPY (
  SELECT
    -- ---- identity and resolution keys ----
    ip_str,
    org,
    isp,
    asn,
    domains,                                     -- VARCHAR[]
    hostnames,                                   -- VARCHAR[]
    ssl.cert.subject.O    AS cert_subject_o,     -- certificate organization
    ssl.cert.subject.CN   AS cert_subject_cn,
    ssl.cert.issuer.O     AS cert_issuer_o,
    location.country_code AS country_code,
    location.country_name AS country,
    location.city         AS city,
    cloud.provider        AS cloud_provider,     -- non-null means cloud-hosted

    -- ---- service inventory (signals 2, 5, 7) ----
    port,
    transport,
    _shodan.module        AS module,
    product,
    version,
    cpe23                 AS cpe,                 -- VARCHAR[]
    os,
    devicetype,                                  -- firewall, router, webcam, ...

    -- ---- vulnerabilities (signal 1), enriched ----
    map_keys(vulns)       AS vuln_cves,          -- list of CVE ids
    len(map_keys(vulns))  AS vuln_count,
    list_max(list_transform(map_values(vulns), lambda x: x.cvss)) AS max_cvss,
    coalesce(list_aggr(list_transform(map_values(vulns), lambda x: x.kev),
                       'bool_or'), false)        AS any_kev,  -- known exploited

    -- ---- shodan tags (signal 6) ----
    tags,                                        -- VARCHAR[]

    -- ---- transport security (signal 3) ----
    ssl.versions          AS ssl_versions,       -- VARCHAR[], e.g. TLSv1.2
    ssl.cipher.name       AS ssl_cipher_name,
    ssl.cipher.bits       AS ssl_cipher_bits,
    ssl.cert.expired      AS ssl_cert_expired,
    ssl.cert.expires      AS ssl_cert_expires,

    -- ---- web exposure (signal 4) ----
    http.title            AS http_title,
    http.server           AS http_server,
    http.waf              AS http_waf,
    map_keys(http.components) AS http_components, -- list of detected tech

    -- ---- recency, for dedup to the latest banner per service ----
    timestamp             AS ts
  -- ignore_errors skips a few malformed JSON records (bad unicode surrogates).
  -- Without it the pass aborts on the first bad line. The skipped count is
  -- reported after the run; it is a tiny fraction of the file.
  FROM read_json_auto('/root/shodan/2026-10-26T12:00:00.json.zst',
         maximum_object_size=33554432, format='newline_delimited',
         ignore_errors=true)
)
TO '/root/shodan/slim.parquet' (FORMAT parquet, COMPRESSION zstd);
