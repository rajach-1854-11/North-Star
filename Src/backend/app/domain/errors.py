"""Domain-specific exception hierarchy and FastAPI handlers."""
#test
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.instrumentation.trace import trace_exception


class AppError(Exception):
    """Base class for domain errors with structured metadata."""

    status_code: int = 400
    code: str = "app_error"
    message: str = "Application error"

    def __init__(self, message: str | None = None, *, code: str | None = None, status_code: int | None = None) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class NotFoundError(AppError):
    """Raised when a requested resource is missing."""

    status_code = 404
    code = "not_found"
    message = "Resource not found"


class PermissionDeniedError(AppError):
    """Raised when a user lacks privileges for an operation."""

    status_code = 403
    code = "permission_denied"
    message = "You do not have permission for this action"


class ValidationError(AppError):
    """Raised when input payloads fail validation."""

    status_code = 422
    code = "validation_error"
    message = "Invalid input"


class ExternalServiceError(AppError):
    """Raised when an upstream dependency fails."""

    status_code = 502
    code = "external_service_error"
    message = "Upstream service failed"


def add_exception_handlers(app: FastAPI) -> None:
    """Register exception handlers for :class:`AppError` and :class:`HTTPException`."""

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        trace_exception("app_error", exc, code=exc.code, status=exc.status_code)
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(HTTPException)
    async def http_exc_handler(_: Request, exc: HTTPException) -> JSONResponse:
        trace_exception("http_exception", exc, status=exc.status_code, detail=exc.detail)
        payload = {
            "detail": exc.detail,
            "error": {"code": "http_error", "message": exc.detail},
        }
        return JSONResponse(status_code=exc.status_code, content=payload)
