"""Document upload routes for ingestion."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.application.ingestion_service import ingest_file
from app.deps import get_current_user

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("")
async def upload(
    project_key: str = Form(...),
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Ingest an uploaded file for the specified project."""

    tenant_id = user["tenant_id"]
    data = await file.read()
    return ingest_file(data, file.filename or "", tenant_id, project_key)
