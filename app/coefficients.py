"""Calibrated coefficients for the GDP-footprint model.

The model is log-linear (a regression specification estimated structurally
rather than on labelled microdata). See METHODOLOGY.md for the derivation,
calibration anchors, and refinement history. Every number here is a tunable
prior: replace these dicts with fitted coefficients to upgrade the model
without touching any other code.

    ln(annual_gdp_contribution) =
        BASE_LOG_INTERCEPT
        + SENIORITY_BETA[level]
        + FUNCTION_BETA[function]
        + INDUSTRY_BETA[industry]
        + LEVERAGE_WEIGHT[level] * FIRM_TIER_BETA[tier]   # capital/scale leverage
        + MACRO_BETA * ln(MACRO_INDEX[decade])
"""

import math

MODEL_VERSION = "0.1.0-calibrated"

# ---------------------------------------------------------------------------
# FRAMING & DISCLAIMER (legal/ASA)
# ---------------------------------------------------------------------------
# Every figure this service emits is a MODELLED ESTIMATE, never a statement of
# fact about a named individual — required to keep the public counter defensible
# to the ASA. The default narrative framing is "what Britain missed out on"
# (about the founder's success), not "GDP loss caused by you leaving" (which
# carries defamation risk against individuals). The punchier "loss" framing
# remains available where the audience/use-case makes it appropriate.
DEFAULT_FRAMING = "missed_out"   # "missed_out" (defensible default) | "loss"

DISCLAIMER = (
    "Modelled estimate produced by an economic model from public career data — "
    "not a statement of fact about any individual. See the methodology for how "
    "it is calculated."
)


# Reference worker: mid-level individual contributor, generalist function,
# present-day macro regime, small/SMB employer. Anchored to ~US GDP-per-worker
# (~$165k) discounted toward the wage floor for a non-leveraged role.
BASE_LOG_INTERCEPT = math.log(150_000)

# Additive in log space => multiplicative on the dollar figure.
SENIORITY_BETA = {
    "entry": -0.70,
    "junior": -0.30,
    "mid": 0.00,
    "senior": 0.35,
    "manager": 0.50,
    "senior_manager": 0.75,
    "director": 1.10,
    "vp": 1.70,
    "partner": 1.90,
    "owner": 1.40,
    "founder": 2.00,
    "clevel": 2.50,
}

# How much of a firm's scale/capital leverage a person at this level actually
# steers. A megabank CEO captures it all (1.0); a junior captures almost none.
# This is what stops a graduate at Goldman scoring like the CFO.
LEVERAGE_WEIGHT = {
    "entry": 0.10,
    "junior": 0.15,
    "mid": 0.20,
    "senior": 0.35,
    "manager": 0.45,
    "senior_manager": 0.55,
    "director": 0.70,
    "vp": 0.85,
    "partner": 0.90,
    "owner": 0.90,
    "founder": 1.00,
    "clevel": 1.00,
}

FUNCTION_BETA = {
    "engineering": 0.20,
    "product": 0.25,
    "research": 0.30,
    "finance": 0.50,
    "executive": 0.45,
    "sales": 0.30,
    "marketing": 0.15,
    "operations": 0.10,
    "legal": 0.20,
    "consulting": 0.35,
    "medical": 0.25,
    "hr": 0.00,
    "public": -0.10,
    "general": 0.00,
}

INDUSTRY_BETA = {
    "finance": 0.40,
    "technology": 0.35,
    "energy": 0.30,
    "healthcare": 0.25,
    "consulting": 0.30,
    "real_estate": 0.20,
    "telecom": 0.15,
    "media": 0.10,
    "manufacturing": 0.10,
    "retail": 0.00,
    "education": -0.20,
    "government": -0.20,
    "nonprofit": -0.30,
    "general": 0.00,
}

# Firm scale/systemic-importance tiers. Curated tier-5 names + size/revenue
# heuristics live in parsing.py. The dollar impact of a tier only lands in
# proportion to LEVERAGE_WEIGHT above.
FIRM_TIER_BETA = {
    0: -0.50,  # micro / unknown (<50 staff)
    1: 0.00,   # SMB (<500)
    2: 0.60,   # mid-market (<5k)
    3: 1.20,   # large enterprise (<25k)
    4: 1.80,   # global leader / F500 (<100k)
    5: 2.60,   # systemic: bulge-bracket banks, megacap tech, top-tier funds
}

# Macroeconomic context by decade, normalised so the 2010s = 1.0. A stand-in
# for the productivity / interest-rate / asset-price regime in which the value
# was created. Swap for a real per-year series (TFP, real rates) when available.
MACRO_INDEX = {
    1970: 0.65,
    1980: 0.75,
    1990: 0.85,
    2000: 0.95,
    2010: 1.00,
    2020: 1.05,
}
MACRO_BETA = 1.00

