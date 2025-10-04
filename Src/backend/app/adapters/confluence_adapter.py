"""Adapter for Confluence REST API interactions."""

from __future__ import annotations

import base64
from typing import Any, Dict

import httpx
from fastapi import HTTPException

from app.config import settings
from app.domain.errors import ExternalServiceError
from app.utils.http import sync_client


def _auth_headers() -> Dict[str, str]:
    """Return HTTP headers for Confluence authentication."""

    if not settings.atlassian_email or not settings.atlassian_api_token:
        raise ExternalServiceError("Atlassian credentials are not configured")
    token = base64.b64encode(f"{settings.atlassian_email}:{settings.atlassian_api_token}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def _tool_args_invalid(message: str, *, details: Dict[str, Any] | None = None) -> HTTPException:
    detail = {"code": "TOOL_ARGS_INVALID", "message": message}
    if details:
        detail["details"] = details
    return HTTPException(status_code=400, detail=detail)


def _to_str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return str(value)


def resolve_space(space_key: str | None = None, space_id: str | None = None) -> Dict[str, Any]:
    """Resolve a Confluence space to its metadata."""

    if not space_key and not space_id:
        raise _tool_args_invalid(
            "space_key or space_id required",
            details={"missing": ["space_key", "space_id"]},
        )

    if not settings.atlassian_base_url:
        raise ExternalServiceError("Atlassian base URL is not configured")

    base = settings.atlassian_base_url.rstrip('/')
    if space_id:
        space_id = _to_str_or_none(space_id)
        url = f"{base}/wiki/api/v2/spaces/{space_id}"
        params = None
    else:
        space_key = _to_str_or_none(space_key)
        url = f"{base}/wiki/api/v2/spaces"
        params = {"keys": space_key}

    with sync_client(timeout=30) as client:
        response = client.get(url, headers=_auth_headers(), params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            body = exc.response.text[:500]
            if status in {400, 401, 403, 404}:
                raise _tool_args_invalid(
                    f"Confluence space lookup failed ({status})",
                    details={"body": body, "space_key": space_key, "space_id": space_id},
                )
            raise ExternalServiceError(f"Confluence {status}: {body}") from exc

        data = response.json()
        if space_id:
            return {
                "id": _to_str_or_none(data.get("id") or space_id),
                "key": _to_str_or_none(data.get("key") or space_key),
                "name": data.get("name"),
            }

        results = data.get("results", [])
        if not results:
            raise _tool_args_invalid("Confluence space not found", details={"space_key": space_key})

        item = results[0]
        return {
            "id": _to_str_or_none(item.get("id")),
            "key": _to_str_or_none(item.get("key", space_key)),
            "name": item.get("name"),
        }


def discover_default_space() -> Dict[str, Any]:
    """Return the first accessible Confluence space for the credentials."""

    if not settings.atlassian_base_url:
        raise ExternalServiceError("Atlassian base URL is not configured")

    base = settings.atlassian_base_url.rstrip('/')
    url = f"{base}/wiki/api/v2/spaces"
    params = {"limit": 1}

    with sync_client(timeout=30) as client:
        response = client.get(url, headers=_auth_headers(), params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            body = exc.response.text[:500]
            raise ExternalServiceError(f"Confluence {status}: {body}") from exc

        data = response.json()
        results = data.get("results", [])
        if not results:
            raise _tool_args_invalid("No Confluence spaces available")
        item = results[0]
        return {
            "id": _to_str_or_none(item.get("id")),
            "key": _to_str_or_none(item.get("key")),
            "name": item.get("name"),
        }


def create_page(
    *,
    space_id: str,
    space_key: str,
    title: str,
    body_html: str,
    draft: bool = False,
) -> Dict[str, Any]:
    """Create a Confluence page and return identifiers."""

    if not settings.atlassian_base_url:
        raise ExternalServiceError("Atlassian base URL is not configured")

    space_id_str = _to_str_or_none(space_id)
    space_key_str = _to_str_or_none(space_key)
    if not space_id_str or not space_key_str:
        raise _tool_args_invalid(
            "space_key or space_id required",
            details={"space_key": space_key, "space_id": space_id},
        )

    title = title.strip()
    body_html = (body_html or "").strip() or "<p>Auto-generated by North Star</p>"

    url = f"{settings.atlassian_base_url.rstrip('/')}/wiki/api/v2/pages"
    payload = {
        "spaceId": space_id_str,
        "title": title,
        "body": {"representation": "storage", "value": body_html},
        "status": "draft" if draft else "current",
    }

    with sync_client(timeout=60) as client:
        response = client.post(url, headers=_auth_headers(), json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:800]
            raise ExternalServiceError(f"Confluence {exc.response.status_code}: {body}") from exc

        data = response.json()
        page_id = data.get("id")
        links = data.get("_links") or {}
        return {
            "page_id": page_id,
            "space_id": space_id_str,
            "space_key": space_key_str,
            "url": f"{settings.atlassian_base_url.rstrip('/')}/wiki/spaces/{space_key_str}/pages/{page_id}",
            "status": "draft" if draft else "current",
            "_links": links,
        }
