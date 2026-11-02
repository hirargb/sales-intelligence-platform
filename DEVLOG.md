# Dev loop

This document records how the project was built, what was checked, and where the
output was wrong and corrected. The brief grades the build process, not only the
result.

## How AI was used

An AI coding assistant wrote most of the code and the documents. The human set
the direction, read the data by hand, checked every output, and corrected it. AI
drafted; the human decided.

## What was checked

1. Tests. The API and the SQL scoring have contract tests. See
   services/api/tests/.
2. Measurement. The ranking quality is measured, not assumed. See MEASUREMENT.md
   and eval/measure.py.
3. The profile numbers. Every number in data-profile.md comes from a live query,
   not from a guess.
4. Reason consistency. A check confirms that each reason text matches its own
   columns.

## Where the output was wrong, and the fix

1. Naive resolution returned hosting providers, not buyers. The by-hand profile
   showed that the filled fields point to clouds, CDNs, and ISPs. The fix is the
   resolution layer, which removes infrastructure before scoring.
2. Resolution surfaced device-vendor and placeholder certificates as companies,
   for example Fortinet and Internet Widgits Pty Ltd. The fix is a certificate
   stoplist.
3. The scored output held junk company names, for example "Company", single
   characters, pure numbers, and IP literals. A review of the output caught them.
   The fix is a name-quality filter in the scoring and the data.
4. The first name filter dropped legitimate non-Latin names, for example Chinese
   company names. A check of the dropped rows caught it. The fix uses a unicode
   letter test, so it keeps non-Latin names.
5. The first app deploy returned HTTP 404. The buildpack started the server but
   did not run the build. The fix is a gcp-build script.
6. The measurement showed that the default sort surfaces low-confidence,
   hosting-like companies at the top. This is recorded as an honest finding, and
   the identity filter gives the clean buyer list.

## The loop

The loop was: read the data by hand, form a signal thesis, let AI build the
pipeline and the app, measure the result, find where it was wrong, and correct
it. The corrections above are the value of the loop, not a failure of it.
