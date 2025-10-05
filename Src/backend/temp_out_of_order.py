import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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

from app.domain import models as m
from worker.handlers import skill_extractor
import worker.services.database as db
from worker.services.github_processor import GitHubEventProcessor
from worker.services.jira_processor import JiraEventProcessor

engine = create_engine("sqlite:///:memory:", future=True)
m.Base.metadata.create_all(engine)
SessionTest = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)
db.engine = engine
db.SessionLocal = SessionTest
skill_extractor.engine = engine


def fake_generate_skill_assertions(event, payload):
    return [{"path": ["Engineering", "Backend"], "confidence": 0.9}]


skill_extractor.generate_skill_assertions = fake_generate_skill_assertions

session = SessionTest()
tenant = m.Tenant(id="tenant-1", name="Tenant One")
session.add(tenant)
project = m.Project(key="PX", name="Project X", description="Test Project", tenant_id=tenant.id)
session.add(project)
user = m.User(username="devuser", password_hash="hash", role="Dev", tenant_id=tenant.id)
session.add(user)
session.flush()
developer = m.Developer(user_id=user.id, display_name="Dev User", tenant_id=tenant.id)
session.add(developer)
session.flush()
identity = m.DeveloperIdentity(
    developer_id=developer.id,
    tenant_id=tenant.id,
    provider="github",
    provider_login="devuser",
    email="dev@example.com",
    email_lower="dev@example.com",
    is_primary=True,
    metadata_json={},
)
session.add(identity)
mapping = m.RepositoryMapping(
    provider="github",
    repo_full_name="acme/widgets",
    tenant_id=tenant.id,
    project_id=project.id,
    metadata_json={},
    active=True,
)
session.add(mapping)
session.commit()
session.close()

now = datetime.now(timezone.utc)
push_payload = {
    "event": "push",
    "payload": {
        "commits": [
            {"id": "abc123", "message": "PX-123 initial work", "author": {"email": "dev@example.com", "login": "devuser"}},
        ],
        "head_commit": {
            "id": "abc123",
            "message": "PX-123 initial work",
            "pr_number": 123,
            "author": {"email": "dev@example.com", "login": "devuser"},
        },
        "repository": {"full_name": "acme/widgets"},
        "sender": {"login": "devuser"},
    },
    "delivery": "push-delivery",
}

GitHubEventProcessor(push_payload).process()

session = SessionTest()
print("after_push", session.query(m.AttributionWorkflow).count())
for wf in session.query(m.AttributionWorkflow).all():
    print("  push_wf", wf.id, wf.pr_number, wf.jira_key, wf.developer_id)
session.close()

JiraEventProcessor({
    "webhookEvent": "jira:issue_updated",
    "id": "jira-PX-123-delivery",
    "issue": {
        "key": "PX-123",
        "fields": {
            "status": {"name": "Done"},
            "resolutiondate": now.isoformat(),
        },
    },
}).process()

session = SessionTest()
print("after_jira", session.query(m.AttributionWorkflow).count())
for wf in session.query(m.AttributionWorkflow).all():
    print("  jira_wf", wf.id, wf.pr_number, wf.jira_key, wf.jira_done_at)
session.close()

pr_body = {
    "event": "pull_request",
    "payload": {
        "action": "closed",
        "pull_request": {
            "number": 567,
            "title": "PX-123 Implement feature",
            "body": "Implements PX-123",
            "created_at": (now - timedelta(hours=2)).isoformat(),
            "merged_at": now.isoformat(),
            "merged": True,
            "user": {"email": "dev@example.com"},
        },
        "repository": {"full_name": "acme/widgets"},
        "sender": {"login": "devuser"},
    },
    "delivery": "pr-order",
}

GitHubEventProcessor(pr_body).process()
GitHubEventProcessor(pr_body).process()

session = SessionTest()
print("workflows", session.query(m.AttributionWorkflow).count())
for wf in session.query(m.AttributionWorkflow).all():
    print("WF", wf.id, wf.pr_number, wf.jira_key, wf.pr_merged_at, wf.jira_done_at, wf.developer_id, wf.baseline_applied_at)
    print("  peer_credit", wf.peer_review_credit, "assertions", wf.assertions)
print("skills", session.query(m.DeveloperSkill).count())
for skill in session.query(m.DeveloperSkill).all():
    print("skill", skill.developer_id, skill.skill_id, skill.score)
print("triage", session.query(m.AttributionTriage).count())
for tri in session.query(m.AttributionTriage).all():
    print("tri", tri.reason)
session.close()
