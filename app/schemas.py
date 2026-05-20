from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GDPImpactRequest(BaseModel):
    linkedin_url: Optional[str] = Field(default=None, description="Full LinkedIn profile URL.")
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    organization_name: Optional[str] = Field(
        default=None, description="Current employer; improves Apollo match accuracy."
    )
    email: Optional[str] = None

    @model_validator(mode="after")
    def _require_identifier(self) -> "GDPImpactRequest":
        has_name = bool(self.name or (self.first_name and self.last_name))
        if not (self.linkedin_url or self.email or has_name):
            raise ValueError(
                "Provide linkedin_url, email, or a name (full name or first+last)."
            )
        return self


class RawStintInput(BaseModel):
    company: str = ""
    title: str = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    current: bool = False
    industry: Optional[str] = None
    employees: Optional[int] = None
    annual_revenue: Optional[float] = None


class PreviewRequest(BaseModel):
    name: str = "This person"
    history: list[RawStintInput]


class StintScoreOut(BaseModel):
    company: str
    title: str
    seniority: str
    function: str
    industry_key: str
    tier: int
    years: float
    annual_gdp_contribution: float
    total_gdp_contribution: float
    components: dict[str, float]


class PersonOut(BaseModel):
    name: str
    headline: str = ""
    current_title: str = ""
    current_company: str = ""
    linkedin_url: str = ""


class SummaryOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    historical_gdp_contribution: float
    current_annual_gdp_contribution: float
    estimated_experience_years: float
    projected_remaining_years: int
    future_gdp_contribution_undiscounted: float
    future_gdp_contribution_npv: float
    lifetime_gdp_contribution: float
    headline_statement: str
    model_version: str


class GDPImpactResponse(BaseModel):
    person: PersonOut
    summary: SummaryOut
    stints: list[StintScoreOut]
