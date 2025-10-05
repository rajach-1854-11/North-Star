"""Chatbot orchestration routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Tuple

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.deps import get_db, require_role
from app.domain.schemas import (
    ChatQueryReq,
    ChatResp,
    ChatThreadCreateReq,
    ChatThreadListResp,
    ChatThreadPatchReq,
    ChatThreadMessagesResp,
    ChatThreadResp,
)
from app.services import chat_history
from app.services.chat_orchestrator import ChatOrchestrator

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/session", response_model=ChatResp)
def chat_session(
    req: ChatQueryReq,
    user: Dict[str, Any] = Depends(require_role(("Admin", "PO", "BA", "Dev"))),
    db: Session = Depends(get_db),
) -> ChatResp:
    """Handle a unified chat request that can access retrieval, Jira, and Confluence tools."""

    try:
        orchestrator = ChatOrchestrator(user_claims=user, db=db)
        return orchestrator.handle(req)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _thread_to_resp(thread, message_count: int, last_message_at: datetime | None) -> ChatThreadResp:
    return ChatThreadResp(
        id=thread.id,
        title=thread.title,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        message_count=message_count,
        last_message_at=last_message_at,
    )


def _resolve_user_identity(user: Dict[str, Any]) -> Tuple[str, int]:
    tenant = user.get("tenant_id")
    user_id = user.get("user_id")
    if not tenant or user_id is None:
        raise HTTPException(status_code=400, detail="Missing user identity for chat threads")
    return str(tenant), int(user_id)


@router.post("/threads", response_model=ChatThreadResp)
def create_chat_thread(
    req: ChatThreadCreateReq,
    user: Dict[str, Any] = Depends(require_role(("Admin", "PO", "BA", "Dev"))),
    db: Session = Depends(get_db),
) -> ChatThreadResp:
    tenant_id, user_id = _resolve_user_identity(user)
    thread = chat_history.create_thread(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        title=req.title,
    )
    return _thread_to_resp(thread, 0, None)


@router.get("/threads", response_model=ChatThreadListResp)
def list_chat_threads(
    user: Dict[str, Any] = Depends(require_role(("Admin", "PO", "BA", "Dev"))),
    db: Session = Depends(get_db),
) -> ChatThreadListResp:
    tenant_id, user_id = _resolve_user_identity(user)
    rows = chat_history.list_threads(db, tenant_id=tenant_id, user_id=user_id)
    threads = [_thread_to_resp(thread, count, last_at) for thread, count, last_at in rows]
    return ChatThreadListResp(threads=threads)


def _load_thread_messages(
    thread_id: int,
    user: Dict[str, Any],
    db: Session,
) -> ChatThreadMessagesResp:
    tenant_id, user_id = _resolve_user_identity(user)
    try:
        thread, messages = chat_history.get_thread_messages(
            db,
            thread_id=thread_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ChatThreadMessagesResp(
        thread_id=thread.id,
        title=thread.title,
        message_count=len(messages),
        messages=messages,
    )


@router.get("/threads/{thread_id}", response_model=ChatThreadMessagesResp)
def get_chat_thread(
    thread_id: int,
    user: Dict[str, Any] = Depends(require_role(("Admin", "PO", "BA", "Dev"))),
    db: Session = Depends(get_db),
) -> ChatThreadMessagesResp:
    return _load_thread_messages(thread_id, user, db)


@router.get("/threads/{thread_id}/messages", response_model=ChatThreadMessagesResp)
def get_chat_thread_messages(
    thread_id: int,
    user: Dict[str, Any] = Depends(require_role(("Admin", "PO", "BA", "Dev"))),
    db: Session = Depends(get_db),
) -> ChatThreadMessagesResp:
    return _load_thread_messages(thread_id, user, db)


@router.patch("/threads/{thread_id}", response_model=ChatThreadResp)
def patch_chat_thread(
    thread_id: int,
    req: ChatThreadPatchReq,
    user: Dict[str, Any] = Depends(require_role(("Admin", "PO", "BA", "Dev"))),
    db: Session = Depends(get_db),
) -> ChatThreadResp:
    tenant_id, user_id = _resolve_user_identity(user)
    try:
        thread = chat_history.rename_thread(
            db,
            thread_id=thread_id,
            tenant_id=tenant_id,
            user_id=user_id,
            title=req.title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    messages = chat_history.load_thread_history(db, thread_id=thread.id, tenant_id=tenant_id)
    message_count = len(messages)
    last_message_at = None
    if messages:
        last_timestamp = messages[-1].timestamp
        if isinstance(last_timestamp, datetime):
            last_message_at = last_timestamp
    if last_message_at is None:
        last_message_at = thread.updated_at
    return _thread_to_resp(thread, message_count, last_message_at)


@router.delete("/threads/{thread_id}", status_code=204, response_class=Response)
def delete_chat_thread(
    thread_id: int,
    user: Dict[str, Any] = Depends(require_role(("Admin", "PO", "BA", "Dev"))),
    db: Session = Depends(get_db),
) -> Response:
    tenant_id, user_id = _resolve_user_identity(user)
    try:
        chat_history.delete_thread(
            db,
            thread_id=thread_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)
