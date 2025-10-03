# FILE: backend/app/deps.py
from __future__ import annotations
import logging
from typing import Any, Callable, Dict, Generator, Iterable
from fastapi import Depends, HTTPException, Request
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker, Session
import jwt
from jwt import PyJWTError

from app.config import settings


logger = logging.getLogger(__name__)

# --- SQLAlchemy engine + session factory ----------------------------------------------------
def _build_db_url() -> URL:
    """Construct the SQLAlchemy URL used for engine creation."""

    if settings.database_url:
        return make_url(settings.database_url)

    return URL.create(
        drivername="postgresql+psycopg2",
        username=settings.postgres_user,
        password=settings.postgres_password,
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
    )


def _build_postgres_connect_args() -> Dict[str, Any]:
    """Apply SSL / timeout settings when connecting to managed Postgres."""

    connect_args: Dict[str, Any] = {"sslmode": "require"}
    if settings.postgres_sslmode:
        connect_args["sslmode"] = settings.postgres_sslmode
    if settings.postgres_sslrootcert:
        connect_args["sslrootcert"] = settings.postgres_sslrootcert
    if settings.postgres_connect_timeout:
        connect_args["connect_timeout"] = settings.postgres_connect_timeout
    return connect_args


def _build_connect_args(url: URL) -> Dict[str, Any]:
    dialect_name = url.get_dialect().name
    if dialect_name == "sqlite":
        return {"check_same_thread": False}
    if dialect_name.startswith("postgresql"):
        return _build_postgres_connect_args()
    return {}


_db_url = _build_db_url()
logger.info("Initializing database engine", extra={"db_url": _db_url.render_as_string(hide_password=True)})
engine = create_engine(
    _db_url,
    connect_args=_build_connect_args(_db_url),
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,
    max_overflow=10,
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

def require_role(*allowed: str | Iterable[str]) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """Dependency factory allowing multiple roles (supports tuples/lists)."""

    roles: set[str] = set()
    for item in allowed:
        if isinstance(item, str):
            roles.add(item)
        else:
            roles.update(str(role) for role in item)

    if not roles:
        raise ValueError("require_role must receive at least one allowed role")

    def _dep(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        role = user.get("role")
        if role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role {role} not allowed, need one of {sorted(roles)}",
            )
        return user

    return _dep
