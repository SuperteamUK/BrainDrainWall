from datetime import date

from app.model import annual_contribution, compute_impact, score_stint
from app.parsing import Stint, classify_stint


def make(title, company, start, end=None, current=False, employees=None, industry=None):
    return classify_stint(
        Stint(
            company=company,
            title=title,
            start_date=date.fromisoformat(start),
            end_date=date.fromisoformat(end) if end else None,
            current=current,
            employees=employees,
            industry=industry,
        )
    )


def test_seniority_monotonicity_same_firm():
    """More senior roles at the same firm contribute more per year."""
    junior = make("Junior Analyst", "Goldman Sachs", "2020-01-01", current=True)
    cfo = make("Chief Financial Officer", "Goldman Sachs", "2020-01-01", current=True)
    assert annual_contribution(cfo)[0] > annual_contribution(junior)[0] * 10


def test_firm_tier_leverage_scales_with_seniority():
    """Firm scale barely moves a junior, but hugely moves a C-suite."""
    cfo_big = annual_contribution(make("CFO", "Goldman Sachs", "2020-01-01"))[0]
    cfo_small = annual_contribution(
        make("CFO", "Tiny LLC", "2020-01-01", employees=10)
    )[0]
    jr_big = annual_contribution(make("Junior Analyst", "Goldman Sachs", "2020-01-01"))[0]
    jr_small = annual_contribution(
        make("Junior Analyst", "Tiny LLC", "2020-01-01", employees=10)
    )[0]
    assert (cfo_big / cfo_small) > (jr_big / jr_small)


def test_megabank_cfo_in_plausible_range():
    cfo = make("Chief Financial Officer", "Goldman Sachs", "2018-01-01", current=True)
    annual = annual_contribution(cfo)[0]
    assert 5_000_000 < annual < 200_000_000


def test_mid_ic_in_plausible_range():
    eng = make("Software Engineer", "Mystery Co", "2020-01-01", current=True)
    annual = annual_contribution(eng)[0]
    assert 80_000 < annual < 600_000


def test_total_scales_with_tenure():
    short = score_stint(make("Manager", "Acme", "2022-01-01", "2023-01-01"))
    long = score_stint(make("Manager", "Acme", "2015-01-01", "2023-01-01"))
    assert long.total_gdp_contribution > short.total_gdp_contribution * 5


def test_compute_impact_shape_and_projection():
    stints = [
        make("Chief Executive Officer", "MegaCorp", "2019-01-01", current=True, employees=120000),
        make("VP Strategy", "MegaCorp", "2014-01-01", "2018-12-31"),
        make("Analyst", "Startup", "2008-06-01", "2013-12-31"),
    ]
    summary, scores = compute_impact(stints, person_name="Test Exec", today=date(2024, 1, 1))
    assert len(scores) == 3
    assert summary.historical_gdp_contribution > 0
    assert summary.future_gdp_contribution_undiscounted > summary.future_gdp_contribution_npv
    assert summary.projected_remaining_years > 0
    assert summary.lifetime_gdp_contribution == (
        summary.historical_gdp_contribution + summary.future_gdp_contribution_undiscounted
    )
    assert "GDP" in summary.headline_statement


def test_overlapping_roles_not_double_counted():
    """A long role fully overlapping another must not add a second full salary;
    historical = the highest-value role per interval, not the sum of stints."""
    main = make("Software Engineer", "MainCo", "2020-01-01", "2024-01-01")
    side = make("Tutor", "SideCo", "2020-01-01", "2024-01-01")
    main_only = score_stint(
        make("Software Engineer", "MainCo", "2020-01-01", "2024-01-01"),
        today=date(2024, 1, 1),
    ).total_gdp_contribution
    summary, _ = compute_impact([main, side], today=date(2024, 1, 1))
    # Engineer outscores tutor, so the envelope ~= the engineer role alone,
    # well below the naive sum of the two stints.
    assert summary.historical_gdp_contribution <= main_only * 1.02
    assert summary.historical_gdp_contribution < (
        main_only + score_stint(side, today=date(2024, 1, 1)).total_gdp_contribution
    )


def test_sequential_roles_still_add_up():
    """Non-overlapping roles are summed as before (no regression)."""
    a = make("Manager", "Acme", "2010-01-01", "2014-01-01")
    b = make("Manager", "Beta", "2014-01-01", "2018-01-01")
    summary, scores = compute_impact([a, b], today=date(2018, 1, 1))
    naive = sum(s.total_gdp_contribution for s in scores)
    assert abs(summary.historical_gdp_contribution - naive) < naive * 0.02


def test_sub_scale_founder_scores_far_below_scaled_founder():
    micro = make("Founder", "Hobby Brand", "2019-01-01", "2020-01-01")  # no scale
    scaled = make("Founder", "RealCo", "2019-01-01", current=True, employees=200)
    assert micro.seniority == "self_employed"
    assert scaled.seniority == "founder"
    assert annual_contribution(micro)[0] < annual_contribution(scaled)[0] / 3


def test_part_time_scales_down_annual_contribution():
    full = make("Tutor", "MyTutor", "2018-01-01", "2023-01-01")
    part = make("Tutor", "MyTutor", "2018-01-01", "2023-01-01")
    part.employment_type = "part_time"
    full_annual = annual_contribution(full)[0]
    part_annual = annual_contribution(part)[0]
    assert abs(part_annual - full_annual * 0.4) < 1.0
    # explicit low FTE drives it lower still (e.g. a few hours a week)
    part.fte = 0.1
    assert abs(annual_contribution(part)[0] - full_annual * 0.1) < 1.0


def test_tutor_is_junior_not_mid():
    tutor = make("Tutor", "MyTutor", "2018-01-01", "2023-01-01")
    mid = make("Coordinator", "MyTutor", "2018-01-01", "2023-01-01")
    assert tutor.seniority == "junior"
    assert annual_contribution(tutor)[0] < annual_contribution(mid)[0]


def test_no_dates_does_not_crash():
    stint = classify_stint(Stint(company="X", title="Engineer"))
    summary, scores = compute_impact([stint], person_name="Nobody")
    assert scores[0].years == 0.0
    assert summary.historical_gdp_contribution == 0
