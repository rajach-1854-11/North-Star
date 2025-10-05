"""File ingestion port enforcing tenant boundaries and RBAC."""

from __future__ import annotations

from fastapi import HTTPException
from loguru import logger
from sqlalchemy.orm import Session

from app.application.ingestion_service import extract_text, ingest_file
from app.application.local_kb import store_chunks
from app.domain import models as m
from app.domain.errors import ExternalServiceError
from app.domain.schemas import UploadResp


def ingest_upload(
    db: Session,
    *,
    user_claims: dict,
    project_key: str,
    file_bytes: bytes,
    filename: str,
) -> UploadResp:
    """Ingest a document for the caller's tenant and return upload stats."""

    tenant_id = user_claims.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Missing tenant context")
    role = user_claims.get("role")
    if role not in {"PO", "Admin"}:
        raise HTTPException(status_code=403, detail="Only product owners or admins may upload documents")

    project = (
        db.query(m.Project)
        .filter(m.Project.key == project_key, m.Project.tenant_id == tenant_id)
        .one_or_none()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        stats = ingest_file(file_bytes, filename, tenant_id=tenant_id, project_key=project_key)
    except ExternalServiceError as exc:
        logger.bind(req="").warning(
            "Falling back to local knowledge store", project=project_key, error=str(exc)
        )
        text = extract_text(file_bytes, filename)
        fallback = store_chunks(
            db,
            tenant_id=tenant_id,
            project=project,
            text=text,
            source=filename or "upload",
        )
        return UploadResp(
            project_key=project_key,
            collection=fallback["collection"],
            count=int(fallback["count"]),
            chunks=int(fallback["chunks"]),
            message="Remote vector index unavailable; using local fallback store. Please retry later.",
        )

    # Best-effort mirror into the fallback store for retrieval resilience.
    try:
        text = extract_text(file_bytes, filename)
        store_chunks(
            db,
            tenant_id=tenant_id,
            project=project,
            text=text,
            source=filename or "upload",
        )
    except Exception as mirror_exc:  # noqa: BLE001 - fallback is best-effort
        logger.bind(req="").debug(
            "Unable to mirror upload into local knowledge store", error=str(mirror_exc)
        )

    return UploadResp(
        project_key=project_key,
        collection=stats["collection"],
        count=int(stats["count"]),
        chunks=int(stats["chunks"]),
    )