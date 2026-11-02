-- 30_resolve.sql
-- Entity resolution layer: turn banners into real companies, not infrastructure.
--
-- The problem (from data-profile.md): the org field is the ISP or cloud owner,
-- and most domains are hosting reverse-DNS. Naive resolution returns hosts.
--
-- The method, in three moves:
--   1. Data-driven infra filter. A registrable domain seen on more than 500
--      distinct IPs is hosting, CDN, or ISP, not one company. No hand list.
--   2. Drop honeypots. They are decoys, look maximally vulnerable, never buy.
--   3. Resolve each banner to a company by the certificate organization first
--      (unless it is a known infra or CA org), then the first non-infra domain.
--      A banner with neither is infrastructure-only and does not resolve.
--
-- Run with a disk-backed scratch database so DuckDB can spill (the box has
-- 22 GB and the UI holds about 6 GB, so an in-memory run gets OOM-killed):
--   /root/bin/duckdb /root/shodan/work.duckdb < 30_resolve.sql

PRAGMA memory_limit='10GB';
PRAGMA threads=4;
PRAGMA temp_directory='/root/shodan/duck_tmp';

CREATE OR REPLACE VIEW slim AS
  SELECT * FROM read_parquet('/root/shodan/slim.parquet');

-- 1. Infra domains, straight from the data.
CREATE OR REPLACE TABLE infra_domains AS
  SELECT d AS domain, count(DISTINCT ip_str) AS ips
  FROM slim, UNNEST(domains) AS t(d)
  GROUP BY d
  HAVING count(DISTINCT ip_str) > 500;

-- 2. Latest banner per service, honeypots removed. Only the columns the lists
--    need, to keep memory small. The service key is the dedup key.
CREATE OR REPLACE TABLE dedup AS
  SELECT ip_str, port, transport, module, domains, cert_subject_o,
         vuln_count, max_cvss, any_kev
  FROM (
    SELECT ip_str, port, transport, module, domains, cert_subject_o,
           vuln_count, max_cvss, any_kev,
           row_number() OVER (
             PARTITION BY ip_str, port, transport, module ORDER BY ts DESC) AS rn
    FROM slim
    WHERE NOT coalesce(list_contains(tags, 'honeypot'), false)
  ) WHERE rn = 1;

-- 3a. The first non-infra registrable domain per banner. Also drop reverse-DNS
--     artifacts and small hosting domains the 500 threshold misses.
CREATE OR REPLACE TABLE companydom AS
  SELECT ip_str, port, transport, module, min(d) AS company_domain
  FROM (SELECT ip_str, port, transport, module, unnest(domains) AS d FROM dedup) e
  LEFT JOIN infra_domains i ON e.d = i.domain
  WHERE i.domain IS NULL
    AND e.d IS NOT NULL AND e.d <> ''
    AND e.d NOT LIKE '%.arpa'
    AND e.d <> 'reverse-dns'
    AND NOT regexp_matches(e.d,
          '(^|[.-])(server|srv|vps|hosting|dedibox|dedi|colo|datacenter|dc)([0-9.-]|$)')
  GROUP BY ip_str, port, transport, module;

-- 3b. Resolve. Certificate organization wins, unless it is an infra or CA org,
--     a device-vendor default cert, or a placeholder/self-signed default value.
--     Those are not identities; fall back to the domain instead.
CREATE OR REPLACE TABLE resolved AS
  SELECT d.*,
    coalesce(
      CASE WHEN d.cert_subject_o IS NOT NULL AND d.cert_subject_o <> ''
            AND NOT regexp_matches(lower(d.cert_subject_o),
              -- infra and certificate authorities
              'cloudflare|amazon|google|akamai|microsoft|fastly|incapsula|imperva|letsencrypt|let.s.encrypt|digicert|sectigo|gandi|godaddy|ovh|hetzner|digitalocean|linode|vultr|cloudfront'
              -- placeholder / default certificate subjects
              || '|someorganization|unspecified|^example|^default|acme co|default company|internet widgits|widgits|localhost|^test$|^n/?a$|^xx$|^dis$|^na$|self.?signed|management certificate'
              -- device-vendor default certs (one vendor is many owners)
              || '|sonicwall|fortinet|draytek|synology|ubiquiti|huawei|^plesk|hestia|bt-panel|cpanel|webmin|mikrotik|tp-link|d-link|axentra|issabel|zte|parallels|starfield')
           THEN d.cert_subject_o END,
      c.company_domain
    ) AS company
  FROM dedup d
  LEFT JOIN companydom c USING (ip_str, port, transport, module);


-- Before and after: how much infrastructure was removed.
SELECT
  (SELECT count(*) FROM infra_domains)                               AS infra_domains_found,
  (SELECT count(*) FROM dedup)                                       AS banners_after_honeypot_drop,
  (SELECT count(*) FROM resolved WHERE company IS NOT NULL)          AS banners_resolved,
  (SELECT count(DISTINCT company) FROM resolved WHERE company IS NOT NULL)
                                                                     AS real_companies;


-- Top companies by vulnerability load (real companies only).
SELECT company,
  count(DISTINCT ip_str) AS exposed_ips,
  sum(vuln_count)        AS total_vuln_hits,
  max(max_cvss)          AS worst_cvss,
  bool_or(any_kev)       AS known_exploited
FROM resolved
WHERE company IS NOT NULL AND vuln_count > 0
GROUP BY company
ORDER BY known_exploited DESC, worst_cvss DESC, total_vuln_hits DESC
LIMIT 25;


-- Top companies by risky exposed services (real companies only).
SELECT company,
  count(*) FILTER (WHERE port IN (3389,5900))                            AS remote_desktop,
  count(*) FILTER (WHERE port IN (3306,5432,1433,27017,9200,6379,11211)) AS exposed_databases,
  count(*) FILTER (WHERE port IN (23,445))                               AS legacy_services,
  count(DISTINCT ip_str)                                                 AS exposed_ips
FROM resolved
WHERE company IS NOT NULL
  AND port IN (23,445,3389,5900,27017,9200,6379,11211,5432,3306,1433)
GROUP BY company
ORDER BY (exposed_databases*3 + remote_desktop*2 + legacy_services*2) DESC
LIMIT 25;


-- Top companies by attack-surface size (real companies only).
SELECT company,
  count(DISTINCT ip_str) AS exposed_ips,
  count(DISTINCT port)   AS distinct_ports,
  count(*)               AS services
FROM resolved
WHERE company IS NOT NULL
GROUP BY company
ORDER BY exposed_ips DESC
LIMIT 25;
