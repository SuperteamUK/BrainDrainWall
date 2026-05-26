"""Founder / startup GDP-impact model.

When a founder leaves the country, what is lost is not their salary but the
expected economic footprint of the company they would have built here. This
module computes that expectation over a power-law of outcomes, implementing the
four pathways requested for the campaign:

  Path 1  per-startup economic activity (jobs, wages, procurement, taxes)
  Path 2  VC outcome multiples (failure / modest exit / superstar)
  Path 3  reinvestment & cohort effects (exits recycled into new startups)
  Path 4  listings / financial-ecosystem effect (LSE depth, fees, fin-services jobs)

All figures are GBP. Closed-form expected values (no simulation) keep it fast
and auditable. See METHODOLOGY.md §7-8.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import coefficients as C
from .parsing import Stint


@dataclass
class BucketResult:
    bucket: str
    probability: float
    lifetime_gva: float          # direct+indirect GVA over the company's life
    reinvestment_gva: float      # Path 3
    ecosystem_gva: float         # Path 4
    total_gva: float
    peak_jobs_supported: float   # direct+indirect at peak
    total_tax: float             # employment + corp/VAT + CGT over life


@dataclass
class FounderImpact:
    currency: str
    expected_gva_footprint: float        # expected lifetime GDP (GVA) at stake
    expected_peak_jobs_supported: float
    expected_total_tax: float
    expected_exit_value: float
    buckets: list[BucketResult]
    realized_current_company: Optional[dict] = None
    headline_statement: str = ""


def _bucket_footprint(name: str, params: dict[str, float]) -> BucketResult:
    p = params["probability"]
    avg_emp = params["avg_employees"]
    peak_emp = params["peak_employees"]
    years = params["lifespan_years"]
    exit_value = params["exit_value"]

    # Path 1: direct economic activity over the company's life.
    direct_gva = avg_emp * C.GVA_PER_EMPLOYEE * years
    lifetime_gva = direct_gva * C.GVA_MULTIPLIER

    total_wages = avg_emp * C.AVG_STARTUP_SALARY * years
    employment_tax = total_wages * C.EMPLOYMENT_TAX_WEDGE
    operating_surplus = max(0.0, direct_gva - total_wages)
    corp_tax = operating_surplus * C.CORP_OTHER_TAX_RATE

    peak_jobs = peak_emp * C.EMPLOYMENT_MULTIPLIER

    # Path 3: founder liquidity event -> CGT + capital recycled into new startups.
    reinvestment_gva = 0.0
    cgt = 0.0
    if exit_value > 0:
        proceeds = exit_value * C.FOUNDER_EQUITY_AT_EXIT
        cgt = proceeds * C.CGT_EFFECTIVE_RATE
        net_proceeds = proceeds - cgt
        reinvestment_gva = net_proceeds * C.REINVEST_FRACTION * C.SEED_TO_GVA_MULTIPLIER

    # Path 4: listings / financial-services ecosystem (superstar only).
    ecosystem_gva = 0.0
    if name == "superstar" and exit_value > 0:
        ecosystem_gva = exit_value * C.FINANCIAL_ECOSYSTEM_GVA_RATE * C.IPO_PROBABILITY_SUPERSTAR

    total_gva = lifetime_gva + reinvestment_gva + ecosystem_gva
    total_tax = employment_tax + corp_tax + cgt

    return BucketResult(
        bucket=name,
        probability=p,
        lifetime_gva=round(lifetime_gva),
        reinvestment_gva=round(reinvestment_gva),
        ecosystem_gva=round(ecosystem_gva),
        total_gva=round(total_gva),
        peak_jobs_supported=round(peak_jobs, 1),
        total_tax=round(total_tax),
    )


def _money(x: float) -> str:
    if x >= 1_000_000_000:
        return f"£{x / 1_000_000_000:.1f}bn"
    if x >= 1_000_000:
        return f"£{x / 1_000_000:.1f}m"
    if x >= 1_000:
        return f"£{x / 1_000:.0f}k"
    return f"£{x:.0f}"


def _realized_current_company(stints: list[Stint]) -> Optional[dict]:
    """If Apollo gave us the founder's current company size, score it directly
    (Path 1 on actuals) rather than relying on the expected distribution."""
    current = next((s for s in stints if s.current and s.employees), None)
    if not current or not current.employees:
        return None
    emp = current.employees
    annual_gva = emp * C.GVA_PER_EMPLOYEE * C.GVA_MULTIPLIER
    annual_wages = emp * C.AVG_STARTUP_SALARY
    annual_tax = annual_wages * C.EMPLOYMENT_TAX_WEDGE + max(
        0.0, emp * C.GVA_PER_EMPLOYEE - annual_wages
    ) * C.CORP_OTHER_TAX_RATE
    return {
        "company": current.company,
        "employees": emp,
        "annual_gva": round(annual_gva),
        "annual_jobs_supported": round(emp * C.EMPLOYMENT_MULTIPLIER, 1),
        "annual_tax": round(annual_tax),
    }


def is_founder(stints: list[Stint]) -> bool:
    return any(s.seniority in ("founder", "owner") for s in stints)


def compute_founder_impact(
    stints: list[Stint], person_name: str = "This founder"
) -> FounderImpact:
    buckets = [_bucket_footprint(name, p) for name, p in C.OUTCOME_BUCKETS.items()]

    exp_gva = sum(b.probability * b.total_gva for b in buckets)
    exp_jobs = sum(b.probability * b.peak_jobs_supported for b in buckets)
    exp_tax = sum(b.probability * b.total_tax for b in buckets)
    exp_exit = sum(
        C.OUTCOME_BUCKETS[b.bucket]["probability"] * C.OUTCOME_BUCKETS[b.bucket]["exit_value"]
        for b in buckets
    )

    statement = (
        f"In expectation, {person_name} builds a company worth {_money(exp_gva)} in "
        f"lifetime GDP, sustaining ~{round(exp_jobs)} jobs and {_money(exp_tax)} in tax. "
        f"If they found abroad instead, that is the UK's loss."
    )

    return FounderImpact(
        currency=C.FOUNDER_CURRENCY,
        expected_gva_footprint=round(exp_gva),
        expected_peak_jobs_supported=round(exp_jobs, 1),
        expected_total_tax=round(exp_tax),
        expected_exit_value=round(exp_exit),
        buckets=buckets,
        realized_current_company=_realized_current_company(stints),
        headline_statement=statement,
    )


@dataclass
class NationalImpact:
    currency: str
    founders_per_year: int
    expected_gva_per_founder: float
    annual_gdp_at_stake: float
    annual_jobs_at_stake: float
    annual_tax_at_stake: float
    cumulative_gdp_at_stake: float
    horizon_years: int
    headline_statement: str = ""


def compute_national_impact(
    founders_per_year: int = C.FOUNDERS_LEAVING_PER_YEAR_HIGH_GROWTH,
    horizon_years: int = 5,
) -> NationalImpact:
    per = compute_founder_impact([])
    annual_gdp = per.expected_gva_footprint * founders_per_year
    annual_jobs = per.expected_peak_jobs_supported * founders_per_year
    annual_tax = per.expected_total_tax * founders_per_year
    cumulative = annual_gdp * horizon_years

    statement = (
        f"At ~{founders_per_year} high-growth founders leaving per year, the UK forgoes an "
        f"estimated {_money(annual_gdp)} of GDP, ~{round(annual_jobs):,} jobs and "
        f"{_money(annual_tax)} of tax per annual cohort — "
        f"{_money(cumulative)} over {horizon_years} years."
    )

    return NationalImpact(
        currency=C.FOUNDER_CURRENCY,
        founders_per_year=founders_per_year,
        expected_gva_per_founder=per.expected_gva_footprint,
        annual_gdp_at_stake=round(annual_gdp),
        annual_jobs_at_stake=round(annual_jobs),
        annual_tax_at_stake=round(annual_tax),
        cumulative_gdp_at_stake=round(cumulative),
        horizon_years=horizon_years,
        headline_statement=statement,
    )
