"""Adapter for Confluence REST API interactions."""

from __future__ import annotations

import base64
from typing import Any, Dict

import httpx

from app.config import settings
from app.domain.errors import ExternalServiceError
from app.utils.http import sync_client


def _auth_headers() -> Dict[str, str]:
    """Return HTTP headers for Confluence authentication."""

    if not settings.atlassian_email or not settings.atlassian_api_token:
        raise ExternalServiceError("Atlassian credentials are not configured")
    token = base64.b64encode(f"{settings.atlassian_email}:{settings.atlassian_api_token}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def create_page(space: str, title: str, body_html: str) -> Dict[str, Any]:
    """Create a Confluence page and return identifiers."""

    if not settings.atlassian_base_url:
        raise ExternalServiceError("Atlassian base URL is not configured")

    url = f"{settings.atlassian_base_url.rstrip('/')}/wiki/api/v2/pages"
    payload = {"spaceKey": space, "title": title, "body": {"representation": "storage", "value": body_html}}

    with sync_client(timeout=60) as client:
        response = client.post(url, headers=_auth_headers(), json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ExternalServiceError(f"Confluence responded with status {exc.response.status_code}") from exc

        data = response.json()
        page_id = data.get("id")
        return {"page_id": page_id, "url": f"{settings.atlassian_base_url.rstrip('/')}/wiki/spaces/{space}/pages/{page_id}"}
