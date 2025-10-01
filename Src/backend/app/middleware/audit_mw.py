"""Middleware that records audit logs for incoming HTTP requests."""

from __future__ import annotations

from typing import Awaitable, Callable

from loguru import logger as loguru_logger
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.deps import SessionLocal
from app.domain.models import AuditLog
from app.logging_setup import RequestLogger
from app.utils.hashing import hash_args

request_logger = RequestLogger(loguru_logger)


class AuditMiddleware(BaseHTTPMiddleware):
    """Persist minimal request metadata for auditing purposes."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        req_id = request.headers.get("X-Request-Id", "")
        route = request.url.path
        user_claims = getattr(request.state, "user", {}) or {}
        tenant = user_claims.get("tenant_id", "unknown")
        started_at = request_logger.request_start(req_id, route, tenant)

        response = await call_next(request)

        user_claims = getattr(request.state, "user", {}) or user_claims
        actor_id = user_claims.get("user_id", 0)
        tenant = user_claims.get("tenant_id", "unknown")

        session = SessionLocal()
        try:
            session.add(
                AuditLog(
                    tenant_id=tenant,
                    actor_user_id=actor_id,
                    action=route,
                    args_hash=hash_args({"method": request.method}, namespace="audit"),
                    result_code=response.status_code,
                    request_id=req_id,
                    trace_id="",
                )
            )
            session.commit()
        except SQLAlchemyError as exc:
            loguru_logger.error("Failed to persist audit log", error=str(exc))
            session.rollback()
        finally:
            session.close()

        request_logger.request_end(started_at, req_id, route, tenant, response.status_code)
        return response
