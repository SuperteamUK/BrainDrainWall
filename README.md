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

When the person is a **founder/owner**, the response also carries a
`founder_impact` block: the *expected* GDP footprint of the company they build
(see below), since for founders that dwarfs their salary leverage.

### `POST /v1/national-impact`
Aggregate the loss across founders leaving the country per year.

```bash
curl -X POST localhost:8000/v1/national-impact \
  -H 'Content-Type: application/json' \
  -d '{"founders_per_year": 300, "horizon_years": 5}'
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

## Two models

**Employee model** (`app/model.py`) — the log-linear value-add score described
above, for people on a career ladder.

**Founder / startup model** (`app/founder_model.py`) — for founders, the loss is
the company they'd have built. A power-law expectation over outcomes
(fail / modest exit / superstar) combining four pathways: per-startup economic
activity (jobs, wages, taxes), VC outcome multiples, founder-exit reinvestment &
cohort effects, and the LSE listings / financial-services ecosystem effect.
Currency is GBP; the national aggregate turns this into a modelled GDP figure
per cohort of founders building abroad.

The scoring engines and their coefficients are deliberately isolated:

- `app/coefficients.py` — every tunable number (the "regression line" + the
  founder priors).
- `app/model.py` / `app/founder_model.py` — pure scoring functions.
- `app/parsing.py` — title → seniority/function, company → tier, Apollo payload
  normalisation.

The coefficients are **calibrated priors** designed to be refit on real data
without touching the rest of the codebase. The reasoning, calibration anchors,
and refinement history are in [METHODOLOGY.md](METHODOLOGY.md).

## Tests

```bash
python -m pytest
```

---

# Methodology (for publication)

*This section is written to be published as the "How it's calculated" page the
public counter links to. Plain-English summary; the full technical version with
coefficients and calibration is in [METHODOLOGY.md](METHODOLOGY.md).*

**Every number this tool produces is a modelled estimate, not a statement of
fact about any individual.** It estimates the economic value associated with a
person's career — the value a country gains by attracting talent and founders,
and what Britain missed out on when they built elsewhere.

### For people on a career path

GDP is not just wages. Measured by the income approach, GDP is employee
compensation *plus* the operating surplus (profit/value-add) that work
generates *plus* production taxes. Wages are therefore a floor on a person's
contribution; for senior, high-leverage roles the gap is large. We estimate an
annual contribution from a log-linear model whose factors multiply together:

- **Seniority** — from individual contributor up to C-suite.
- **Function** — e.g. finance and engineering carry higher value-add.
- **Industry** — sector productivity premia.
- **Firm scale, *weighted by seniority*** — a systemic employer's scale only
  counts in proportion to how much of it a role actually steers, so a graduate
  at a global bank does not score like its CFO.
- **Era** — the macroeconomic/productivity regime when the work happened.

This is projected over the person's remaining working years and reported both
undiscounted and as a present value.

### For founders

When a founder builds elsewhere, what a country misses is the *company* — so we
estimate the **expected** economic footprint of the company a founder builds,
across a realistic spread of outcomes (most startups fail, some are modest
exits, a few are runaway successes). Four effects are added together:

1. **Company activity** — jobs, wages, supplier spend and taxes over the firm's
   life, with standard supply-chain/induced multipliers and the UK's 18.8% tax
   wedge.
2. **Outcome multiples** — the venture-capital reality that a small fraction of
   companies generate most of the value.
3. **Reinvestment** — successful founders recycle proceeds into new start-ups
   and often found again; offshore if they have left.
4. **Listings / financial ecosystem** — the largest successes have historically
   listed in London, sustaining financial-services activity; this base is
   eroding in a self-reinforcing way (see sources).

On these assumptions, a representative high-growth founder is associated with
**~£29m of lifetime GDP, ~57 jobs and ~£3.6m of tax** in expectation.

### How many founders are leaving?

UK Companies House records show roughly **3,000–4,500 company directors per
year** moving their residence abroad and accelerating; of these, on the order of
**a few hundred are high-growth/VC-backed founders** (consistent with ~17,000
UK VC-backed start-ups and a 3–4% relocation rate, mostly to the US). The
national figure applies the per-founder estimate to the **high-growth** count,
not the broad director count.

### Key sources

- Adam Smith Institute, *Profitable Peripherals* (2025) — multiplier
  methodology and the LSE/capital-depth decline.
- UK Companies House director-residence data (reported via Rathbones / European
  Business Magazine, 2025).
- BVCA, *VC investment in British start-ups* (2024) — VC-backed population and
  jobs.
- Science|Business (2025) — share of European VC-backed start-ups relocating.
- Venture-capital power-law / outcome-distribution literature.

---

# Responsible use, framing & legal

This is effectively a **public-facing campaign tool naming real people**, so the
following are built in or required before launch:

- **Modelled-estimate labelling (built in).** Every response carries a
  `disclaimer` and a `framing` field, and headlines say "modelled estimate". The
  public counter **must** show this and link to the methodology above — a bare
  real-time £ figure attached to a named person is not substantiable and would
  attract an upheld ASA complaint.
- **Framing (built in, defaults to defensible).** The default framing is
  *"what Britain missed out on"* — about the founder's success — rather than
  *"GDP loss caused by you leaving"*, which risks implying a named individual
  harmed the country (defamation exposure). Set `"framing": "loss"` on a request
  only for contexts where that wording is appropriate; the public site should
  use the default.
- **Privacy / UK GDPR (site responsibility, not in this repo).** Featuring a
  person (photo, name, employer, inferred reasons) processes personal data. A
  live privacy notice, a documented lawful basis (legitimate interests, written
  down), and a one-click "remove me" route are needed.
- **Consent (process, not in this repo).** Get short written sign-off from each
  featured founder on the exact framing and any quote, and keep records. Some
  may dislike the framing and ask not to be featured — honour that.
- **Positioning.** Treat this as a political campaign and expect scrutiny of who
  is behind it; keep the methodology transparent and the figures clearly
  modelled so the work can stand on its own.

None of the above changes the maths — only how the figures are labelled and
presented.
