"""Application factory for the North Star API."""

from __future__ import annotations

from fastapi import FastAPI

from app.deps import engine
from app.domain.errors import add_exception_handlers
from app.domain.models import Base
from app.logging_setup import setup_logging
from app.middleware.audit_mw import AuditMiddleware
from app.middleware.auth_mw import AuthMiddleware
from app.ports import tools as agent_tools
from app.routes import (
    agent_routes,
    audit_routes,
    auth_routes,
    github_routes,
    onboarding_routes,
    project_routes,
    retrieve_routes,
    skills_routes,
    staff_routes,
    upload_routes,
)


def create_app() -> FastAPI:
    """Initialise and configure the FastAPI application."""

    setup_logging()
    Base.metadata.create_all(bind=engine)
    agent_tools.register_all_tools()

    app = FastAPI(title="North Star API", version="1.2.0")
    add_exception_handlers(app)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(AuditMiddleware)
    app.include_router(auth_routes.router)
    app.include_router(project_routes.router)
    app.include_router(upload_routes.router)
    app.include_router(retrieve_routes.router)
    app.include_router(staff_routes.router)
    app.include_router(onboarding_routes.router)
    app.include_router(github_routes.router)
    app.include_router(skills_routes.router)
    app.include_router(audit_routes.router)
    app.include_router(agent_routes.router)
    return app


app = create_app()
