"""Adapter for interacting with Jira's REST API."""

from __future__ import annotations

import base64
from threading import Lock
from typing import Any, Dict, List, Tuple

import httpx
from fastapi import HTTPException

from app.config import settings
from app.domain.errors import ExternalServiceError
from app.schemas.publish import PublishJiraRequest
from app.utils.http import sync_client


_EPIC_NAME_FIELD_ID_CACHE: str | None = None
_EPIC_NAME_FIELD_LOOKUP_FAILED = False
_EPIC_NAME_FIELD_LOCK = Lock()
_EPIC_CREATE_META_CACHE: Dict[Tuple[str | None, str | None, str], bool] = {}


def _tool_args_invalid(message: str, *, details: Dict[str, Any] | None = None) -> HTTPException:
    detail = {"code": "TOOL_ARGS_INVALID", "message": message}
    if details:
        detail["details"] = details
    raise HTTPException(status_code=400, detail=detail)


def _upstream_validation_error(message: str, *, details: Dict[str, Any] | None = None) -> HTTPException:
    detail = {"code": "UPSTREAM_VALIDATION", "message": message}
    if details:
        detail["details"] = details
    raise HTTPException(status_code=400, detail=detail)


def _auth_headers() -> Dict[str, str]:
    """Return HTTP headers for Atlassian basic authentication."""

    if not settings.atlassian_email or not settings.atlassian_api_token:
        raise ExternalServiceError("Atlassian credentials are not configured")
    token = base64.b64encode(f"{settings.atlassian_email}:{settings.atlassian_api_token}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


def _to_str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return str(value)


def resolve_project(project_key: str | None, project_id: str | None) -> Dict[str, Any]:
    """Resolve project metadata ensuring both id and key when possible."""

    if not project_key and not project_id:
        _tool_args_invalid("project_key or project_id required", details={"missing": ["project_key", "project_id"]})

    if not settings.atlassian_base_url:
        raise ExternalServiceError("Atlassian base URL is not configured")

    identifier = project_id or project_key
    identifier = identifier.strip() if isinstance(identifier, str) else str(identifier)
    url = f"{settings.atlassian_base_url.rstrip('/')}/rest/api/3/project/{identifier}"  # accepts key or id

    with sync_client(timeout=30) as client:
        response = client.get(url, headers=_auth_headers())
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            body = exc.response.text[:500]
            if status in {400, 401, 403, 404}:
                _tool_args_invalid(
                    f"Jira project lookup failed ({status})",
                    details={"body": body, "project_key": project_key, "project_id": project_id},
                )
            raise ExternalServiceError(f"Jira {status}: {body}") from exc
        data = response.json()
        resolved_id = data.get("id") or project_id
        resolved_key = data.get("key") or project_key
        return {
            "id": _to_str_or_none(resolved_id),
            "key": _to_str_or_none(resolved_key),
            "name": data.get("name"),
        }


def get_epic_name_field_id() -> str | None:
    """Return the Jira custom field id used for the Epic Name, if available."""

    if settings.atlassian_epic_name_field_id:
        return settings.atlassian_epic_name_field_id

    global _EPIC_NAME_FIELD_ID_CACHE, _EPIC_NAME_FIELD_LOOKUP_FAILED
    if _EPIC_NAME_FIELD_ID_CACHE:
        return _EPIC_NAME_FIELD_ID_CACHE
    if _EPIC_NAME_FIELD_LOOKUP_FAILED:
        return None

    if not settings.atlassian_base_url:
        raise ExternalServiceError("Atlassian base URL is not configured")

    with _EPIC_NAME_FIELD_LOCK:
        if _EPIC_NAME_FIELD_ID_CACHE:
            return _EPIC_NAME_FIELD_ID_CACHE
        if _EPIC_NAME_FIELD_LOOKUP_FAILED:
            return None

        url = f"{settings.atlassian_base_url.rstrip('/')}/rest/api/3/field"
        with sync_client(timeout=60) as client:
            response = client.get(url, headers=_auth_headers())
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                body = exc.response.text[:800]
                raise ExternalServiceError(f"Jira {exc.response.status_code}: {body}") from exc

            for field in response.json():
                if isinstance(field, dict) and field.get("name") == "Epic Name":
                    field_id = field.get("id")
                    if field_id:
                        _EPIC_NAME_FIELD_ID_CACHE = str(field_id)
                        return _EPIC_NAME_FIELD_ID_CACHE

        _EPIC_NAME_FIELD_LOOKUP_FAILED = True
        return None


def _ensure_description_adf(description_adf: Dict[str, Any] | None, description_text: str | None) -> Dict[str, Any]:
    if description_adf:
        return description_adf
    text = (description_text or "").strip() or "Auto-generated"
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]},
        ],
    }


