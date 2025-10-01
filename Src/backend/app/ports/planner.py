# FILE: northstar/backend/app/agentic/planner.py
"""
Agentic planner + executor for North Star.
"""
from __future__ import annotations
from typing import Any, Callable, Dict, List
import httpx
import re
from fastapi import HTTPException
from app.adapters.cerebras_planner import chat_json
from app.application.policy_bus import enforce
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
    try:
        plan = chat_json(full_prompt, SCHEMA_HINT)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Planner upstream error: {exc.response.status_code}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Planner parsing error: {exc}") from exc
    if not isinstance(plan, dict) or "steps" not in plan:
        raise HTTPException(status_code=500, detail="Planner returned invalid structure.")
    return plan

# ---- Small templating for step args -----------------------------------------

_PLACEHOLDER = re.compile(r"\$\{([^}]+)\}")

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
