"""Onboarding plan port with tenancy and RBAC enforcement."""

from __future__ import annotations

from typing import Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.application.onboarding_service import generate_onboarding
from app.domain import models as m
from app.domain.errors import ExternalServiceError
from app.domain.schemas import OnboardingPlan, OnboardingResp


def generate_plan(
    db: Session,
    *,
    user_claims: Dict[str, object],
    developer_id: int,
    project_id: int,
    autonomy: str,
) -> OnboardingResp:
    """Generate an onboarding plan within tenant boundaries."""

    if user_claims.get("role") not in {"Admin", "PO"}:
        raise HTTPException(status_code=403, detail="Only product owners or admins may request onboarding plans")

    tenant_id = user_claims.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Missing tenant context")
    project = db.get(m.Project, project_id)
    if not project or project.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Project not found")

    developer = db.get(m.Developer, developer_id)
    if not developer or developer.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Developer not found")

    try:
        plan: OnboardingPlan = generate_onboarding(
            db,
            user_claims=user_claims,
            project_key=project.key,
            project_id=project.id,
            developer_id=developer.id,
            dev_name=developer.display_name,
            autonomy=autonomy,
        )
    except ExternalServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:  # pragma: no cover - safety net for unexpected failures
        raise HTTPException(status_code=500, detail=f"Failed to generate onboarding plan: {exc}") from exc

    resp_kwargs = {"plan": plan, "audit_ref": "onboarding"}
    if plan.notice:
        resp_kwargs["message"] = plan.notice
    return OnboardingResp(**resp_kwargs)