"""Turn raw Apollo / free-text career data into normalised, scoreable stints."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from . import coefficients as C


@dataclass
class Stint:
    company: str
    title: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    current: bool = False
    industry: Optional[str] = None
    employees: Optional[int] = None
    annual_revenue: Optional[float] = None
    # Filled in by classification.
    seniority: str = "mid"
    function: str = "general"
    industry_key: str = "general"
    tier: int = 1


@dataclass
class PersonInfo:
    name: str = ""
    headline: str = ""
    current_title: str = ""
    current_company: str = ""
    linkedin_url: str = ""
    raw_employment_count: int = 0


# --- date parsing -----------------------------------------------------------

def parse_date(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return date(*_strptime_parts(text, fmt))
        except ValueError:
            continue
    m = re.match(r"^(\d{4})$", text)
    if m:
        return date(int(m.group(1)), 1, 1)
    return None


def _strptime_parts(text: str, fmt: str) -> tuple[int, int, int]:
    from datetime import datetime

    dt = datetime.strptime(text, fmt)
    return dt.year, dt.month, dt.day


# --- title classification ---------------------------------------------------

_SENIORITY_RULES: list[tuple[str, str]] = [
    (r"\b(founder|co[- ]?founder|founding)\b", "founder"),
    (r"\b(owner|proprietor|principal owner)\b", "owner"),
    (r"\b(managing partner|partner)\b", "partner"),
    (
        r"\b(chief|c[\.\s]?e[\.\s]?o|c[\.\s]?f[\.\s]?o|c[\.\s]?t[\.\s]?o|"
        r"c[\.\s]?o[\.\s]?o|c[\.\s]?m[\.\s]?o|c[\.\s]?i[\.\s]?o|cio|chro|cdo|cpo|"
        r"president)\b",
        "clevel",
    ),
    (r"\b(svp|evp|vp|vice[- ]president)\b", "vp"),
    (r"\b(director|head of|head,|department head)\b", "director"),
    (r"\b(senior manager|sr\.? manager)\b", "senior_manager"),
    (r"\b(manager|mgr)\b", "manager"),
    (r"\b(senior|sr\.?|staff|principal|lead)\b", "senior"),
    (r"\b(junior|jr\.?|associate|analyst|assistant)\b", "junior"),
    (r"\b(intern|trainee|apprentice|graduate|entry)\b", "entry"),
]

_FUNCTION_RULES: list[tuple[str, str]] = [
    (r"\b(chief executive|ceo|coo|chief operating|managing director|general manager|president)\b", "executive"),
    (r"\b(cfo|finance|financial|investment|invest(or|ment) banking|banker|trader|trading|portfolio|m&a|equity|treasur|capital markets|hedge fund|private equity|venture)\b", "finance"),
    (r"\b(engineer|developer|software|devops|sre|architect|programmer|data scientist|machine learning|\bml\b)\b", "engineering"),
    (r"\b(product manager|product owner|head of product|\bproduct\b)\b", "product"),
    (r"\b(research|scientist|r&d|professor|fellow)\b", "research"),
    (r"\b(consultant|consulting|advisory|advisor)\b", "consulting"),
    (r"\b(sales|account executive|account manager|business development|\bbd\b|revenue)\b", "sales"),
    (r"\b(marketing|growth|brand|communications|seo|demand gen)\b", "marketing"),
    (r"\b(operations|supply chain|logistics|\bops\b|procurement)\b", "operations"),
    (r"\b(legal|counsel|attorney|lawyer|paralegal|compliance)\b", "legal"),
    (r"\b(physician|doctor|surgeon|nurse|clinical|medical|pharmacist)\b", "medical"),
    (r"\b(human resources|recruit|talent|people ops|hr\b)\b", "hr"),
    (r"\b(government|public sector|policy|civil service|minister|councillor)\b", "public"),
]

_INDUSTRY_RULES: list[tuple[str, str]] = [
    (r"bank|financ|insurance|capital|invest|asset manage|securities", "finance"),
    (r"software|technolog|internet|saas|computer|information technology|semiconductor|\bit\b", "technology"),
    (r"oil|gas|energy|petroleum|utilit|renewable|power", "energy"),
    (r"health|hospital|pharma|biotech|medical|life science", "healthcare"),
    (r"consult|advisory|professional services", "consulting"),
    (r"real estate|property|construction|reit", "real_estate"),
    (r"telecom|wireless|communications carrier", "telecom"),
    (r"media|entertainment|publishing|broadcast|advertis", "media"),
    (r"manufactur|industrial|automotive|aerospace|chemical|machinery", "manufacturing"),
    (r"retail|consumer|wholesale|e-?commerce|apparel|grocery", "retail"),
    (r"education|university|school|academ|edtech", "education"),
    (r"government|public administration|defense|defence", "government"),
    (r"non[- ]?profit|charity|ngo|foundation", "nonprofit"),
]

# A person at one of these (substring match, lowercased) inherits systemic scale
# regardless of the headcount Apollo reports. The "minority of firms" that move
# disproportionate GDP. Extend freely.
_TIER5_FIRMS = {
    "goldman sachs", "morgan stanley", "jpmorgan", "j.p. morgan", "jp morgan",
    "citigroup", "citibank", "bank of america", "merrill lynch", "barclays",
    "deutsche bank", "ubs", "credit suisse", "hsbc", "lazard", "rothschild",
    "blackrock", "blackstone", "kkr", "carlyle", "apollo global", "bridgewater",
    "citadel", "two sigma", "jane street", "point72", "berkshire hathaway",
    "google", "alphabet", "apple", "microsoft", "amazon", "meta", "facebook",
    "nvidia", "openai", "anthropic", "tesla", "netflix", "oracle", "salesforce",
    "mckinsey", "bain", "boston consulting", "bcg", "deloitte", "pwc", "ey", "kpmg",
    "exxon", "shell", "bp ", "chevron", "saudi aramco", "totalenergies",
}


def classify_seniority(title: str) -> str:
    t = f" {title.lower()} "
    for pattern, level in _SENIORITY_RULES:
        if re.search(pattern, t):
            return level
    return "mid"


def classify_function(title: str) -> str:
    t = f" {title.lower()} "
    for pattern, func in _FUNCTION_RULES:
        if re.search(pattern, t):
            return func
    return "general"


def classify_industry(industry: Optional[str]) -> str:
    if not industry:
        return "general"
    text = industry.lower()
    for pattern, key in _INDUSTRY_RULES:
        if re.search(pattern, text):
            return key
    return "general"


def tier_for_company(
    name: str,
    employees: Optional[int] = None,
    annual_revenue: Optional[float] = None,
) -> int:
    lname = (name or "").lower()
    for firm in _TIER5_FIRMS:
        if firm in lname:
            return 5

    if annual_revenue:
        if annual_revenue >= 10_000_000_000:
            return 5
        if annual_revenue >= 1_000_000_000:
            return 4
        if annual_revenue >= 100_000_000:
            return 3
        if annual_revenue >= 10_000_000:
            return 2
        return 1

    if employees:
        if employees >= 100_000:
            return 5
        if employees >= 25_000:
            return 4
        if employees >= 5_000:
            return 3
        if employees >= 500:
            return 2
        if employees >= 50:
            return 1
        return 0

    return 1  # unknown private company: assume SMB


def _founder_has_scale(stint: Stint) -> bool:
    """Evidence that a founder/owner's venture is a real, scaled company rather
    than a solo, side or defunct micro-venture.

    The founder lens — the steep seniority premium here and the expected-company
    footprint in founder_model — is calibrated to scale-qualified, company-
    building founders (METHODOLOGY.md §7-8). Applying it to a one-person
    Instagram brand or a hobby project massively overstates GDP, so we require a
    scale signal before granting it.
    """
    if stint.employees and stint.employees >= C.FOUNDER_SCALE_MIN_EMPLOYEES:
        return True
    if stint.annual_revenue and stint.annual_revenue > 0:
        return True
    return stint.tier >= 2


def classify_stint(stint: Stint) -> Stint:
    stint.seniority = classify_seniority(stint.title)
    stint.function = classify_function(stint.title)
    stint.industry_key = classify_industry(stint.industry)
    stint.tier = tier_for_company(stint.company, stint.employees, stint.annual_revenue)
    # A founder/owner with no evidence of scale is scored as self-employed, not
    # as a company-building founder (which would otherwise grant a ~7x premium
    # and the high-growth founder footprint regardless of the venture's size).
    if stint.seniority in ("founder", "owner") and not _founder_has_scale(stint):
        stint.seniority = "self_employed"
    return stint


# --- Apollo payload normalisation -------------------------------------------

def normalize_apollo(person: dict[str, Any]) -> tuple[PersonInfo, list[Stint]]:
    org = person.get("organization") or {}
    info = PersonInfo(
        name=person.get("name") or " ".join(
            filter(None, [person.get("first_name"), person.get("last_name")])
        ),
        headline=person.get("headline") or "",
        current_title=person.get("title") or "",
        current_company=org.get("name") or "",
        linkedin_url=person.get("linkedin_url") or "",
    )

    history = person.get("employment_history") or []
    info.raw_employment_count = len(history)

    stints: list[Stint] = []
    for entry in history:
        company = entry.get("organization_name") or ""
        title = entry.get("title") or ""
        if not company and not title:
            continue
        is_current = bool(entry.get("current"))
        # Apollo only enriches the *current* organization with size/industry.
        emp = org.get("estimated_num_employees") if is_current else None
        rev = org.get("annual_revenue") if is_current else None
        industry = org.get("industry") if is_current else None
        stint = Stint(
            company=company,
            title=title,
            start_date=parse_date(entry.get("start_date")),
            end_date=parse_date(entry.get("end_date")),
            current=is_current,
            industry=industry,
            employees=emp,
            annual_revenue=rev,
        )
        stints.append(classify_stint(stint))

    return info, stints
