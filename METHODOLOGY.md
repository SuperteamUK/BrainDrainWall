# Methodology: Estimating a Person's GDP Footprint from Career History

This document explains how BrainDrainWall converts a LinkedIn-style career
history into a GDP figure. It is written to be defended in public.

> **Status of the figures.** Everything here produces a **modelled estimate**,
> not a statement of fact about any individual. The default public framing is
> *"what Britain missed out on"* (about a founder's success), not *"GDP loss
> caused by an individual leaving"*. Outputs carry a `disclaimer` and a
> `framing` field; the public counter must display the estimate caveat and link
> to this page. See the README's "Responsible use, framing & legal" section.

## 1. The economic question

What is a person "worth" to a country's GDP? Naively, you might use their
salary. But GDP measured by the **income approach** is:

```
GDP = compensation of employees + gross operating surplus (profit/value-add)
      + (taxes − subsidies on production)
```

A worker's wage is only the *first* term. The work they do also generates the
**operating surplus** their employer books, plus **spillovers** into suppliers,
customers and the wider economy. Wages are, on average, a *lower bound* on a
person's marginal product — firms capture part of the surplus. For most
workers the gap is modest. For high-leverage roles it is enormous: a bank
executive who closes a $10bn financing does not see that value in their
paycheck, but the economy does.

So the model must capture three things the user explicitly called out:

1. **Value beyond wages** — the surplus and spillover a role catalyses.
2. **Heavy firm tiering** — a minority of firms (bulge-bracket banks, megacap
   tech, top funds) intermediate disproportionate economic value.
3. **Context** — *when* the work happened: the macro/productivity/rate regime.

## 2. The specification (the "regression line")

We model the **annual GDP contribution** of a single job stint as log-linear —
i.e. the exact functional form an econometrician would fit:

```
ln(annual_gdp_contribution) =
      β0                                  # base: a generalist mid-level worker
    + β_seniority[level]                  # IC … C-suite
    + β_function[function]                # finance/exec/eng/…
    + β_industry[industry]                # sector productivity premium
    + λ[level] · β_firm_tier[tier]        # firm scale, captured in proportion
                                          #   to how much of it the role steers
    + β_macro · ln(macro_index[decade])   # era / rate / asset-price regime
```

Working in logs means each factor is **multiplicative** on dollars, which is
how productivity premia actually compound (a senior person at a top firm in a
high-leverage function is not "senior + firm + function" dollars, they are the
product). The whole career is then:

```
career_footprint = Σ_stints  exp(...) · years_in_stint
```

The single most important design choice is the **λ[level] interaction**: firm
scale only converts into GDP *in proportion to how much of that scale the
person actually steers.* A graduate analyst at Goldman Sachs steers almost none
of the balance sheet (λ ≈ 0.15); the CFO steers it all (λ = 1.0). This is what
stops "worked at a famous company" from dominating the score, and it is the
mechanism behind the "$10bn deal not in their wages" intuition.

The coefficients live in `app/coefficients.py`. They are **calibrated priors**,
not fitted on labelled microdata — see §4 on honesty and §5 on upgrading them.

## 3. Calibration anchors

The coefficients were chosen ("act like an economist, then refine") to hit a
set of anchors drawn from national accounts and the labour-economics
literature:

- **Average worker.** US GDP ÷ employed persons ≈ \$165k of value-add per
  worker. The base intercept (\$150k for a mid-level generalist IC at an SMB in
  the current era) sits just below this — the typical worker generates somewhat
  more GDP than their wage, consistent with labour's ~55–60% share of GDP
  implying an economy-wide wage→value-add multiplier of ≈ 1.7–2.0.
- **Sector premia.** Finance and tech carry the largest value-add-per-worker in
  the national accounts; education, government and non-profits the smallest.
  `β_industry` is signed and sized accordingly.
- **Executive leverage.** Studies of executive marginal product and of
  finance-sector value-added support order-of-magnitude (10×–100×) gaps between
  a frontline worker and a systemically-placed executive. The
  `seniority × firm-tier × λ` stack reproduces this without any single factor
  doing the work.

A sanity panel (reproduced from the test suite):

| Profile                          | ≈ annual GDP contribution |
| -------------------------------- | ------------------------- |
| Mid-level engineer, SMB          | ~\$180k                   |
| Staff engineer, megacap tech     | ~\$0.9M                   |
| Startup founder/CEO              | ~\$1.0M                   |
| Public-school teacher            | ~\$120k                   |
| Megabank CFO                     | ~\$60M                    |

## 4. Refinement history (hypothesis → test → refine)

**Round 1 — wages only.** Hypothesis: GDP footprint ≈ estimated salary.
Rejected: it cannot represent the surplus/spillover the user cares about, and
collapses the gap between a banker and a clerk to their (already compressed)
pay ratio.

**Round 2 — additive multipliers.** Hypothesis:
`wage × seniority × firm_tier × function`, all independent. Rejected after the
sanity panel: a *junior* at a tier-5 firm inherited the firm's full scale and
scored like a director. Firm prestige should not flow to people who don't steer
the firm's capital.

**Round 3 — leverage interaction.** Introduced `λ[level]`, the share
of firm scale a role actually commands. A junior at Goldman now scores like a
junior; the CFO absorbs the firm's systemic scale. The sanity panel lands in
defensible ranges and the ordering is monotone in seniority within a firm —
both checked in `tests/test_model.py`.

**Round 4 — two over-counting fixes (current).** Live testing on a real career
surfaced two ways the model overstated GDP:

1. *Concurrent roles were summed.* Historical contribution added every stint's
   full value over its calendar span, so overlapping roles — a side project, a
   part-time gig, an advisory seat held alongside a day job — billed the same
   years twice or more. In the test case a five-year part-time tutoring role,
   running underneath four other roles, was counted in full *on top* of them.
   Fix: integrate value-add over the career **timeline** — in any interval only
   the single highest-value active role counts, since a person delivers about
   one full-time-equivalent of value-add at a time. `historical` is now the
   union-of-time envelope, not the sum of stints (per-stint figures are still
   reported individually for transparency). Code: `model._historical_gdp`.
2. *Every "Founder" got the high-growth premium.* A title containing "founder"
   earned both the steep founder seniority multiplier (≈7.4×) **and** the ≈£29m
   expected-company footprint — regardless of whether the venture had any
   employees, revenue or scale. A defunct one-person Instagram brand (sold for
   pocket money) scored like a VC-backed startup. Fix: **scale-gate** founders.
   A founder/owner is treated as a company-building founder only with evidence
   of scale (≥ `FOUNDER_SCALE_MIN_EMPLOYEES` employees, or any revenue, or a
   mid-market+ firm tier); otherwise the role is scored as `self_employed` on
   the employee model and triggers **no** founder footprint. This keeps the
   ≈£29m figure on the high-growth founders it was calibrated for (§7-8). Code:
   `parsing._founder_has_scale`; the "Startup founder/CEO ~$1.0M" sanity anchor
   above assumes such a scale-qualified founder.

**Round 5 — founder footprint scales with the observed company (current).**
Scale-gating (Round 4) was binary: every *qualifying* founder then received the
same flat ≈£29m cohort-average footprint, so a founder of a 15-person company and
a founder of a 2,000-person company scored identically. Fix: when we can
**observe** the founder's company size (Apollo enriches the current employer's
headcount), the footprint is the *realised* footprint of **that company** — the
report's jobs → wages → taxes chain on actual headcount over a representative
lifespan, scaling roughly linearly with size — instead of the cohort average. The
generic power-law expectation is kept only when no size is known (and for the
national aggregate, which is a cohort average by construction). The response now
carries `basis` (`observed_company` / `generic_cohort`),
`company_scale_employees`, and an `established_company_footprint` breakdown. Code:
`founder_model._established_company_footprint`. A residual step remains at the
employee-count gate (a venture is either a real company or not), but above it the
footprint is continuous in size — e.g. ≈£25m at 15 staff, ≈£0.3bn at 200, ≈£3.3bn
at 2,000.

