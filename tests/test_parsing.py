from datetime import date

from app.parsing import (
    classify_function,
    classify_industry,
    classify_seniority,
    normalize_apollo,
    parse_date,
    tier_for_company,
)


def test_parse_date_variants():
    assert parse_date("2019-03-01") == date(2019, 3, 1)
    assert parse_date("2019-03") == date(2019, 3, 1)
    assert parse_date("2019") == date(2019, 1, 1)
    assert parse_date(None) is None
    assert parse_date("") is None


def test_seniority_classification():
    assert classify_seniority("Chief Financial Officer") == "clevel"
    assert classify_seniority("VP of Engineering") == "vp"
    assert classify_seniority("Senior Software Engineer") == "senior"
    assert classify_seniority("Software Engineer") == "mid"
    assert classify_seniority("Junior Analyst") == "junior"
    assert classify_seniority("Co-Founder & CEO") == "founder"
    assert classify_seniority("Marketing Intern") == "entry"
    assert classify_seniority("Managing Partner") == "partner"


def test_function_classification():
    assert classify_function("Software Engineer") == "engineering"
    assert classify_function("Investment Banking Analyst") == "finance"
    assert classify_function("Chief Executive Officer") == "executive"
    assert classify_function("Product Manager") == "product"
    assert classify_function("Management Consultant") == "consulting"
    assert classify_function("Registered Nurse") == "medical"


def test_industry_classification():
    assert classify_industry("Investment Banking") == "finance"
    assert classify_industry("Computer Software") == "technology"
    assert classify_industry("Oil & Energy") == "energy"
    assert classify_industry(None) == "general"


def test_company_tiering():
    assert tier_for_company("Goldman Sachs") == 5
    assert tier_for_company("Google LLC") == 5
    assert tier_for_company("Unknown Co", employees=200_000) == 5
    assert tier_for_company("Mid Co", employees=8_000) == 3
    assert tier_for_company("Small Co", employees=120) == 1
    assert tier_for_company("Tiny Co", employees=10) == 0
    assert tier_for_company("Big Rev Co", annual_revenue=20_000_000_000) == 5
    assert tier_for_company("Mystery Co") == 1


def test_normalize_apollo_payload():
    person = {
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
    info, stints = normalize_apollo(person)
    assert info.name == "Jane Doe"
    assert info.current_company == "Goldman Sachs"
    assert len(stints) == 2
    cfo = stints[0]
    assert cfo.seniority == "clevel"
    assert cfo.function == "finance"
    assert cfo.tier == 5
    assert cfo.current is True
