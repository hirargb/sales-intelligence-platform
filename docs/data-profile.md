# Data profile

This is the by-hand profile of the dataset. It ran before any framework, on the
real file. This is the profile deliverable. Every number comes from a live query
against the full source, materialized to a slim Parquet. The queries are in sql/.
The method is at the end.

## What the data is

The data is Shodan internet-scan banners. One row is one service on one IP and
port. These are not company records. You must reconstruct a company from the
banners. You cannot read it from a field.

- Source: one newline-delimited JSON file, zstd-compressed, 17.6 GB on disk,
  114 GiB raw.
- 89 columns per record. Most are protocol-specific and sparse.
- Slim scoring Parquet: 36 columns, 547 MB. It builds in about two minutes forty
  seconds.

## Scale

- Banners (rows): 13,107,986
- Distinct IP addresses: 4,924,854
- Distinct companies by naive resolution: 348,413. See the warning below.
  Infrastructure inflates this count.

The reader skipped a small number of malformed JSON records (bad unicode
surrogates). The share is tiny. It does not affect the profile.

## The central finding: naive resolution returns hosting providers, not businesses

This is the hidden problem in the brief. If you resolve a company from the filled
fields, you get infrastructure, not buyers.

Fill rates:

- org: 100 percent filled. It is the network owner, so it is the ISP or hosting
  company, not the customer.
- certificate organization (ssl.cert.subject.O): 1.4 percent filled. The
  strongest identity key is almost always empty.
- a domain present: 74.3 percent. The domain is usually the hosting provider
  reverse-DNS domain.
- cloud-hosted: 28.5 percent of banners sit on a known cloud provider.

The most common domains by distinct IP addresses: googleusercontent.com,
amazonaws.com, akamaitechnologies.com, btcentralplus.com, cloudfront.net,
your-server.de, incapdns.net, imperva.com, t-ipconnect.de, flyio.net,
contaboserver.net, vultrusercontent.com, secureserver.net, myvzw.com.

Each one is a cloud, CDN, or ISP. None is a buyer. So the first real step is
entity resolution that separates real companies from infrastructure. It uses a
blocklist of hosting, CDN, and ISP domains and ASNs. It prefers the certificate
organization and the registrable customer domain. It never resolves a
cloud-hosted banner by its network owner. This is the heart of the test. It is
the entity-resolution problem the hiring team works on.

## Signals, measured

### Signal 1: vulnerabilities (strongest need signal)

- 3.2 percent of banners carry at least one known CVE.
- 1.9 percent carry a CVE on the known-exploited list (the KEV flag). This is the
  sharpest subset. A vendor can name the exact exploited weakness.
- The worst CVSS reaches 10.0, and it is common.
- Per banner, keep the CVE list, the count, the worst CVSS, and the KEV flag. A
  reason line can then name the service and the weakness.

Caveat: Shodan infers most CVEs from the software version, not from an exploit
test. A CVE here means the version is known-vulnerable, not proven exploitable.
The reason text must say this.

### Signal 2: risky exposed services

Companies with the service exposed to the open internet:

- RDP 3389: 5,167 companies
- MySQL 3306: 3,229 companies
- SMB 445: 1,253 companies
- Telnet 23: 1,092 companies
- PostgreSQL 5432: 757 companies
- MSSQL 1433: 644 companies
- VNC 5900: 380 companies
- Redis 6379: 364 companies
- Elasticsearch 9200: 349 companies
- MongoDB 27017: 309 companies
- Memcached 11211: 196 companies

These are concrete and easy to sell against. Weight exposed databases above
exposed remote-desktop.

### Signal 3: transport security

Of the services that present TLS:

- 7.6 percent serve an expired certificate.
- 12.3 percent still support obsolete TLS (TLS 1.0, TLS 1.1, or SSL 3.0).

This is a clean proxy for poor security maintenance.

### Signal 4: web exposure without a WAF

- 1,998,685 web services seen.
- 77.3 percent have no detected WAF.

This number is high because WAF detection has many false negatives. Treat it as a
weak signal and keep its weight low. Do not claim a company has no firewall.
Claim only that no WAF was detected.

### Signal 6: Shodan tags (cheap confirmation)

Companies that carry each tag:

- eol-product (end-of-life software): 42,990 companies. Large and valuable.
- self-signed certificate: 17,671 companies.
- vpn: 13,894 companies.
- database exposed: 4,058 companies.
- open-dir: 2,318 companies.
- eol-os: 1,723 companies.
- compromised: 43 companies. c2: 21. malware: 4. doublepulsar: 1. Rare but
  maximal severity.
- honeypot: 1,999 companies, 2.4 percent of all banners. These are decoy systems
  that researchers run. They look maximally vulnerable and are not buyers.
  Exclude every honeypot banner before scoring.

### Signal 8: market mix

Distinct companies by country: United States 90,222, Germany 53,622, France
18,967, United Kingdom 17,888, Netherlands 14,923, Japan 12,958, Brazil 10,283,
Singapore 8,761, Canada 8,491. Use the market as a filter and a tie-breaker, set
by the sales team territory.

## Measurement caveats, stated plainly

1. The company count of 348,413 is inflated by infrastructure. The real count of
   businesses is far lower. It needs the resolution cleanup above.
2. WAF absence is a weak signal, because detection is incomplete.
3. Vulnerabilities are version-inferred, not exploit-proven.
4. The reader skipped a few malformed records.

