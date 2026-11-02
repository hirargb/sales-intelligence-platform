-- 00_inspect.sql
-- Run these on the FAST `sample` view first. They are instant.
-- The goal: learn the real schema and the real types of the nested fields,
-- so the build SQL in 10_build_parquet.sql uses the correct access syntax.
--
-- Paste the output of all three back, and the build SQL gets locked to it.

-- 1. Top-level columns and their types.
DESCRIBE SELECT * FROM sample;

-- 2. One whole row, pretty. Read the shape of the nested objects:
--    location, ssl, http, _shodan, vulns, domains, hostnames, tags.
SELECT * FROM sample LIMIT 1;

-- 3. The types of the nested fields that the build extracts from.
--    If a field shows as JSON or VARCHAR, use the json_extract syntax (the default in 10).
--    If it shows as STRUCT(...), switch that field to dot access (noted in 10).
--    If a name below does not exist, DESCRIBE in query 1 shows the real name.
SELECT
  typeof(location)  AS t_location,
  typeof(ssl)       AS t_ssl,
  typeof(http)      AS t_http,
  typeof(vulns)     AS t_vulns,
  typeof(tags)      AS t_tags,
  typeof(domains)   AS t_domains,
  typeof(hostnames) AS t_hostnames,
  typeof(_shodan)   AS t_shodan
FROM sample
LIMIT 1;
