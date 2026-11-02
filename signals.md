# Candidate signals

This document lists the buying-intent signals, ranked. Each signal shows its
evidence and its source fields. This is the signal thesis for the scoring model.

The dataset is Shodan internet-scan data. One row is one service banner on one IP
and port. The data shows a company exposed attack surface. It is not a company
profile. Each signal is derived, not read from a field. The work turns banners
into a per-company view.

## How to read this

Each signal has six parts.

1. Hypothesis: the plain reason a salesperson cares.
2. Fields: the columns in the slim Parquet that supply it.
3. Compute: the method that turns rows into a per-company value.
4. Strength: the weight it carries, and the reason.
5. Axis: need (the company has a problem) or fit (the company is a good account).
6. Caveat: the condition that makes it wrong.

The model keeps two axes separate. It never sums them into one hidden number.
Need answers one question: does the company have a problem. Fit answers another:
is the company a good account. A company can score high on one axis and low on
the other. The sales team sees both.

## Step zero: resolve devices to companies

A signal has no meaning until it joins to a company. One company owns many IP
addresses, under different names, across cloud and on-premises. So resolution
comes first.

The resolution keys, in order of trust:

1. ssl.cert.subject.O and ssl.cert.subject.CN. The organization on a TLS
   certificate is a strong, self-declared identity.
2. domains and hostnames. The registrable domain joins to a company and to a
   later DNS enrichment.
3. org and asn. These show ownership of the IP block. They work for on-premises.
   They are weak for cloud, because many tenants share one cloud ASN.

Rule: never resolve a company by a cloud ASN alone. A device in a cloud ASN does
not show who runs it. Use the certificate organization and the domain instead.
Treat org on a known cloud ASN as unreliable.

The unit of scoring is the resolved company. Each signal aggregates the company
banners. First deduplicate to the latest timestamp per ip_str, port, transport,
and module.

## The signals, ranked

### 1. Known vulnerabilities on exposed services (NEED, highest weight)

- Hypothesis: a company with public CVEs on internet-facing services has a named
  problem. This is the clearest "needs help now".
- Fields: vulns, product, version, cpe.
- Compute: per company, count the distinct CVEs across services. Weight by
  severity. Keep the worst few as named evidence. Do not only count. A
  salesperson must name the service and the CVE.
- Strength: highest. It is direct, specific, and defensible.
- Caveat: Shodan infers some CVEs from the version banner, not from an active
  test. A CVE here means the version is known-vulnerable, not proven
  exploitable. State this in the reason text.

### 2. Risky exposed services (NEED, high weight)

- Hypothesis: some services must not face the open internet. Their presence is a
  hygiene failure that a security vendor sells against.
- Fields: port, transport, module, product.
- Compute: flag the high-risk exposures and count them per company. Examples:
  RDP 3389, Telnet 23, SMB 445, VNC 5900, and unauthenticated databases
  (MongoDB 27017, Elasticsearch 9200, Redis 6379, Memcached 11211). Weight an
  exposed database above an exposed remote-desktop port.
- Strength: high. It is concrete and easy to explain.
- Caveat: some exposures are intentional, or firewalled below the layer Shodan
  sees. Treat it as elevated risk, not proof. Cross-check with tags.

### 3. Weak transport security and certificate rot (NEED, medium-high weight)

- Hypothesis: expired certificates and obsolete TLS show a company that does not
  maintain its front door. Visible neglect usually means more neglect behind it.
- Fields: ssl.versions, ssl.cipher.name, ssl.cipher.bits, ssl.cert.expired,
  ssl.cert.expires.
- Compute: per company, the share of services that support TLS 1.0 or SSLv3, use
  weak ciphers, or serve an expired certificate. Use a ratio, not a raw count, so
  large and small companies compare fairly.
- Strength: medium-high. It is a strong proxy for security maturity and cheap to
  compute.
- Caveat: some legacy systems keep old TLS for a reason. One expired certificate
  on a forgotten host is noise. Use the ratio and a minimum surface size.

### 4. Missing web application firewall on public apps (NEED, medium weight)

- Hypothesis: a public web application with no detected WAF is an
  under-protected surface, and a clean opening for a security pitch.
- Fields: http.waf, http.title, http.server, http.components.
- Compute: per company, count the public HTTP services that look like real
  applications (a title, a known framework in http.components) and have no
  detected WAF.