## Resolution layer: results

The resolution layer is built (sql/30_resolve.sql) and the lists are re-run. It
removes four noise classes, in order of discovery.

1. Hosting, CDN, and ISP domains. This is data-driven: 377 domains seen on more
   than 500 distinct IP addresses each.
2. Honeypots. These are decoy systems. Drop them before scoring.
3. Placeholder and self-signed default certificates. Values such as "Internet
   Widgits Pty Ltd" (the OpenSSL default), "SomeOrganization", and "Default
   Company Ltd".
4. Device-vendor default certificates. Fortinet, SonicWALL, DrayTek, Synology,
   and similar, where one vendor name is really thousands of separate owners.

Before and after:

- Banners after the honeypot drop: 12,863,098.
- Banners that resolve to a company: 988,235. The rest are infrastructure only,
  with no customer domain and no usable certificate, so they do not resolve. This
  is correct, not a loss.
- Candidate companies: 325,094. The distinct count barely moves from the naive
  348,413, because the long tail is many small real domains. The real win is the
  top of the ranking. It no longer shows hosting giants.

The top of the attack-surface list now reads as real companies: Proofpoint,
Salesforce, Meta Platforms, Oracle, Apple, Cisco, Medidata, NTT DOCOMO. The
risky-service list now shows mit.edu, walmart.com, and universities with exposed
remote-desktop and databases.

Residual limitation, stated plainly. Small hosting providers below the 500-IP
threshold still leak into the lists (for example bloom.host, qualityserver.de,
han-solo.net). Full removal needs a maintained hosting and ASN-type list, because
the dataset carries no "this ASN is a hosting provider" flag beyond the cloud
field. The threshold is tunable. A lower threshold risks the drop of a genuine
multi-site company. This is the next refinement, not a blocker.

## Scoring model and results

The scoring is built (sql/40_score.sql). It writes a scored Parquet the app reads
(services/api/data/scored.parquet). There are two scores, kept separate, never
summed into one hidden number.

Need score, 0 to 100. Every point comes from a named signal.

- Known-exploited CVEs (the KEV flag): up to 35 points. The sharpest signal.
- Worst CVSS severity: up to 10.
- Breadth of vulnerable services: up to 15.
- Exposed databases: up to 15.
- Exposed remote-desktop and legacy services: up to 10.
- TLS hygiene (expired certificates and obsolete TLS): up to 8.
- End-of-life software: up to 7.
- Compromised or self-signed flags: up to 10.

Fit score, 0 to 100: surface size up to 70, port diversity up to 30.

Priority = need lifted by fit. So need leads, and a larger account breaks ties.

Each company carries a plain-language reason list, built from its own banners.
For example: "35 services with known-exploited CVEs, worst CVSS 9.8 | 14 expired
certificates, 47 services on obsolete TLS | 383 internet-exposed hosts across 51
ports".

### The central scoring insight

Raw vulnerability volume, aggregated by domain, ranks hosting providers, not
buyers, at every surface size. The exposed and vulnerable machines live on the
customer boxes. So a hosting reverse-DNS domain always looks worse than a
well-run end-company. Volume is not the buyer signal.

The fix is a confidence tier from the resolution source.

1. High confidence: the company presented a real organization name on a
   certificate. This list reads as real companies: Cisco, Comcast, University of
   Wisconsin-Madison, Oracle, Tencent, Medidata, University of Miami, Lumen, Axis
   Communications. This is the buyer list the sales team works first.
2. Lower confidence: resolved only by its own non-infra domain. Keep it, but
   treat a large surface with no certificate identity as a probable hosting
   provider and drop it.

### Remaining noise, stated plainly

Certificate subjects carry a long tail of default values and vendor names. The
stoplist removes control panels (CentOS Web Panel, Vesta, FASTPANEL), appliance
vendors (Fortinet, SonicWALL, ZyXEL), and placeholders (Internet Widgits Pty Ltd,
SomeOrganization). A final name-quality filter then drops the short placeholders
and IP-literal names (for example Company, CERTIFICATE, 127.0.0.1). It keeps
non-Latin names. The long tail of entity-resolution maintenance remains the
ongoing work the hiring team owns, not a one-time fix.

### From candidates to the ranked list

The app ranks multi-host companies. A rule of at least two exposed hosts drops
the single-host long tail. So the 325,094 candidates become 58,078 ranked
companies. A final name-quality filter then removes 171 junk names (placeholders,
single characters, pure numbers, and IP literals). It keeps non-Latin names. This
leaves 57,907 companies in the live app. Of those, 5,895 carry a certificate
identity, the high-confidence buyer list.

## Next step

The thin app is built and live. It is a ranked, filterable list. A salesperson
picks a market and sees each company scores and reasons, with a detail page per
company. The next step is measurement: a small hand-labelled set and precision at
k over the ranking.

## Method

- Build: an in-memory DuckDB session reads the compressed file directly with
  read_json_auto and writes the slim Parquet. This avoids the write lock that the
  running DuckDB UI holds. It never touches the database file or the live UI.
  Script: sql/10_build_parquet.sql.
- Profile: the queries read the small Parquet, so each returns in seconds.
  Script: sql/20_profile.sql.
- Schema: confirmed against the real file before the build, not assumed. Script:
  sql/00_inspect.sql.
