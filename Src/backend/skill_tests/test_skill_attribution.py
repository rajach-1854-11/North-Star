import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure configuration requirements are satisfied before importing settings
os.environ.setdefault("ENV", "test")
os.environ.setdefault("JWT_SECRET", "testing-secret")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_DB", "northstar_test")
os.environ.setdefault("POSTGRES_USER", "tester")
os.environ.setdefault("POSTGRES_PASSWORD", "tester")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("QUEUE_MODE", "direct")
os.environ.setdefault("ROUTER_MODE", "static")
os.environ.setdefault("LLM_PROVIDER", "cerebras")
os.environ.setdefault("AUTO_PROVISION_DEV_FROM_GH", "false")

from app.config import settings
from app.domain import models as m
from app.utils.passwords import hash_password
from worker.handlers import skill_extractor
import worker.services.database as db
from worker.services.github_processor import GitHubEventProcessor
from worker.services.jira_processor import JiraEventProcessor


@pytest.fixture(autouse=True)
def _tune_settings():
    originals = {
        "enable_review_signals": settings.enable_review_signals,
        "skill_baseline_increment": settings.skill_baseline_increment,
        "review_first_review_multiplier": settings.review_first_review_multiplier,
        "review_approval_bonus": settings.review_approval_bonus,
        "review_cycle_penalty": settings.review_cycle_penalty,
        "review_major_rework_penalty": settings.review_major_rework_penalty,
        "review_nit_penalty": settings.review_nit_penalty,
        "review_peer_credit": settings.review_peer_credit,
        "review_peer_credit_cap_per_window": settings.review_peer_credit_cap_per_window,
        "review_peer_credit_window_days": settings.review_peer_credit_window_days,
        "time_to_merge_threshold_hours": settings.time_to_merge_threshold_hours,
        "time_to_merge_penalty": settings.time_to_merge_penalty,
        "time_to_merge_bonus": settings.time_to_merge_bonus,
    }
    settings.enable_review_signals = True
    settings.skill_baseline_increment = 1.0
    settings.review_first_review_multiplier = 1.0
    settings.review_approval_bonus = 0.3
    settings.review_cycle_penalty = 0.3
    settings.review_major_rework_penalty = 0.5
    settings.review_nit_penalty = 0.1
    settings.review_peer_credit = 0.2
    settings.review_peer_credit_cap_per_window = 10
    settings.review_peer_credit_window_days = 14
    settings.time_to_merge_threshold_hours = 24
    settings.time_to_merge_penalty = 0.2
    settings.time_to_merge_bonus = 0.1
    try:
        yield
    finally:
        for key, value in originals.items():
            setattr(settings, key, value)


@pytest.fixture()
def session_factory(monkeypatch):
    engine = create_engine("sqlite:///:memory:", future=True)
    m.Base.metadata.create_all(engine)
    SessionTest = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )

    monkeypatch.setattr(db, "engine", engine, raising=False)
    monkeypatch.setattr(db, "SessionLocal", SessionTest, raising=False)
    monkeypatch.setattr(skill_extractor, "engine", engine, raising=False)

    def fake_generate_skill_assertions(event: str, payload: dict[str, object]):
        return [{"path": ["Engineering", "Backend"], "confidence": 0.9}]

    monkeypatch.setattr(skill_extractor, "generate_skill_assertions", fake_generate_skill_assertions)
    return SessionTest


def _seed_core_entities(SessionTest, *, email: str | None = None, login: str | None = None, project_required: bool = True):
    session = SessionTest()
    try:
        tenant = m.Tenant(id="tenant-1", name="Tenant One")
        session.add(tenant)
        project = None
        if project_required:
            project = m.Project(
                key="PX",
                name="Project X",
                description="Test Project",
                tenant_id=tenant.id,
            )
            session.add(project)
        user = m.User(
            username="devuser",
            password_hash=hash_password("dev-pass"),
            role="Dev",
            tenant_id=tenant.id,
        )
        session.add(user)
        session.flush()
        developer = m.Developer(user_id=user.id, display_name="Dev User", tenant_id=tenant.id)
        session.add(developer)
        session.flush()
        identity = m.DeveloperIdentity(
            developer_id=developer.id,
            tenant_id=tenant.id,
            provider="github",
            provider_login=login.lower() if login else None,
            email=email,
            email_lower=email.lower() if email else None,
            is_primary=True,
            metadata_json={},
        )
        session.add(identity)
        project_id = project.id if project is not None else None
        mapping = m.RepositoryMapping(
            provider="github",
            repo_full_name="acme/widgets",
            tenant_id=tenant.id,
            project_id=project_id,
            metadata_json={},
            active=True,
        )
        session.add(mapping)
        session.commit()
        return {
            "tenant": tenant,
            "project": project,
            "developer": developer,
            "identity": identity,
            "mapping": mapping,
        }
    finally:
        session.close()


