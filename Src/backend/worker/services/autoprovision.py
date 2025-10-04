from __future__ import annotations

import logging
import secrets
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.domain import models as m

logger = logging.getLogger(__name__)


def provision_developer(
    session: Session,
    *,
    tenant_id: str,
    login: str | None,
    email: str | None,
) -> Optional[m.DeveloperIdentity]:
    if not settings.auto_provision_dev_from_gh:
        return None
    if not login and not email:
        return None

    username = login or (email.split("@", 1)[0] if email else None)
    if not username:
        return None

    existing_user = (
        session.query(m.User)
        .filter(m.User.username == username)
        .one_or_none()
    )
    if existing_user is None:
        existing_user = m.User(
            username=username,
            password_hash=secrets.token_hex(16),
            role="Dev",
            tenant_id=tenant_id,
        )
        session.add(existing_user)
        session.flush()

    developer = (
        session.query(m.Developer)
        .filter(m.Developer.user_id == existing_user.id)
        .one_or_none()
    )
    if developer is None:
        developer = m.Developer(
            user_id=existing_user.id,
            display_name=username.title(),
            tenant_id=tenant_id,
        )
        session.add(developer)
        session.flush()

    identity = m.DeveloperIdentity(
        developer_id=developer.id,
        tenant_id=tenant_id,
        provider="github",
        provider_login=login.lower() if login else None,
        email=email,
        email_lower=email.lower() if email else None,
        is_primary=True,
        metadata_json={},
    )
    session.add(identity)
    session.flush()
    logger.info(
        "autoprovision.developer",
        extra={"developer_id": developer.id, "tenant_id": tenant_id, "login": login},
    )
    return identity
