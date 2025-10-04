# FILE: northstar/backend/app/agentic/planner.py
"""
Agentic planner + executor for North Star.
"""
from __future__ import annotations
from typing import Any, Callable, Dict, List, Sequence, Tuple
from datetime import datetime, timezone
import html
import httpx
import re
from fastapi import HTTPException
from app.config import settings
from app.adapters.cerebras_planner import chat_json as cerebras_chat_json
from app.adapters.openai_planner import chat_json as openai_chat_json
from app.application.policy_bus import enforce
from app.domain.errors import ExternalServiceError
from loguru import logger

# ---- Tool registry (names -> callables) -------------------------------------

ToolFn = Callable[..., Any]
_TOOL_REGISTRY: Dict[str, ToolFn] = {}

def register_tool(name: str, fn: ToolFn) -> None:
    """Register a callable for planner execution under *name*."""

    _TOOL_REGISTRY[name] = fn

def list_tools() -> List[str]:
    """Return registered tool names sorted alphabetically."""

    return sorted(_TOOL_REGISTRY.keys())

# ---- Planning ---------------------------------------------------------------

SCHEMA_HINT = """JSON schema:
{
  "steps": [
    {"tool": "rag_search" | "jira_epic" | "confluence_page", "args": { }}
  ],
  "output": {
    "summary": str,
    "gaps": [{"topic": str, "confidence": float}],
    "two_week_plan": [{"day": int, "task": str}],
    "notes": str
  }
}
"""

SYSTEM_PROMPT = (
    "You are North Star's planning agent. You must return ONLY valid JSON, "
    "matching the provided schema. Do not include markdown fences. Keep steps minimal."
)

def create_plan(task_prompt: str, allowed_tools: List[str] | None = None) -> Dict[str, Any]:
    """Call the planner LLM and return the generated plan payload."""

    tools_hint = ", ".join(allowed_tools or ["rag_search", "jira_epic", "confluence_page"])
    full_prompt = (
        f"Available tools: {tools_hint}\n"
        f"Task:\n{task_prompt}\n"
        "Constraints:\n- Prefer 1-5 steps.\n- Keep arguments compact and explicit.\n"
        "Return strictly valid JSON."
    )
    # Select LLM provider (default is OpenAI/GPT-5)
    provider = (settings.llm_provider or "openai").lower()
    chat_impl = openai_chat_json if provider == "openai" else cerebras_chat_json
    try:
        plan = chat_impl(full_prompt, SCHEMA_HINT)
    except ExternalServiceError as exc:
        logger.warning("Planner provider unavailable; using heuristic fallback. reason={}".format(exc))
        return _fallback_plan(task_prompt, allowed_tools)
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Planner HTTP failure; using heuristic fallback. status={}".format(exc.response.status_code)
        )
        return _fallback_plan(task_prompt, allowed_tools)
    except HTTPException as exc:
        logger.warning("Planner raised HTTPException; using heuristic fallback. detail={}".format(exc.detail))
        return _fallback_plan(task_prompt, allowed_tools)
    except Exception as exc:
        logger.exception("Planner parsing error; using heuristic fallback: {}".format(exc))
        return _fallback_plan(task_prompt, allowed_tools)
    if not isinstance(plan, dict) or "steps" not in plan:
        raise HTTPException(status_code=500, detail="Planner returned invalid structure.")
    plan.setdefault("output", {})
    plan["output"].setdefault("notes", "llm_plan")
    meta = plan.setdefault("_meta", {})
    meta.setdefault("task_prompt", task_prompt)
    return plan


