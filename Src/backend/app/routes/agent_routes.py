"""Agent planning and execution routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.domain.schemas import AgentQueryReq, AgentQueryResp
from app.ports.planner import create_plan, execute_plan

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/query", response_model=AgentQueryResp)
def agent_query(req: AgentQueryReq, user: Dict[str, Any] = Depends(get_current_user)) -> AgentQueryResp:
    """Generate and execute an agentic plan for the provided prompt."""

    plan = create_plan(task_prompt=req.prompt, allowed_tools=req.allowed_tools)
    result = execute_plan(plan, user_claims=user)
    return AgentQueryResp(plan=plan, artifacts=result.get("artifacts", {}), output=result.get("output", {}))
