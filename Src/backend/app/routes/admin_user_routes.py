"""Administrative user management routes."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db, require_role
from app.domain.schemas import UserListResp, UserResp, UserRolePatchReq
from app.ports.users import list_users, update_user_role

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=UserListResp)
def list_tenant_users(
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(require_role("Admin")),
) -> UserListResp:
    """Return all users for the caller's tenant."""

    tenant_id = user["tenant_id"]
    return list_users(db, tenant_id=tenant_id)


@router.patch("/users/{user_id}/role", response_model=UserResp)
def patch_user_role(
    user_id: int,
    body: UserRolePatchReq,
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(require_role("Admin")),
) -> UserResp:
    """Update the role for the selected user in the tenant."""

    tenant_id = user["tenant_id"]
    return update_user_role(db, tenant_id=tenant_id, user_id=user_id, role=body.role)
