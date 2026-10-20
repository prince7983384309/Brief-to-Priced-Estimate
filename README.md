# Brief to Priced Estimate -- Jewelry

A FastAPI service that turns a sales rep's brief (plus an optional reference
photo) into a structured spec, matches it against a small jewelry inventory,
estimates gem count from the photo, turns that into a priced estimate, and
reports a confidence level for every output so low-trust results get
flagged for human review.

**Domain chosen: jewelry** (rings, necklaces, bracelets, earrings, pendants).

## Why jewelry

Gem count maps directly onto "count of small repeated items," the spec
(product type / material / gem count / size) is rich enough to exercise
both extraction and matching meaningfully, and synthetic reference images
(see `backend/scripts/generate_images.py`) give the CV baseline exact
ground truth instead of relying on scraped photos with unknown true counts.

## Project structure

```
brief-to-estimate/
├── .env                      # shared secrets/config -- used by the backend (see below)
├── .env.example
├── .gitignore
├── README.md
├── EVALUATION.md
├── docker-compose.yml         # runs both services together (see "Running with Docker")
│
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, POST /analyze, Swagger at /docs, CORS for the frontend
│   │   ├── config.py           # loads ../.env, env-var settings (provider, model, fallback, keys)
│   │   ├── schemas.py           # all Pydantic models
│   │   ├── extractor.py         # LLM extraction + retry/repair/fallback
│   │   ├── matcher.py            # deterministic weighted inventory matching (no LLM)
│   │   ├── vision.py             # OpenCV gem-count baseline + optional vision-LLM
│   │   ├── confidence.py         # per-field confidence + review-flag logic
│   │   └── pricing.py            # turns a match + gem count into a priced estimate
│   ├── data/
│   │   ├── inventory.csv         # 40-row jewelry catalog
│   │   └── test_cases.json       # 18 labeled evaluation cases (5 with images)
│   ├── images/                   # reference photos used by test cases (synthetic + real)
│   ├── tests/
│   │   ├── test_matcher.py       # matcher correctness + determinism
│   │   └── test_extractor.py     # malformed/empty/erroring model output never crashes
│   ├── scripts/
│   │   ├── generate_images.py    # creates the synthetic reference images with known gem counts
│   │   └── evaluate.py           # runs the evaluation harness, writes evaluation_report.json
│   ├── requirements.txt
│   └── Dockerfile
│
└── frontend/
    ├── index.html                # single-page UI: brief + optional photo -> results
    ├── style.css
    └── app.js                    # calls the backend's /analyze and renders the response
```

The frontend is a plain static page (no build step, no npm) so it's a
double-click away from running -- open `frontend/index.html` directly in a
browser, or serve it (see below). It has no secrets of its own, which is
why `.env` lives at the project root and is only read by the backend.

## Pipeline

```
Brief + optional image
        |
        v
  extractor.py  --(retry / repair / fallback)-->  ExtractedSpec (Pydantic)
        |
        +--> matcher.py (deterministic weighted scoring)  -->  top-3 inventory candidates
        |
        +--> vision.py (classical OpenCV)   -->  CV gem-count estimate
        |
        +--> pricing.py (best match + gem count)  -->  priced estimate
        |
        v
  confidence.py (per-field + CV/LLM agreement + match score)
        |
        v
  AnalyzeResponse  (spec, matches, CV estimate, price estimate, confidence, review flags)
```

## Setup

```powershell
# from the project root, with myenv already created
.\myenv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
copy .env.example .env
# edit .env (at the project root) and set GEMINI_API_KEY (or OPENAI_API_KEY / ANTHROPIC_API_KEY)
```

## Running the backend

```powershell
.\myenv\Scripts\Activate.ps1
cd backend
python app/main.py
```

(`python backend/app/main.py` from the project root also works -- paths are
resolved relative to the file, not the current directory.)

This starts the API on **http://127.0.0.1:8000**. Swagger UI (interactive
API docs) is auto-served at **http://127.0.0.1:8000/docs** (ReDoc at
`/redoc`). For auto-reload during development, use
`uvicorn app.main:app --reload` instead (run from `backend/`).

POST to `/analyze` with form fields `brief` (text) and optionally `image`
(file).

## Running the frontend

With the backend running on port 8000, either:

- Open `frontend/index.html` directly in a browser, or
- Serve it so it behaves like a normal site:
  ```powershell
  cd frontend
  python -m http.server 5500
  ```
  then visit **http://127.0.0.1:5500**.

The backend allows cross-origin requests from any origin in dev (see
`CORS_ALLOWED_ORIGINS` in `.env.example`), so either method works. If you
run the API on a different host/port, update `API_BASE_URL` at the top of
`frontend/app.js`.

## Running tests

