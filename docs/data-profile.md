# Data profile

I profiled the file by hand before I wrote any pipeline. This note is what I
found, in the order I found it. Every number comes from a live query against the
full file. The queries are in sql/.

## What the file holds

The file is Shodan internet-scan data. One row is one service seen on one IP and
port. It is a banner, not a company. There is no company table and no company id.
A company is something I had to rebuild from the banners, and that rebuild turned
out to be the whole job.

The shape of it:

- One newline-delimited JSON file, zstd-compressed, 17.6 GB on disk, 114 GiB raw.
- 89 columns per record. Most are protocol-specific and empty on most rows.
- 13,107,986 banners across 4,924,854 distinct IP addresses.

## The first thing I tried, and why it failed

My first instinct was to read the company straight off a field. The data has an
org field, filled on every record, so I grouped by it and ranked the biggest. The
top of the list was Amazon, Google, Akamai, and a row of German hosts. None of
them buys security for the machines in this scan. They rent those machines to the
companies that do.

That one query is the trap the brief points at. The fill rates explain it:

- org is filled on 100 percent of records. It is the network owner, so it is the
  ISP or the host, not the customer.
- ssl.cert.subject.O, the one field that carries a real company name, is filled
  on 1.4 percent of records.
- A domain is present on 74.3 percent of records, but it is usually the host
  reverse-DNS domain, not the customer domain.
- 28.5 percent of banners sit on a known cloud provider.

I then ranked the most common domains by distinct IP. The whole top is
infrastructure: googleusercontent.com, amazonaws.com, akamaitechnologies.com,
btcentralplus.com, cloudfront.net, your-server.de, incapdns.net, imperva.com,
t-ipconnect.de, flyio.net, contaboserver.net, vultrusercontent.com,
secureserver.net, myvzw.com. Not one is a buyer.

So the real first step is not scoring. It is entity resolution: separate the real
companies from the infrastructure they rent. I prefer the certificate
organization and the registrable customer domain. I block the hosting, CDN, and
ISP domains. I never name a company from its cloud network owner, because a
machine in a cloud ASN tells me nothing about who runs it. This is the heart of
the task, and it is the work the hiring team does every day.

## What the signals look like, measured

With resolution in mind, I measured each candidate signal on the real data, to
see which ones the file can actually support.

### Vulnerabilities, the sharpest signal

3.2 percent of banners carry a known CVE. The subset that matters more is the 1.9
percent with a known-exploited CVE, the KEV flag. That is the signal a
salesperson can say out loud: the exact service, and the exact weakness that
attackers are using now. The worst CVSS reaches 10.0, and it is common.

One honest caveat, and it matters. Shodan reads most CVEs from the version
banner, not from an exploit test. So a CVE here means the running version is known
to be vulnerable, not that anyone proved it exploitable. The reason text says
this plainly. A sales claim that overreaches is worse than no claim.

### Services that should never face the internet

I counted the companies that expose each high-risk service to the open internet:

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

These are concrete and easy to sell against. An exposed database is worse than an
exposed remote-desktop port, so it carries more weight.

### Transport security, a proxy for neglect

Of the services that present TLS, 7.6 percent serve an expired certificate, and
12.3 percent still support obsolete TLS (TLS 1.0, TLS 1.1, or SSL 3.0). A company
that does not fix its own front door usually has more problems behind it.

### Web services with no detected firewall

The data shows 1,998,685 web services, and 77.3 percent have no detected WAF. I
distrust this number, and I keep its weight low. WAF detection misses a lot, so a
high rate like this is as much about the detector as about the companies. The
reason text never claims a company has no firewall. It claims only that no WAF was
detected.

### Shodan tags, and the honeypot problem

Shodan already labels many dangerous conditions, so the tags are near-free signal.
Companies per tag: eol-product 42,990, self-signed 17,671, vpn 13,894, database
exposed 4,058, open-dir 2,318, eol-os 1,723. The severe tags are rare:
compromised 43, c2 21, malware 4, doublepulsar 1.

One tag is a trap, not a signal. 1,999 companies, 2.4 percent of all banners,
carry the honeypot tag. These are decoy systems that researchers run to attract
attackers. They look maximally vulnerable and they buy nothing. I drop every
honeypot banner before scoring.

### Where the companies are

Distinct companies by country: United States 90,222, Germany 53,622, France
18,967, United Kingdom 17,888, Netherlands 14,923, Japan 12,958, Brazil 10,283,
Singapore 8,761, Canada 8,491. The market is a filter and a tie-breaker, set by
the sales team territory, not a score.

## Building the resolution layer, and what it changed

I built the resolution layer (sql/30_resolve.sql) and re-ran the lists. It removes
four kinds of noise, in the order I found them:

1. Hosting, CDN, and ISP domains. I did not hand-write this list. I took every
   domain that appears on more than 500 distinct IP addresses, which is 377
   domains, and treated them as infrastructure.
2. Honeypots. Decoy systems, dropped before scoring.
3. Placeholder and self-signed default certificates. Values such as "Internet
   Widgits Pty Ltd" (the OpenSSL default), "SomeOrganization", and "Default
   Company Ltd".
4. Device-vendor default certificates. Fortinet, SonicWALL, DrayTek, Synology,
   and the like, where one vendor name hides thousands of separate owners.

The before and after:

- After the honeypot drop: 12,863,098 banners.
- Banners that resolve to a company: 988,235. The rest are infrastructure only,
  with no customer domain and no usable certificate, so they do not resolve. That
  is correct, not a loss.
- Candidate companies: 325,094. The distinct count barely moves from the naive
  348,413, because the long tail is many small real domains. The win is not the
  count. The win is the top of the list.

The attack-surface list now reads as real companies: Proofpoint, Salesforce, Meta
Platforms, Oracle, Apple, Cisco, Medidata, NTT DOCOMO. The risky-service list now
shows mit.edu, walmart.com, and universities with exposed remote-desktop and
databases. Before resolution, that top was hosting giants.

The honest limit: small hosting providers below the 500-IP threshold still leak
in, for example bloom.host, qualityserver.de, and han-solo.net. The file carries
no "this ASN is a hosting provider" flag beyond the cloud field, so a full fix
needs a maintained hosting and ASN list. The threshold is a dial. Lower it and I
start dropping genuine multi-site companies. This is the next refinement, not a
blocker.

## Scoring, and the second trap

I built the scoring (sql/40_score.sql). It writes a scored Parquet the app reads
(services/api/data/scored.parquet). There are two scores, kept apart, never summed
into one hidden number.

The need score, 0 to 100, with every point from a named signal:

- Known-exploited CVEs, the KEV flag: up to 35. The sharpest signal.
- Worst CVSS severity: up to 10.
- Breadth of vulnerable services: up to 15.
- Exposed databases: up to 15.
- Exposed remote-desktop and legacy services: up to 10.
- TLS hygiene, expired certificates and obsolete TLS: up to 8.
- End-of-life software: up to 7.
- Compromised or self-signed flags: up to 10.

The fit score, 0 to 100: surface size up to 70, port diversity up to 30. Priority
is need lifted by fit, so need leads and a larger account breaks ties.

Then I hit the second trap. Ranking by raw vulnerability volume, grouped by
domain, puts hosting providers back on top, at every surface size. The exposed and
vulnerable machines live on the host's customers' boxes, so a hosting reverse-DNS
domain always looks worse than a well-run end-company. Volume is not the buyer
signal.

The fix is a confidence tier from how the company was resolved:

- High confidence: the company put a real organization name on a certificate.
  This list reads as real companies: Cisco, Comcast, University of
  Wisconsin-Madison, Oracle, Tencent, Medidata, University of Miami, Lumen, Axis
  Communications. This is the list a sales team works first.
- Lower confidence: resolved only by its own non-infra domain. I keep it, but I
  treat a large surface with no certificate identity as a probable host and drop
  it.

A last pass cleaned the names. The certificate subjects carry a long tail of
default values and vendor names. The stoplist removes control panels (CentOS Web
Panel, Vesta, FASTPANEL), appliance vendors (Fortinet, SonicWALL, ZyXEL), and
placeholders (Internet Widgits Pty Ltd, SomeOrganization). A name-quality filter
then drops the short placeholders and the IP-literal names, for example Company,
CERTIFICATE, and 127.0.0.1, while it keeps non-Latin names such as the Chinese
company names. The long tail of this cleanup is the ongoing entity-resolution
work, not a one-time fix.

## From candidates to the list the app shows

The app ranks multi-host companies. A rule of at least two exposed hosts drops the
single-host long tail, so the 325,094 candidates become 58,078 ranked companies.
The name-quality filter then removes 179 junk names, which leaves 57,899 companies
in the live app. Of those, 5,890 carry a certificate identity, the high-confidence
buyer list.

## Named evidence, and what I withhold

A count tells a rep the scale. A name gives them the opener. So each company also
carries the named evidence: the CVEs found on its known-exploited services, the
worst service by CVSS with its product and port, and which databases and
remote-desktops are exposed. The scan file holds all of this, in vuln_cves,
product, and port.

I draw a hard line at host level. The app is public, and a CVE next to a live
hostname is a map of how to break into a real company. So the evidence is
company-level only, with no hostnames and no IP addresses. The CVE and the service
are enough for a credible call, and the host-level detail belongs behind a login
in the real product.

One honesty note on the CVEs. The slim data keeps a per-service known-exploited
flag, not a per-CVE one, so the CVE list is the set found on the flagged services,
where at least one is known-exploited. The app labels it that way.

## What I would do next

The ranking works at the top: the measurement in MEASUREMENT.md shows that the top
of the list is all concrete-problem companies, 4.68 times the base rate, with
reason text that matches the data on every one I checked. The same measurement
shows the two open problems: small hosting still leaks into the raw priority sort,
and the clean buyer list comes from the certificate filter, not the default sort.
The next build is the maintained hosting and ASN list, and a larger hand-labelled
set to measure precision beyond the rubric.

## Method

- Build: an in-memory DuckDB session reads the compressed file directly with
  read_json_auto and writes the slim Parquet (36 columns, 547 MB, about two
  minutes forty seconds). It never touches the running DuckDB UI or its database
  file. Script: sql/10_build_parquet.sql.
- Profile: the queries read the small Parquet, so each returns in seconds. Script:
  sql/20_profile.sql.
- Schema: confirmed against the real file before the build, not assumed. A few
  malformed JSON records, with bad unicode surrogates, were skipped on read; the
  share is tiny. Script: sql/00_inspect.sql.
