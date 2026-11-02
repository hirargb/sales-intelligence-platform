-- 40_score.sql
-- Transparent need/fit scoring on the resolved companies, with a reason list.
--
-- Two scores, kept separate (never summed into one opaque number):
--   NEED (0-100): does this company have a security problem a vendor sells against.
--   FIT  (0-100): is the company a reachable, worthwhile account (surface size).
--   PRIORITY = NEED lifted by FIT, so need leads and a bigger account breaks ties.
--
-- Every point is traceable to a measured signal. The weights are stated here and
-- can be changed in one place. Nothing in the score is hidden.
--
-- Run: /root/bin/duckdb /root/shodan/work.duckdb < 40_score.sql
-- (Rebuilds the resolution tables so the file is self-contained.)

SET memory_limit='10GB';
SET threads=4;
SET temp_directory='/root/shodan/duck_tmp';

CREATE OR REPLACE VIEW slim AS SELECT * FROM read_parquet('/root/shodan/slim.parquet');

-- ---- resolution (same logic as 30_resolve.sql, carrying scoring columns) ----
CREATE OR REPLACE TABLE infra_domains AS
  SELECT d AS domain FROM slim, UNNEST(domains) AS t(d)
  GROUP BY d HAVING count(DISTINCT ip_str) > 500;

CREATE OR REPLACE TABLE dedup AS
  SELECT ip_str, port, transport, module, domains, cert_subject_o,
         product, vuln_cves,
         vuln_count, max_cvss, any_kev, tags, ssl_versions,
         ssl_cert_expired, http_waf, http_title, country_code
  FROM (
    SELECT *, row_number() OVER (
        PARTITION BY ip_str, port, transport, module ORDER BY ts DESC) AS rn
    FROM slim
    WHERE NOT coalesce(list_contains(tags, 'honeypot'), false)
  ) WHERE rn = 1;

CREATE OR REPLACE TABLE companydom AS
  SELECT ip_str, port, transport, module, min(d) AS company_domain
  FROM (SELECT ip_str, port, transport, module, unnest(domains) AS d FROM dedup) e
  LEFT JOIN infra_domains i ON e.d = i.domain
  WHERE i.domain IS NULL AND e.d IS NOT NULL AND e.d <> ''
    AND e.d NOT LIKE '%.arpa' AND e.d <> 'reverse-dns'
    AND NOT regexp_matches(e.d, '(^|[.-])(server|srv|vps|hosting|dedibox|dedi|colo|datacenter|dc)([0-9.-]|$)')
  GROUP BY ip_str, port, transport, module;

CREATE OR REPLACE TABLE resolved AS
  SELECT d.*,
    CASE WHEN d.cert_subject_o IS NOT NULL AND d.cert_subject_o <> ''
          AND NOT regexp_matches(lower(d.cert_subject_o),
            'cloudflare|amazon|google|akamai|microsoft|fastly|incapsula|imperva|letsencrypt|let.s.encrypt|digicert|sectigo|gandi|godaddy|ovh|hetzner|digitalocean|linode|vultr|cloudfront'
            || '|someorganization|unspecified|^example|^default|acme co|default company|internet widgits|widgits|localhost|^test$|^n/?a$|^xx$|^dis$|^na$|self.?signed|management certificate'
            || '|sonicwall|fortinet|draytek|synology|ubiquiti|huawei|^plesk|hestia|bt-panel|cpanel|webmin|mikrotik|tp-link|d-link|axentra|issabel|zte|parallels|starfield'
            || '|centos web panel|vesta|fastpanel|bitnami|cwp|directadmin|cyberpanel|froxlor|ispconfig|virtualmin|technicolor|zyxel|grandstream|watchguard|vmware|icatch|ruckus|netgear|qnap|^asus|zabbix'
            || '|^none$|^unknown$|^organization$|mycompany|^-$|^\.$')
         THEN d.cert_subject_o
         ELSE c.company_domain END       AS company,
    CASE WHEN d.cert_subject_o IS NOT NULL AND d.cert_subject_o <> ''
          AND NOT regexp_matches(lower(d.cert_subject_o),
            'cloudflare|amazon|google|akamai|microsoft|fastly|incapsula|imperva|letsencrypt|let.s.encrypt|digicert|sectigo|gandi|godaddy|ovh|hetzner|digitalocean|linode|vultr|cloudfront'
            || '|someorganization|unspecified|^example|^default|acme co|default company|internet widgits|widgits|localhost|^test$|^n/?a$|^xx$|^dis$|^na$|self.?signed|management certificate'
            || '|sonicwall|fortinet|draytek|synology|ubiquiti|huawei|^plesk|hestia|bt-panel|cpanel|webmin|mikrotik|tp-link|d-link|axentra|issabel|zte|parallels|starfield'
            || '|centos web panel|vesta|fastpanel|bitnami|cwp|directadmin|cyberpanel|froxlor|ispconfig|virtualmin|technicolor|zyxel|grandstream|watchguard|vmware|icatch|ruckus|netgear|qnap|^asus|zabbix'
            || '|^none$|^unknown$|^organization$|mycompany|^-$|^\.$')
         THEN 'cert' WHEN c.company_domain IS NOT NULL THEN 'domain' END AS res_source
  FROM dedup d
  LEFT JOIN companydom c USING (ip_str, port, transport, module);

