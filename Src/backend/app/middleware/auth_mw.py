"""Middleware that hydrates ``request.state.user`` from JWT claims."""

from __future__ import annotations

from typing import Awaitable, Callable

import jwt
from jwt import PyJWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings


class AuthMiddleware(BaseHTTPMiddleware):
    """Decode bearer tokens opportunistically for downstream dependencies."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        auth_header = request.headers.get("Authorization", "")
        claims: dict[str, object] = {}

        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            options = {
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": bool(settings.jwt_aud),
                "verify_iss": False,
            }
            decode_kwargs = {
                "key": settings.jwt_secret,
                "algorithms": ["HS256"],
                "options": options,
            }
            if settings.jwt_aud:
                decode_kwargs["audience"] = settings.jwt_aud
            try:
                claims = jwt.decode(token, **decode_kwargs)
            except PyJWTError:
                claims = {}

        request.state.user = claims
        response = await call_next(request)
        return response
