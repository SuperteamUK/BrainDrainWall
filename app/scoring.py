"""Run an Apollo `person` payload through the GDP model and return a plain dict.

Shared by the HTTP API and the `scripts/score_apollo.py` CLI. Accepts the same
person object Apollo's People Enrichment returns (the thing under `person` in a
/people/match response), so it works equally for the live API path and the
Apollo-connector path (where the agent fetches the person object itself).
"""

from __future__ import annotations

from typing import Any, Optional

from . import founder_model, model
from .parsing import normalize_apollo


def score_apollo_person(person: dict[str, Any], framing: Optional[str] = None) -> dict:
    info, stints = normalize_apollo(person)
    summary, scores = model.compute_impact(
        stints, person_name=info.name or "This person", framing=framing
    )

    result: dict[str, Any] = {
        "person": {
            "name": info.name,
            "headline": info.headline,
            "current_title": info.current_title,
            "current_company": info.current_company,
            "linkedin_url": info.linkedin_url,
        },
        "summary": dict(summary.__dict__),
        "stints": [dict(s.__dict__) for s in scores],
        "founder_impact": None,
    }

    if founder_model.is_founder(stints):
        fi = founder_model.compute_founder_impact(
            stints, person_name=info.name or "This founder", framing=summary.framing
        )
        fi_dict = dict(fi.__dict__)
        fi_dict["buckets"] = [dict(b.__dict__) for b in fi.buckets]
        result["founder_impact"] = fi_dict

    return result