- Strength: medium. It is a good fit signal and a weaker need signal.
- Caveat: WAF detection has false negatives. No detection is not proof of no WAF.
  Keep the weight low.

### 5. End-of-life software and operating systems (NEED, medium weight)

- Hypothesis: software past its support date gets no more security patches. This
  is a standing risk that a vendor addresses.
- Fields: product, version, cpe, os.
- Compute: match product and version against a small end-of-life reference list
  for common server software and operating systems. Count the matches per
  company.
- Strength: medium. It is strong where it hits, but it needs a curated list.
- Caveat: version strings are inconsistent and sometimes false. Keep the list
  small and high-confidence.

### 6. Shodan risk tags (NEED, medium weight, cheap)

- Hypothesis: Shodan already labels many dangerous conditions. These labels are
  free signal.
- Fields: tags.
- Compute: per company, the presence and count of tags such as self-signed,
  expired, compromised, malware, ics, and vpn. Weight by tag severity.
- Strength: medium, and almost free. It is a good cross-check on signals 2 and 3.
- Caveat: tag coverage is uneven. Use tags to confirm other signals, not as the
  only basis for a high score.

### 7. Attack-surface size (FIT, scaling weight)

- Hypothesis: a larger exposed surface means more to defend, and usually a larger
  company with budget. It scales the opportunity.
- Fields: ip_str, port, hostnames, domains.
- Compute: per company, the distinct exposed IP addresses, the distinct open
  ports, and the distinct hosts.
- Strength: a fit multiplier, not a need signal. A large surface with no problems
  is a mature target. A large surface with problems is the best target.
- Caveat: cloud inflates the IP count. Count the distinct resolved hosts and
  domains, not the raw IP addresses.

### 8. Market and segment fit (FIT, filter)

- Hypothesis: the sales team sells into specific markets and company sizes. A
  high-need company in the wrong country is not a lead.
- Fields: location.country_code, location.country, location.city.
- Compute: set a primary market per company from the dominant location of its
  services. Use it as a filter and a tie-breaker, not a score.
- Strength: a gate, not a point score.
- Caveat: a cloud region is not a headquarters. Treat the location as the service
  location. Prefer certificate and domain evidence for the market.

## The email-authentication extension (not in this dataset)

SPF, DKIM, and DMARC are DNS TXT records. Shodan scan banners do not contain
them. This dataset shows mail-server banners on ports 25, 465, and 587, and
whether mail TLS is present. It does not show the SPF or DMARC policy.

So the email-auth signal is a planned enrichment, not a column. The method: take
the resolved domains, run one DNS lookup per domain for the SPF, DMARC, and MX
records, and score a missing or weak DMARC policy as a need signal. This step
runs as a small, separate, idempotent step, keyed by domain, after resolution.
Leave it out of the first version if time is short. Name it in the write-up as
the next signal.

## What the data cannot support (dropped on purpose)

Name what you reject. These signals were considered and dropped.

1. Actual breach or compromise status. A banner does not show it. The compromised
   tag is the closest proxy, and it is sparse.
2. Security budget or team size. Scan data does not carry it. Attack-surface size
   is a weak proxy only.
3. Intent from hiring or news. This needs a separate data source. It is out of
   scope for this file.
4. Raw banner text mining. The data and http.html blobs are large and low
   signal. Keep them in the full table for on-demand evidence, not in the slim
   Parquet.

## From signals to score

Each company gets two numbers and a reason list.

1. Need score: a transparent weighted sum of signals 1 to 6, each normalized,
   with signal 1 the heaviest.
2. Fit score: from signals 7 and 8, as a multiplier and a market gate.
3. Reasons: the top three to five concrete findings in plain words. Each names
   the service, the port, and the issue.

There is no single hidden score. The ranked list shows the reason each company
ranks, from its own banners.

## Validate without labels

The data has no ground-truth buyers. So measure the ranking, not a label.

1. Hand-label a small set. Pick thirty companies across the score range. Judge by
   eye whether the top ones look exposed.
2. Precision at k. Of the top twenty companies, count how many a human agrees are
   strong leads.
3. Ablation. Remove one signal at a time. Check that the top of the list moves in
   a sensible way. A signal that changes nothing is dead weight.
4. Spot-check the reasons. Each high-ranked company reason text must be true
   against its raw banners. One false reason breaks trust in the whole list.
