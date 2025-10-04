"""Application factory for the North Star API."""

from __future__ import annotations

from fastapi import FastAPI
from loguru import logger

from app.adapters.qdrant_client import ensure_all_payload_indexes
from app.agentic import tools as agent_tools
from app import deps
from app.config import settings
from app.domain.errors import ExternalServiceError, add_exception_handlers
from app.domain.models import Base
from app.instrumentation.middleware import TraceRequestMiddleware
from app.instrumentation.trace import tracepoint
from app.logging_setup import setup_logging
from app.middleware.audit_mw import AuditMiddleware
from app.middleware.auth_mw import AuthMiddleware
from app.utils.migrations.skill_attribution import ensure_skill_attribution_schema
from app.utils.seed_data import ensure_seed_data


def create_app() -> FastAPI:
    """Initialise and configure the FastAPI application."""

    setup_logging()
    Base.metadata.create_all(bind=deps.engine)
    ensure_skill_attribution_schema(deps.engine)
    ensure_seed_data()
    if settings.qdrant_run_index_migration:
        try:
            ensure_all_payload_indexes()
        except ExternalServiceError as exc:
            logger.warning("Qdrant payload index bootstrap skipped: {}", exc)
    tracepoint("embed_dim.enforced", expected=settings.embed_dim)

    app = FastAPI(title="North Star API", version="1.2.0")
    add_exception_handlers(app)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(AuditMiddleware)
    app.add_middleware(TraceRequestMiddleware)
    from app.routes import (
        admin_user_routes,
        agent_routes,
        assignment_routes,
        audit_routes,
        auth_routes,
        github_routes,
        jira_routes,
        onboarding_routes,
        project_read_routes,
        project_routes,
        retrieve_routes,
        skills_routes,
        staff_routes,
        upload_routes,
    )

    app.include_router(auth_routes.router)
    app.include_router(admin_user_routes.router)
    app.include_router(project_read_routes.router)
    app.include_router(project_routes.router)
    app.include_router(assignment_routes.router)
    app.include_router(upload_routes.router)
    app.include_router(retrieve_routes.router)
    app.include_router(staff_routes.router)
    app.include_router(onboarding_routes.router)
    app.include_router(github_routes.router)
    app.include_router(jira_routes.router)
    app.include_router(skills_routes.router)
    app.include_router(audit_routes.router)
    app.include_router(agent_routes.router)

    if hasattr(agent_tools, "register_all_tools"):
        agent_tools.register_all_tools()
    return app


app = create_app()
