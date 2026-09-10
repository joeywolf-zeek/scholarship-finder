# Scholarship Finder

A personal, local-first CLI that matches scholarship listings against your
profile and tracks which ones you've applied to. Built for one person's use,
not as a public product.

## How it works

1. **`profile.json`** describes you (academic info, financial need, field of
   study, geography, identity/background where you're comfortable sharing
   it). This file is gitignored -- it's not meant to leave your machine.
2. **`data/scholarships.json`** is the normalized listing database. It was
   seeded by having Claude Code run WebSearch/WebFetch against public
   sources (see "Refreshing the data" below) -- it is not a one-time
   snapshot, it's meant to be periodically refreshed.
3. **`python cli.py match`** scores every scholarship against your profile
   and writes `reports/report.md` and `reports/report.csv`.
4. **`python cli.py status <id> <new-status>`** records where you are on an
   application (`not started` / `in progress` / `submitted` / `awarded` /
   `rejected`). Statuses persist in `data/status.json` and show up in every
   future report.

## Setup

```
cp profile.example.json profile.json
# edit profile.json with your own answers
python cli.py match
```

No third-party packages are required -- everything here is Python 3
standard library.

## Matching logic

For each scholarship, `scholarship_finder/matcher.py` checks every
eligibility dimension it has structured data for (GPA minimum, state
residency, school location, major, age range, citizenship, and a small set
of known identity criteria -- LGBTQ+, ADHD/learning disability, first-gen
under a strict or broad definition, military dependent, single-parent
background). Each scholarship lands in exactly one tier:

- **Excluded** -- a dimension definitively fails (e.g. your GPA is below a
  published minimum). Never shown in the two main report sections, but kept
  visible at the bottom of the report so you can see *why*.
- **Needs manual review** -- something is missing, ambiguous, low-confidence,
  or references a requirement the matcher doesn't recognize. This tool
  never silently excludes or silently includes an uncertain match.
- **High confidence match** -- everything checkable passes and nothing is
  unresolved.

Within a tier, results sort by soonest real deadline first, then by highest
award amount for same-day deadlines; scholarships with a rolling/unknown
deadline sort after dated ones, and scholarships whose deadline has already
passed sort last (flagged `PASSED` so you don't mistake a stale listing for
an open one -- normal, since scholarship cycles are seasonal).

The matcher never invents an eligibility detail. If a fact isn't in the
data, it either isn't checked, or (when it's the sort of thing that would
normally gate eligibility) it pushes the scholarship into manual review with
a plain-English note about what's unconfirmed.

## Refreshing the data

`python cli.py refresh` prints a reminder, but the actual refresh has to
happen inside a Claude Code session (this CLI has no network access by
design -- it's a pure local scorer). To refresh:

1. Open this repo in Claude Code.
2. Ask it to search for current scholarships matching your `profile.json`
   using WebSearch/WebFetch, the same way the initial dataset was built:
   check official sources first (association/chapter pages, state financial
   aid agencies, university financial aid pages, employer benefits pages),
   skip anything disallowed by robots.txt/terms, and prefer no-essay/rolling
   scholarships plus anything with a near-term deadline.
3. Have it update `data/scholarships.json` in place, keeping existing `id`
   values stable (so your `data/status.json` tracking isn't orphaned) and
   filling in the same schema fields used by the existing entries.
4. Re-run `python cli.py match`.

## Data confidence and dates

Every scholarship record carries a `data_confidence` field and a free-text
`deadline_note`. Search-engine summaries are not the same as the funder's
own page, and scholarship deadlines move year to year -- when in doubt an
entry is marked `low` confidence and routed to manual review rather than
presented as a sure thing. Always confirm the live details on the linked
page before spending time on an application.

## Privacy

`profile.json` can contain sensitive personal data (race/ethnicity, LGBTQ+
identity, disability status, income, immigration status). It's listed in
`.gitignore` and should never be committed. `profile.example.json` is the
sanitized schema template that *is* committed, in case you rebuild this on
another machine.

## Files

```
cli.py                    entry point (match / status / refresh)
scholarship_finder/
  models.py               Scholarship / EligibilityCriteria / profile loading
  matcher.py               eligibility tiers + fit scoring
  report.py                markdown + CSV report rendering
  status_store.py          persisted application-status tracking
data/scholarships.json    the listing database (refreshed periodically)
data/status.json          your application status per scholarship (persists across runs)
profile.json               your profile (gitignored -- not in this repo)
profile.example.json      sanitized schema template (committed)
reports/report.md          latest markdown report (generated by `match`, gitignored -- personal to you)
reports/report.csv          latest CSV report (same)
```
