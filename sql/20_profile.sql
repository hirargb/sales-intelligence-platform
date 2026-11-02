-- 20_profile.sql
-- Profile the slim Parquet. Fast, because it reads the small columnar file,
-- not the 114 GiB source. Run it to set the scoring weights from real fill
-- rates, not from guesses.
--
-- Run it in an in-memory session on the box (no lock, no UI needed):
--   /root/bin/duckdb < 20_profile.sql
-- or paste the queries into the DuckDB UI.

CREATE OR REPLACE VIEW slim AS
  SELECT * FROM read_parquet('/root/shodan/slim.parquet');

-- Dedup to the latest banner per service, for every company-level query.
CREATE OR REPLACE VIEW latest AS
  SELECT * FROM (
    SELECT *, row_number() OVER (
             PARTITION BY ip_str, port, transport, module
             ORDER BY ts DESC) AS rn
    FROM slim)
  WHERE rn = 1;

-- One company key, in the resolution order from signals.md:
-- certificate organization, then first domain, then network owner.
-- Do not resolve a cloud-hosted banner by org; fall back to domain only.
CREATE OR REPLACE VIEW scored AS
  SELECT *,
    coalesce(
      nullif(cert_subject_o, ''),
      CASE WHEN len(domains) > 0 THEN domains[1] END,
      CASE WHEN cloud_provider IS NULL THEN nullif(org, '') END
    ) AS company
  FROM latest;


-- 0. Scale.
SELECT
  count(*)                AS banners,
  count(DISTINCT ip_str)  AS distinct_ips,
  count(DISTINCT company) AS distinct_companies
FROM scored;


-- 1. Fill rates. A signal is only as good as its fill rate; this sets weights.
SELECT
  round(100.0 * count(org)            / count(*), 1) AS pct_org,
  round(100.0 * count(cert_subject_o) / count(*), 1) AS pct_cert_org,
  round(100.0 * avg((len(domains)   > 0)::INT), 1)  AS pct_has_domain,
  round(100.0 * avg((vuln_count > 0)::INT), 1)      AS pct_has_vuln,
  round(100.0 * avg(any_kev::INT), 1)               AS pct_kev,
  round(100.0 * count(ssl_cert_expired)/ count(*), 1) AS pct_has_ssl,
  round(100.0 * count(http_title)     / count(*), 1) AS pct_has_http,
  round(100.0 * avg((len(tags) > 0)::INT), 1)       AS pct_has_tags,
  round(100.0 * avg((cloud_provider IS NOT NULL)::INT), 1) AS pct_cloud
FROM scored;


-- Signal 1a. Vulnerability load per company (uses the enriched columns).
SELECT
  company,
  count(DISTINCT ip_str)               AS exposed_ips,
  sum(vuln_count)                      AS total_vuln_hits,
  max(max_cvss)                        AS worst_cvss,
  bool_or(any_kev)                     AS has_known_exploited
FROM scored
WHERE company IS NOT NULL AND vuln_count > 0
GROUP BY company
ORDER BY has_known_exploited DESC, worst_cvss DESC, total_vuln_hits DESC
LIMIT 25;

-- Signal 1b. Most common CVEs across the dataset.
SELECT cve, count(*) AS banners
FROM scored, UNNEST(vuln_cves) AS t(cve)
GROUP BY cve
ORDER BY banners DESC
LIMIT 25;


-- Signal 2. Risky exposed services.
SELECT port, transport,
  count(*)                AS banners,
  count(DISTINCT company) AS companies
FROM scored
WHERE port IN (23, 445, 3389, 5900, 27017, 9200, 6379, 11211, 5432, 3306, 1433)
GROUP BY port, transport
ORDER BY companies DESC;


-- Signal 3. Transport security. Expired certs and obsolete TLS.
SELECT
  round(100.0 * avg(ssl_cert_expired::INT), 1) AS pct_expired_cert,
  round(100.0 * avg((list_contains(ssl_versions, 'TLSv1')
                  OR list_contains(ssl_versions, 'TLSv1.1')
                  OR list_contains(ssl_versions, 'SSLv3'))::INT), 1) AS pct_weak_tls
FROM scored
WHERE ssl_versions IS NOT NULL;


-- Signal 4. Web exposure without a WAF.
SELECT
  count(*) FILTER (WHERE http_title IS NOT NULL)                      AS web_services,
  count(*) FILTER (WHERE http_title IS NOT NULL AND http_waf IS NULL) AS web_without_waf,
  round(100.0 * count(*) FILTER (WHERE http_title IS NOT NULL AND http_waf IS NULL)
        / nullif(count(*) FILTER (WHERE http_title IS NOT NULL), 0), 1) AS pct_without_waf
FROM scored;


-- Signal 5. Software exposure. Build a small end-of-life list from this.
SELECT product, version, count(*) AS banners
FROM scored
WHERE product IS NOT NULL
GROUP BY product, version
ORDER BY banners DESC
LIMIT 40;


-- Signal 6. Shodan tags.
SELECT tag, count(*) AS banners, count(DISTINCT company) AS companies
FROM scored, UNNEST(tags) AS t(tag)
GROUP BY tag
ORDER BY banners DESC
LIMIT 30;


-- Signal 7. Attack-surface size.
SELECT company,
  count(DISTINCT ip_str) AS exposed_ips,
  count(DISTINCT port)   AS distinct_ports,
  count(*)               AS banners
FROM scored
WHERE company IS NOT NULL
GROUP BY company
ORDER BY exposed_ips DESC
LIMIT 25;


-- Signal 8. Market mix.
SELECT country_code, count(DISTINCT company) AS companies
FROM scored
WHERE company IS NOT NULL
GROUP BY country_code
ORDER BY companies DESC
LIMIT 25;