## 5. Forward projection (what is lost / gained)

The wall number is forward-looking: the GDP a person *would* contribute over
their remaining working life.

- **Experience** = (latest role end → earliest role start), used to estimate
  age (career start assumed at 22) and therefore remaining years to a
  retirement age of 65 (capped at a 45-year career).
- **Trajectory.** The current annual contribution is grown at a real
  productivity-plus-promotion drift of 4%/yr.
- **Two figures are reported.** An **undiscounted** lifetime sum (the headline
  "GDP at stake") and a **present value** discounted at a 3% real social
  discount rate (the defensible, finance-literate figure).

`historical + future_undiscounted = lifetime_gdp_contribution`.

## 6. Honesty and limitations

- These are **structural, calibrated coefficients**, not estimates from a
  labelled training set. We present the model in regression form because that
  is its true functional shape and because it is built to be *refit*: drop
  fitted β's into `app/coefficients.py` and nothing else changes.
- Apollo enriches firm size/industry for the **current** employer only, so
  historical stints are tiered from a curated systemic-firm list plus name
  heuristics. Unknown private firms default to SMB (tier 1).
- Salary/value-add is inferred from role, not observed. The model is built for
  a campaign's order-of-magnitude storytelling, not for individual financial
  advice.
- Coefficients are USD-denominated and US-economy-anchored. Other countries
  need their own base intercept and macro series.
