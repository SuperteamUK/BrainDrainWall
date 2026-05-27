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
    basis: str = "generic_cohort"               # "observed_company" | "generic_cohort"
    company_scale_employees: Optional[int] = None
    established_company_footprint: Optional[dict] = None
    headline_statement: str = ""
    framing: str = C.DEFAULT_FRAMING
    disclaimer: str = C.DISCLAIMER


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


def _observed_founder_company(stints: list[Stint]) -> Optional[int]:
    """Headcount of the largest company the person actually founded/owns that we
    have a size for. Apollo enriches only the current employer, so in practice
    this is the founder's current company when it is the venture they built."""
    sizes = [s.employees for s in stints if s.seniority in ("founder", "owner") and s.employees]
    return max(sizes) if sizes else None


def _established_company_footprint(employees: int) -> dict:
    """Realised lifetime footprint of an OBSERVED founder company of `employees`
    people: the report's jobs -> wages -> taxes chain on actual headcount over a
    representative company lifespan, plus the founder's exit/reinvestment term.

    Scales with company size, so a 2,000-person company scores far above a
    15-person one (unlike the flat cohort average). Omits the speculative
    listings/ecosystem term — that stays in the generic superstar bucket only.
    """
    n = employees
    years = C.ESTABLISHED_COMPANY_LIFESPAN

    direct_gva = n * C.GVA_PER_EMPLOYEE * years
    lifetime_gva = direct_gva * C.GVA_MULTIPLIER

    total_wages = n * C.AVG_STARTUP_SALARY * years
    employment_tax = total_wages * C.EMPLOYMENT_TAX_WEDGE
    operating_surplus = max(0.0, direct_gva - total_wages)
    corp_tax = operating_surplus * C.CORP_OTHER_TAX_RATE

    exit_value = n * C.VALUATION_PER_EMPLOYEE
    proceeds = exit_value * C.FOUNDER_EQUITY_AT_EXIT
    cgt = proceeds * C.CGT_EFFECTIVE_RATE
    reinvestment_gva = (proceeds - cgt) * C.REINVEST_FRACTION * C.SEED_TO_GVA_MULTIPLIER

    return {
        "employees": n,
        "lifespan_years": years,
        "gva": round(lifetime_gva + reinvestment_gva),
        "lifetime_gva": round(lifetime_gva),
        "reinvestment_gva": round(reinvestment_gva),
        "peak_jobs_supported": round(n * C.EMPLOYMENT_MULTIPLIER, 1),
        "total_tax": round(employment_tax + corp_tax + cgt),
        "exit_value": round(exit_value),
    }


def is_founder(stints: list[Stint]) -> bool:
    """True only for *scale-qualified* founders/owners. parsing.classify_stint
    reclassifies sub-scale founders (no employees/revenue/firm scale) to
    `self_employed`, so a solo or side venture does not trigger the founder
    footprint — that lens is calibrated to high-growth founders (METHODOLOGY §7-8)."""
    return any(s.seniority in ("founder", "owner") for s in stints)


def _founder_headline(framing, name, exp_gva, exp_jobs, exp_tax, observed_employees=None):
    if observed_employees:
        scale = f"the company {name} has built (~{observed_employees:,} staff)"
        if framing == "loss":
            return (
                f"On a modelled basis, {scale} represents {_money(exp_gva)} in lifetime GDP, "
                f"sustaining ~{round(exp_jobs)} jobs and {_money(exp_tax)} in tax. If they build "
                f"their next company abroad, that economic value is lost to the UK."
            )
        return (
            f"On a modelled estimate, {scale} represents ~{_money(exp_gva)} in lifetime GDP, "
            f"sustaining ~{round(exp_jobs)} jobs and {_money(exp_tax)} in tax — what Britain gains "
            f"by keeping its founders, and what it missed out on when they built abroad."
        )
    if framing == "loss":
        return (
            f"On a modelled basis, {name} builds a company worth {_money(exp_gva)} in "
            f"lifetime GDP, sustaining ~{round(exp_jobs)} jobs and {_money(exp_tax)} in tax. "
            f"If they found abroad, that economic value is lost to the UK."
        )
    return (
        f"On a modelled, expected basis, a founder like {name} builds a company worth "
        f"~{_money(exp_gva)} in lifetime GDP, sustaining ~{round(exp_jobs)} jobs and "
        f"{_money(exp_tax)} in tax — what Britain gains by keeping its founders, and "
        f"what it missed out on when they built abroad."
    )


