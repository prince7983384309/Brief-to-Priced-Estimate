# Evaluation

Run `python scripts/evaluate.py` from `backend/` to regenerate the numbers
below from `backend/data/test_cases.json` (21 labeled cases, 8 with
reference images -- 5 original synthetic rings plus 3 added specifically to
reproduce a real false-positive bug found through manual testing, see
below). Numbers below are from a live run against Gemini -- see
`backend/evaluation_report.json` for the full per-case breakdown.

Note: Gemini's free tier caps each model at 20 requests/day. Extensive
manual testing that day exhausted the first two model IDs we tried
(`gemini-3.8-flash`, `gemini-flash-lite-latest`); the numbers below are from
a clean run after switching to fresh-quota models (`gemini-3.5-flash-lite`
primary, `gemini-3.1-flash-lite` fallback). When quota is exhausted the
service does not crash -- it degrades to `fallback_default` and flags for
review, which is the "never crash" requirement working correctly, just not
representative of extraction quality.

## Metrics

| Metric | Value |
|---|---|
| Extraction accuracy -- product_type | 100% (21/21) |
| Extraction accuracy -- material | 100% (21/21) |
| Extraction accuracy -- gem_count | 90.5% (19/21) |
| Extraction accuracy -- size | 100% (21/21) |
| Match top-1 hit rate | 71.4% (15/21) |
| Match top-3 hit rate | 81.0% (17/21) |
| Gem count MAE (classical CV, 8 image cases) | 2.25 |
| Review-flag rate | 14.3% (3/21) |

Extraction is strong once a real model is wired up. The two weaker spots
are the classical CV gem counter and the matcher's top-1 hit rate, which
drops whenever the inventory has no row that matches the extracted spec on
every attribute at once.

## Manually found bug, now a regression test

While testing through Swagger, a real photo of a plain ring with **zero**
diamonds produced a classical-CV reading of **7** gems -- false positives
from reflections/highlights on the metal, close enough to the brief's
stated count to stay under the disagreement tolerance and slip through
with **no review flag**. `case_19`/`case_20`/`case_21` in the test set
reproduce this with synthetic images that isolate the cause:

| Case | Real gems | Decoy highlights | CV detected | Flagged? |
|---|---|---|---|---|
| `case_19` (negative control) | 0 | 0 | 0 | -- (correct) |
| `case_20` | 0 | 6 | 2 | **No** |
| `case_21` | 4 | 4 | 6 | **No** |

The negative control (`case_19`) proves the band/image generation itself
isn't the source of false positives -- it's specifically the decoy
highlight circles (simulating specular reflections on real metal) that
Hough circle detection picks up as if they were gems, exactly as suspected
from the real-photo case.

## Failure analysis (3 worst failures)

1. **Case ID: `case_20`** -- **What happened:** A ring with explicitly
   zero real gems (brief: "no stones") but 6 decoy reflection-highlights in
   the image. Extraction correctly said `gem_count: 0`. The classical CV
   counter detected 2 "gems" that don't exist. No review flag was raised.
   **Why:** CV-vs-LLM disagreement is diff-based (tolerance 3), so a
   0-vs-2 gap passes silently even though it's categorically wrong (none
   vs. some) -- this is the same mechanism that caused the real-photo
   failure, now isolated and reproducible with known ground truth.
   **What I'd change:** Treat a CV count of 0 as a privileged signal --
   if the brief says "no stones"/"plain" and CV detects a small nonzero
   count, don't silently trust the CV value for pricing, or lower the
   disagreement tolerance specifically when the brief-stated count is 0.

2. **Case ID: `case_21`** -- **What happened:** 4 real gems plus 4 decoy
   reflections; CV detected 6 (a 50% overcount). No review flag, and the
   wrong count also contributed to missing the expected top-1 match.
   **Why:** Same root cause as `case_20`, but compounding with imperfect
   gem-count-based matching once the CV number is wrong.
   **What I'd change:** Same fix as above, plus a second classical method
   (contour/blob counting) that's less sensitive to bright circular
   highlights than Hough circles, taking the more conservative of the two
   counts rather than trusting Hough alone.

3. **Case ID: `case_12`** -- **What happened:** A silver bracelet, 0 gems,
   size 7 (text-only, no image). Extraction was fully correct. The
   inventory has no silver 0-gem bracelet, only a gold one (`BRC-006`), so
   top-1 and top-3 both missed the "expected" SKU -- arguably correct
   matcher behavior given what's actually in stock, not a bug.
   **Why:** This is an inventory-coverage gap, not an extraction or
   matching bug: with only 40 rows, several material x gem_count
   combinations simply aren't represented, capping the achievable top-1/
   top-3 hit rate regardless of matcher quality.
   **What I'd change:** Grow the inventory to cover more combinations, or
   have the review logic flag "no inventory row matches the spec on every
   attribute" even when a partial match clears the score threshold, so a
   sales rep knows a custom/special order may be needed.

## Next steps

- **Highest priority:** fix the reflection false-positive gap demonstrated
  by `case_20`/`case_21` above -- either a brief-says-zero override, a
  second classical method taken as the conservative estimate, or enabling
  the already-stubbed vision-LLM comparison (`VISION_LLM_ENABLED=true` in
  `backend/app/vision.py`) specifically to cross-check CV on gem counts
  near zero or on "plain"/"no stones" briefs.
- Grow the inventory past 40 rows (or widen attribute coverage) so
  top-1/top-3 hit rate reflects matcher quality rather than catalog gaps.
- Make confidence/review logic attribute-aware (flag specific-field
  mismatches on the top match) instead of only checking the aggregate
  match score and a flat CV/LLM count-difference threshold.
- Add more adversarial briefs (typos, multiple products in one message,
  conflicting numbers) to stress the extractor further.
- When running the harness against Gemini's free tier, space out calls or
  use a paid tier -- 20+ cases in one run can exhaust the daily per-model
  quota mid-run (as happened once during this project).