def _create_reviewer(SessionTest, tenant_id: str, *, login: str, email: str | None = None):
    session = SessionTest()
    try:
        user = m.User(
            username="reviewer",
            password_hash=hash_password("reviewer-pass"),
            role="Dev",
            tenant_id=tenant_id,
        )
        session.add(user)
        session.flush()
        developer = m.Developer(user_id=user.id, display_name="Reviewer", tenant_id=tenant_id)
        session.add(developer)
        session.flush()
        identity = m.DeveloperIdentity(
            developer_id=developer.id,
            tenant_id=tenant_id,
            provider="github",
            provider_login=login.lower(),
            email=email,
            email_lower=email.lower() if email else None,
            is_primary=True,
            metadata_json={},
        )
        session.add(identity)
        session.commit()
        return developer
    finally:
        session.close()


def _process_github(event: str, body: dict[str, object], delivery: str):
    payload = {"event": event, "payload": body, "delivery": delivery}
    GitHubEventProcessor(payload).process()


def _process_jira(body: dict[str, object]):
    JiraEventProcessor(body).process()


def _base_pr_payload(pr_number: int, *, merged: bool, merged_at: datetime, created_at: datetime, user_payload: dict[str, object]):
    return {
        "action": "closed" if merged else "opened",
        "pull_request": {
            "number": pr_number,
            "title": "PX-123 Implement feature",
            "body": "Implements PX-123",
            "created_at": created_at.isoformat(),
            "merged_at": merged_at.isoformat() if merged else None,
            "merged": merged,
            "user": user_payload,
        },
        "repository": {"full_name": "acme/widgets"},
        "sender": {"login": user_payload.get("login", "sender")},
    }


def _jira_payload(key: str, *, done_at: datetime):
    return {
        "webhookEvent": "jira:issue_updated",
        "id": f"jira-{key}-delivery",
        "issue": {
            "key": key,
            "fields": {
                "status": {"name": "Done"},
                "resolutiondate": done_at.isoformat(),
            },
        },
    }


def _pull_request_review_payload(pr_number: int, *, state: str, user: dict[str, object]):
    return {
        "action": "submitted",
        "pull_request": {
            "number": pr_number,
            "title": "PX-123 Implement feature",
            "body": "PX-123",
            "head": {"ref": "feature/PX-123"},
        },
        "repository": {"full_name": "acme/widgets"},
        "review": {
            "state": state,
            "user": user,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "id": 321,
        },
        "sender": user,
    }


def _pull_request_comment_payload(pr_number: int, *, user: dict[str, object]):
    return {
        "action": "created",
        "pull_request": {
            "number": pr_number,
            "title": "PX-123 Implement feature",
            "head": {"ref": "feature/PX-123"},
        },
        "repository": {"full_name": "acme/widgets"},
        "comment": {
            "user": user,
            "body": "nit: fix spacing",
        },
        "sender": user,
    }


def _push_payload(*, email: str | None, login: str | None):
    commit_author = {"email": email, "login": login}
    return {
        "event": "push",
        "payload": {
            "commits": [
                {"id": "abc123", "message": "PX-123 initial work", "author": commit_author},
            ],
            "head_commit": {
                "id": "abc123",
                "message": "PX-123 initial work",
                "pr_number": 123,
                "author": commit_author,
            },
            "repository": {"full_name": "acme/widgets"},
            "sender": {"login": login},
        },
        "delivery": "push-delivery",
    }


def test_identity_match_by_email(session_factory):
    SessionTest = session_factory
    entities = _seed_core_entities(SessionTest, email="dev@example.com")

    now = datetime.now(timezone.utc)
    pr_body = _base_pr_payload(
        123,
        merged=True,
        merged_at=now,
        created_at=now - timedelta(hours=2),
        user_payload={"email": "dev@example.com"},
    )
    _process_github("pull_request", pr_body, "pr-email")
    _process_jira(_jira_payload("PX-123", done_at=now))

    session = SessionTest()
    try:
        skill = session.query(m.DeveloperSkill).one()
        assert skill.developer_id == entities["developer"].id
        assert skill.score == pytest.approx(1.0 + settings.time_to_merge_bonus)
        assert skill.last_seen_at is not None
    finally:
        session.close()