-- ---- company-level features ----
CREATE OR REPLACE TABLE company_features AS
  SELECT company,
    count(DISTINCT ip_str) AS exposed_ips,
    count(DISTINCT port)   AS distinct_ports,
    count(*)               AS services,
    count(*) FILTER (WHERE any_kev)                 AS n_kev,
    coalesce(max(max_cvss), 0)                      AS worst_cvss,
    count(*) FILTER (WHERE vuln_count > 0)          AS n_vuln_services,
    count(*) FILTER (WHERE port IN (3306,5432,1433,27017,9200,6379,11211)) AS n_db,
    count(*) FILTER (WHERE port IN (3389,5900))     AS n_remote,
    count(*) FILTER (WHERE port IN (23,445))        AS n_legacy,
    count(*) FILTER (WHERE ssl_cert_expired)        AS n_expired,
    count(*) FILTER (WHERE coalesce(list_contains(ssl_versions,'TLSv1'),false)
                        OR coalesce(list_contains(ssl_versions,'TLSv1.1'),false)
                        OR coalesce(list_contains(ssl_versions,'SSLv3'),false)) AS n_weak_tls,
    count(*) FILTER (WHERE coalesce(list_contains(tags,'eol-product'),false)
                        OR coalesce(list_contains(tags,'eol-os'),false))        AS n_eol,
    count(*) FILTER (WHERE coalesce(list_contains(tags,'self-signed'),false))   AS n_selfsigned,
    count(*) FILTER (WHERE coalesce(list_contains(tags,'compromised'),false)
                        OR coalesce(list_contains(tags,'malware'),false)
                        OR coalesce(list_contains(tags,'c2'),false))            AS n_compromised,
    count(*) FILTER (WHERE http_title IS NOT NULL AND http_waf IS NULL)         AS n_no_waf,
    bool_or(res_source = 'cert') AS has_cert_identity,
    mode(country_code) AS country
  FROM resolved
  WHERE company IS NOT NULL
    -- drop residual hosting names the domain threshold missed (heuristic)
    AND NOT regexp_matches(lower(company),
          'server|hosting|\.host|vps|cloud|datacenter|dedibox|dedi|\.arpa|reverse-dns')
  GROUP BY company;

-- ---- named evidence for the sales case (CVE ids and services, no hostnames) ----
-- Hostnames and IPs are left out on purpose. The app is public, and a CVE plus a
-- live hostname would be an attack map. The CVE and the service are enough for a
-- credible sales opener.
CREATE OR REPLACE TABLE evidence AS
WITH base AS (
  SELECT company, product, port, max_cvss, vuln_cves, any_kev
  FROM resolved WHERE company IS NOT NULL
),
kev AS (
  SELECT company, list_slice(list_sort(array_agg(DISTINCT cve)), 1, 6) AS kev_cves
  FROM (SELECT company, unnest(vuln_cves) AS cve FROM base WHERE any_kev AND vuln_cves IS NOT NULL)
  GROUP BY company
),
agg AS (
  SELECT company,
    arg_max(format('{} (port {})', coalesce(nullif(product,''), 'service'), port), max_cvss)
      FILTER (WHERE max_cvss > 0) AS worst_service,
    list_distinct(array_agg(CASE port
        WHEN 3306 THEN 'MySQL (port 3306)' WHEN 5432 THEN 'PostgreSQL (port 5432)'
        WHEN 1433 THEN 'MSSQL (port 1433)' WHEN 27017 THEN 'MongoDB (port 27017)'
        WHEN 9200 THEN 'Elasticsearch (port 9200)' WHEN 6379 THEN 'Redis (port 6379)'
        WHEN 11211 THEN 'Memcached (port 11211)' END)
      FILTER (WHERE port IN (3306,5432,1433,27017,9200,6379,11211))) AS db_services,
    list_distinct(array_agg(CASE port
        WHEN 3389 THEN 'RDP (port 3389)' WHEN 5900 THEN 'VNC (port 5900)'
        WHEN 23 THEN 'Telnet (port 23)' WHEN 445 THEN 'SMB (port 445)' END)
      FILTER (WHERE port IN (3389,5900,23,445))) AS remote_services
  FROM base GROUP BY company
)
SELECT a.company, k.kev_cves, a.worst_service, a.db_services, a.remote_services
FROM agg a LEFT JOIN kev k USING (company);

