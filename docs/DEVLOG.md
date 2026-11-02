# Dev loop

The brief grades how I build, not only what I ship. So this is an honest account
of the loop: what AI did, what I checked, and the places I caught it wrong.

## How I used AI

An AI coding assistant wrote most of the code and the first draft of most of the
docs. I set the direction, read the data by hand, decided the signals, checked
every output, and corrected it. The split was simple. AI drafted fast. I decided
what was true.

## What I checked, and how

I did not trust the output because it looked right. Each claim has a check behind
it.

- The API and the SQL scoring have contract tests, in services/api/tests/.
- The ranking quality is measured, not asserted. See MEASUREMENT.md and
  eval/measure.py.
- Every number in data-profile.md comes from a live query against the full file,
  not from memory.
- A check confirms that each company's reason text matches its own columns, so the
  reasons cannot drift from the data.

## Where I caught it wrong

This is the part that matters, because it is where the loop earned its keep.

1. The obvious resolution was wrong. Grouping by the filled fields put Amazon,
   Google, and Akamai at the top. They host the exposed machines; they do not buy
   security for them. The fix is the resolution layer, which strips infrastructure
   before scoring.
2. Resolution then surfaced the wrong companies. Device-vendor and placeholder
   certificates showed up as names: Fortinet, Internet Widgits Pty Ltd,
   SomeOrganization. The fix is a certificate stoplist.
3. The scored output still held junk names. "Company", single letters, bare
   numbers, and IP addresses sat in the list. I caught them by reading the output,
   not by trusting it. The fix is a name-quality filter, in the scoring and in the
   data.
4. The first name filter was too blunt. It dropped legitimate non-Latin names,
   including Chinese company names, because it tested for Latin letters. I caught
   it by reading the rows it removed. The fix uses a unicode letter test, so it
   keeps them.
5. The first deploy served a 404. The buildpack started the Next server without
   running the build. The fix is a gcp-build script.
6. The measurement found a real limit. The default priority sort puts
   low-confidence, hosting-like companies at the top, so the clean buyer list comes
   from the certificate filter, not the default order. I recorded this rather than
   hiding it.

## The shape of the loop

Read the data by hand. Form a thesis. Let AI build the pipeline and the app against
it. Measure the result. Find where it is wrong. Fix it, and write down what the fix
taught me. The six corrections above are not failures of the loop. They are the
loop working.
