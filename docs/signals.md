# Candidate signals

This is the signal thesis the scoring is built on. It lists the buying-intent
signals, ranked, with the evidence for each and the fields it comes from. I wrote
it after the by-hand profile, so it reflects what the data can actually support,
not what I wished it held.

The data is Shodan internet-scan banners. One row is one service on one IP and
port. It shows a company's exposed attack surface, not a company profile. So every
signal here is derived, not read off a field. The work is turning banners into a
per-company picture, and I keep two questions apart the whole way through.

## Two questions, never one score

Need asks whether the company has a security problem. Fit asks whether the company
is a good account to chase. I never sum them into one opaque number. A company can
score high on need and low on fit, or the reverse, and a salesperson should see
both. Need is the heavier of the two, because a problem is the reason to call.

Each signal below has six parts: the hypothesis (why a salesperson cares), the
fields it is built from, how to compute it, how much weight it carries, which axis
it serves, and the caveat that keeps it honest.

## First, resolve devices to companies

A signal means nothing until it attaches to a company, and in this data a company
is hard to find. One company owns many IP addresses, under different names, across
cloud and on-premises. So resolution comes first, and it decides everything after
it.

I trust the resolution keys in this order:

1. ssl.cert.subject.O and ssl.cert.subject.CN. The organization on a TLS
   certificate is a strong, self-declared identity.
2. domains and hostnames. The registrable domain is the join key to the company
   and to any later DNS enrichment.
3. org and asn. These show who owns the IP block. They work on-premises. They are
   weak in cloud, where many tenants share one ASN.

The firm rule: never resolve a company from a cloud ASN alone. A device in a cloud
ASN does not say who runs it. I fall back to the certificate organization and the
domain, and I treat org on a known cloud ASN as unreliable.

The unit of scoring is the resolved company. Each signal aggregates that company's
banners, after I deduplicate to the newest reading of each service (the latest
timestamp per IP, port, transport, and module).

## The signals, ranked

### 1. Known vulnerabilities on exposed services

Need signal, highest weight.

- Hypothesis. A company with public CVEs on its internet-facing services has a
  named, active problem. This is the clearest "needs help now".
- Fields. vulns, product, version, cpe.
- Compute. Per company, count the distinct CVEs across services, weight by
  severity, and keep the worst few as named evidence. Do not only count. A rep
  needs to name the service and the CVE.
- Strength. Highest. It is direct, specific, and defensible in a call.
- Caveat. Shodan infers some CVEs from the version, not from an active test. A CVE
  here means the version is known-vulnerable, not proven exploitable. Say so in
  the reason text.

### 2. Risky exposed services

Need signal, high weight.

- Hypothesis. Some services should never face the open internet. Their presence is
  a hygiene failure that a security vendor sells against directly.
- Fields. port, transport, module, product.
- Compute. Flag the high-risk exposures and count them per company. RDP 3389,
  Telnet 23, SMB 445, VNC 5900, and unauthenticated databases (MongoDB 27017,
  Elasticsearch 9200, Redis 6379, Memcached 11211). An exposed database weighs
  more than an exposed remote-desktop port.
- Strength. High. Concrete, visual, easy to explain.
- Caveat. Some exposures are intentional, or firewalled below the layer Shodan
  sees. Treat it as elevated risk, not proof, and cross-check with tags.

### 3. Weak transport security and certificate rot

Need signal, medium-high weight.

- Hypothesis. Expired certificates and obsolete TLS show a company that does not
  maintain its own front door. Visible neglect usually means more neglect behind
  it.
- Fields. ssl.versions, ssl.cipher.name, ssl.cipher.bits, ssl.cert.expired,
  ssl.cert.expires.
- Compute. Per company, the share of services that run TLS 1.0 or SSLv3, use weak
  ciphers, or serve an expired certificate. Use a ratio, not a raw count, so large
  and small companies compare fairly.
- Strength. Medium-high. A strong proxy for security maturity, and cheap.
- Caveat. Some legacy systems keep old TLS for a reason, and one expired
  certificate on a forgotten host is noise. Use the ratio and a minimum surface
  size.

### 4. Missing web application firewall on public apps

Need signal, medium weight.

- Hypothesis. A public web application with no detected WAF is an under-protected
  surface, and a clean opening for a security pitch.
- Fields. http.waf, http.title, http.server, http.components.
- Compute. Per company, count the public HTTP services that look like real
  applications (a title, a known framework in http.components) and show no WAF.
