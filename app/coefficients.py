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