def build_jira_fields(
    request: PublishJiraRequest,
    description_adf: Dict[str, Any],
    labels: List[str] | None,
    project_meta: Dict[str, Any],
) -> Dict[str, Any]:
    project_ref: Dict[str, Any]
    project_id = _to_str_or_none(project_meta.get("id"))
    project_key = _to_str_or_none(project_meta.get("key"))
    if project_id:
        project_ref = {"id": project_id}
    elif project_key:
        project_ref = {"key": project_key}
    else:
        _tool_args_invalid("Unable to resolve Jira project reference")

    fields: Dict[str, Any] = {
        "project": project_ref,
        "issuetype": {"name": request.issue_type},
        "summary": request.summary,
        "description": description_adf,
    }

    if labels:
        fields["labels"] = labels

    if request.issue_type == "Sub-task":
        fields["parent"] = {"key": str(request.parent_issue_key)}

    return {"fields": fields}


def _epic_name_allowed_on_create(project_key: str | None, project_id: str | None, field_id: str) -> bool:
    cache_key = (project_key, project_id, field_id)
    if cache_key in _EPIC_CREATE_META_CACHE:
        return _EPIC_CREATE_META_CACHE[cache_key]

    if not settings.atlassian_base_url:
        raise ExternalServiceError("Atlassian base URL is not configured")

    params: List[Tuple[str, str]] = [("issuetypeNames", "Epic"), ("expand", "projects.issuetypes.fields")]
    if project_key:
        params.append(("projectKeys", project_key))
    if project_id:
        params.append(("projectId", str(project_id)))

    url = f"{settings.atlassian_base_url.rstrip('/')}/rest/api/3/issue/createmeta"
    with sync_client(timeout=60) as client:
        response = client.get(url, headers=_auth_headers(), params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:800]
            raise ExternalServiceError(f"Jira {exc.response.status_code}: {body}") from exc

        data = response.json() or {}
        for project in data.get("projects", []) or []:
            issue_types = project.get("issuetypes") or []
            for issue_type in issue_types:
                if issue_type.get("name") == "Epic":
                    fields = issue_type.get("fields") or {}
                    allowed = field_id in fields
                    _EPIC_CREATE_META_CACHE[cache_key] = allowed
                    return allowed

    _EPIC_CREATE_META_CACHE[cache_key] = False
    return False


