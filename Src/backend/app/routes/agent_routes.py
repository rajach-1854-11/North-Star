"""Agent planning and execution routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.deps import require_role
from app.domain.schemas import AgentQueryReq, AgentQueryResp
from app.ports.planner import create_plan, execute_plan

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/query", response_model=AgentQueryResp)
def agent_query(
    req: AgentQueryReq,
    user: Dict[str, Any] = Depends(require_role(("Admin", "PO", "BA"))),
) -> AgentQueryResp:
    """Generate and execute an agentic plan for the provided prompt."""

    plan = create_plan(task_prompt=req.prompt, allowed_tools=req.allowed_tools)
    result = execute_plan(plan, user_claims=user)
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
