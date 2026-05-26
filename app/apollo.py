"""Thin client for the Apollo.io People Enrichment API."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from .config import settings


class ApolloError(RuntimeError):
    pass


class ApolloNotFound(ApolloError):
    pass


def _payload(
    linkedin_url: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
    name: Optional[str],
    organization_name: Optional[str],
    email: Optional[str],
) -> dict[str, Any]:
    body: dict[str, Any] = {"reveal_personal_emails": False, "reveal_phone_number": False}
    if linkedin_url:
        body["linkedin_url"] = linkedin_url
    if email:
        body["email"] = email
    if name:
        body["name"] = name
    if first_name:
        body["first_name"] = first_name
    if last_name:
        body["last_name"] = last_name
    if organization_name:
        body["organization_name"] = organization_name
    return body


async def enrich_person(
    *,
    linkedin_url: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    name: Optional[str] = None,
    organization_name: Optional[str] = None,
    email: Optional[str] = None,
) -> dict[str, Any]:
    if not settings.apollo_api_key:
        raise ApolloError("APOLLO_API_KEY is not configured.")

    body = _payload(linkedin_url, first_name, last_name, name, organization_name, email)
    url = f"{settings.apollo_base_url.rstrip('/')}/people/match"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "x-api-key": settings.apollo_api_key,
    }

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        resp = await client.post(url, json=body, headers=headers)

    if resp.status_code == 401:
        raise ApolloError("Apollo rejected the API key (401).")
    if resp.status_code == 429:
        raise ApolloError("Apollo rate limit hit (429). Try again later.")
    if resp.status_code >= 400:
        raise ApolloError(f"Apollo returned {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    person = data.get("person")
    if not person:
        raise ApolloNotFound("Apollo could not match a person for the given input.")
    return person
