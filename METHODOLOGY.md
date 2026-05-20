# Methodology: Estimating a Person's GDP Footprint from Career History

This document explains how BrainDrainWall converts a LinkedIn-style career
history into a GDP figure — the number we put on the wall when someone leaves
or arrives. It is written to be defended in public.

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

**Round 3 — leverage interaction (current).** Introduced `λ[level]`, the share
of firm scale a role actually commands. A junior at Goldman now scores like a
junior; the CFO absorbs the firm's systemic scale. The sanity panel lands in
defensible ranges and the ordering is monotone in seniority within a firm —
both checked in `tests/test_model.py`.

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