def create_issue(
    *,
    request: PublishJiraRequest,
    description_adf: Dict[str, Any] | None = None,
    labels: List[str] | None = None,
    epic_name_field_id: str | None = None,
) -> Dict[str, Any]:
    """Create a Jira issue (Epic/Task/etc) and return identifiers."""

    if not settings.atlassian_base_url:
        raise ExternalServiceError("Atlassian base URL is not configured")

    project_meta = {
        "id": _to_str_or_none(request.project_id),
        "key": _to_str_or_none(request.project_key),
    }
    if not project_meta["id"] or not project_meta["key"]:
        resolved = resolve_project(request.project_key, request.project_id)
        project_meta["id"] = project_meta["id"] or _to_str_or_none(resolved.get("id"))
        project_meta["key"] = project_meta["key"] or _to_str_or_none(resolved.get("key"))

    payload = build_jira_fields(
        request=request,
        description_adf=_ensure_description_adf(description_adf, request.description_text),
        labels=labels,
        project_meta=project_meta,
    )

    fields = payload["fields"]
    epic_field_id_used: str | None = None
    if request.issue_type == "Epic":
        candidate_field_id = _to_str_or_none(epic_name_field_id) or get_epic_name_field_id()
        epic_value = _to_str_or_none(request.epic_name) or _to_str_or_none(request.summary)
        project_key = _to_str_or_none(project_meta.get("key"))
        project_id = _to_str_or_none(project_meta.get("id"))
        if candidate_field_id and epic_value and (project_key or project_id):
            if _epic_name_allowed_on_create(project_key, project_id, candidate_field_id):
                fields[candidate_field_id] = epic_value
                epic_field_id_used = candidate_field_id

    url = f"{settings.atlassian_base_url.rstrip('/')}/rest/api/3/issue"

    with sync_client(timeout=60) as client:
        response = client.post(url, headers=_auth_headers(), json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            body = exc.response.text[:800]
            if status == 400:
                if request.issue_type == "Epic" and epic_field_id_used:
                    mentions_field = False
                    try:
                        error_json = exc.response.json()
                    except ValueError:
                        error_json = {}
                    field_errors = (error_json.get("errors") or {}) if isinstance(error_json, dict) else {}
                    field_error = None
                    if isinstance(field_errors, dict):
                        field_error = field_errors.get(epic_field_id_used)
                    if isinstance(field_error, str):
                        lower_msg = field_error.lower()
                        if "cannot be set" in lower_msg or "not on the appropriate screen" in lower_msg:
                            mentions_field = True
                    if not mentions_field and epic_field_id_used in (body or ""):
                        mentions_field = True

                    if mentions_field:
                        trimmed_payload = {**payload, "fields": dict(payload["fields"])}
                        trimmed_payload["fields"].pop(epic_field_id_used, None)
                        retry_response = client.post(url, headers=_auth_headers(), json=trimmed_payload)
                        try:
                            retry_response.raise_for_status()
                        except httpx.HTTPStatusError as retry_exc:
                            retry_body = retry_exc.response.text[:800]
                            _upstream_validation_error(
                                "Jira epic creation failed after retry",
                                details={
                                    "status": retry_exc.response.status_code,
                                    "body": retry_body,
                                    "payload": trimmed_payload,
                                },
                            )

                        data = retry_response.json()
                        key = data.get("key")
                        return {
                            "key": key,
                            "project_id": project_meta.get("id"),
                            "project_key": project_meta.get("key"),
                            "url": f"{settings.atlassian_base_url.rstrip('/')}/browse/{key}",
                        }

                _upstream_validation_error(
                    f"Jira issue create failed ({status})",
                    details={"body": body, "payload": payload},
                )
            if status in {401, 403, 404}:
                _tool_args_invalid(
                    f"Jira issue create failed ({status})",
                    details={"body": body, "payload": payload},
                )
            raise ExternalServiceError(f"Jira {status}: {body}") from exc

        data = response.json()
        key = data.get("key")
        return {
            "key": key,
            "project_id": project_meta.get("id"),
            "project_key": project_meta.get("key"),
            "url": f"{settings.atlassian_base_url.rstrip('/')}/browse/{key}",
        }


def create_epic(
    *,
    request: PublishJiraRequest,
    description_adf: Dict[str, Any] | None = None,
    labels: List[str] | None = None,
    epic_name_field_id: str | None = None,
    project_id: str | None = None,
    project_key: str | None = None,
) -> Dict[str, Any]:
    """Backwards-compatible wrapper that always creates an Epic."""

    epic_request = request
    if request.issue_type != "Epic":
        epic_request = request.model_copy(update={"issue_type": "Epic"})
    # Preserve request values when callers pass explicit identifiers to satisfy
    # legacy usages that expect these keywords to be accepted.
    if project_id and not epic_request.project_id:
        epic_request = epic_request.model_copy(update={"project_id": project_id})
    if project_key and not epic_request.project_key:
        epic_request = epic_request.model_copy(update={"project_key": project_key})
    return create_issue(
        request=epic_request,
        description_adf=description_adf,
        labels=labels,
        epic_name_field_id=epic_name_field_id,
    )
