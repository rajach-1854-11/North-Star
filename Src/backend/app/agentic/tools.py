"""Agent tools and registration conveniences for the planner."""

from __future__ import annotations

from typing import Any, Dict, List, Generator
from contextlib import contextmanager


from fastapi import HTTPException
from loguru import logger
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.adapters import confluence_adapter, jira_adapter
from app.application.policy_bus import enforce
from app.config import settings
import app.deps as deps
from app.domain.errors import ExternalServiceError
from app.domain import models as m
from app.ports.planner import register_tool
from app.ports.staffing import recommend_staff as recommend_staff_port
from app.schemas.publish import PublishConfluenceRequest, PublishJiraRequest
from worker.handlers.evidence_builder import to_confluence_html

from .utility import local_extract_for_fields, validate_tool_args


def _validation_error_to_http(exc: ValidationError) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={
            "code": "TOOL_ARGS_INVALID",
            "message": "Invalid tool arguments",
            "details": exc.errors(),
        },
    )


@contextmanager
def _borrow_session(db_session: Session | None = None) -> Generator[Session, None, None]:
    if db_session is not None:
        yield db_session
        return

    session = deps.SessionLocal()
    try:
        yield session
    finally:
        session.close()


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
    db_session: Session | None = None,
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

    desired_k = max(limit or 0, k or 0, 40)
    payload = retriever_port.rag_search(
        tenant_id=tenant_id,
        user_claims=user_claims,
        query=query,
        targets=targets or default_targets or ["global"],
        k=desired_k,
        strategy=strategy,
        include_rosetta=include_rosetta,
        known_projects=inferred_known,
        db=db_session,
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
    db_session: Session | None = None,
    **_: Any,
) -> Dict[str, Any]:
    role = user_claims.get("role", "Dev")
    enforce("publish_artifact", role)

    allowed_list = user_claims.get("allowed_tools")
    allowed_set = {str(tool).lower() for tool in allowed_list or [] if tool}
    jira_allowed = allowed_list is None or "jira" in allowed_set
    llm_allowed = allowed_list is not None and "llm" in allowed_set

    context_items: List[Dict[str, Any]] = user_claims.get("chat_context", [])  # type: ignore[assignment]

    if not settings.atlassian_base_url or not settings.atlassian_email or not settings.atlassian_api_token:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "ATLASSIAN_CONFIG_MISSING",
                "message": "Atlassian Jira integration is not configured",
            },
        )

    summary_value = (summary or "").strip()
    description_value = (description_text or description or "").strip()

    validation = validate_tool_args(
        "jira_epic",
        {"summary": summary_value, "description": description_value, "description_text": description_value},
    )

    if not validation["ok"]:
        suggestions = local_extract_for_fields(context_items, validation["missing"])
        if not jira_allowed:
            reply_lines = [
                f"⚠️ Jira creation blocked: missing required fields: {', '.join(validation['missing'])}.",
                "Suggested action:",
                "- Provide these fields explicitly in your request, or",
                "- Re-run with allowed_tools including 'jira' and optionally 'llm' for auto-generation.",
            ]
            if suggestions:
                reply_lines.append("Auto-suggestions:")
                for field, value in suggestions.items():
                    reply_lines.append(f"- {field}: \"{value}\"")
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "TOOL_ARGS_INVALID",
                    "message": "Jira issue requires additional fields",
                    "details": {"missing": validation["missing"], "suggestions": suggestions},
                    "reply_md": "\n".join(reply_lines),
                },
            )

        autofill = suggestions.copy()
        if llm_allowed:
            for key, value in list(autofill.items()):
                autofill[key] = f"{value} (auto-generated)"

        summary_value = summary_value or autofill.get("summary", "")
        description_value = description_value or autofill.get("description_text") or autofill.get("description", "")

        validation = validate_tool_args(
            "jira_epic",
            {"summary": summary_value, "description": description_value, "description_text": description_value},
        )
        if not validation["ok"]:
            reply_lines = [
                f"⚠️ Jira creation blocked: missing required fields: {', '.join(validation['missing'])}.",
                "Suggested action:",
                "- Provide the missing fields directly, or",
                "- Allow tools ['jira','llm'] so the agent can auto-generate them.",
            ]
            if suggestions:
                reply_lines.append("Auto-suggestions:")
                for field, value in suggestions.items():
                    reply_lines.append(f"- {field}: \"{value}\"")
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "TOOL_ARGS_INVALID",
                    "message": "Jira issue requires additional fields",
                    "details": {"missing": validation["missing"], "suggestions": suggestions},
                    "reply_md": "\n".join(reply_lines),
                },
            )

    try:
        request = PublishJiraRequest(
            project_key=project_key,
            project_id=project_id,
            issue_type=issue_type or "Epic",
            summary=summary_value,
            description_text=description_value or description,
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
            with _borrow_session(db_session) as session:
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
            allow_external=jira_allowed,
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
    db_session: Session | None = None,
    **_: Any,
) -> Dict[str, Any]:
    _ = db_session  # shared session kept for interface parity
    role = user_claims.get("role", "Dev")
    enforce("publish_artifact", role)

    allowed_list = user_claims.get("allowed_tools")
    allowed_set = {str(tool).lower() for tool in allowed_list or [] if tool}
    confluence_allowed = allowed_list is None or "confluence" in allowed_set
    llm_allowed = allowed_list is not None and "llm" in allowed_set
    context_items: List[Dict[str, Any]] = user_claims.get("chat_context", [])  # type: ignore[assignment]

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

    title_value = (title or "").strip()
    body_value = (body_html or "").strip()

    validation = validate_tool_args("confluence_page", {"title": title_value, "body_html": body_value})
    if not validation["ok"]:
        suggestions = local_extract_for_fields(context_items, validation["missing"])
        if not confluence_allowed:
            reply_lines = [
                f"⚠️ Confluence publish blocked: missing required fields: {', '.join(validation['missing'])}.",
                "Suggested action:",
                "- Provide the missing fields explicitly, or",
                "- Re-run with allowed_tools including 'confluence' and optionally 'llm'.",
            ]
            if suggestions:
                reply_lines.append("Auto-suggestions:")
                for field, value in suggestions.items():
                    reply_lines.append(f"- {field}: \"{value}\"")
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "TOOL_ARGS_INVALID",
                    "message": "Confluence page requires additional fields",
                    "details": {"missing": validation["missing"], "suggestions": suggestions},
                    "reply_md": "\n".join(reply_lines),
                },
            )

        autofill = suggestions.copy()
        if llm_allowed:
            for key, value in list(autofill.items()):
                autofill[key] = f"{value} (auto-generated)"
        title_value = title_value or autofill.get("title", title_value)
        body_value = body_value or autofill.get("body_html", body_value)

        validation = validate_tool_args("confluence_page", {"title": title_value, "body_html": body_value})
        if not validation["ok"]:
            reply_lines = [
                f"⚠️ Confluence publish blocked: missing required fields: {', '.join(validation['missing'])}.",
                "Suggested action:",
                "- Provide the missing fields directly, or",
                "- Allow tools ['confluence','llm'] for automatic generation.",
            ]
            if suggestions:
                reply_lines.append("Auto-suggestions:")
                for field, value in suggestions.items():
                    reply_lines.append(f"- {field}: \"{value}\"")
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "TOOL_ARGS_INVALID",
                    "message": "Confluence page requires additional fields",
                    "details": {"missing": validation["missing"], "suggestions": suggestions},
                    "reply_md": "\n".join(reply_lines),
                },
            )

    try:
        request = PublishConfluenceRequest(
            space_key=resolved_space_key,
            space_id=resolved_space_id,
            title=title_value,
            body_html=body_value,
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
            allow_external=confluence_allowed,
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


def staffing_recommend_tool(
    *,
    user_claims: Dict[str, Any],
    project_key: str | None = None,
    project_id: int | str | None = None,
    top_k: int = 3,
    include_full: bool = False,
    db_session: Session | None = None,
) -> Dict[str, Any]:
    role = user_claims.get("role", "Dev")
    enforce("staffing_recommend", role)

    tenant_id = user_claims.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Missing tenant context")

    resolved_project = None
    resolved_project_id: int | None = None
    resolved_project_key: str | None = None

    with _borrow_session(db_session) as session:
        if project_id is not None:
            try:
                resolved_project_id = int(project_id)
            except (TypeError, ValueError):
                resolved_project_id = None
            else:
                resolved_project = session.get(m.Project, resolved_project_id)
                if resolved_project and resolved_project.tenant_id != tenant_id:
                    resolved_project = None

        key_candidate = str(project_key or "").strip()
        if resolved_project is None and key_candidate:
            resolved_project = (
                session.query(m.Project)
                .filter(m.Project.tenant_id == tenant_id)
                .filter(func.lower(m.Project.key) == key_candidate.lower())
                .one_or_none()
            )

        if resolved_project is None:
            accessible = [
                str(project).strip()
                for project in user_claims.get("accessible_projects", [])
                if isinstance(project, str) and str(project).strip().lower() != "global"
            ]
            fallback_key = next((value for value in accessible if value), None)
            if fallback_key:
                resolved_project = (
                    session.query(m.Project)
                    .filter(m.Project.tenant_id == tenant_id)
                    .filter(func.lower(m.Project.key) == fallback_key.lower())
                    .one_or_none()
                )

        if resolved_project is None:
            raise HTTPException(status_code=404, detail="Project not found for staffing recommendation")

        resolved_project_id = resolved_project.id
        resolved_project_key = resolved_project.key

        response = recommend_staff_port(
            session,
            user_claims=dict(user_claims),
            project_id=resolved_project.id,
        )

        payload = response.model_dump()
        all_candidates: List[Dict[str, Any]] = payload.get("candidates", []) or []

        developer_ids: List[int] = []
        for candidate in all_candidates:
            dev_id = candidate.get("developer_id")
            try:
                parsed_id = int(dev_id)
            except (TypeError, ValueError):
                continue
            developer_ids.append(parsed_id)
            candidate["developer_id"] = parsed_id

        name_map: Dict[int, str] = {}
        if developer_ids:
            rows = (
                session.query(m.Developer.id, m.Developer.display_name)
                .filter(m.Developer.id.in_(sorted(set(developer_ids))))
                .all()
            )
            name_map = {dev_id: display_name for dev_id, display_name in rows}

        for candidate in all_candidates:
            dev_id = candidate.get("developer_id")
            if isinstance(dev_id, int) and dev_id in name_map:
                candidate["developer_name"] = name_map[dev_id]

        try:
            clamped_top = int(top_k)
        except (TypeError, ValueError):
            clamped_top = 3
        clamped_top = max(1, min(clamped_top, 10))
        trimmed_candidates = all_candidates[:clamped_top]

        summary = ""
        top_candidate = trimmed_candidates[0] if trimmed_candidates else None
        if top_candidate:
            name = top_candidate.get("developer_name") or f"Developer {top_candidate.get('developer_id')}"
            fit = top_candidate.get("fit")
            summary = f"Top staffing match: {name}"
            if isinstance(fit, (int, float)):
                summary += f" (fit {fit:.2f})"
        else:
            summary = f"No staffing candidates available for {resolved_project_key}."

        result: Dict[str, Any] = {
            "project": {
                "id": resolved_project_id,
                "key": resolved_project_key,
                "name": resolved_project.name,
            },
            "candidates": trimmed_candidates,
            "top_candidate": top_candidate,
            "total_candidates": len(all_candidates),
            "summary": summary,
        }

        if include_full:
            result["all_candidates"] = all_candidates

        return result


def register_all_tools() -> None:
    register_tool("rag_search", rag_search_tool)
    register_tool("jira_epic", jira_epic_tool)
    register_tool("confluence_page", confluence_page_tool)
    register_tool("staffing_recommend", staffing_recommend_tool)