- **The model reads job titles and firm size, not hours or impact-per-hour.** It
  cannot tell a full-time role from a few-hours-a-week one, so a part-time or
  student job is scored at the full-time base unless its calendar overlaps a
  higher-value role (in which case the timeline rule, §4 Round 4, drops it). A
  genuinely standalone part-time stint will still be overstated; supply explicit
  hours/FTE via the preview endpoint where accuracy matters.
- **Value created outside an employer's books is invisible.** A community
  builder or ecosystem lead who unlocks grants, jobs and companies for *other*
  people generates GDP the model cannot see from their own title and headcount,
  and will be understated. The model measures a person's value-add *within* a
  firm, not network or catalytic effects around them.

---

## 7. The founder / startup model

The §2 model scores an *employee's* value-add. It is the wrong lens for a
**founder**: when a founder leaves, what the country loses is not their salary
but the expected economic footprint of the **company they would have built
here**, and now build abroad. That footprint is power-law distributed — most
startups fail, a few are modest exits, a tiny fraction carry everything — so we
compute an **expectation over outcomes** rather than a point estimate. Code:
`app/founder_model.py`; coefficients in the FOUNDER block of
`app/coefficients.py`. All figures are **GBP** (the campaign is UK-specific).

This footprint is applied only to **scale-qualified** founders (§4, Round 4): a
founder/owner with evidence of a real company — employees, revenue, or a
mid-market+ firm tier. A solo, side or defunct micro-venture is scored on the
employee model as `self_employed` and gets no founder footprint, because the
priors below are calibrated to high-growth, company-building founders and would
otherwise turn a hobby project into a multi-million-pound figure.

The model is the sum of four pathways, each requested for the campaign and each
grounded in the "Profitable Peripherals" report's multiplier methodology (jobs
→ wages → taxes, with the 18.8% UK tax wedge) and standard VC outcome data.