def _fallback_plan(task_prompt: str, allowed_tools: List[str] | None = None) -> Dict[str, Any]:
    """Generate a deterministic plan when the planner service is unavailable."""

    snippet = task_prompt.strip().splitlines()[0] if task_prompt.strip() else "request"
    snippet = snippet[:120]
    alt_tools = ", ".join(allowed_tools or ["rag_search", "jira_epic", "confluence_page"])
    return {
        "steps": [],
        "output": {
            "summary": f"Heuristic plan for {snippet or 'request'}",
            "gaps": [],
            "two_week_plan": [
                {"day": 1, "task": "Review project documentation and architecture diagrams."},
                {"day": 3, "task": "Meet with key stakeholders to clarify goals and workflows."},
                {"day": 6, "task": "Shadow an experienced teammate and document environment setup."},
                {"day": 10, "task": "Deliver a scoped contribution or demo to confirm onboarding."},
            ],
            "notes": "fallback_heuristic_plan",
            "tools_considered": alt_tools,
        },
        "_meta": {"task_prompt": task_prompt},
    }

# ---- Small templating for step args -----------------------------------------

_PLACEHOLDER = re.compile(r"\$\{([^}]+)\}")
_BRACE_PLACEHOLDER = re.compile(r"\[[^\]]+\]")
_KNOWN_PLACEHOLDERS = {"todo", "tbd", "placeholder", "fill me", "fill in", "lorem ipsum", "sample"}
_JIRA_LABEL_INVALID = re.compile(r"[^A-Za-z0-9_-]+")


def _raise_tool_args_invalid(missing: Sequence[str], hint: str) -> None:
    unique_missing = sorted({field for field in missing if field})
    raise HTTPException(
        status_code=400,
        detail={
            "code": "TOOL_ARGS_INVALID",
            "message": hint,
            "details": {"missing": unique_missing},
        },
    )


def _default_confluence_body(plan: Dict[str, Any]) -> str:
    output = plan.get("output", {}) or {}
    summary = (output.get("summary") or "Onboarding plan").strip()
    tasks = output.get("two_week_plan") or []
    gaps = output.get("gaps") or []

    gap_items: list[str] = []
    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        topic = str(gap.get("topic") or "").strip()
        if not topic:
            continue
        confidence = gap.get("confidence")
        if isinstance(confidence, (int, float)):
            gap_items.append(f"<li>{topic} (confidence {confidence:.0%})</li>")
        else:
            gap_items.append(f"<li>{topic}</li>")

    task_items: list[str] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        description = str(task.get("task") or "").strip()
        if not description:
            continue
        day = task.get("day")
        if isinstance(day, (int, float)):
            task_items.append(f"<li><strong>Day {int(day)}</strong>: {description}</li>")
        else:
            task_items.append(f"<li>{description}</li>")

    gaps_html = f"<ul>{''.join(gap_items)}</ul>" if gap_items else ""
    tasks_html = f"<ol>{''.join(task_items)}</ol>" if task_items else ""
    return f"<p>{summary}</p>{gaps_html}{tasks_html}"


def _default_jira_description(plan: Dict[str, Any]) -> str:
    output = plan.get("output", {}) or {}
    summary = (output.get("summary") or "Onboarding objectives").strip()
    tasks = output.get("two_week_plan") or []

    lines: list[str] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        description = str(task.get("task") or "").strip()
        if not description:
            continue
        day = task.get("day")
        if isinstance(day, (int, float)):
            lines.append(f"* Day {int(day)}: {description}")
        else:
            lines.append(f"* {description}")

    if not lines:
        lines.append("* Review project documentation and align with mentor.")

    return f"{summary}\n\n" + "\n".join(lines)


def _adf_from_text(text: str | None) -> Dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raw = "generated by North Star"

    lines = [segment.strip() for segment in raw.splitlines() if segment.strip()]
    if not lines:
        lines = [raw]

    paragraphs = []
    for line in lines:
        paragraphs.append(
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": line},
                ],
            }
        )

    return {
        "type": "doc",
        "version": 1,
        "content": paragraphs,
    }


