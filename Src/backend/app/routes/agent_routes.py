"""Agent planning and execution routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import deps
from app.deps import require_role
from app.domain.schemas import AgentQueryReq, AgentQueryResp
from app.ports.planner import create_plan, execute_plan

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/query", response_model=AgentQueryResp)
def agent_query(
    req: AgentQueryReq,
    user: Dict[str, Any] = Depends(require_role(("Admin", "PO", "BA", "Dev"))),
    db: Session = Depends(deps.get_db),
) -> AgentQueryResp:
    """Generate and execute an agentic plan for the provided prompt."""

    try:
        plan = create_plan(task_prompt=req.prompt, allowed_tools=req.allowed_tools)
        if req.tool_overrides:
            overrides = req.tool_overrides
            for step in plan.get("steps", []):
                tool_name = step.get("tool")
                if not tool_name:
                    continue
                override_args = overrides.get(tool_name)
                if not isinstance(override_args, dict):
                    continue
                step_args = step.setdefault("args", {}) or {}
                for key, value in override_args.items():
                    if value is not None:
                        step_args[key] = value
        result = execute_plan(plan, user_claims=user, db_session=db)
    except HTTPException as exc:
        detail = exc.detail
        if isinstance(detail, dict) and detail.get("code"):
            return JSONResponse(status_code=exc.status_code, content=detail)
        raise
    message: str | None = None
    if result.get("output", {}).get("notes") == "fallback_heuristic_plan":
        message = "Planner service unreachable; responding with heuristic fallback. Please retry later."
    resp_kwargs = {
        "plan": plan,
        "artifacts": result.get("artifacts", {}),
        "output": result.get("output", {}),
    }
    if message:
        resp_kwargs["message"] = message
    return AgentQueryResp(**resp_kwargs)
