# BrainDrainWall

Estimates what a person is worth to their country in GDP — the number behind
the "brain drain wall" campaign. Feed it a person (via the Apollo.io People
Enrichment API), and it returns the GDP they've contributed so far and the GDP
lost if they leave / gained if they arrive.

This repo is a **backend JSON API** (FastAPI). No frontend.

## How it works

1. **Enrich** — given a LinkedIn URL (or name + company, or email), Apollo.io
   returns the person's employment history.
2. **Classify** — each role is mapped to a seniority level, job function,
   industry, and a firm tier (systemic banks/megacap tech score highest).
3. **Score** — a log-linear "regression-style" model converts the career into a
   GDP figure. Crucially it captures value *beyond wages*: firm scale converts
   to GDP in proportion to how much of it the role actually steers, so a
   megabank CFO scores far above their salary while a junior at the same bank
   does not. See [METHODOLOGY.md](METHODOLOGY.md).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # then add your APOLLO_API_KEY
uvicorn app.main:app --reload
```

Interactive docs at `http://localhost:8000/docs`.

## Endpoints

### `POST /v1/gdp-impact`
Enrich via Apollo, then score. Provide at least one identifier.

```bash
curl -X POST localhost:8000/v1/gdp-impact \
  -H 'Content-Type: application/json' \
  -d '{"linkedin_url": "https://www.linkedin.com/in/someone", "organization_name": "Goldman Sachs"}'
```

### `POST /v1/gdp-impact/preview`
Score a hand-supplied career history — for testing/integration without calling
Apollo.

```bash
curl -X POST localhost:8000/v1/gdp-impact/preview \
  -H 'Content-Type: application/json' \
  -d '{"name":"Jane Exec","history":[
        {"company":"Goldman Sachs","title":"Chief Financial Officer",
         "start_date":"2017-01-01","current":true,"industry":"Investment Banking"}]}'
```

### `GET /health`
Liveness + model version.

## Response shape

```jsonc
{
  "person":  { "name": "...", "current_title": "...", "current_company": "..." },
  "summary": {
    "historical_gdp_contribution":            567600000,   // already delivered
    "current_annual_gdp_contribution":         60500000,
    "estimated_experience_years":                  18.5,
    "projected_remaining_years":                     24,
    "future_gdp_contribution_undiscounted":  4200000000,   // GDP at stake
    "future_gdp_contribution_npv":           2400000000,   // present value
    "lifetime_gdp_contribution":             4767600000,
    "headline_statement": "Jane has contributed ... If they leave ...",
    "model_version": "0.1.0-calibrated"
  },
  "stints": [ /* per-role breakdown with the multiplier components */ ]
}
```

## Model

The scoring engine and its coefficients are deliberately isolated:

- `app/coefficients.py` — every tunable number (the "regression line").
- `app/model.py` — pure scoring functions over normalised roles.
- `app/parsing.py` — title → seniority/function, company → tier, Apollo payload
  normalisation.

The coefficients are **calibrated priors** designed to be refit on real data
without touching the rest of the codebase. The reasoning, calibration anchors,
and refinement history are in [METHODOLOGY.md](METHODOLOGY.md).

## Tests

```bash
python -m pytest
```
