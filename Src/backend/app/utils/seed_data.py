"""Lightweight development seed data for the North Star API."""

from __future__ import annotations

from datetime import date
from typing import Dict, Iterable, Tuple

from sqlalchemy.orm import Session

from app import deps
from app.config import settings
from app.domain import models as m


def _get_or_create_user(db: Session, *, tenant_id: str, username: str, role: str, password: str) -> m.User:
    user = db.query(m.User).filter(m.User.username == username).one_or_none()
    if user is None:
        user = m.User(username=username, password_hash=password, role=role, tenant_id=tenant_id)
        db.add(user)
        db.flush()
    else:
        if user.role != role:
            user.role = role
        if user.tenant_id != tenant_id:
            user.tenant_id = tenant_id
    return user


def _get_or_create_project(db: Session, *, tenant_id: str, key: str, name: str, description: str) -> m.Project:
    project = db.query(m.Project).filter(m.Project.key == key, m.Project.tenant_id == tenant_id).one_or_none()
    if project is None:
        project = m.Project(key=key, name=name, description=description, tenant_id=tenant_id)
        db.add(project)
        db.flush()
    else:
        if project.name != name:
            project.name = name
        if project.description != description:
            project.description = description
    return project


def _get_or_create_skill(
    db: Session,
    *,
    path: str,
    display_name: str,
    parent: m.Skill | None = None,
    depth: int | None = None,
) -> m.Skill:
    skill = db.query(m.Skill).filter(m.Skill.path_cache == path).one_or_none()
    if skill is None:
        skill = m.Skill(
            name=display_name,
            parent_id=parent.id if parent else None,
            path_cache=path,
            depth=depth if depth is not None else (parent.depth + 1 if parent else 0),
        )
        db.add(skill)
        db.flush()
    return skill


def ensure_seed_data() -> None:
    """Create deterministic seed data if the database is empty."""

    tenant_id = settings.tenant_id

    with deps.SessionLocal() as db:
        if db.query(m.Tenant).filter(m.Tenant.id == tenant_id).one_or_none() is None:
            db.add(m.Tenant(id=tenant_id, name="North Star Demo Tenant"))
            db.flush()

        users: Dict[str, m.User] = {}
        for username, role in (
            ("admin_root", "Admin"),
            ("po_admin", "PO"),
            ("ba_anita", "BA"),
            ("ba_nancy", "BA"),
            ("dev_alex", "Dev"),
        ):
            users[username] = _get_or_create_user(
                db, tenant_id=tenant_id, username=username, role=role, password="x"
            )

        developer = db.query(m.Developer).filter(m.Developer.user_id == users["dev_alex"].id).one_or_none()
        if developer is None:
            developer = m.Developer(
                user_id=users["dev_alex"].id,
                display_name="Alex Developer",
                tenant_id=tenant_id,
            )
            db.add(developer)
            db.flush()

        po_projects: Iterable[Tuple[str, str, str]] = (
            ("PX", "Realtime Pricing", "Pricing platform modernisation"),
            ("PB", "Product Beta", "Beta backlog and discovery"),
        )
        projects: Dict[str, m.Project] = {}
        for key, name, description in po_projects:
            projects[key] = _get_or_create_project(
                db, tenant_id=tenant_id, key=key, name=name, description=description
            )

        if (
            db.query(m.Assignment)
            .filter(
                m.Assignment.developer_id == developer.id,
                m.Assignment.project_id == projects["PX"].id,
            )
            .one_or_none()
            is None
        ):
            db.add(
                m.Assignment(
                    developer_id=developer.id,
                    project_id=projects["PX"].id,
                    role="Engineer",
                    start_date=date(2024, 6, 1),
                    status="active",
                )
            )

        # Skills hierarchy (minimal viable set)
        eng = _get_or_create_skill(db, path="engineering", display_name="Engineering", depth=0)
        backend = _get_or_create_skill(db, path="engineering.backend", display_name="Backend", parent=eng)
        data = _get_or_create_skill(db, path="engineering.data", display_name="Data", parent=eng)
        kafka = _get_or_create_skill(
            db,
            path="engineering.backend.kafka",
            display_name="Apache Kafka",
            parent=backend,
        )
        python_skill = _get_or_create_skill(
            db,
            path="engineering.backend.python",
            display_name="Python",
            parent=backend,
        )
        spark = _get_or_create_skill(
            db,
            path="engineering.data.spark",
            display_name="Apache Spark",
            parent=data,
        )

        for project_key, skill_weights in {
            "PX": {
                kafka.id: 0.9,
                python_skill.id: 0.8,
            },
            "PB": {
                python_skill.id: 0.7,
                spark.id: 0.6,
            },
        }.items():
            project = projects[project_key]
            for skill_id, importance in skill_weights.items():
                if (
                    db.query(m.ProjectSkill)
                    .filter(m.ProjectSkill.project_id == project.id, m.ProjectSkill.skill_id == skill_id)
                    .one_or_none()
                    is None
                ):
                    db.add(
                        m.ProjectSkill(
                            project_id=project.id,
                            skill_id=skill_id,
                            importance=importance,
                        )
                    )

        for skill, score in {
            kafka: 0.82,
            python_skill: 0.88,
            spark: 0.55,
        }.items():
            if (
                db.query(m.DeveloperSkill)
                .filter(
                    m.DeveloperSkill.developer_id == developer.id,
                    m.DeveloperSkill.skill_id == skill.id,
                )
                .one_or_none()
                is None
            ):
                db.add(
                    m.DeveloperSkill(
                        developer_id=developer.id,
                        skill_id=skill.id,
                        score=score,
                        confidence=0.75,
                    )
                )

        db.commit()
