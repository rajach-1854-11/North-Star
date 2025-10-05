"""Persistence helpers for chat threads and messages."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Mapping, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain import models as m
from app.domain.schemas import ChatMessage


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _sanitize_title(title: str | None) -> str | None:
    if not title:
        return None
    sanitized = title.strip()
    if not sanitized:
        return None
    return sanitized[:255]


def create_thread(
    db: Session,
    *,
    tenant_id: str,
    user_id: int,
    title: str | None = None,
    metadata: Mapping[str, object] | None = None,
) -> m.ChatThread:
    """Create a new chat thread for the user."""

    thread = m.ChatThread(
        tenant_id=tenant_id,
        user_id=user_id,
        title=_sanitize_title(title),
        metadata_json=dict(metadata or {}),
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


def touch_thread_title(db: Session, thread: m.ChatThread, title: str | None) -> None:
    """Populate thread title if it's empty and a candidate title is provided."""

    if thread.title:
        return
    candidate = _sanitize_title(title)
    if candidate:
        thread.title = candidate
        thread.updated_at = _utcnow()
        db.add(thread)
        db.commit()


def require_thread(db: Session, *, thread_id: int, tenant_id: str, user_id: int) -> m.ChatThread:
    """Fetch a thread ensuring it belongs to the user."""

    thread = (
        db.query(m.ChatThread)
        .filter(
            m.ChatThread.id == thread_id,
            m.ChatThread.tenant_id == tenant_id,
            m.ChatThread.user_id == user_id,
        )
        .one_or_none()
    )
    if thread is None:
        raise ValueError("Thread not found or access denied")
    return thread


def list_threads(
    db: Session,
    *,
    tenant_id: str,
    user_id: int,
) -> List[Tuple[m.ChatThread, int, datetime | None]]:
    """Return threads with message counts and last activity timestamp."""

    last_message_at = func.max(m.ChatMessageLog.created_at)
    stmt = (
        select(m.ChatThread, func.count(m.ChatMessageLog.id), last_message_at)
        .outerjoin(m.ChatMessageLog, m.ChatMessageLog.thread_id == m.ChatThread.id)
        .where(
            m.ChatThread.tenant_id == tenant_id,
            m.ChatThread.user_id == user_id,
        )
        .group_by(m.ChatThread.id)
        .order_by(func.coalesce(last_message_at, m.ChatThread.updated_at).desc(), m.ChatThread.id.desc())
    )
    rows = db.execute(stmt).all()
    return [(row[0], int(row[1]), row[2]) for row in rows]


def load_thread_history(
    db: Session,
    *,
    thread_id: int,
    tenant_id: str,
    limit: int | None = None,
) -> List[ChatMessage]:
    """Load prior messages for a thread ordered chronologically."""

    query = (
        db.query(m.ChatMessageLog)
        .filter(
            m.ChatMessageLog.thread_id == thread_id,
            m.ChatMessageLog.tenant_id == tenant_id,
        )
        .order_by(m.ChatMessageLog.turn_index.asc(), m.ChatMessageLog.created_at.asc(), m.ChatMessageLog.id.asc())
    )
    if limit is not None:
        query = query.limit(limit)
    messages: List[ChatMessage] = []
    for entry in query.all():
        metadata = dict(entry.metadata_json or {})
        if not metadata:
            metadata = None
        messages.append(
            ChatMessage(
                role=entry.role,
                content=entry.content,
                timestamp=entry.created_at,
                metadata=metadata,
            )
        )
    return messages


def _next_turn_index(db: Session, *, thread_id: int, tenant_id: str) -> int:
    current = (
        db.query(func.max(m.ChatMessageLog.turn_index))
        .filter(
            m.ChatMessageLog.thread_id == thread_id,
            m.ChatMessageLog.tenant_id == tenant_id,
        )
        .scalar()
    )
    if current is None:
        return 0
    return int(current) + 1


def append_messages(
    db: Session,
    *,
    thread: m.ChatThread,
    entries: Sequence[Tuple[str, str, Mapping[str, object] | None]],
) -> None:
    """Persist chat messages and bump thread activity timestamp."""

    if not entries:
        return

    base_index = _next_turn_index(db, thread_id=thread.id, tenant_id=thread.tenant_id)
    for offset, (role, content, metadata) in enumerate(entries):
        message = m.ChatMessageLog(
            thread_id=thread.id,
            tenant_id=thread.tenant_id,
            role=role,
            content=content,
            metadata_json=dict(metadata or {}),
            turn_index=base_index + offset,
        )
        db.add(message)

    thread.updated_at = _utcnow()
    db.add(thread)
    db.commit()


def get_thread_messages(
    db: Session,
    *,
    thread_id: int,
    tenant_id: str,
    user_id: int,
    limit: int | None = None,
) -> Tuple[m.ChatThread, List[ChatMessage]]:
    """Return a thread and its messages ensuring access is granted."""

    thread = require_thread(db, thread_id=thread_id, tenant_id=tenant_id, user_id=user_id)
    messages = load_thread_history(db, thread_id=thread.id, tenant_id=tenant_id, limit=limit)
    return thread, messages


def rename_thread(
    db: Session,
    *,
    thread_id: int,
    tenant_id: str,
    user_id: int,
    title: str | None,
) -> m.ChatThread:
    """Update a thread's title"""

    thread = require_thread(db, thread_id=thread_id, tenant_id=tenant_id, user_id=user_id)
    new_title = _sanitize_title(title)
    if new_title is None:
        raise ValueError("Thread title must not be empty")
    if thread.title == new_title:
        return thread
    thread.title = new_title
    thread.updated_at = _utcnow()
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


def delete_thread(
    db: Session,
    *,
    thread_id: int,
    tenant_id: str,
    user_id: int,
) -> None:
    """Remove a thread and all associated messages."""

    thread = require_thread(db, thread_id=thread_id, tenant_id=tenant_id, user_id=user_id)
    db.query(m.ChatMessageLog).filter(
        m.ChatMessageLog.thread_id == thread.id,
        m.ChatMessageLog.tenant_id == tenant_id,
    ).delete(synchronize_session=False)
    db.delete(thread)
    db.commit()