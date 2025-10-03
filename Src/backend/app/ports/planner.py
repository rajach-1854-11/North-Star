# FILE: northstar/backend/app/agentic/planner.py
"""
Agentic planner + executor for North Star.
"""
from __future__ import annotations
from typing import Any, Callable, Dict, List, Tuple
from datetime import datetime, timezone
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
_ANGLE_PLACEHOLDER = re.compile(r"<[^>]+>")
_BRACE_PLACEHOLDER = re.compile(r"\[[^\]]+\]")
_KNOWN_PLACEHOLDERS = {"todo", "tbd", "placeholder", "fill me", "fill in", "lorem ipsum", "sample"}

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
    if _ANGLE_PLACEHOLDER.search(stripped) or _BRACE_PLACEHOLDER.search(stripped):
        return True
    for token in _KNOWN_PLACEHOLDERS:
        if token in lowered:
            return True
    if lowered.startswith("insert ") or lowered.startswith("add placeholder"):
        return True
    return False


def _first_accessible_project(user_claims: Dict[str, Any]) -> str | None:
    projects = user_claims.get("accessible_projects") or []
    for key in projects:
        if isinstance(key, str) and key.lower() != "global":
            return key
    return None


def _sanitize_tool_args(
    tool: str,
    args: Dict[str, Any],
    user_claims: Dict[str, Any],
    plan: Dict[str, Any],
) -> Tuple[Dict[str, Any], str | None]:
    prompt = plan.get("_meta", {}).get("task_prompt") or ""
    plan_summary = plan.get("output", {}).get("summary")
    summary_seed = _normalized_snippet(plan_summary or prompt)
    sanitized = dict(args)

    if tool == "jira_epic":
        project_key = sanitized.get("project_key")
        if _looks_placeholder(project_key):
            fallback_project = _first_accessible_project(user_claims)
            if fallback_project:
                sanitized["project_key"] = fallback_project
            else:
                return sanitized, "no project key available"
        summary = sanitized.get("summary")
        if _looks_placeholder(summary):
            sanitized["summary"] = summary_seed
        description = sanitized.get("description")
        if _looks_placeholder(description):
            sanitized["description"] = f"Auto-generated by North Star based on task: {summary_seed}"
        return sanitized, None

    if tool == "confluence_page":
        space = sanitized.get("space")
        if _looks_placeholder(space):
            space = getattr(settings, "atlassian_space", None)
            if space:
                sanitized["space"] = space
        if _looks_placeholder(sanitized.get("space")):
            return sanitized, "no Confluence space provided"

        title = sanitized.get("title")
        if _looks_placeholder(title):
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            sanitized["title"] = f"Auto page - {summary_seed} ({timestamp} UTC)"

        html = sanitized.get("html")
        if _looks_placeholder(html):
            sanitized.pop("html", None)

        evidence = sanitized.get("evidence")
        if _looks_placeholder(evidence):
            sanitized["evidence"] = summary_seed

        return sanitized, None

    return sanitized, None

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
