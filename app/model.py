"""The GDP-footprint scoring engine.

Pure functions over normalised `Stint`s, independent of Apollo so the model can
be unit-tested and refitted in isolation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from . import coefficients as C
from .parsing import Stint


@dataclass
class StintScore:
    company: str
    title: str
    seniority: str
    function: str
    industry_key: str
    tier: int
    years: float
    annual_gdp_contribution: float
    total_gdp_contribution: float
    components: dict[str, float] = field(default_factory=dict)


@dataclass
class ImpactSummary:
    historical_gdp_contribution: float
    current_annual_gdp_contribution: float
    estimated_experience_years: float
    projected_remaining_years: float
    future_gdp_contribution_undiscounted: float
    future_gdp_contribution_npv: float
    lifetime_gdp_contribution: float
    headline_statement: str
    framing: str = C.DEFAULT_FRAMING
    disclaimer: str = C.DISCLAIMER
    model_version: str = C.MODEL_VERSION


def _stint_years(stint: Stint, today: Optional[date] = None) -> float:
    today = today or date.today()
    start = stint.start_date
    end = stint.end_date or (today if stint.current else None)
    if not start:
        return 0.0
    if not end:
        end = today
    days = (end - start).days
    return max(0.0, days / 365.25)


def annual_contribution(stint: Stint) -> tuple[float, dict[str, float]]:
    """Annual GDP value-add for a stint, via the log-linear specification."""
    year = (stint.start_date or date.today()).year

    base = C.BASE_LOG_INTERCEPT
    b_sen = C.SENIORITY_BETA.get(stint.seniority, 0.0)
    b_fun = C.FUNCTION_BETA.get(stint.function, 0.0)
    b_ind = C.INDUSTRY_BETA.get(stint.industry_key, 0.0)
    leverage = C.LEVERAGE_WEIGHT.get(stint.seniority, 0.2) * C.FIRM_TIER_BETA.get(stint.tier, 0.0)
    b_macro = C.MACRO_BETA * math.log(C.macro_index_for_year(year))

    log_value = base + b_sen + b_fun + b_ind + leverage + b_macro
    value = math.exp(log_value)

    components = {
        "base": round(math.exp(base)),
        "seniority_x": round(math.exp(b_sen), 3),
        "function_x": round(math.exp(b_fun), 3),
        "industry_x": round(math.exp(b_ind), 3),
        "firm_leverage_x": round(math.exp(leverage), 3),
        "macro_x": round(math.exp(b_macro), 3),
    }
    return value, components


def score_stint(stint: Stint, today: Optional[date] = None) -> StintScore:
    years = _stint_years(stint, today)
    annual, components = annual_contribution(stint)
    return StintScore(
        company=stint.company,
        title=stint.title,
        seniority=stint.seniority,
        function=stint.function,
        industry_key=stint.industry_key,
        tier=stint.tier,
        years=round(years, 2),
        annual_gdp_contribution=round(annual),
        total_gdp_contribution=round(annual * years),
        components=components,
    )


def _historical_gdp(stints: list[Stint], today: date) -> float:
    """Value-add summed over the career *calendar*, not over stints.

    Roles routinely overlap — a side project, a part-time gig, an advisory seat
    held alongside a main job. Summing each stint's full contribution bills the
    same calendar time several times over (a multi-year part-time role running
    underneath several others would be counted in full on top of them). Instead
    we lay the stints on a timeline and, for every interval, count only the
    single highest-value role active then: a person delivers about one
    full-time-equivalent of value-add at a time, set by their primary role.
    """
    intervals: list[tuple[date, date, float]] = []
    for s in stints:
        if not s.start_date:
            continue
        end = s.end_date or today
        if end <= s.start_date:
            continue
        intervals.append((s.start_date, end, annual_contribution(s)[0]))
    if not intervals:
        return 0.0

    boundaries = sorted({p for iv in intervals for p in (iv[0], iv[1])})
    total = 0.0
    for t0, t1 in zip(boundaries, boundaries[1:]):
        active = [rate for (start, end, rate) in intervals if start <= t0 and end >= t1]
        if active:
            total += max(active) * ((t1 - t0).days / 365.25)
    return total


def _experience_years(stints: list[Stint], today: Optional[date] = None) -> float:
    today = today or date.today()
    starts = [s.start_date for s in stints if s.start_date]
    if not starts:
        return 0.0
    earliest = min(starts)
    ends = [s.end_date or today for s in stints]
    latest = max(ends) if ends else today
    return max(0.0, (latest - earliest).days / 365.25)


def _current_stint(stints: list[Stint]) -> Optional[Stint]:
    current = [s for s in stints if s.current]
    if current:
        return max(current, key=lambda s: s.start_date or date.min)
    dated = [s for s in stints if s.end_date or s.start_date]
    if dated:
        return max(dated, key=lambda s: s.end_date or s.start_date or date.min)
    return stints[0] if stints else None


def _project_future(annual: float, remaining_years: int) -> tuple[float, float]:
    g, r = C.REAL_GROWTH_RATE, C.DISCOUNT_RATE
    undiscounted = 0.0
    npv = 0.0
    for t in range(1, remaining_years + 1):
        grown = annual * (1 + g) ** t
        undiscounted += grown
        npv += grown / (1 + r) ** t
    return undiscounted, npv


def _money(x: float) -> str:
    if x >= 1_000_000_000:
        return f"${x / 1_000_000_000:.1f}B"
    if x >= 1_000_000:
        return f"${x / 1_000_000:.1f}M"
    if x >= 1_000:
        return f"${x / 1_000:.0f}k"
    return f"${x:.0f}"


def _headline(framing, name, historical, future_undisc, future_npv, remaining):
    if framing == "loss":
        return (
            f"{name} has contributed an estimated {_money(historical)} to GDP so far. "
            f"On a modelled basis, the GDP at stake over their remaining {remaining} "
            f"working years is {_money(future_undisc)} (present value {_money(future_npv)}) "
            f"if this activity moves abroad."
        )
    return (
        f"On a modelled estimate, {name}'s economic contribution to date is about "
        f"{_money(historical)}. Over their remaining {remaining} working years, an "
        f"estimated {_money(future_undisc)} of GDP contribution (present value "
        f"{_money(future_npv)}) is what a country gains by attracting this talent — "
        f"and what Britain missed out on."
    )


def compute_impact(
    stints: list[Stint],
    person_name: str = "This person",
    today: Optional[date] = None,
    framing: Optional[str] = None,
) -> tuple[ImpactSummary, list[StintScore]]:
    framing = framing or C.DEFAULT_FRAMING
    today = today or date.today()
    scores = [score_stint(s, today) for s in stints]
    historical = _historical_gdp(stints, today)

    current = _current_stint(stints)
    current_annual = annual_contribution(current)[0] if current else 0.0

    experience = _experience_years(stints, today)
    current_age = C.CAREER_START_AGE + experience
    remaining = int(max(0.0, min(C.RETIREMENT_AGE - current_age, C.MAX_CAREER_YEARS)))

    future_undisc, future_npv = _project_future(current_annual, remaining)
    lifetime = historical + future_undisc

    statement = _headline(framing, person_name, historical, future_undisc, future_npv, remaining)

    summary = ImpactSummary(
        historical_gdp_contribution=round(historical),
        current_annual_gdp_contribution=round(current_annual),
        estimated_experience_years=round(experience, 1),
        projected_remaining_years=remaining,
        future_gdp_contribution_undiscounted=round(future_undisc),
        future_gdp_contribution_npv=round(future_npv),
        lifetime_gdp_contribution=round(lifetime),
        headline_statement=statement,
        framing=framing,
    )
    return summary, scores