def test_identity_match_by_login(session_factory):
    SessionTest = session_factory
    entities = _seed_core_entities(SessionTest, login="octocat")

    now = datetime.now(timezone.utc)
    pr_body = _base_pr_payload(
        234,
        merged=True,
        merged_at=now,
        created_at=now - timedelta(hours=1),
        user_payload={"login": "OctoCat"},
    )
    _process_github("pull_request", pr_body, "pr-login")
    _process_jira(_jira_payload("PX-123", done_at=now))

    session = SessionTest()
    try:
        skill = session.query(m.DeveloperSkill).one()
        assert skill.developer_id == entities["developer"].id
    finally:
        session.close()


def test_no_match_creates_triage(session_factory):
    SessionTest = session_factory
    _seed_core_entities(SessionTest, email="dev@example.com")
    now = datetime.now(timezone.utc)
    pr_body = _base_pr_payload(
        345,
        merged=True,
        merged_at=now,
        created_at=now - timedelta(hours=1),
        user_payload={"login": "unknown"},
    )
    _process_github("pull_request", pr_body, "pr-miss")

    session = SessionTest()
    try:
        assert session.query(m.DeveloperSkill).count() == 0
        triage = session.query(m.AttributionTriage).one()
        assert triage.reason == "missing_identity"
    finally:
        session.close()


def test_repo_mapping_context_applies_project(session_factory):
    SessionTest = session_factory
    entities = _seed_core_entities(SessionTest, email="dev@example.com", project_required=True)
    now = datetime.now(timezone.utc)
    pr_body = _base_pr_payload(
        456,
        merged=True,
        merged_at=now,
        created_at=now - timedelta(hours=3),
        user_payload={"email": "dev@example.com"},
    )
    _process_github("pull_request", pr_body, "pr-project")
    _process_jira(_jira_payload("PX-123", done_at=now))

    session = SessionTest()
    try:
        skill = session.query(m.DeveloperSkill).one()
        assert skill.project_id == entities["project"].id
    finally:
        session.close()


def test_baseline_applies_once_out_of_order(session_factory):
    SessionTest = session_factory
    _seed_core_entities(SessionTest, email="dev@example.com")

    now = datetime.now(timezone.utc)
    push_payload = _push_payload(email="dev@example.com", login="devuser")
    _process_github("push", push_payload["payload"], "push-delivery")
    _process_jira(_jira_payload("PX-123", done_at=now))

    pr_body = _base_pr_payload(
        567,
        merged=True,
        merged_at=now,
        created_at=now - timedelta(hours=2),
        user_payload={"email": "dev@example.com"},
    )
    _process_github("pull_request", pr_body, "pr-order")
    _process_github("pull_request", pr_body, "pr-order")  # replay same delivery idempotent

    session = SessionTest()
    try:
        skills = session.query(m.DeveloperSkill).all()
        assert len(skills) == 1
        assert skills[0].score == pytest.approx(1.0 + settings.time_to_merge_bonus)
        events = session.query(m.IntegrationEventLog).filter_by(provider="github", delivery_key="pr-order").all()
        assert len(events) == 1
    finally:
        session.close()


def test_first_review_bonus_applied(session_factory):
    SessionTest = session_factory
    _seed_core_entities(SessionTest, email="dev@example.com")

    now = datetime.now(timezone.utc)
    initial_pr = _base_pr_payload(
        678,
        merged=False,
        merged_at=now,
        created_at=now - timedelta(hours=5),
        user_payload={"email": "dev@example.com"},
    )
    _process_github("pull_request", initial_pr, "pr-first-open")

    review_payload = _pull_request_review_payload(678, state="approved", user={"login": "approver"})
    _process_github("pull_request_review", review_payload, "review-first")

    _process_jira(_jira_payload("PX-123", done_at=now))

    pr_body = _base_pr_payload(
        678,
        merged=True,
        merged_at=now,
        created_at=now - timedelta(hours=4),
        user_payload={"email": "dev@example.com"},
    )
    _process_github("pull_request", pr_body, "pr-first-review")

    session = SessionTest()
    try:
        skill = session.query(m.DeveloperSkill).one()
        assert skill.score == pytest.approx(1.0 + 1.0 + 0.3 + settings.time_to_merge_bonus)
    finally:
        session.close()