def compute_founder_impact(
    stints: list[Stint], person_name: str = "This founder", framing: Optional[str] = None
) -> FounderImpact:
    framing = framing or C.DEFAULT_FRAMING
    buckets = [_bucket_footprint(name, p) for name, p in C.OUTCOME_BUCKETS.items()]

    # Generic cohort expectation over the power-law of outcomes. This is the
    # right lens when we know nothing about the venture (and for the national
    # aggregate, which averages over a whole cohort of founders).
    generic_gva = sum(b.probability * b.total_gva for b in buckets)
    generic_jobs = sum(b.probability * b.peak_jobs_supported for b in buckets)
    generic_tax = sum(b.probability * b.total_tax for b in buckets)
    generic_exit = sum(
        C.OUTCOME_BUCKETS[b.bucket]["probability"] * C.OUTCOME_BUCKETS[b.bucket]["exit_value"]
        for b in buckets
    )

    # If we can see the company the founder actually built, use ITS realised
    # footprint (scales with headcount) instead of the flat cohort average — so a
    # founder of a 2,000-person company is not scored like one of a 15-person one.
    observed_n = _observed_founder_company(stints)
    established = _established_company_footprint(observed_n) if observed_n else None

    if established:
        basis = "observed_company"
        exp_gva, exp_jobs = established["gva"], established["peak_jobs_supported"]
        exp_tax, exp_exit = established["total_tax"], established["exit_value"]
    else:
        basis = "generic_cohort"
        exp_gva, exp_jobs = generic_gva, generic_jobs
        exp_tax, exp_exit = generic_tax, generic_exit

    statement = _founder_headline(framing, person_name, exp_gva, exp_jobs, exp_tax, observed_n)

    return FounderImpact(
        currency=C.FOUNDER_CURRENCY,
        expected_gva_footprint=round(exp_gva),
        expected_peak_jobs_supported=round(exp_jobs, 1),
        expected_total_tax=round(exp_tax),
        expected_exit_value=round(exp_exit),
        buckets=buckets,
        realized_current_company=_realized_current_company(stints),
        basis=basis,
        company_scale_employees=observed_n,
        established_company_footprint=established,
        headline_statement=statement,
        framing=framing,
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
    framing: str = C.DEFAULT_FRAMING
    disclaimer: str = C.DISCLAIMER


def compute_national_impact(
    founders_per_year: int = C.FOUNDERS_LEAVING_PER_YEAR_HIGH_GROWTH,
    horizon_years: int = 5,
    framing: Optional[str] = None,
) -> NationalImpact:
    framing = framing or C.DEFAULT_FRAMING
    per = compute_founder_impact([], framing=framing)
    annual_gdp = per.expected_gva_footprint * founders_per_year
    annual_jobs = per.expected_peak_jobs_supported * founders_per_year
    annual_tax = per.expected_total_tax * founders_per_year
    cumulative = annual_gdp * horizon_years

    if framing == "loss":
        statement = (
            f"At ~{founders_per_year} high-growth founders leaving per year, the UK forgoes an "
            f"estimated {_money(annual_gdp)} of GDP, ~{round(annual_jobs):,} jobs and "
            f"{_money(annual_tax)} of tax per annual cohort — {_money(cumulative)} over "
            f"{horizon_years} years (modelled estimate)."
        )
    else:
        statement = (
            f"With ~{founders_per_year} high-growth founders building abroad each year, Britain "
            f"misses out on an estimated {_money(annual_gdp)} of GDP, ~{round(annual_jobs):,} jobs "
            f"and {_money(annual_tax)} of tax per annual cohort — {_money(cumulative)} over "
            f"{horizon_years} years (modelled estimate)."
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
        framing=framing,
    )
