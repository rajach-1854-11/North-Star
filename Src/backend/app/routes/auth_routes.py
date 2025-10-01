"""Authentication helper routes."""

from __future__ import annotations

import time
from typing import Dict

import jwt
from fastapi import APIRouter

from app.config import settings
from app.domain.schemas import TokenResp

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=TokenResp)
def token(username: str, password: str) -> TokenResp:
    """Return a development-only JWT token."""
    role = "PO" if username.startswith("po") else "Dev"
    now = int(time.time())
    payload: Dict[str, object] = {
        "sub": username,
        "user_id": 1 if role == "PO" else 2,
        "role": role,
        "tenant_id": settings.tenant_id,
        "accessible_projects": ["global", "PX", "PB"],
        "iss": settings.jwt_iss,
        "aud": settings.jwt_aud,
        "iat": now,
        "exp": now + 3600,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return TokenResp(access_token=token)
