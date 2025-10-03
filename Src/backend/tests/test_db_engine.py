from __future__ import annotations

import importlib
import sys
from typing import Any, Dict

import pytest
from sqlalchemy.engine import URL


@pytest.fixture(autouse=True)
def _reset_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure required settings are present for module reloads."""

    monkeypatch.setenv("JWT_SECRET", "unit-test-secret")
    monkeypatch.setenv("JWT_AUD", "northstar")
    monkeypatch.setenv("POSTGRES_HOST", "db.example.com")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "northstar")
    monkeypatch.setenv("POSTGRES_USER", "postgres")
    monkeypatch.setenv("POSTGRES_PASSWORD", "Sup3r$!:Pass")
    monkeypatch.setenv("QDRANT_URL", "https://example.qdrant.io")
    monkeypatch.setenv("QUEUE_MODE", "redis")
    monkeypatch.delenv("DATABASE_URL", raising=False)


def test_engine_uses_url_and_masks_password(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    captured: Dict[str, Any] = {}

    def fake_create_engine(url: URL, **kwargs: Any) -> object:
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    sys.modules.pop("app.deps", None)
    sys.modules.pop("app.config", None)
    monkeypatch.setattr("sqlalchemy.create_engine", fake_create_engine)

    with caplog.at_level("INFO", logger="app.deps"):
        importlib.import_module("app.deps")

    assert isinstance(captured["url"], URL)
    assert captured["url"].password == "Sup3r$!:Pass"
    connect_args = captured["kwargs"]["connect_args"]
    assert connect_args["sslmode"] == "require"

    record = next(rec for rec in caplog.records if rec.message == "Initializing database engine")
    masked_url = getattr(record, "db_url")
    assert masked_url is not None
    assert "Sup3r$!:Pass" not in masked_url
    assert "***" in masked_url