from __future__ import annotations

from time import perf_counter
from typing import Awaitable, Callable
from uuid import uuid4

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.instrumentation.trace import push_request_id, reset_request_id


class TraceRequestMiddleware(BaseHTTPMiddleware):
    """Attach request identifiers and structured logging to each request."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming_id = request.headers.get("X-Request-Id") or ""
        request_id = incoming_id or str(uuid4())
        token = push_request_id(request_id)
        request.state.request_id = request_id

        start = perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = (perf_counter() - start) * 1000
            user_claims = getattr(request.state, "user", {}) or {}
            if isinstance(user_claims, dict) and "request_id" not in user_claims:
                user_claims["request_id"] = request_id

            tenant_id = user_claims.get("tenant_id", "unknown") if isinstance(user_claims, dict) else "unknown"
            role = user_claims.get("role", "unknown") if isinstance(user_claims, dict) else "unknown"
            status = response.status_code if response is not None else 500

            logger.bind(
                request_id=request_id,
                tenant_id=str(tenant_id),
                user_role=str(role),
                path=request.url.path,
                method=request.method,
                status=status,
                duration_ms=round(duration_ms, 2),
            ).info("access")

            if response is not None:
                response.headers.setdefault("X-Request-Id", request_id)

            reset_request_id(token)