def test_multi_round_penalty_applied(session_factory):
    SessionTest = session_factory
    _seed_core_entities(SessionTest, email="dev@example.com")

    now = datetime.now(timezone.utc)
    review_user = {"login": "reviewer"}
    initial_pr = _base_pr_payload(
        789,
        merged=False,
        merged_at=now,
        created_at=now - timedelta(hours=6),
        user_payload={"email": "dev@example.com"},
    )
    _process_github("pull_request", initial_pr, "pr-multi-open")
    review_changes = _pull_request_review_payload(789, state="changes_requested", user=review_user)
    review_changes_again = _pull_request_review_payload(789, state="changes_requested", user=review_user)

    _process_jira(_jira_payload("PX-123", done_at=now))
    _process_github("pull_request_review", review_changes, "review-cycle-1")
    _process_github("pull_request_review", review_changes_again, "review-cycle-2")
    pr_body = _base_pr_payload(
        789,
        merged=True,
        merged_at=now,
        created_at=now - timedelta(hours=5),
        user_payload={"email": "dev@example.com"},
    )
    _process_github("pull_request", pr_body, "pr-multi")

    session = SessionTest()
    try:
        skill = session.query(m.DeveloperSkill).one()
        assert skill.score == pytest.approx(1.0 - 0.5 - 0.6 + settings.time_to_merge_bonus)
    finally:
        session.close()


def test_time_to_merge_penalty(session_factory):
    SessionTest = session_factory
    _seed_core_entities(SessionTest, email="dev@example.com")

    merged_at = datetime.now(timezone.utc)
    created_at = merged_at - timedelta(hours=48)
    pr_body = _base_pr_payload(
        890,
        merged=True,
        merged_at=merged_at,
        created_at=created_at,
        user_payload={"email": "dev@example.com"},
    )
    _process_github("pull_request", pr_body, "pr-time")
    _process_jira(_jira_payload("PX-123", done_at=merged_at))

    session = SessionTest()
    try:
        skill = session.query(m.DeveloperSkill).one()
        assert skill.score == pytest.approx(1.0 - 0.2)
    finally:
        session.close()


def test_peer_review_credit_applied(session_factory):
    SessionTest = session_factory
    entities = _seed_core_entities(SessionTest, email="dev@example.com")
    reviewer = _create_reviewer(SessionTest, entities["tenant"].id, login="reviewer")

    now = datetime.now(timezone.utc)
    review_user = {"login": "reviewer"}
    initial_pr = _base_pr_payload(
        901,
        merged=False,
        merged_at=now,
        created_at=now - timedelta(hours=4),
        user_payload={"email": "dev@example.com"},
    )
    _process_github("pull_request", initial_pr, "pr-peer-open")

    review_payload = _pull_request_review_payload(901, state="approved", user=review_user)
    _process_github("pull_request_review", review_payload, "review-peer")

    _process_jira(_jira_payload("PX-123", done_at=now))

    pr_body = _base_pr_payload(
        901,
        merged=True,
        merged_at=now,
        created_at=now - timedelta(hours=3),
        user_payload={"email": "dev@example.com"},
    )
    _process_github("pull_request", pr_body, "pr-peer")

    session = SessionTest()
    try:
        skill = session.query(m.DeveloperSkill).one()
        assert skill.score == pytest.approx(1.0 + 1.0 + 0.3 + settings.review_peer_credit + settings.time_to_merge_bonus)
        credits = session.query(m.PeerReviewCredit).all()
        assert len(credits) == 1
        assert credits[0].reviewer_developer_id == reviewer.id
    finally:
        session.close()


def test_idempotent_replays(session_factory):
    SessionTest = session_factory
    _seed_core_entities(SessionTest, email="dev@example.com")

    now = datetime.now(timezone.utc)
    pr_body = _base_pr_payload(
        999,
        merged=True,
        merged_at=now,
        created_at=now - timedelta(hours=2),
        user_payload={"email": "dev@example.com"},
    )
    jira_body = _jira_payload("PX-123", done_at=now)

    _process_github("pull_request", pr_body, "delivery-dup")
    _process_jira(jira_body)
    _process_github("pull_request", pr_body, "delivery-dup")
    _process_jira(jira_body)

    session = SessionTest()
    try:
        skill = session.query(m.DeveloperSkill).one()
        assert skill.score == pytest.approx(1.0 + settings.time_to_merge_bonus)
    finally:
        session.close()
