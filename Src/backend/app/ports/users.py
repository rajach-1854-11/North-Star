"""User management port enforcing tenant scope and role validation."""

from __future__ import annotations

from typing import Iterable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.domain import models as m
from app.domain.schemas import UserListResp, UserResp

_ALLOWED_ROLES: tuple[str, ...] = ("Admin", "PO", "BA", "Dev")


def _to_user_resp(user: m.User) -> UserResp:
    return UserResp(id=user.id, username=user.username, role=user.role, tenant_id=user.tenant_id)


def list_users(db: Session, *, tenant_id: str) -> UserListResp:
    """Return all users for the given tenant ordered by username."""

    rows: Iterable[m.User] = (
        db.query(m.User).filter(m.User.tenant_id == tenant_id).order_by(m.User.username.asc()).all()
    )
    return UserListResp(users=[_to_user_resp(row) for row in rows])


def update_user_role(db: Session, *, tenant_id: str, user_id: int, role: str) -> UserResp:
    """Update the role for a user within the same tenant."""

    if role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=422, detail="Unsupported role supplied")

    user = db.get(m.User, user_id)
    if user is None or user.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = role
    db.commit()
    db.refresh(user)
    return _to_user_resp(user)
