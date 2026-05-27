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
    # A scale-qualified founder (real headcount) is a founder...
    assert is_founder([founder_stint(employees=60)]) is True
    employee = classify_stint(Stint(company="BigCo", title="Software Engineer"))
    assert is_founder([employee]) is False


def test_sub_scale_founder_is_not_a_founder():
    # A solo / side / defunct micro-venture (no employees, revenue or firm scale)
    # is scored as self-employed and must NOT trigger the founder footprint.
    micro = classify_stint(
        Stint(
            company="Hobby Brand",
            title="Founder",
            start_date=date(2019, 1, 1),
            end_date=date(2020, 1, 1),
        )
    )
    assert micro.seniority == "self_employed"
    assert is_founder([micro]) is False


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


def test_footprint_scales_with_observed_company_size():
    """A founder of a big company must score far above one of a small company."""
    small = compute_founder_impact([founder_stint(employees=20)]).expected_gva_footprint
    mid = compute_founder_impact([founder_stint(employees=200)]).expected_gva_footprint
    big = compute_founder_impact([founder_stint(employees=2000)]).expected_gva_footprint
    assert small < mid < big
    assert big > small * 10  # roughly linear in headcount


def test_observed_company_basis_and_fields():
    fi = compute_founder_impact([founder_stint(employees=200)])
    assert fi.basis == "observed_company"
    assert fi.company_scale_employees == 200
    assert fi.established_company_footprint["employees"] == 200
    # the headline footprint is the observed company's, not the cohort average
    assert fi.established_company_footprint["gva"] == fi.expected_gva_footprint
    assert "200 staff" in fi.headline_statement


def test_unknown_company_size_falls_back_to_generic_cohort():
    # Founder qualified by revenue (not headcount): no observed size -> generic.
    rev_founder = classify_stint(
        Stint(
            company="RevCo",
            title="Founder",
            start_date=date(2020, 1, 1),
            current=True,
            annual_revenue=5_000_000,
        )
    )
    fi = compute_founder_impact([rev_founder])
    assert fi.basis == "generic_cohort"
    assert fi.company_scale_employees is None
    assert fi.established_company_footprint is None
    assert 5_000_000 < fi.expected_gva_footprint < 100_000_000


def _founder_at(industry=None, employees=100, revenue=None):
    return classify_stint(
        Stint(
            company="Co",
            title="Founder",
            start_date=date(2020, 1, 1),
            current=True,
            employees=employees,
            industry=industry,
            annual_revenue=revenue,
        )
    )


def test_founder_footprint_is_sector_aware():
    """A founder of a community/education body scores below a software founder
    at the same headcount (no longer treated like a tech company)."""
    tech = compute_founder_impact([_founder_at("Computer Software")]).expected_gva_footprint
    edu = compute_founder_impact([_founder_at("Education Management")]).expected_gva_footprint
    assert edu < tech
    assert edu < tech * 0.5  # education factor (0.40) vs tech (1.0)


def test_founder_footprint_bounded_by_reported_revenue():
    """A positive but low reported revenue caps the headcount-based GVA."""
    no_rev = compute_founder_impact([_founder_at("Computer Software", revenue=None)]).expected_gva_footprint
    low_rev = compute_founder_impact(
        [_founder_at("Computer Software", revenue=500_000)]
    ).expected_gva_footprint
    assert low_rev < no_rev


def test_realized_company_only_when_employees_known():
    assert compute_founder_impact([founder_stint()]).realized_current_company is None
    fi = compute_founder_impact([founder_stint(employees=120)])
    assert fi.realized_current_company is not None
    assert fi.realized_current_company["employees"] == 120
    assert fi.realized_current_company["annual_gva"] > 0


def test_framing_default_is_missed_out_and_carries_disclaimer():
    fi = compute_founder_impact([founder_stint()])
    assert fi.framing == "missed_out"
    assert "missed out" in fi.headline_statement.lower()
    assert "modelled estimate" in fi.disclaimer.lower()
    assert "not a statement of fact" in fi.disclaimer.lower()


def test_loss_framing_opt_in():
    fi = compute_founder_impact([founder_stint()], framing="loss")
    assert fi.framing == "loss"
    assert "lost to the uk" in fi.headline_statement.lower()


def test_national_impact_scales_with_founders():
    small = compute_national_impact(founders_per_year=100, horizon_years=5)
    big = compute_national_impact(founders_per_year=300, horizon_years=5)
    assert big.annual_gdp_at_stake == small.annual_gdp_at_stake * 3
    assert big.cumulative_gdp_at_stake == big.annual_gdp_at_stake * 5
    assert "GDP" in big.headline_statement
