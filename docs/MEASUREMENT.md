# Measurement

The data has no list of real buyers, so I cannot score the ranking against a truth
label. Instead I measure it against a transparent rubric, and I say plainly what
the rubric is. The script is eval/measure.py, the sample is eval/sample_30.csv, and
every number here is reproducible from the scored data.

## The rubric

A company has a concrete, sellable problem when it has at least one of these: a
known-exploited CVE, an exposed database, or a compromise flag. These are the
things a salesperson can name on a call. That is the label. It is a proxy, not
human judgment, and a reviewer can replace it with a real hand-labelled set.

I then measure four things:

1. Precision at k. Of the top k companies by priority, the share with a concrete
   problem.
2. Lift. That precision divided by the base rate across all companies.
3. Signal contribution. The rank correlation between each signal and the final
   priority. A signal near zero does not move the ranking.
4. Reason consistency. Each company's reason text must match its own columns.

## What it shows

The population is 57,907 companies. In the whole set, 21.4 percent have a concrete
problem and 10.2 percent carry a certificate identity. Against that baseline:

| k   | concrete problem | lift | certificate identity |
| --- | ---------------- | ---- | -------------------- |
| 20  | 1.00             | 4.68 | 0.00                 |
| 50  | 1.00             | 4.68 | 0.00                 |
| 100 | 1.00             | 4.68 | 0.01                 |
| 500 | 1.00             | 4.68 | 0.05                 |

The top of the list is clean. Every one of the top 500 companies has a concrete,
sellable problem, which is 4.68 times the base rate. The reasons hold up too. On
the top 200 companies, all 200 have a reason line that matches their data exactly.
The reasons are read from the columns, so they do not wander.

Signal contribution tells me which signals actually drive the order:

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

CVSS severity, known-exploited CVEs, and end-of-life software do the work, which is
what the weights intend. The compromise flag barely moves anything, at +0.01. It is
too rare, 43 companies in the whole file, to shift the order. I keep it for the
rare maximal case, but it does not drive the ranking.

## Two findings I am not hiding

1. The default sort does not surface the buyer list. At the very top, the
   certificate-identity rate is near zero. The highest-priority companies are
   resolved by domain, not by a certificate, so the clean buyer list comes from the
   "verified identity only" filter, not from the raw sort. The app keeps that filter
   for this reason.
2. Small hosting still leaks in. The top of the sample holds names like
   ioflood.net, scalabledns.com, and privatelayer.com. These are small hosting
   providers that sit below the 500-IP resolution threshold. This is the residual
   limit I named in data-profile.md, and the fix is a maintained hosting and ASN
   list.

## The sample

eval/sample_30.csv is a stratified sample across the priority range: the top, the
middle, and the low end. Each row carries a rubric label, rubric_strong_lead, true
when a company has both a concrete problem and a certificate identity. A human can
override that column to turn it into a real hand-labelled set, which is the next
step on measurement.
