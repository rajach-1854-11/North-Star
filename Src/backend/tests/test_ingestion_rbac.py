from __future__ import annotations

from typing import Any, Dict, Tuple

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.domain import models as m
from app.ports.ingestion import ingest_upload


@pytest.fixture
def _ingestion_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ports import ingestion as ingestion_port

    def fake_ingest_file(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {"collection": "test", "count": 1, "chunks": 1}

    def fake_store_chunks(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {"collection": "local", "count": 1, "chunks": 1}

    monkeypatch.setattr(ingestion_port, "ingest_file", fake_ingest_file)
    monkeypatch.setattr(ingestion_port, "store_chunks", fake_store_chunks)
    monkeypatch.setattr(ingestion_port, "extract_text", lambda *args, **kwargs: "sample text")


def _project_and_tenant(session: Session) -> Tuple[m.Project, str]:
    project = session.query(m.Project).filter(m.Project.key == "PX").one()
    return project, project.tenant_id


def test_ingest_upload_allows_admin(db_session, _ingestion_stubs) -> None:
    project, tenant_id = _project_and_tenant(db_session)

    response = ingest_upload(
        db_session,
        user_claims={"tenant_id": tenant_id, "role": "Admin"},
        project_key=project.key,
        file_bytes=b"hello",
        filename="note.txt",
    )

    assert response.collection == "test"
    assert response.count == 1


def test_ingest_upload_rejects_non_privileged_roles(db_session, _ingestion_stubs) -> None:
    project, tenant_id = _project_and_tenant(db_session)

    with pytest.raises(HTTPException) as exc:
        ingest_upload(
            db_session,
            user_claims={"tenant_id": tenant_id, "role": "BA"},
            project_key=project.key,
            file_bytes=b"hello",
            filename="note.txt",
        )

    assert exc.value.status_code == 403
    assert "product owners or admins" in str(exc.value.detail)
