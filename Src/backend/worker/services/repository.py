from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import models as m

logger = logging.getLogger(__name__)


def resolve_repository_context(session: Session, *, provider: str, repo_full_name: str) -> Optional[m.RepositoryMapping]:
    stmt = (
        select(m.RepositoryMapping)
        .where(m.RepositoryMapping.provider == provider)
        .where(m.RepositoryMapping.repo_full_name == repo_full_name)
    )
    mapping = session.execute(stmt).scalar_one_or_none()
    if mapping is None:
        logger.warning(
            "repository.mapping.missing",
            extra={"provider": provider, "repo_full_name": repo_full_name},
        )
    return mapping