def _normalise_labels(value: Any) -> List[str]:
    if value is None:
        return []

    if isinstance(value, str):
        items = [part for part in re.split(r"[,\n]+", value) if part is not None]
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]

    normalised: List[str] = []
    seen: set[str] = set()

    for raw_item in items:
        item = str(raw_item or "").strip()
        if not item:
            continue

        collapsed = re.sub(r"\s+", " ", item)
        collapsed = collapsed.replace(" ", "-")
        collapsed = re.sub(r"-+", "-", collapsed)
        collapsed = _JIRA_LABEL_INVALID.sub("", collapsed)
        collapsed = collapsed.strip("-_")
        if not collapsed:
            continue
        if len(collapsed) > 255:
            collapsed = collapsed[:255]
        if not collapsed[0].isalpha():
            collapsed = f"n{collapsed}" if collapsed[0].isdigit() else f"label-{collapsed}"
        if collapsed not in seen:
            normalised.append(collapsed)
            seen.add(collapsed)

    return normalised

def _resolve_value(value: Any, ctx: Dict[str, Any]) -> Any:
    """Recursively resolve templated placeholders from the execution context."""

    if isinstance(value, str):

        def repl(match: re.Match[str]) -> str:
            path = match.group(1)
            # Supported: last.evidence, user.role, user.tenant_id
            cur: Any = ctx
            for part in path.split("."):
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                else:
                    return ""  # missing path -> empty
            return str(cur if cur is not None else "")
        return _PLACEHOLDER.sub(repl, value)
    if isinstance(value, list):
        return [_resolve_value(item, ctx) for item in value]
    if isinstance(value, dict):
        return {key: _resolve_value(item, ctx) for key, item in value.items()}
    return value


def _normalized_snippet(text: str | None, fallback: str = "North Star task") -> str:
    snippet = (text or "").strip()
    if not snippet:
        snippet = fallback
    if len(snippet) > 120:
        snippet = snippet[:117] + "..."
    return snippet