**Path 2 — VC outcome multiples (the spine).** Three outcome buckets, calibrated
to the ~80% fail / ~19% modest / ~1% home-run split observed across VC
portfolios (softened to 70/27/3 to include non-VC founders and "great but not
unicorn" outcomes). Each bucket carries a representative *conditional* company:
average and peak headcount, lifespan, and exit value.

| Bucket       |   p  | avg staff | lifespan | exit value |
| ------------ | ---- | --------- | -------- | ---------- |
| failure      | 0.70 |       2.5 | 2.5 yr   | £0         |
| modest exit  | 0.27 |        22 | 8 yr     | £20m       |
| superstar    | 0.03 |       250 | 12 yr    | £750m      |

**Path 1 — per-startup economic activity.** For each bucket: lifetime direct
GVA = `avg_staff × GVA-per-employee (£90k) × lifespan`, scaled by a Type-II
multiplier (×1.8) for supply-chain and induced activity. Taxes = employment tax
(wages × 18.8% wedge) + corporation/VAT tax (20% of operating surplus). Jobs
sustained = peak staff × employment multiplier (×2.0). This is the report's
"capital → jobs → wages → taxes" chain applied to a company instead of a
capital stock.

**Path 3 — reinvestment & cohort effects.** On an exit, the founder's retained
stake (~20%) is a liquidity event: it pays CGT (~20% blended) and a portion
(~30% of net) is recycled into angel/seed investment, which catalyses new
company GVA (×3 seed-to-GVA). If the founder has left, this recycling — and any
re-founding — happens in the Bay Area, not Britain. The most cohort-defining
term and a deliberately conservative one.

**Path 4 — listings / financial-ecosystem effect (superstar only).** The
largest companies historically list on the LSE, sustaining advisory, asset
management, legal and trading activity — the financial-services jobs the report
documents. We capture this as a share (20%) of a superstar's market cap,
weighted by an IPO probability (40%), accruing as UK financial-services GVA.
The report shows this base eroding (LSE market cap $4.3tn in 2007 → $3tn in
2024 while the US tripled to $53tn) in a self-reinforcing loop: fewer listings →
shallower capital → lower multiples → more firms leave. This is the **most
speculative** term and is flagged as such.

**Expected footprint per founder** = Σ_bucket `p · (lifetime_GVA +
reinvestment_GVA + ecosystem_GVA)`. With the priors above this is **≈ £29m of
lifetime GDP, ~57 jobs, and ~£3.6m of tax** per high-growth founder. When
Apollo returns the founder's *current* company size, we additionally report a
`realized_current_company` footprint scored on actual headcount (Path 1 on
observed data) — higher accuracy where the data exists.

## 8. How many founders/companies leave per year?

`POST /v1/national-impact` multiplies the per-founder expectation by an annual
outflow. Two defensible denominators:

- **Broad (all company directors/owners).** Companies House records show ~3,800
  directors changed their country of residence between Oct 2024 and Jul 2025
  (~4,500 annualised), a ~40% jump on the prior year's 2,712; ~6,000 have left
  since late 2023. Headline: **~3,000–4,500 per year, and accelerating.** Top
  destinations: UAE/Dubai, the US, Monaco.
- **High-growth / VC-backed founders (the model's target).** ~17,000 VC-backed
  startups call the UK home; studies find **3.3–4.3% of European VC-backed
  startups relocate**, ~75% to the US. Cross-referenced with the tech sector
  leading the director exodus, this implies on the order of **a few hundred
  high-growth founders per year** (the default used is **300**).

**Important calibration note.** The ≈£29m per-founder figure is calibrated to
*high-growth / VC-backed* founders. Apply it to the 300 figure (→ ≈£8.6bn GDP,
~17k jobs, ~£1.1bn tax per annual cohort), **not** to the broad 4,000-director
count — most of those directors are not building high-growth companies, so using
the broad number with this coefficient overstates the loss. For the broad
population, lower the per-founder priors accordingly.

These are order-of-magnitude campaign figures built on public estimates, not a
fitted micro-dataset. Every coefficient lives in `app/coefficients.py` for
transparent revision as better data arrives.
