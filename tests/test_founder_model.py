from datetime import date

from app import coefficients as C
from app.founder_model import (
    compute_founder_impact,
    compute_national_impact,
    is_founder,
)
from app.parsing import Stint, classify_stint


def founder_stint(employees=None):
    return classify_stint(
        Stint(
            company="NewCo",
            title="Co-Founder & CEO",
            start_date=date(2020, 1, 1),
            current=True,
            employees=employees,
        )
    )


def test_is_founder_detection():
    assert is_founder([founder_stint()]) is True
    employee = classify_stint(Stint(company="BigCo", title="Software Engineer"))
    assert is_founder([employee]) is False


def test_bucket_probabilities_sum_to_one():
    total = sum(b["probability"] for b in C.OUTCOME_BUCKETS.values())
    assert abs(total - 1.0) < 1e-9


def test_expected_footprint_positive_and_ordered():
    fi = compute_founder_impact([founder_stint()])
    assert fi.expected_gva_footprint > 0
    assert fi.expected_total_tax > 0
    assert fi.expected_peak_jobs_supported > 0
    by_name = {b.bucket: b for b in fi.buckets}
    # superstar dwarfs modest dwarfs failure on total GVA.
    assert by_name["superstar"].total_gva > by_name["modest_exit"].total_gva
    assert by_name["modest_exit"].total_gva > by_name["failure"].total_gva


def test_only_superstar_has_ecosystem_term():
    fi = compute_founder_impact([founder_stint()])
    by_name = {b.bucket: b for b in fi.buckets}
    assert by_name["superstar"].ecosystem_gva > 0
    assert by_name["modest_exit"].ecosystem_gva == 0
    assert by_name["failure"].ecosystem_gva == 0


def test_failure_bucket_has_no_exit_effects():
    fi = compute_founder_impact([founder_stint()])
    failure = next(b for b in fi.buckets if b.bucket == "failure")
    assert failure.reinvestment_gva == 0
    assert failure.ecosystem_gva == 0


def test_expected_footprint_in_plausible_range():
    # Per-founder expected lifetime GVA should land in the tens of millions GBP.
    fi = compute_founder_impact([founder_stint()])
    assert 5_000_000 < fi.expected_gva_footprint < 100_000_000


def test_realized_company_only_when_employees_known():
    assert compute_founder_impact([founder_stint()]).realized_current_company is None
    fi = compute_founder_impact([founder_stint(employees=120)])
    assert fi.realized_current_company is not None
    assert fi.realized_current_company["employees"] == 120
    assert fi.realized_current_company["annual_gva"] > 0


def test_national_impact_scales_with_founders():
    small = compute_national_impact(founders_per_year=100, horizon_years=5)
    big = compute_national_impact(founders_per_year=300, horizon_years=5)
    assert big.annual_gdp_at_stake == small.annual_gdp_at_stake * 3
    assert big.cumulative_gdp_at_stake == big.annual_gdp_at_stake * 5
    assert "GDP" in big.headline_statement