def _looks_placeholder(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if not stripped:
        return True
    lowered = stripped.lower()
    if _PLACEHOLDER.search(stripped):
        return True
    if (
        stripped.startswith("<")
        and stripped.endswith(">")
        and "</" not in stripped
        and stripped.count("<") == 1
        and stripped.count(">") == 1
    ) or _BRACE_PLACEHOLDER.search(stripped):
        return True
    for token in _KNOWN_PLACEHOLDERS:
        if token in lowered:
            return True
    if lowered.startswith("insert ") or lowered.startswith("add placeholder"):
        return True
    return False


def _sanitize_tool_args(
    tool: str,
    args: Dict[str, Any],
    user_claims: Dict[str, Any],
    plan: Dict[str, Any],
) -> Tuple[Dict[str, Any], str | None]:
    raw_args = dict(args)
    meta = plan.get("_meta", {}) if isinstance(plan, dict) else {}
    out = plan.get("output", {}) if isinstance(plan, dict) else {}

    if tool in {"jira_epic", "jira_issue"}:
        def _clean_candidate(value: Any) -> str | None:
            if value is None:
                return None
            text = str(value).strip()
            return text or None

        raw_project_key = raw_args.get("project_key") or raw_args.get("projectKey")
        raw_project_id = raw_args.get("project_id") or raw_args.get("projectId")
        meta_project_key = meta.get("project_key")
        meta_project_id = meta.get("project_id")

        project_key = (
            _clean_candidate(raw_project_key)
            or _clean_candidate(meta_project_key)
            or _clean_candidate(settings.atlassian_project_key)
        )
        project_id = (
            _clean_candidate(raw_project_id)
            or _clean_candidate(meta_project_id)
            or _clean_candidate(settings.atlassian_project_id)
        )

        if _looks_placeholder(project_key):
            project_key = None
        if _looks_placeholder(project_id):
            project_id = None

        allow_project_fallback = (
            _clean_candidate(raw_project_key) is not None
            or not _looks_placeholder(out.get("summary"))
        )
        allow_id_fallback = _clean_candidate(raw_project_id) is not None

        missing_fields: list[str] = []

        if not project_key and not project_id:
            claims_project_id = user_claims.get("project_id")
            if allow_id_fallback and claims_project_id and not _looks_placeholder(claims_project_id):
                project_id = str(claims_project_id).strip()
            if not project_key and allow_project_fallback:
                accessible = user_claims.get("accessible_projects") or []
                fallback_key: str | None = None
                for candidate in accessible:
                    candidate_str = str(candidate).strip()
                    if candidate_str and not _looks_placeholder(candidate_str):
                        lowered = candidate_str.lower()
                        if lowered in {"global", "all", "*", "default"}:
                            fallback_key = fallback_key or candidate_str
                            continue
                        project_key = candidate_str
                        break
                if not project_key and fallback_key:
                    project_key = fallback_key

        if not project_key and not project_id:
            if raw_project_key is not None or meta_project_key is not None or settings.atlassian_project_key:
                missing_fields.append("project_key")
            if raw_project_id is not None or meta_project_id is not None or settings.atlassian_project_id:
                missing_fields.append("project_id")
            if not missing_fields:
                missing_fields.append("project_key")

        issue_type = raw_args.get("issue_type") or raw_args.get("issuetype")
        if _looks_placeholder(issue_type):
            issue_type = "Epic" if tool == "jira_epic" else "Task"
        issue_type_str = str(issue_type).strip()
        issue_type_key = issue_type_str.replace("_", "-").replace(" ", "-").lower()
        issue_type_map = {
            "task": "Task",
            "story": "Story",
            "bug": "Bug",
            "epic": "Epic",
            "sub-task": "Sub-task",
            "subtask": "Sub-task",
        }
        issue_type = issue_type_map.get(issue_type_key, "Task")

        raw_summary = raw_args.get("summary") or raw_args.get("title")
        summary: str | None = None
        if _looks_placeholder(raw_summary):
            fallback_summary = out.get("summary")
            if _looks_placeholder(fallback_summary):
                missing_fields.append("summary")
            else:
                summary = _normalized_snippet(str(fallback_summary))
        else:
            summary = str(raw_summary).strip()
            if not summary:
                missing_fields.append("summary")

        raw_description = raw_args.get("description_text") or raw_args.get("description")
        description_text: str | None = None
        if _looks_placeholder(raw_description):
            summary_signal = not _looks_placeholder(out.get("summary"))
            tasks_signal = any(
                isinstance(task, dict) and str(task.get("task") or "").strip()
                for task in out.get("two_week_plan") or []
            )
            if summary_signal or tasks_signal:
                description_text = _default_jira_description(plan)
            else:
                missing_fields.append("description")
        else:
            description_text = str(raw_description).strip()
            if not description_text:
                missing_fields.append("description")

        if missing_fields:
            _raise_tool_args_invalid(missing_fields, "Jira issue requires additional fields")

        assert summary is not None  # for type checkers
        description_text = (description_text or "generated by North Star").strip() or "generated by North Star"
        description_adf = _adf_from_text(description_text)

        labels = _normalise_labels(raw_args.get("labels"))

        epic_name = raw_args.get("epic_name") or raw_args.get("epicName")
        if issue_type == "Epic" and not epic_name:
            epic_name = summary

        parent_issue_key = raw_args.get("parent_issue_key") or raw_args.get("parentIssueKey")
        if issue_type == "Sub-task":
            if _looks_placeholder(parent_issue_key):
                _raise_tool_args_invalid(["parent_issue_key"], "Sub-task requires parent_issue_key")
            parent_issue_key = str(parent_issue_key).strip()

        sanitized = {
            "project_key": str(project_key).strip() if project_key else None,
            "project_id": str(project_id).strip() if project_id else None,
            "issue_type": issue_type,
            "summary": summary,
            "description_text": description_text,
            "description": description_text,
            "description_adf": description_adf,
            "labels": labels,
            "epic_name": str(epic_name).strip() if epic_name else None,
            "parent_issue_key": parent_issue_key,
            "epic_name_field_id": raw_args.get("epic_name_field_id") or raw_args.get("epicNameFieldId"),
        }

        return sanitized, None

    if tool == "confluence_page":
        space_key = (
            raw_args.get("space_key")
            or raw_args.get("space")
            or meta.get("space_key")
            or settings.atlassian_space
        )
        space_id = (
            raw_args.get("space_id")
            or raw_args.get("spaceId")
            or meta.get("space_id")
            or settings.atlassian_space_id
        )
        if _looks_placeholder(space_key):
            space_key = None
        if _looks_placeholder(space_id):
            space_id = None
        if not space_key and not space_id:
            if (
                settings.atlassian_base_url
                and settings.atlassian_email
                and settings.atlassian_api_token
            ):
                try:
                    from app.adapters import confluence_adapter  # local import to avoid cycles

                    default_space = confluence_adapter.discover_default_space()
                    space_key = default_space.get("key") or space_key
                    space_id = default_space.get("id") or space_id
                except HTTPException:
                    raise
                except ExternalServiceError as exc:
                    logger.warning("Default Confluence space discovery failed: {}", exc)
        if not space_key and not space_id:
            _raise_tool_args_invalid(["space_key", "space_id"], "Confluence page requires space_key or space_id")

        default_title = _normalized_snippet(out.get("summary") or "Onboarding plan")
        title = raw_args.get("title")
        if _looks_placeholder(title):
            title = default_title
        title = (title or default_title).strip()

        body_html = raw_args.get("body_html") or raw_args.get("html") or raw_args.get("body")
        if _looks_placeholder(body_html):
            default_text = raw_args.get("description_text") or out.get("summary") or "generated by North Star"
            body_html = f"<p>{html.escape((default_text or 'generated by North Star').strip() or 'generated by North Star')}</p>"
        body_html = body_html or "<p>Automated onboarding summary.</p>"

        evidence = raw_args.get("evidence") or raw_args.get("notes")
        if _looks_placeholder(evidence):
            evidence = out.get("summary") or "North Star onboarding summary"
        evidence = (evidence or "").strip()

        sanitized = {
            "space_key": str(space_key).strip() if space_key else None,
            "space_id": str(space_id).strip() if space_id else None,
            "title": title,
            "body_html": body_html,
            "evidence": evidence,
        }

        # Maintain compatibility with legacy tool signatures that expect `space`
        # instead of `space_key`. Prefer the configured space key when set so the
        # value matches what downstream callers expect; otherwise fall back to the
        # sanitized key.
        configured_space = getattr(settings, "atlassian_space", None)
        if configured_space:
            sanitized["space"] = str(configured_space).strip()
            if not sanitized["space_key"]:
                sanitized["space_key"] = sanitized["space"]
        elif sanitized["space_key"]:
            sanitized["space"] = sanitized["space_key"]

        return sanitized, None

    return dict(args), None

# ---- Execution --------------------------------------------------------------

def execute_plan(plan: Dict[str, Any], user_claims: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a plan against registered tools while enforcing RBAC."""
    role = user_claims.get("role", "Dev")
    artifacts: Dict[str, Any] = {}
    steps = plan.get("steps", [])

    ctx: Dict[str, Any] = {"user": user_claims, "last": {}}

    for idx, step in enumerate(steps, start=1):
        tool = step.get("tool")
        args = step.get("args", {}) or {}
        if tool not in _TOOL_REGISTRY:
            logger.warning(f"Unknown tool '{tool}' in step {idx}; skipping.")
            continue
        enforce(tool, role)  # RBAC check
        # Resolve placeholders against context
        args = _resolve_value(args, ctx)

        args, skip_reason = _sanitize_tool_args(tool, args, user_claims, plan)
        if skip_reason is not None:
            artifacts[f"step_{idx}:{tool}"] = {"skipped": skip_reason}
            logger.warning(f"Skipping tool '{tool}' in step {idx}: {skip_reason}")
            continue

        try:
            res = _TOOL_REGISTRY[tool](user_claims=user_claims, **args)
            artifacts[f"step_{idx}:{tool}"] = res
            ctx["last"] = res if isinstance(res, dict) else {"value": res}
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Tool '{tool}' failed: {e}")
            artifacts[f"step_{idx}:{tool}"] = {"error": str(e)}
            # keep last unchanged on failure

    return {"artifacts": artifacts, "output": plan.get("output", {})}
