from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.domain import models as m
from worker.handlers import skill_extractor
from app.utils.passwords import hash_password


def _unique(label: str) -> str:
    return f"{label}_{uuid.uuid4().hex[:8]}"


def test_apply_skill_delta_sets_last_seen(db_session: Session) -> None:
    tenant = db_session.query(m.Tenant).first()
    if tenant is None:
        tenant = m.Tenant(id=_unique("tenant"), name="Test Tenant")
        db_session.add(tenant)
        db_session.flush()

    user = m.User(
        username=_unique("dev"),
        password_hash=hash_password("x"),
        role="Dev",
        tenant_id=tenant.id,
    )
    db_session.add(user)
    db_session.flush()

    developer = m.Developer(
        user_id=user.id,
        display_name="Unit Dev",
        tenant_id=tenant.id,
    )
    db_session.add(developer)
    db_session.flush()

    skill = m.Skill(
        name=_unique("Skill"),
        parent_id=None,
        path_cache=_unique("skill.path"),
        depth=0,
    )
    db_session.add(skill)
    db_session.flush()

    skill_extractor.apply_skill_delta(
        db_session,
        developer_id=developer.id,
        skill_id=skill.id,
        project_id=None,
        delta=0.3,
        confidence=0.7,
        evidence_ref="unit-test",
    )
    db_session.commit()

    record = (
        db_session.query(m.DeveloperSkill)
        .filter(m.DeveloperSkill.developer_id == developer.id, m.DeveloperSkill.skill_id == skill.id)
        .one()
    )
    assert record.last_seen_at is not None
    initial_seen = record.last_seen_at
    initial_score = record.score

    skill_extractor.apply_skill_delta(
        db_session,
        developer_id=developer.id,
        skill_id=skill.id,
        project_id=None,
        delta=0.2,
        confidence=0.9,
        evidence_ref="unit-test-2",
    )
    db_session.commit()

    updated = (
        db_session.query(m.DeveloperSkill)
        .filter(m.DeveloperSkill.developer_id == developer.id, m.DeveloperSkill.skill_id == skill.id)
        .one()
    )
    assert updated.score == pytest.approx(initial_score + 0.2)
    assert updated.last_seen_at >= initial_seen
