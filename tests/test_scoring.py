from app.scoring import score_apollo_person

CFO_PAYLOAD = {
    "name": "Jane Doe",
    "title": "Chief Financial Officer",
    "headline": "CFO at MegaBank",
    "linkedin_url": "https://linkedin.com/in/janedoe",
    "organization": {
        "name": "Goldman Sachs",
        "industry": "Investment Banking",
        "estimated_num_employees": 45000,
    },
    "employment_history": [
        {
            "organization_name": "Goldman Sachs",
            "title": "Chief Financial Officer",
            "start_date": "2018-01-01",
            "end_date": None,
            "current": True,
        },
        {
            "organization_name": "Some Startup",
            "title": "Financial Analyst",
            "start_date": "2010-06-01",
            "end_date": "2017-12-01",
            "current": False,
        },
    ],
}

FOUNDER_PAYLOAD = {
    "name": "Sam Founder",
    "title": "Co-Founder & CEO",
    "organization": {"name": "NewCo", "estimated_num_employees": 60},
    "employment_history": [
        {
            "organization_name": "NewCo",
            "title": "Co-Founder & CEO",
            "start_date": "2019-01-01",
            "current": True,
        }
    ],
}


def test_score_employee_payload():
    r = score_apollo_person(CFO_PAYLOAD)
    assert r["person"]["name"] == "Jane Doe"
    assert len(r["stints"]) == 2
    assert r["summary"]["historical_gdp_contribution"] > 0
    assert r["summary"]["framing"] == "missed_out"
    assert "disclaimer" in r["summary"]
    assert r["founder_impact"] is None


def test_score_founder_payload_adds_block():
    r = score_apollo_person(FOUNDER_PAYLOAD)
    assert r["founder_impact"] is not None
    assert r["founder_impact"]["expected_gva_footprint"] > 0
    assert len(r["founder_impact"]["buckets"]) == 3
    assert r["founder_impact"]["realized_current_company"]["employees"] == 60


def test_framing_passthrough():
    r = score_apollo_person(CFO_PAYLOAD, framing="loss")
    assert r["summary"]["framing"] == "loss"


SIDE_HUSTLE_PAYLOAD = {
    "name": "Side Hustler",
    "title": "Marketing Lead",
    "organization": {"name": "DayJob Co", "estimated_num_employees": 5000},
    "employment_history": [
        {
            "organization_name": "DayJob Co",
            "title": "Marketing Lead",
            "start_date": "2022-01-01",
            "current": True,
        },
        {
            # A defunct one-person Instagram brand: no headcount, no revenue.
            "organization_name": "Hobby Brand",
            "title": "Founder",
            "start_date": "2018-01-01",
            "end_date": "2019-06-01",
            "current": False,
        },
    ],
}


def test_sub_scale_founder_adds_no_founder_block():
    r = score_apollo_person(SIDE_HUSTLE_PAYLOAD)
    assert r["founder_impact"] is None
    hobby = next(s for s in r["stints"] if s["company"] == "Hobby Brand")
    assert hobby["seniority"] == "self_employed"