- Strength. Medium. A good fit signal, weaker as pure need.
- Caveat. WAF detection has many false negatives. No detection is not proof of no
  WAF, so keep the weight low.

### 5. End-of-life software and operating systems

Need signal, medium weight.

- Hypothesis. Software past its support date gets no more security patches. That
  is a standing risk a vendor fixes.
- Fields. product, version, cpe, os.
- Compute. Match product and version against a small, high-confidence end-of-life
  list for common server software and operating systems, and count the hits per
  company.
- Strength. Medium. Strong where it hits, but it needs a curated list.
- Caveat. Version strings are inconsistent and sometimes false. Keep the list
  small rather than broad and noisy.

### 6. Shodan risk tags

Need signal, medium weight, and almost free.

- Hypothesis. Shodan already labels many dangerous conditions, so the tags are
  free signal.
- Fields. tags.
- Compute. Per company, the presence and count of tags such as self-signed,
  expired, compromised, malware, ics, and vpn, weighted by severity.
- Strength. Medium, and nearly free. A good cross-check on signals 2 and 3.
- Caveat. Tag coverage is uneven. Use tags to confirm other signals, not as the
  sole basis for a high score.

### 7. Attack-surface size

Fit signal, scaling weight.

- Hypothesis. A larger exposed surface means more to defend, and usually a larger
  company with budget. It scales the opportunity.
- Fields. ip_str, port, hostnames, domains.
- Compute. Per company, the distinct exposed IP addresses, open ports, and hosts.
- Strength. A fit multiplier, not a need signal on its own. A large surface with
  no problems is a mature target. A large surface with problems is the best
  target.
- Caveat. Cloud inflates the IP count. Count the distinct resolved hosts and
  domains, not the raw IP addresses.

### 8. Market and segment fit

Fit signal, filter.

- Hypothesis. The sales team sells into specific markets and sizes. A high-need
  company in the wrong country is not a lead.
- Fields. location.country_code, location.country, location.city.
- Compute. Set a primary market per company from the dominant location of its
  services, and use it as a filter and a tie-breaker, not a score.
- Strength. A gate, not a point score.
- Caveat. A cloud region is not a headquarters. Treat the location as the service
  location, and prefer certificate and domain evidence for the market.

## The email-authentication signal I could not build here

SPF, DKIM, and DMARC live in DNS TXT records. Shodan scan banners do not carry
them. This file shows mail-server banners on ports 25, 465, and 587, and whether
mail TLS is present, but not the SPF or DMARC policy.

So this one is a planned enrichment, not a column. The method is small: take the
resolved domains, run one DNS lookup per domain for the SPF, DMARC, and MX
records, and score a missing or weak DMARC policy as need. It runs as a separate,
idempotent step keyed by domain, after resolution. If time is short, I leave it
out of the first version and name it as the obvious next signal.

## What I rejected, and why

Naming what the data cannot support is part of the work.

1. Real breach status. A banner does not show it. The compromised tag is the
   closest proxy, and it is sparse.
2. Security budget or team size. Scan data does not carry it. Surface size is a
   weak proxy at best.
3. Intent from hiring or news. That needs another data source, out of scope for
   this file.
4. Raw banner-text mining. The data and http.html blobs are large and low signal
   for a first version. I keep them in the full table for on-demand evidence, not
   in the slim Parquet.

## From signals to score

Each company gets two numbers and a reason list. The need score is a weighted sum
of signals 1 to 6, each normalized, with signal 1 the heaviest. The fit score
comes from signals 7 and 8, as a multiplier and a market gate. The reasons are the
top three to five concrete findings in plain words, each naming the service, the
port, and the issue, so a salesperson can open a call with one. There is no single
hidden score, and the ranked list shows why each company ranks, straight from its
own banners.

## Measuring a ranking with no labels

The data has no ground-truth buyers, so I measure the ranking, not a label. The
full results are in MEASUREMENT.md. The method:

1. Precision at k. Of the top companies by priority, how many have a concrete,
   sellable problem, against the base rate.
2. Signal contribution. How much each signal moves the final order. A signal that
   moves nothing is dead weight.
3. Reason spot-check. Every high-ranked company's reason text must be true against
   its raw banners. One false reason breaks trust in the whole list.
4. A hand-labelled set. A human judges a stratified sample across the score range,
   to check the rubric against real judgment.
