"""Assignment administration routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db, require_role
from app.domain.schemas import (
    AssignmentCreateReq,
    AssignmentListResp,
    AssignmentResp,
    AssignmentUpdateReq,
)
from app.ports.assignments import (
    create_assignment,
    list_assignments_for_project,
    update_assignment,
)

router = APIRouter(tags=["assignments"])


@router.post("/assignments", response_model=AssignmentResp)
def post_assignment(
    body: AssignmentCreateReq,
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(require_role("Admin", "PO")),
) -> AssignmentResp:
    """Create a new assignment for a developer."""

    tenant_id = user["tenant_id"]
    return create_assignment(
        db,
        tenant_id=tenant_id,
        developer_id=body.developer_id,
        project_id=body.project_id,
        role=body.role,
        start_date=body.start_date,
    )


@router.patch("/assignments/{assignment_id}", response_model=AssignmentResp)
def patch_assignment(
    assignment_id: int,
    body: AssignmentUpdateReq,
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(require_role("Admin", "PO")),
) -> AssignmentResp:
    """Update details of an existing assignment."""

    tenant_id = user["tenant_id"]
    return update_assignment(
        db,
        tenant_id=tenant_id,
        assignment_id=assignment_id,
        role=body.role,
        status=body.status,
        end_date=body.end_date,
    )


@router.get("/projects/{project_id}/assignments", response_model=AssignmentListResp)
def get_project_assignments(
    project_id: int,
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(require_role("Admin", "PO", "BA")),
) -> AssignmentListResp:
    """Return assignments for the specified project."""

    tenant_id = user["tenant_id"]
    return list_assignments_for_project(db, tenant_id=tenant_id, project_id=project_id)
