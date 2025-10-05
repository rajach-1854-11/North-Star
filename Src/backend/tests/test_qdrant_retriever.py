from __future__ import annotations

import pytest
from qdrant_client.http import models as qm

from app.adapters import hybrid_retriever, qdrant_client
from app.domain.errors import ExternalServiceError


class _DummySparse:
    def __init__(self):
        self.indices = [0]
        self.values = [0.5]


def _set_embed_dim(monkeypatch, value: int) -> None:
    monkeypatch.setattr(hybrid_retriever.settings, "embed_dim", value, raising=False)
    monkeypatch.setattr(qdrant_client.settings, "embed_dim", value, raising=False)


def test_search_missing_collection_raises(monkeypatch):
    _set_embed_dim(monkeypatch, 3)
    monkeypatch.setattr(hybrid_retriever, "embed_one", lambda query: [0.1, 0.2, 0.3])
    monkeypatch.setattr(hybrid_retriever, "encode_sparse", lambda query: _DummySparse())

    def _missing_collection(name, dense_dim, create_if_missing):
        raise ExternalServiceError("missing collection")

    monkeypatch.setattr(hybrid_retriever, "ensure_collection", _missing_collection)

    with pytest.raises(ExternalServiceError):
        hybrid_retriever.search("tenant", ["global"], "hello")


def test_search_with_filter_returns_hits(monkeypatch):
    _set_embed_dim(monkeypatch, 2)
    monkeypatch.setattr(hybrid_retriever, "embed_one", lambda query: [0.1, 0.2])
    monkeypatch.setattr(hybrid_retriever, "encode_sparse", lambda query: _DummySparse())
    monkeypatch.setattr(hybrid_retriever, "ensure_collection", lambda *args, **kwargs: None)

    captured: dict[str, qm.Filter] = {}

    def _fake_hybrid_search(collections, query_dense, query_sparse, k, _lambda, query_filter):
        captured["collections"] = collections
        captured["filter"] = query_filter
        return [(0.9, collections[0], {"tenant_id": "tenant", "project_key": "PX"})]

    monkeypatch.setattr(hybrid_retriever, "qdrant_hybrid_search", _fake_hybrid_search)

    results = hybrid_retriever.search(
        "tenant",
        ["global"],
        "hello",
        k=5,
        meta_filters={"tenant_id": "tenant"},
    )

    assert pytest.approx(results[0][0], rel=1e-6) == 0.9
    assert captured["collections"] == ["tenant__global"]
    assert isinstance(captured["filter"], qm.Filter)
    assert captured["filter"].must[0].key == "tenant_id"


def test_ensure_payload_indexes_idempotent(monkeypatch):
    calls: list[tuple[str, str]] = []

    class DummyException(Exception):
        def __init__(self, status_code: int, message: str):
            super().__init__(message)
            self.status_code = status_code

    class DummyClient:
        def create_payload_index(self, collection_name: str, field_name: str, field_schema):
            calls.append((collection_name, field_name))
            if field_name == "project_id":
                raise DummyException(400, "index already exists")

    monkeypatch.setattr(qdrant_client, "client", DummyClient())
    monkeypatch.setattr(qdrant_client, "ResponseHandlingException", DummyException)
    monkeypatch.setattr(qdrant_client, "UnexpectedResponse", DummyException)

    qdrant_client.ensure_payload_indexes("tenant__global")

    fields = [field for _, field in calls]
    assert fields.count("tenant_id") == 1
    assert fields.count("project_id") == 1
    assert fields.count("project_key") == 1