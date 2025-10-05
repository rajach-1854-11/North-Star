"""Agent tools and registration conveniences for the planner."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import HTTPException
from loguru import logger
from pydantic import ValidationError

from app.adapters import confluence_adapter, jira_adapter
from app.application.policy_bus import enforce
from app.config import settings
import app.deps as deps
from app.domain.errors import ExternalServiceError
from app.domain import models as m
from app.ports.planner import register_tool
from app.schemas.publish import PublishConfluenceRequest, PublishJiraRequest
from worker.handlers.evidence_builder import to_confluence_html


def _validation_error_to_http(exc: ValidationError) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={
            "code": "TOOL_ARGS_INVALID",
            "message": "Invalid tool arguments",
            "details": exc.errors(),
        },
    )


def rag_search_tool(
    *,
    user_claims: Dict[str, Any],
    query: str,
    targets: List[str] | None = None,
    k: int = 12,
    strategy: str = "qdrant",
    limit: int | None = None,
    include_rosetta: bool = False,
    known_projects: List[str] | None = None,
) -> Dict[str, Any]:
    """Expose the retrieval service as a planner tool."""
    tenant_id = user_claims.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Missing tenant context")

    from app.ports import retriever as retriever_port

    accessible_projects = [
        project
        for project in user_claims.get("accessible_projects", [])
        if isinstance(project, str) and project
    ]
    default_targets = [project for project in accessible_projects if project.lower() != "global"]
    if "global" in {project.lower() for project in accessible_projects}:
        default_targets.append("global")

    inferred_known = known_projects or default_targets or accessible_projects

    payload = retriever_port.rag_search(
        tenant_id=tenant_id,
        user_claims=user_claims,
        query=query,
        targets=targets or default_targets or ["global"],
        k=k,
        strategy=strategy,
        include_rosetta=include_rosetta,
        known_projects=inferred_known,
    )
    return payload

def jira_epic_tool(
    *,
    user_claims: Dict[str, Any],
    project_key: str | None = None,
    project_id: str | None = None,
    issue_type: str = "Epic",
    summary: str,
    description: str | None = None,
    description_text: str | None = None,
    description_adf: Dict[str, Any] | None = None,
    epic_name: str | None = None,
    epic_name_field_id: str | None = None,
    parent_issue_key: str | None = None,
    labels: List[str] | None = None,
    **_: Any,
) -> Dict[str, Any]:
    role = user_claims.get("role", "Dev")
    enforce("publish_artifact", role)

    if not settings.atlassian_base_url or not settings.atlassian_email or not settings.atlassian_api_token:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "ATLASSIAN_CONFIG_MISSING",
                "message": "Atlassian Jira integration is not configured",
            },
        )

    try:
        request = PublishJiraRequest(
            project_key=project_key,
            project_id=project_id,
            issue_type=issue_type or "Epic",
            summary=summary,
            description_text=description_text or description,
            epic_name=epic_name,
            parent_issue_key=parent_issue_key,
        )
    except ValidationError as exc:
        raise _validation_error_to_http(exc)

    normalised_labels = labels or []

    resolved_key = request.project_key
    resolved_id = request.project_id
    if not resolved_key and resolved_id:
        try:
            db_project_id = int(resolved_id)
        except (TypeError, ValueError):
            db_project_id = None
        else:
            with deps.SessionLocal() as session:
                project_row = session.get(m.Project, db_project_id)
                if project_row:
                    resolved_key = project_row.key
                    resolved_id = None

    if resolved_key:
        resolved_key = str(resolved_key).strip() or None
    if resolved_id:
        resolved_id = str(resolved_id).strip() or None

    if resolved_key != request.project_key or resolved_id != request.project_id:
        request = request.model_copy(update={"project_key": resolved_key, "project_id": resolved_id})

    try:
        project_meta = jira_adapter.resolve_project(project_key=request.project_key, project_id=request.project_id)
    except TypeError:
        if request.project_key:
            project_meta = jira_adapter.resolve_project(request.project_key)
        elif request.project_id:
            project_meta = jira_adapter.resolve_project(request.project_id)
        else:
            raise
    except HTTPException:
        raise
    except ExternalServiceError as exc:
        return {"error": exc.message}

    resolved_id = project_meta.get("id") or request.project_id
    resolved_key = project_meta.get("key") or request.project_key
    request = request.model_copy(update={"project_id": resolved_id, "project_key": resolved_key})

    try:
        result = jira_adapter.create_epic(
            request=request,
            description_adf=description_adf,
            labels=normalised_labels,
            epic_name_field_id=epic_name_field_id,
            project_id=request.project_id,
            project_key=request.project_key,
        )
        logger.info(
            "publish_artifact:jira_epic",
            project_key=request.project_key,
            project_id=request.project_id,
            actor_role=role,
            actor="redacted",
        )
        return result
    except ExternalServiceError as exc:
        return {"error": exc.message}


def confluence_page_tool(
    *,
    user_claims: Dict[str, Any],
    space_key: str | None = None,
    space_id: str | None = None,
    title: str,
    body_html: str | None = None,
    evidence: str | None = None,
    **_: Any,
) -> Dict[str, Any]:
    role = user_claims.get("role", "Dev")
    enforce("publish_artifact", role)

    if not settings.atlassian_base_url or not settings.atlassian_email or not settings.atlassian_api_token:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "ATLASSIAN_CONFIG_MISSING",
                "message": "Atlassian Confluence integration is not configured",
            },
        )

    resolved_space_key = space_key or settings.atlassian_space
    resolved_space_id = space_id or settings.atlassian_space_id

    if not resolved_space_key and not resolved_space_id:
        default_space = confluence_adapter.discover_default_space()
        resolved_space_key = default_space.get("key")
        resolved_space_id = default_space.get("id")

    try:
        request = PublishConfluenceRequest(
            space_key=resolved_space_key,
            space_id=resolved_space_id,
            title=title,
            body_html=body_html,
        )
    except ValidationError as exc:
        raise _validation_error_to_http(exc)

    try:
        space = confluence_adapter.resolve_space(space_key=request.space_key, space_id=request.space_id)
    except TypeError:
        # Support older call signatures (tests patch resolve_space expecting positional args)
        if request.space_key:
            space = confluence_adapter.resolve_space(request.space_key)
        elif request.space_id:
            space = confluence_adapter.resolve_space(request.space_id)
        else:
            raise
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        code = detail.get("code") if isinstance(detail, dict) else None
        if exc.status_code == 400 and code == "TOOL_ARGS_INVALID":
            fallback_space = confluence_adapter.discover_default_space()
            updated_request = request.model_copy(
                update={
                    "space_key": fallback_space.get("key"),
                    "space_id": fallback_space.get("id"),
                }
            )
            try:
                space = confluence_adapter.resolve_space(
                    space_key=updated_request.space_key,
                    space_id=updated_request.space_id,
                )
            except TypeError:
                space = confluence_adapter.resolve_space(
                    updated_request.space_key or updated_request.space_id
                )
            request = updated_request
        else:
            raise

    final_body = request.body_html or (to_confluence_html(evidence) if evidence else None)
    if final_body is None:
        final_body = to_confluence_html("Auto-generated by North Star")

    try:
        result = confluence_adapter.create_page(
            space_id=space["id"],
            space_key=space["key"],
            title=request.title,
            body_html=final_body,
            draft=settings.confluence_draft_mode,
        )
        logger.info(
            "publish_artifact:confluence_page",
            space_key=space["key"],
            space_id=space.get("id"),
            title=request.title[:120],
            actor_role=role,
            actor="redacted",
        )
        return result
    except ExternalServiceError as exc:
        return {"error": exc.message}


def register_all_tools() -> None:
    register_tool("rag_search", rag_search_tool)
    register_tool("jira_epic", jira_epic_tool)
    register_tool("confluence_page", confluence_page_tool)
