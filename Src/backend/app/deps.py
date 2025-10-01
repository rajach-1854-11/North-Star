# FILE: backend/app/deps.py
from __future__ import annotations
from typing import Any, Callable, Dict, Generator
from fastapi import Depends, HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import jwt
from jwt import PyJWTError

from app.config import settings

# --- SQLAlchemy engine + session factory ---
engine = create_engine(
    f"postgresql+psycopg2://{settings.postgres_user}:{settings.postgres_password}"
    f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}",
    pool_pre_ping=True,
    # Optional tuning knobs (safe defaults for dev; tweak for prod):
    # pool_size=5, max_overflow=10, pool_recycle=1800, pool_timeout=30, future=True
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a scoped Session per-request.
    Properly annotated as a Generator to satisfy type checkers.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request: Request) -> Dict[str, Any]:
    """
    Decode JWT and return claims; enforce presence.
    Also sets request.state.user for middleware (audit, etc.).
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = auth.split(" ", 1)[1]

    # Build decode kwargs so 'audience' is optional
    options = {
        "verify_signature": True,
        "verify_exp": True,
        "verify_aud": bool(getattr(settings, "jwt_aud", None)),
        "verify_iss": False,
    }
    decode_kwargs: Dict[str, Any] = {
        "key": settings.jwt_secret,
        "algorithms": ["HS256"],
        "options": options,
    }
    if getattr(settings, "jwt_aud", None):
        decode_kwargs["audience"] = settings.jwt_aud

    try:
        claims = jwt.decode(token, **decode_kwargs)
    except PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}") from exc

    # Make claims available to middlewares / handlers that read request.state.user
    request.state.user = claims
    return claims

def require_role(required: str) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """
    Dependency factory: require a specific role (e.g., 'PO', 'Dev').
    Usage: user = Depends(require_role("PO"))
    """
    def _dep(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        role = user.get("role")
        if role != required:
            raise HTTPException(status_code=403, detail=f"Role {role} not allowed; need {required}")
        return user
    return _dep
