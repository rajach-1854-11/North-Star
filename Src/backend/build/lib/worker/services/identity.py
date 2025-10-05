from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain import models as m

logger = logging.getLogger(__name__)


@dataclass
class IdentityMatch:
    developer_id: int
    tenant_id: str
    source: str


def normalize_email(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower()


def candidate_emails(payload: dict[str, object]) -> Iterable[str]:
    emails: list[str] = []
    keys = [
        "pusher",
        "sender",
        "author",
        "committer",
        "user",
        "head_commit",
    ]
    for key in keys:
        entity = payload.get(key)
        if isinstance(entity, dict):
            for email_key in ("email", "login", "name"):
                value = entity.get(email_key)
                if isinstance(value, str) and "@" in value:
                    emails.append(value)
            nested_author = entity.get("author") if isinstance(entity.get("author"), dict) else None
            nested_committer = entity.get("committer") if isinstance(entity.get("committer"), dict) else None
            for nested in (nested_author, nested_committer):
                if isinstance(nested, dict):
                    email = nested.get("email")
                    if isinstance(email, str) and "@" in email:
                        emails.append(email)
    commits = payload.get("commits")
    if isinstance(commits, list):
        for commit in commits:
            if not isinstance(commit, dict):
                continue
            for person_key in ("author", "committer"):
                person = commit.get(person_key)
                if isinstance(person, dict):
                    email = person.get("email")
                    if isinstance(email, str) and "@" in email:
                        emails.append(email)
    pull_request = payload.get("pull_request")
    if isinstance(pull_request, dict):
        for subkey in ("user", "merged_by"):
            entity = pull_request.get(subkey)
            if isinstance(entity, dict):
                email = entity.get("email")
                if isinstance(email, str) and "@" in email:
                    emails.append(email)
    return emails


def candidate_logins(payload: dict[str, object]) -> Iterable[str]:
    logins: list[str] = []
    for key in ("sender", "author", "committer", "user"):
        entity = payload.get(key)
        if isinstance(entity, dict):
            login = entity.get("login")
            if isinstance(login, str):
                logins.append(login.strip().lower())
    return logins


def resolve_identity(session: Session, *, provider: str, payload: dict[str, object]) -> Optional[IdentityMatch]:
    emails = [normalize_email(email) for email in candidate_emails(payload) if normalize_email(email)]
    logins = [login for login in candidate_logins(payload) if login]

    if emails:
        stmt = (
            select(m.DeveloperIdentity.developer_id, m.DeveloperIdentity.tenant_id)
            .where(m.DeveloperIdentity.provider == provider)
            .where(m.DeveloperIdentity.email_lower.in_(emails))
            .limit(1)
        )
        result = session.execute(stmt).first()
        if result:
            developer_id, tenant_id = result
            return IdentityMatch(developer_id=developer_id, tenant_id=tenant_id, source="email")

    if logins:
        stmt = (
            select(m.DeveloperIdentity.developer_id, m.DeveloperIdentity.tenant_id)
            .where(m.DeveloperIdentity.provider == provider)
            .where(func.lower(m.DeveloperIdentity.provider_login).in_(logins))
            .limit(1)
        )
        result = session.execute(stmt).first()
        if result:
            developer_id, tenant_id = result
            return IdentityMatch(developer_id=developer_id, tenant_id=tenant_id, source="login")

    logger.info("identity.resolve.no_match", extra={"provider": provider, "emails": emails, "logins": logins})
    return None
