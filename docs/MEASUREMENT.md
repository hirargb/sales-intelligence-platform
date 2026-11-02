# Measurement

This document measures the ranking quality. The data has no ground-truth buyers.
So it measures the ranking against a transparent rubric, not a human label. The
script is eval/measure.py. The sample is eval/sample_30.csv. Every number is
reproducible from the scored data.

## Method

1. Concrete problem. A company has a concrete, sellable problem when it has a
   known-exploited CVE, an exposed database, or a compromise flag. This is the
   rubric label.
2. Precision at k. Of the top k companies by priority, the share with a concrete
   problem.
3. Lift. The precision at k divided by the base rate in the whole population.
4. Signal contribution. The Spearman rank correlation between each signal and the
   final priority. A signal near zero does not move the ranking.
5. Reason consistency. Each company reason text must match its own columns.

## Results

Population: 57,907 companies. Base rates: concrete problem 21.4 percent,
certificate identity 10.2 percent.

Precision at k, by priority:

| k   | concrete problem | lift | certificate identity |
| --- | ---------------- | ---- | -------------------- |
| 20  | 1.00             | 4.68 | 0.00                 |
| 50  | 1.00             | 4.68 | 0.00                 |
| 100 | 1.00             | 4.68 | 0.01                 |
| 500 | 1.00             | 4.68 | 0.05                 |

Reading:

1. The top of the ranking is all concrete-problem companies, 4.68 times the base
   rate. The scoring puts companies with a named, sellable problem first.
2. Reason consistency: 200 of 200 top companies have a reason text that matches
   their columns exactly. The reasons are true, not generated guesses.

Signal contribution, Spearman with priority:

| signal                 | rho   |
| ---------------------- | ----- |
| worst CVSS             | +0.80 |
| known-exploited CVEs   | +0.68 |
| end-of-life software   | +0.53 |
| exposed hosts, surface | +0.26 |
| remote-desktop         | +0.19 |
| exposed databases      | +0.17 |
| distinct ports         | +0.16 |
| legacy services        | +0.12 |
| compromise flag        | +0.01 |

Reading:

1. CVSS severity, known-exploited CVEs, and end-of-life software drive the order,
   as the weights intend.
2. The compromise flag is near zero. It is too rare, 43 companies, to move the
   ranking. It is kept for the rare maximal-severity case, but it is close to
   dead weight in the order.

## Two honest findings

1. The default priority sort surfaces low-confidence companies first. The
   certificate-identity rate at the top is near zero. The highest-priority
   companies are resolved by domain, not by a certificate. So the
   certificate-identified buyer list comes from the "verified identity only"
   filter, not from the default sort. The app keeps this filter for this reason.
2. Small hosting providers still leak into the top. The top sample includes names
   such as ioflood.net, scalabledns.com, and privatelayer.com. These are small
   hosting providers below the 500-IP resolution threshold. This confirms the
   residual limitation named in data-profile.md. The fix is a maintained hosting
   and ASN-type list, which is the ongoing entity-resolution work.

## The sample

eval/sample_30.csv holds a stratified sample across the priority range: the top,
the middle, and the low end. Each row carries a rubric label, rubric_strong_lead,
which is true when a company has a concrete problem and a certificate identity. A
human can override the label to produce a true hand-labelled set.
