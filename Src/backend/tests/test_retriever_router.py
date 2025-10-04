from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.config import settings
from app.ports import retriever


def test_retriever_router_learned_returns_501(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "router_mode", "learned")

    with pytest.raises(HTTPException) as exc:
        retriever.rag_search(
            tenant_id="tenant1",
            user_claims={"accessible_projects": ["global"]},
            query="What is up?",
        )

    assert exc.value.status_code == 501
    assert exc.value.detail == {
        "code": "ROUTER_NOT_IMPLEMENTED",
        "message": "Learned router pending",
    }