```powershell
.\myenv\Scripts\Activate.ps1
cd backend
pytest
```

## Generating the synthetic test images

```powershell
cd backend
python scripts/generate_images.py
```

## Running the evaluation harness

```powershell
cd backend
python scripts/evaluate.py
```

Writes `backend/evaluation_report.json` and prints a metrics summary. See
`EVALUATION.md` for the write-up.

## Running with Docker (stretch goal)

```powershell
docker compose up --build
```

Runs the API on **http://localhost:8000** and the static frontend (via
nginx) on **http://localhost:5500**, wired together already.

## Design decisions

- **Matching is deterministic code, not an LLM call** -- see the module
  docstring in `backend/app/matcher.py`. Same spec + same inventory must
  always return the same ranked candidates, and the score must be
  auditable to a sales rep ("why did this SKU rank #1?").
- **Confidence is derived, not self-reported** -- levels come from how the
  spec was extracted (`llm_success` / `llm_repaired` / `fallback_default`),
  whether fields are plausible, and whether CV and the brief agree on gem
  count -- not from asking the LLM to rate its own confidence.
- **Pricing is a simple heuristic** -- the matched SKU's price, adjusted by
  a fixed percentage per gem of difference between the catalog item and the
  estimated actual gem count. It's intentionally simple and documented in
  `backend/app/pricing.py` rather than hidden behind an LLM call.
- **Backend and frontend are split, with one shared root `.env`.** The
  frontend is a static page with no secrets of its own; `backend/app/config.py`
  loads `../.env` explicitly so the backend works no matter which directory
  it's launched from.
- **CORS is wide open in dev** (`CORS_ALLOWED_ORIGINS=*`) since the frontend
  is served from a different origin/port than the API. Restrict it via
  `.env` before deploying anywhere public.

## Limitations

Measured against the 18-case evaluation set (see `EVALUATION.md` for full
numbers and failure analysis):

- **Classical CV undercounts on dense/overlapping gem arrangements.** Gem
  count MAE is 2.8 across 5 images; the worst case (12 true gems) was
  undercounted by half because overlapping circles merge under Hough
  detection. The baseline is reliable on sparse, well-separated gems and
  gets worse as gem count and clutter increase -- the same reason real
  diamond photos are hard for classical CV.
- **Classical CV can also *over*-count on busy real photos.** A textured
  real-world image (fabric, chain detail, lighting) can trigger thousands
  of false-positive Hough circle detections. `backend/app/main.py` now
  checks the raw CV count against a plausible range (0-200) before it's allowed to
  feed `pricing.py` or the CV/LLM disagreement check -- an implausible
  reading is still shown in the response for transparency, but is excluded
  from pricing and flags its own low-confidence review reason instead of
  silently producing a nonsensical price.
- **The matcher's top-1 hit rate (72%) is partly capped by inventory
  coverage, not matcher quality.** With only 40 rows, some
  material/gem_count/size combinations simply aren't in stock, so the
  "correct" answer is sometimes "no exact match exists."
- **Review flags are score-based, not attribute-based.** A match that gets
  the wrong material or product type but still clears the aggregate score
  threshold on other attributes (size, gem count) is not currently flagged.
  This is the single biggest gap found in failure analysis.
- **Gemini model IDs are a moving target.** `gemini-1.5-flash` and
  `gemini-2.5-flash` were both deprecated/unavailable mid-development;
  `MODEL_NAME` may need updating again later (see `.env.example`).

## AI usage

I used Claude Code (Claude Sonnet 5.5) as a coding agent for nearly all of
this project's implementation: scaffolding the FastAPI service, Pydantic
schemas, the deterministic matcher, the OpenCV baseline, the confidence/
review-flag logic, the pricing heuristic, the pytest suite, and the
evaluation harness, working from the assignment brief end-to-end. I made
the domain call (jewelry) and the structural call (I rejected its first,
more deeply-nested package layout in favor of a flatter one-file-per-concern
structure that's faster to review), and supplied my own Gemini API key.
When wiring that key in, the agent's first two guessed Gemini model IDs
(`gemini-1.5-flash`, then `gemini-2.5-flash`) both 404'd against the live
API because Google had deprecated them for new keys since the agent's
training cutoff -- we debugged that live against the real API and landed
on `gemini-3.8-flash`. I had it run the real evaluation harness rather than
accept invented numbers, and used those actual results (not estimates) to
write the failure analysis above and in `EVALUATION.md`. I also had it add
a small frontend and split the project into `backend/`/`frontend/` with a
shared root `.env` -- while testing through Swagger myself, I found a real
bug (a textured real photo made the classical CV counter return thousands
of false-positive circles, which fed unclamped into the price estimate);
the agent added a plausibility check and I verified the fix by reproducing
the failure with a synthetic noisy image before accepting it.