# Forward projection (what is lost if they leave / gained if they arrive).
CAREER_START_AGE = 22
RETIREMENT_AGE = 65
REAL_GROWTH_RATE = 0.04   # productivity + promotion drift
DISCOUNT_RATE = 0.03      # real social discount rate for NPV
MAX_CAREER_YEARS = 45


def macro_index_for_year(year: int) -> float:
    decade = (year // 10) * 10
    decade = min(max(decade, 1970), 2020)
    return MACRO_INDEX[decade]


# ---------------------------------------------------------------------------
# FOUNDER / STARTUP MODEL
# ---------------------------------------------------------------------------
# For a founder, the GDP at stake is not their salary leverage but the expected
# economic footprint of the *company they build* — and, if they leave, build
# abroad instead. This is a probabilistic (power-law) model: most startups fail,
# a few are modest exits, a tiny fraction are superstars that carry the return.
#
# Currency: GBP (the campaign and the leaving estimate are UK-specific). Anchors
# come from the Adam Smith Institute "Profitable Peripherals" report (the 18.8%
# UK tax wedge; the multiplier framing of jobs/taxes supported) and from VC
# outcome data (~80% fail / ~19% modest / ~1% home run; power-law returns).
# See METHODOLOGY.md sections 7-8. Every number is a tunable prior.

FOUNDER_CURRENCY = "GBP"

# Outcome buckets implement Path 2 (VC multiples). Probabilities sum to 1.0.
# Each bucket carries a representative *conditional* company profile.
OUTCOME_BUCKETS: dict[str, dict[str, float]] = {
    # high failure rate; tiny, short-lived footprint, no exit.
    "failure": {
        "probability": 0.70,
        "avg_employees": 2.5,
        "peak_employees": 4,
        "lifespan_years": 2.5,
        "exit_value": 0.0,
    },
    # "reasonable exit": a real business, modest acquisition.
    "modest_exit": {
        "probability": 0.27,
        "avg_employees": 22,
        "peak_employees": 40,
        "lifespan_years": 8,
        "exit_value": 20_000_000,
    },
    # superstar / (near-)unicorn: carries the cohort.
    "superstar": {
        "probability": 0.03,
        "avg_employees": 250,
        "peak_employees": 500,
        "lifespan_years": 12,
        "exit_value": 750_000_000,
    },
}

# Path 1: per-startup economic activity.
GVA_PER_EMPLOYEE = 90_000          # UK tech GVA/worker (national avg ~£60k)
AVG_STARTUP_SALARY = 55_000        # GBP
LABOUR_SHARE = 0.60                # wages as share of GVA -> rest is surplus
GVA_MULTIPLIER = 1.8               # supply-chain + induced (Type II) GVA
EMPLOYMENT_MULTIPLIER = 2.0        # direct + indirect + induced jobs

# Tax take (Path 1 -> taxes & jobs sustained).
EMPLOYMENT_TAX_WEDGE = 0.188       # ASI report: 2023 UK tax wedge, married worker
CORP_OTHER_TAX_RATE = 0.20         # corp tax + VAT share on operating surplus
CGT_EFFECTIVE_RATE = 0.20          # blended UK CGT on founder liquidity event

# Path 3: reinvestment & cohort effects.
FOUNDER_EQUITY_AT_EXIT = 0.20      # founder's average retained stake at exit
REINVEST_FRACTION = 0.30           # of net proceeds recycled into angel/seed
SEED_TO_GVA_MULTIPLIER = 3.0       # GVA catalysed per £ of seed capital (speculative)

# Path 4: listings / financial-ecosystem effect (superstar bucket only). An IPO
# sustains advisory, asset-management, legal and trading activity. Modelled as a
# share of market cap captured as UK financial-services GVA over the listing's
# life. The most speculative term; the ASI report documents the LSE's decline
# (market cap $4.3tn 2007 -> $3tn 2024) as a self-reinforcing loss of this base.
IPO_PROBABILITY_SUPERSTAR = 0.40
FINANCIAL_ECOSYSTEM_GVA_RATE = 0.20  # fraction of market cap as lifetime UK fin-GVA

# Default annual outflow used by the national aggregate. See METHODOLOGY.md §8.
# Companies House: ~3,800 directors emigrated Oct-2024..Jul-2025 (~4,500/yr
# annualised, +40% YoY); high-growth/VC-backed founders are a subset.
FOUNDERS_LEAVING_PER_YEAR_BROAD = 4000
FOUNDERS_LEAVING_PER_YEAR_HIGH_GROWTH = 300
