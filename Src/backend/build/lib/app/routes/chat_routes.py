"""Chatbot orchestration routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.deps import require_role
from app.domain.schemas import ChatQueryReq, ChatResp
from app.services.chat_orchestrator import ChatOrchestrator

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/session", response_model=ChatResp)
def chat_session(
    req: ChatQueryReq,
    user: Dict[str, Any] = Depends(require_role(("Admin", "PO", "BA", "Dev"))),
) -> ChatResp:
    """Handle a unified chat request that can access retrieval, Jira, and Confluence tools."""

    orchestrator = ChatOrchestrator(user_claims=user)
    return orchestrator.handle(req)
