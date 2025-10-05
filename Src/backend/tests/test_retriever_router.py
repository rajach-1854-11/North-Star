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


def test_retriever_targets_are_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "router_mode", "static")
    monkeypatch.setattr(settings, "abmap_enabled", False)

    class _DummySession:
        def get(self, *_args, **_kwargs) -> object:
            return object()

        def close(self) -> None:  # pragma: no cover - trivial cleanup
            return None

    monkeypatch.setattr(retriever, "SessionLocal", lambda: _DummySession())

    class _DummyPlan:
        steps: list = []
        plan_hash: str = "hash"

    monkeypatch.setattr("app.ports.retriever.compile_policy", lambda *_args, **_kwargs: _DummyPlan())

    captured: dict[str, list[str]] = {}

    def _fake_hybrid_search(_tenant_id: str, targets_arg: list[str], *_args, **_kwargs) -> list:
        captured["targets"] = targets_arg
        return []

    monkeypatch.setattr("app.ports.retriever.hybrid_search", _fake_hybrid_search)
    monkeypatch.setattr("app.ports.retriever.fallback_search", lambda *_, **__: [])
    monkeypatch.setattr("app.ports.retriever.build_evidence_snippets", lambda *_: "")

    result = retriever.rag_search(
        tenant_id="tenant1",
        user_claims={"accessible_projects": ["PX", "PB", "global"]},
        query="Tell me about PX",
        targets=["px", "Global"],
    )

    # With normalised targets, no HTTPException should be raised and payload should be returned
    assert result["results"] == []
    assert captured["targets"] == ["PX", "global"]