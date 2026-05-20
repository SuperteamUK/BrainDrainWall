"""BrainDrainWall GDP-impact API.

Estimates how much GDP a person contributes to their country over their working
life, derived from their career history. Drives the "brain drain wall" campaign:
GDP lost when someone emigrates, gained when someone arrives.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from . import apollo, model
from .coefficients import MODEL_VERSION
from .parsing import Stint, classify_stint, normalize_apollo, parse_date
from .schemas import (
    GDPImpactRequest,
    GDPImpactResponse,
    PersonOut,
    PreviewRequest,
    StintScoreOut,
    SummaryOut,
)

app = FastAPI(
    title="BrainDrainWall GDP Impact API",
    version=MODEL_VERSION,
    description="Estimates a person's lifetime GDP contribution from their career history.",
)


def _serialize(person: PersonOut, summary, scores) -> GDPImpactResponse:
    return GDPImpactResponse(
        person=person,
        summary=SummaryOut(**summary.__dict__),
        stints=[StintScoreOut(**s.__dict__) for s in scores],
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model_version": MODEL_VERSION}


@app.post("/v1/gdp-impact", response_model=GDPImpactResponse)
async def gdp_impact(req: GDPImpactRequest) -> GDPImpactResponse:
    """Enrich a person via Apollo, then score their lifetime GDP contribution."""
    try:
        person_raw = await apollo.enrich_person(
            linkedin_url=req.linkedin_url,
            first_name=req.first_name,
            last_name=req.last_name,
            name=req.name,
            organization_name=req.organization_name,
            email=req.email,
        )
    except apollo.ApolloNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except apollo.ApolloError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    info, stints = normalize_apollo(person_raw)
    if not stints:
        raise HTTPException(status_code=422, detail="No employment history found for this person.")

    summary, scores = model.compute_impact(stints, person_name=info.name or "This person")
    person = PersonOut(
        name=info.name,
        headline=info.headline,
        current_title=info.current_title,
        current_company=info.current_company,
        linkedin_url=info.linkedin_url,
    )
    return _serialize(person, summary, scores)


@app.post("/v1/gdp-impact/preview", response_model=GDPImpactResponse)
def gdp_impact_preview(req: PreviewRequest) -> GDPImpactResponse:
    """Score a hand-supplied career history. For testing/integration without Apollo."""
    stints: list[Stint] = []
    for item in req.history:
        stint = Stint(
            company=item.company,
            title=item.title,
            start_date=parse_date(item.start_date),
            end_date=parse_date(item.end_date),
            current=item.current,
            industry=item.industry,
            employees=item.employees,
            annual_revenue=item.annual_revenue,
        )
        stints.append(classify_stint(stint))

    if not stints:
        raise HTTPException(status_code=422, detail="history must contain at least one entry.")

    summary, scores = model.compute_impact(stints, person_name=req.name)
    person = PersonOut(name=req.name, current_company=stints[0].company, current_title=stints[0].title)
    return _serialize(person, summary, scores)
