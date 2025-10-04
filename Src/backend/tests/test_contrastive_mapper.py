from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.application.contrastive_mapper import ABMapper
from app.domain.models import ABMapEdge, TenantMapperWeights


class _Hit:
    def __init__(self, text: str, source: str, score: float, chunk_id: str) -> None:
        self.text = text
        self.source = source
        self.score = score
        self.chunk_id = chunk_id


def _upsert_weights(session, tenant_id: str, weights: dict[str, float]) -> None:
    existing = session.execute(
        select(TenantMapperWeights).where(TenantMapperWeights.tenant_id == tenant_id)
    ).scalars().first()
    payload = {"weights": weights, "version": 1}
    if existing:
        existing.weights = payload
    else:
        session.add(TenantMapperWeights(tenant_id=tenant_id, weights=payload))
    session.commit()


def test_tenant_isolation_no_leak(client, db_session) -> None:
    tenant_id = "tenant-isolation"
    _upsert_weights(db_session, tenant_id, {"helm": 1.0})

    mapper = ABMapper(tenant_id, session=db_session)
    hits = [
        _Hit("Helm upgrade best practices", "proj-allowed", 0.9, "c1"),
        _Hit("Helm upgrade best practices", "proj-denied", 0.8, "c2"),
    ]

    result = mapper.infer(
        known_projects=["proj-allowed"],
        top_hits=hits,
        allowed_targets={"proj-allowed"},
    )

    assert result.curated_docs
    assert all(doc["project"] != "proj-denied" for doc in result.curated_docs)


def test_weights_and_scores(client, db_session) -> None:
    tenant_id = "tenant-weights"
    _upsert_weights(db_session, tenant_id, {"helm": 1.5})

    mapper = ABMapper(tenant_id, session=db_session)

    low_result = mapper.infer(
        known_projects=["proj-a"],
        top_hits=[_Hit("Helm upgrade", "proj-a", 0.2, "c-low")],
        allowed_targets={"proj-a"},
    )

    db_session.execute(delete(ABMapEdge).where(ABMapEdge.tenant_id == tenant_id))
    db_session.commit()

    high_result = mapper.infer(
        known_projects=["proj-a"],
        top_hits=[_Hit("Helm upgrade", "proj-a", 0.9, "c-high")],
        allowed_targets={"proj-a"},
    )

    assert low_result.skills_gap and high_result.skills_gap
    assert high_result.skills_gap[0]["delta"] > low_result.skills_gap[0]["delta"]


def test_narrative_non_empty(client, db_session) -> None:
    tenant_id = "tenant-narr"
    _upsert_weights(db_session, tenant_id, {"kubernetes": 1.0})

    mapper = ABMapper(tenant_id, session=db_session)
    result = mapper.infer(
        known_projects=["proj-known"],
        top_hits=[_Hit("Kubernetes cluster hardening", "proj-known", 0.7, "c1")],
        allowed_targets={"proj-known"},
    )

    narrative = result.narrative_md
    assert "### Rosetta Narrative" in narrative
    assert "#### Key Divergences" in narrative
    assert "#### Curated Documents" in narrative


def test_persist_edge_conditionally(client, db_session) -> None:
    tenant_id = "tenant-edges"
    _upsert_weights(db_session, tenant_id, {"helm": 1.0})

    mapper = ABMapper(tenant_id, session=db_session)

    mapper.infer(
        known_projects=["proj-a"],
        top_hits=[_Hit("Helm upgrade", "proj-a", 0.8, "c1")],
        allowed_targets={"proj-a"},
    )
    edges = db_session.execute(
        select(ABMapEdge).where(ABMapEdge.tenant_id == tenant_id)
    ).scalars().all()
    assert len(edges) == 1

    db_session.execute(delete(ABMapEdge).where(ABMapEdge.tenant_id == tenant_id))
    db_session.commit()

    mapper.infer(
        known_projects=["proj-a"],
        top_hits=[_Hit("No skill match here", "proj-a", 0.8, "c2")],
        allowed_targets={"proj-a"},
    )
    edges = db_session.execute(
        select(ABMapEdge).where(ABMapEdge.tenant_id == tenant_id)
    ).scalars().all()
    assert len(edges) == 0


def test_no_session_factory_raises() -> None:
    mapper = ABMapper("tenant-missing")
    with pytest.raises(RuntimeError):
        mapper.infer(known_projects=[], top_hits=[])
