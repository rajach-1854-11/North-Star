"""Document upload routes for ingestion."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.deps import get_db, require_role
from app.domain.schemas import UploadResp
from app.ports.ingestion import ingest_upload

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("", response_model=UploadResp)
async def upload(
    project_key: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: Dict[str, Any] = Depends(require_role("Admin", "PO")),
) -> UploadResp:
    """Ingest an uploaded file for the specified project."""

    data = await file.read()
    return ingest_upload(
        db,
        user_claims=user,
        project_key=project_key,
        file_bytes=data,
        filename=file.filename or "",
    )
