"""Adapter for interacting with Jira's REST API."""

from __future__ import annotations

import base64
from typing import Any, Dict

import httpx

from app.config import settings
from app.domain.errors import ExternalServiceError
from app.utils.http import sync_client


def _auth_headers() -> Dict[str, str]:
    """Return HTTP headers for Atlassian basic authentication."""

    if not settings.atlassian_email or not settings.atlassian_api_token:
        raise ExternalServiceError("Atlassian credentials are not configured")
    token = base64.b64encode(f"{settings.atlassian_email}:{settings.atlassian_api_token}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def create_epic(project_key: str, summary: str, description: str) -> Dict[str, Any]:
    """Create a Jira epic and return its key and browse URL."""

    if not settings.atlassian_base_url:
        raise ExternalServiceError("Atlassian base URL is not configured")

    url = f"{settings.atlassian_base_url.rstrip('/')}/rest/api/3/issue"
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": "Epic"},
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": description}],
                    }
                ],
            },
        }
    }

    with sync_client(timeout=60) as client:
        response = client.post(url, headers=_auth_headers(), json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ExternalServiceError(f"Jira responded with status {exc.response.status_code}") from exc

        data = response.json()
        key = data.get("key")
        return {"key": key, "url": f"{settings.atlassian_base_url.rstrip('/')}/browse/{key}"}
