"""Authentication helper routes."""

from __future__ import annotations

import time
from typing import Dict, List

import jwt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import get_db
from app.domain import models as m
from app.domain.schemas import TokenResp

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=TokenResp)
def token(username: str, password: str, db: Session = Depends(get_db)) -> TokenResp:
    """Return a JWT sourced from the database user record."""

    user = db.query(m.User).filter(m.User.username == username).one_or_none()
    if user is None or user.password_hash != password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    tenant_id = user.tenant_id
    role = user.role

    developer = (
        db.query(m.Developer)
        .filter(m.Developer.user_id == user.id, m.Developer.tenant_id == tenant_id)
        .one_or_none()
    )
    accessible: set[str] = {"global"}

    if role in {"Admin", "PO", "BA"}:
        keys: List[str] = [row[0] for row in db.query(m.Project.key).filter(m.Project.tenant_id == tenant_id).all()]
        accessible.update(keys)
    elif developer is not None:
        keys = [
            row[0]
            for row in (
                db.query(m.Project.key)
                .join(m.Assignment, m.Assignment.project_id == m.Project.id)
                .filter(
                    m.Assignment.developer_id == developer.id,
                    m.Project.tenant_id == tenant_id,
                    or_(m.Assignment.status.is_(None), m.Assignment.status == "active"),
                )
                .all()
            )
        ]
        accessible.update(keys)

    accessible_projects = sorted(accessible)
    now = int(time.time())
    payload: Dict[str, object] = {
        "sub": username,
        "user_id": user.id,
        "role": role,
        "tenant_id": tenant_id,
        "accessible_projects": accessible_projects,
        "iss": settings.jwt_iss,
        "aud": settings.jwt_aud,
        "iat": now,
        "exp": now + 3600,
    }
    if developer is not None:
        payload["developer_id"] = developer.id
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return TokenResp(access_token=token)