-- ---- scores and reasons ----
CREATE OR REPLACE TABLE scored AS
  SELECT *,
    least(100, round(
        35 * least(1.0, n_kev / 5.0)                         -- known-exploited CVEs
      + 10 * (worst_cvss / 10.0)                             -- worst severity
      + 15 * least(1.0, ln(1 + n_vuln_services) / ln(51))    -- vulnerable breadth
      + 15 * least(1.0, n_db / 3.0)                          -- exposed databases
      + 10 * least(1.0, (n_remote + n_legacy) / 5.0)         -- remote-desktop/legacy
      +  8 * least(1.0, (n_expired + n_weak_tls) / 5.0)      -- TLS hygiene
      +  7 * least(1.0, n_eol / 5.0)                         -- end-of-life software
      + (CASE WHEN n_compromised > 0 THEN 10
              ELSE 5 * least(1.0, n_selfsigned / 5.0) END)   -- compromise / self-signed
    , 1)) AS need_score,
    round(
        70 * least(1.0, ln(1 + exposed_ips) / ln(201))       -- surface size
      + 30 * least(1.0, distinct_ports / 20.0)               -- port diversity
    , 1) AS fit_score,
    list_filter([
      CASE WHEN n_kev > 0 THEN format('{} service(s) with known-exploited CVEs, worst CVSS {}', n_kev, worst_cvss) END,
      CASE WHEN n_vuln_services > 0 AND n_kev = 0 THEN format('{} service(s) on known-vulnerable software, worst CVSS {}', n_vuln_services, worst_cvss) END,
      CASE WHEN n_db > 0 THEN format('{} database service(s) exposed to the internet', n_db) END,
      CASE WHEN n_remote > 0 THEN format('{} remote-desktop service(s) exposed', n_remote) END,
      CASE WHEN n_legacy > 0 THEN format('{} legacy service(s) exposed (Telnet/SMB)', n_legacy) END,
      CASE WHEN n_expired > 0 OR n_weak_tls > 0 THEN format('{} expired cert(s), {} service(s) on obsolete TLS', n_expired, n_weak_tls) END,
      CASE WHEN n_eol > 0 THEN format('{} service(s) running end-of-life software', n_eol) END,
      CASE WHEN n_compromised > 0 THEN format('{} service(s) flagged compromised/malware', n_compromised) END,
      format('{} internet-exposed host(s) across {} port(s)', exposed_ips, distinct_ports)
    ], lambda x: x IS NOT NULL) AS reasons
  FROM company_features;

-- PRIORITY: need leads, fit lifts it (fit acts as a 0.5 to 1.0 multiplier).
CREATE OR REPLACE TABLE ranked AS
  SELECT *, round(need_score * (0.5 + 0.5 * fit_score / 100.0), 1) AS priority
  FROM scored
  WHERE exposed_ips >= 2            -- drop single-host noise
    -- A large surface with no certificate identity is almost always a hosting
    -- provider resolved by reverse DNS, not one company. Real large companies
    -- carry a certificate org somewhere. Keep small domain-only companies.
    AND NOT (has_cert_identity = false AND exposed_ips > 200)
    -- Drop junk names: placeholders, single tokens, pure numbers, IP literals.
    -- The letter test uses \p{L}, so it keeps non-Latin names (for example CJK).
    AND length(trim(company)) >= 3
    AND regexp_matches(company, '\p{L}.*\p{L}')
    AND NOT regexp_matches(lower(trim(company)),
        '^(company|company ?name|companyname|org ?name|orgname|unknown|none|null|test|testing|localhost|localdomain|example.*|sample.*|default|server|servers|acme|n/?a|host|hostname|admin|administrator|user|users|root|guest|guestuser|internet widgits.*|some ?company|some ?organization|my ?company|your ?company|yourcompany|organization|org|changeme|self[- ]?signed|certificate|ssl|tls|device|router|gateway|ltd|inc|llc|co|corp|corporation|gmbh|srl|spa|pty|waf|system:.*)$');

-- Persist for the thin app (includes the confidence flag so the app can filter).
COPY (SELECT r.company, need_score, fit_score, priority, country,
             exposed_ips, distinct_ports, n_kev, worst_cvss, n_db,
             n_remote, n_legacy, n_eol, n_compromised,
             has_cert_identity, reasons,
             coalesce(e.kev_cves, []::VARCHAR[])        AS kev_cves,
             e.worst_service,
             coalesce(e.db_services, []::VARCHAR[])     AS db_services,
             coalesce(e.remote_services, []::VARCHAR[]) AS remote_services
      FROM ranked r LEFT JOIN evidence e USING (company))
  TO '/root/shodan/scored.parquet' (FORMAT parquet, COMPRESSION zstd);

-- High-confidence leaderboard: companies identified by a real certificate
-- organization. This is the buyer list a sales team would work first.
SELECT company, need_score, fit_score, priority, country,
       exposed_ips, n_kev, n_db, worst_cvss
FROM ranked
WHERE has_cert_identity = true
ORDER BY priority DESC, need_score DESC
LIMIT 25;
