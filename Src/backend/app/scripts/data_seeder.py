"""CSV-driven data seeder for North Star.

Usage examples (run from the backend directory):

    # Seed all files from the default directory
    python -m app.scripts.data_seeder --dir backend/data/seed

    # Dry run with verbose counts
    python -m app.scripts.data_seeder --dir backend/data/seed --dry-run --stats

    # Seed a single file
    python -m app.scripts.data_seeder --file backend/data/seed/projects.csv

The seeder is idempotent, tenant-aware, and honours the existing SQLAlchemy models.
It only inserts missing rows (unless --update is provided) and supports dry-run
mode to preview actions without mutating the database.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from pathlib import Path
from typing import Callable, Dict, Iterable, Iterator, List, Sequence, Tuple, Type

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import SessionLocal
from app.domain import models as m


class SeederError(RuntimeError):
    """Raised when seeding fails due to bad references or invalid data."""


@dataclass(slots=True)
class SeederContext:
    tenant_id: str
    dry_run: bool
    allow_update: bool


@dataclass(slots=True)
class FileStats:
    inserted: int = 0
    skipped: int = 0
    updated: int = 0

    def note(self, outcome: str) -> None:
        if outcome not in {"inserted", "skipped", "updated"}:
            raise ValueError(f"Unknown outcome '{outcome}'")
        setattr(self, outcome, getattr(self, outcome) + 1)


def _iso_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    slug = slug.strip("-")
    return slug or value.strip().lower()


class _CSVModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class TenantRow(_CSVModel):
    id: str
    name: str


class ProjectRow(_CSVModel):
    key: str
    name: str
    description: str | None = None


class UserRow(_CSVModel):
    username: str
    role: str
    password_hash: str


class DeveloperRow(_CSVModel):
    username: str
    display_name: str


class AssignmentRow(_CSVModel):
    username: str
    project_key: str
    role: str | None = None
    status: str | None = "active"


class SkillRow(_CSVModel):
    name: str
    parent: str | None = None
    importance: float = 0.5


class ProjectSkillRow(_CSVModel):
    project_key: str
    skill_name: str
    importance: float = 0.5


class DeveloperSkillRow(_CSVModel):
    username: str
    skill_name: str
    score: float = 0.0
    confidence: float = 0.5


RowModel = Type[_CSVModel]
Handler = Callable[["Seeder", Sequence[_CSVModel], str], FileStats]


class Seeder:
    """Helper encapsulating common lookup and persistence helpers."""

    def __init__(self, session: Session, context: SeederContext) -> None:
        self.session = session
        self.context = context
        self._users: Dict[str, m.User] = {}
        self._projects: Dict[str, m.Project] = {}
        self._developers: Dict[str, m.Developer] = {}
        self._skills: Dict[str, m.Skill] = {}

    # --- session helpers -------------------------------------------------
    def remember_user(self, user: m.User) -> None:
        self._users[user.username] = user

    def remember_project(self, project: m.Project) -> None:
        self._projects[project.key] = project

    def remember_developer(self, username: str, developer: m.Developer) -> None:
        self._developers[username] = developer

    def remember_skill(self, name: str, skill: m.Skill) -> None:
        self._skills[name] = skill

    def add(self, instance: object) -> None:
        if not self.context.dry_run:
            self.session.add(instance)

    def flush(self) -> None:
        if not self.context.dry_run:
            self.session.flush()

    # --- resolvers -------------------------------------------------------
    def get_user(self, username: str) -> m.User | None:
        if username in self._users:
            return self._users[username]
        user = self.session.query(m.User).filter(m.User.username == username).one_or_none()
        if user is not None:
            self._users[username] = user
        return user

    def get_project(self, key: str) -> m.Project | None:
        if key in self._projects:
            return self._projects[key]
        project = (
            self.session.query(m.Project)
            .filter(m.Project.key == key, m.Project.tenant_id == self.context.tenant_id)
            .one_or_none()
        )
        if project is not None:
            self._projects[key] = project
        return project

    def get_developer(self, username: str) -> m.Developer | None:
        if username in self._developers:
            return self._developers[username]
        user = self.get_user(username)
        if user is None:
            return None
        developer = self.session.query(m.Developer).filter(m.Developer.user_id == user.id).one_or_none()
        if developer is not None:
            self._developers[username] = developer
        return developer

    def get_skill(self, name: str) -> m.Skill | None:
        if name in self._skills:
            return self._skills[name]
        skill = self.session.query(m.Skill).filter(m.Skill.name == name).one_or_none()
        if skill is not None:
            self._skills[name] = skill
        return skill


def _read_csv(path: Path, model: RowModel) -> List[_CSVModel]:
    if not path.exists():
        return []

    def _line_iter(handle: Iterable[str]) -> Iterator[str]:
        for line in handle:
            if not line.strip():
                continue
            if line.lstrip().startswith("#"):
                continue
            yield line

    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(_line_iter(handle))
        if reader.fieldnames is None:
            raise SeederError(f"{path}: missing header row")

        required_columns = {name for name, field in model.model_fields.items() if field.is_required()}
        missing = required_columns.difference(reader.fieldnames)
        if missing:
            raise SeederError(f"{path}: missing required columns {sorted(missing)}")

        rows: List[_CSVModel] = []
        for raw in reader:
            cleaned: Dict[str, object | None] = {}
            for key, value in raw.items():
                if value is None:
                    cleaned[key] = None
                    continue
                stripped = value.strip()
                cleaned[key] = stripped if stripped != "" else None
            try:
                rows.append(model.model_validate(cleaned))
            except ValidationError as exc:
                raise SeederError(f"{path}: line {reader.line_num} validation error: {exc}") from exc
        return rows


def _seed_tenants(seeder: Seeder, rows: Sequence[TenantRow], file_name: str) -> FileStats:
    stats = FileStats()
    for row in rows:
        existing = seeder.session.query(m.Tenant).filter(m.Tenant.id == row.id).one_or_none()
        if existing is None:
            tenant = m.Tenant(id=row.id, name=row.name)
            seeder.add(tenant)
            seeder.flush()
            stats.note("inserted")
        else:
            if seeder.context.allow_update and existing.name != row.name:
                if not seeder.context.dry_run:
                    existing.name = row.name
                stats.note("updated")
            else:
                stats.note("skipped")
    return stats


def _seed_projects(seeder: Seeder, rows: Sequence[ProjectRow], file_name: str) -> FileStats:
    stats = FileStats()
    tenant_id = seeder.context.tenant_id
    for row in rows:
        existing = (
            seeder.session.query(m.Project)
            .filter(m.Project.key == row.key, m.Project.tenant_id == tenant_id)
            .one_or_none()
        )
        if existing is None:
            project = m.Project(key=row.key, name=row.name, description=row.description, tenant_id=tenant_id)
            seeder.add(project)
            seeder.flush()
            seeder.remember_project(project)
            stats.note("inserted")
        else:
            changed = False
            if seeder.context.allow_update:
                if existing.name != row.name:
                    if not seeder.context.dry_run:
                        existing.name = row.name
                    changed = True
                if row.description is not None and existing.description != row.description:
                    if not seeder.context.dry_run:
                        existing.description = row.description
                    changed = True
            stats.note("updated" if changed else "skipped")
    return stats


_ALLOWED_ROLES = {"PO", "BA", "Dev"}


def _seed_users(seeder: Seeder, rows: Sequence[UserRow], file_name: str) -> FileStats:
    stats = FileStats()
    tenant_id = seeder.context.tenant_id
    for row in rows:
        role = row.role
        if role not in _ALLOWED_ROLES:
            raise SeederError(f"{file_name}: role '{role}' is not permitted (allowed: {_ALLOWED_ROLES})")
        existing = seeder.session.query(m.User).filter(m.User.username == row.username).one_or_none()
        if existing is None:
            user = m.User(username=row.username, role=role, password_hash=row.password_hash, tenant_id=tenant_id)
            seeder.add(user)
            seeder.flush()
            seeder.remember_user(user)
            stats.note("inserted")
        else:
            changed = False
            if seeder.context.allow_update:
                if existing.role != role:
                    if not seeder.context.dry_run:
                        existing.role = role
                    changed = True
                if existing.password_hash != row.password_hash:
                    if not seeder.context.dry_run:
                        existing.password_hash = row.password_hash
                    changed = True
                if existing.tenant_id != tenant_id:
                    if not seeder.context.dry_run:
                        existing.tenant_id = tenant_id
                    changed = True
            seeder.remember_user(existing)
            stats.note("updated" if changed else "skipped")
    return stats


def _seed_developers(seeder: Seeder, rows: Sequence[DeveloperRow], file_name: str) -> FileStats:
    stats = FileStats()
    tenant_id = seeder.context.tenant_id
    for row in rows:
        user = seeder.get_user(row.username)
        if user is None:
            raise SeederError(f"{file_name}: developer username '{row.username}' not found; seed users first")
        existing = seeder.session.query(m.Developer).filter(m.Developer.user_id == user.id).one_or_none()
        if existing is None:
            developer = m.Developer(user_id=user.id, display_name=row.display_name, tenant_id=tenant_id)
            seeder.add(developer)
            seeder.flush()
            seeder.remember_developer(row.username, developer)
            stats.note("inserted")
        else:
            changed = False
            if seeder.context.allow_update and existing.display_name != row.display_name:
                if not seeder.context.dry_run:
                    existing.display_name = row.display_name
                changed = True
            if seeder.context.allow_update and existing.tenant_id != tenant_id:
                if not seeder.context.dry_run:
                    existing.tenant_id = tenant_id
                changed = True
            seeder.remember_developer(row.username, existing)
            stats.note("updated" if changed else "skipped")
    return stats


def _seed_assignments(seeder: Seeder, rows: Sequence[AssignmentRow], file_name: str) -> FileStats:
    stats = FileStats()
    tenant_id = seeder.context.tenant_id
    for row in rows:
        developer = seeder.get_developer(row.username)
        if developer is None:
            raise SeederError(f"{file_name}: assignment username '{row.username}' not found")
        project = seeder.get_project(row.project_key)
        if project is None:
            raise SeederError(f"{file_name}: project '{row.project_key}' not found for tenant '{tenant_id}'")
        existing = (
            seeder.session.query(m.Assignment)
            .filter(m.Assignment.developer_id == developer.id, m.Assignment.project_id == project.id)
            .one_or_none()
        )
        desired_status = row.status or "active"
        if existing is None:
            assignment = m.Assignment(
                developer_id=developer.id,
                project_id=project.id,
                role=row.role,
                status=desired_status,
            )
            seeder.add(assignment)
            stats.note("inserted")
        else:
            changed = False
            if seeder.context.allow_update:
                if row.role is not None and existing.role != row.role:
                    if not seeder.context.dry_run:
                        existing.role = row.role
                    changed = True
                if existing.status != desired_status:
                    if not seeder.context.dry_run:
                        existing.status = desired_status
                    changed = True
            stats.note("updated" if changed else "skipped")
    return stats


def _skill_path(name: str, parent: m.Skill | None) -> Tuple[str, int]:
    slug = _slugify(name)
    if parent is None:
        return slug, 0
    return f"{parent.path_cache}.{slug}", parent.depth + 1


def _seed_skills(seeder: Seeder, rows: Sequence[SkillRow], file_name: str) -> FileStats:
    stats = FileStats()
    for row in rows:
        existing = seeder.get_skill(row.name)
        if existing is None:
            parent_skill = None
            if row.parent:
                parent_skill = seeder.get_skill(row.parent)
                if parent_skill is None:
                    raise SeederError(f"{file_name}: parent skill '{row.parent}' not found for '{row.name}'")
            path_cache, depth = _skill_path(row.name, parent_skill)
            skill = m.Skill(name=row.name, parent_id=parent_skill.id if parent_skill else None, path_cache=path_cache, depth=depth)
            seeder.add(skill)
            seeder.flush()
            seeder.remember_skill(row.name, skill)
            stats.note("inserted")
        else:
            stats.note("skipped")
    return stats


def _seed_project_skills(seeder: Seeder, rows: Sequence[ProjectSkillRow], file_name: str) -> FileStats:
    stats = FileStats()
    tenant_id = seeder.context.tenant_id
    for row in rows:
        project = seeder.get_project(row.project_key)
        if project is None:
            raise SeederError(f"{file_name}: project '{row.project_key}' not found for tenant '{tenant_id}'")
        skill = seeder.get_skill(row.skill_name)
        if skill is None:
            raise SeederError(f"{file_name}: skill '{row.skill_name}' not found")
        existing = (
            seeder.session.query(m.ProjectSkill)
            .filter(m.ProjectSkill.project_id == project.id, m.ProjectSkill.skill_id == skill.id)
            .one_or_none()
        )
        if existing is None:
            ps = m.ProjectSkill(project_id=project.id, skill_id=skill.id, importance=row.importance)
            seeder.add(ps)
            stats.note("inserted")
        else:
            if seeder.context.allow_update and existing.importance != row.importance:
                if not seeder.context.dry_run:
                    existing.importance = row.importance
                stats.note("updated")
            else:
                stats.note("skipped")
    return stats


def _seed_developer_skills(seeder: Seeder, rows: Sequence[DeveloperSkillRow], file_name: str) -> FileStats:
    stats = FileStats()
    for row in rows:
        developer = seeder.get_developer(row.username)
        if developer is None:
            raise SeederError(f"{file_name}: developer '{row.username}' not found")
        skill = seeder.get_skill(row.skill_name)
        if skill is None:
            raise SeederError(f"{file_name}: skill '{row.skill_name}' not found")
        existing = (
            seeder.session.query(m.DeveloperSkill)
            .filter(m.DeveloperSkill.developer_id == developer.id, m.DeveloperSkill.skill_id == skill.id)
            .one_or_none()
        )
        if existing is None:
            ds = m.DeveloperSkill(
                developer_id=developer.id,
                skill_id=skill.id,
                score=row.score,
                confidence=row.confidence,
            )
            seeder.add(ds)
            stats.note("inserted")
        else:
            changed = False
            if seeder.context.allow_update:
                if existing.score != row.score:
                    if not seeder.context.dry_run:
                        existing.score = row.score
                    changed = True
                if existing.confidence != row.confidence:
                    if not seeder.context.dry_run:
                        existing.confidence = row.confidence
                    changed = True
            stats.note("updated" if changed else "skipped")
    return stats


FILE_HANDLERS: Dict[str, Tuple[RowModel, Handler]] = {
    "tenants": (TenantRow, _seed_tenants),
    "projects": (ProjectRow, _seed_projects),
    "users": (UserRow, _seed_users),
    "developers": (DeveloperRow, _seed_developers),
    "assignments": (AssignmentRow, _seed_assignments),
    "skills": (SkillRow, _seed_skills),
    "project_skills": (ProjectSkillRow, _seed_project_skills),
    "developer_skills": (DeveloperSkillRow, _seed_developer_skills),
}

DEFAULT_ORDER = [
    "tenants.csv",
    "projects.csv",
    "users.csv",
    "developers.csv",
    "assignments.csv",
    "skills.csv",
    "project_skills.csv",
    "developer_skills.csv",
]


def _process_file(path: Path, context: SeederContext, session: Session | None = None, seeder: Seeder | None = None) -> FileStats:
    key = path.stem.lower()
    if key not in FILE_HANDLERS:
        raise SeederError(f"Unsupported seed file '{path.name}'")
    model, handler = FILE_HANDLERS[key]
    rows = _read_csv(path, model)
    if not rows:
        stats = FileStats()
        print(f"{_iso_timestamp()} | {path.name} | inserted={stats.inserted} skipped={stats.skipped} updated={stats.updated} (no rows)")
        return stats

    created_session = False
    if session is None:
        session = SessionLocal()
        created_session = True
    if seeder is None:
        seeder = Seeder(session, context)
    try:
        stats = handler(seeder, rows, path.name)
        if context.dry_run:
            if created_session:
                session.rollback()
        else:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        if created_session:
            session.close()

    print(f"{_iso_timestamp()} | {path.name} | inserted={stats.inserted} skipped={stats.skipped} updated={stats.updated}")
    return stats


def _process_directory(directory: Path, context: SeederContext) -> Dict[str, FileStats]:
    summaries: Dict[str, FileStats] = {}
    if context.dry_run:
        with SessionLocal() as session:
            seeder = Seeder(session, context)
            try:
                for filename in DEFAULT_ORDER:
                    path = directory / filename
                    if not path.exists():
                        continue
                    summaries[filename] = _process_file(path, context, session=session, seeder=seeder)
                session.rollback()
            except Exception:
                session.rollback()
                raise
    else:
        for filename in DEFAULT_ORDER:
            path = directory / filename
            if not path.exists():
                continue
            summaries[filename] = _process_file(path, context)
    return summaries


def _emit_table_counts(context: SeederContext) -> None:
    with SessionLocal() as session:
        tenant_id = context.tenant_id
        counts = {
            "tenant": session.query(func.count()).select_from(m.Tenant).scalar() or 0,
            "project": session.query(func.count()).select_from(m.Project).filter(m.Project.tenant_id == tenant_id).scalar() or 0,
            "user": session.query(func.count()).select_from(m.User).filter(m.User.tenant_id == tenant_id).scalar() or 0,
            "developer": session.query(func.count()).select_from(m.Developer).filter(m.Developer.tenant_id == tenant_id).scalar() or 0,
            "assignment": session.query(func.count()).select_from(m.Assignment).join(m.Developer, m.Assignment.developer_id == m.Developer.id).filter(m.Developer.tenant_id == tenant_id).scalar() or 0,
            "skill": session.query(func.count()).select_from(m.Skill).scalar() or 0,
            "project_skill": session.query(func.count()).select_from(m.ProjectSkill).scalar() or 0,
            "developer_skill": session.query(func.count()).select_from(m.DeveloperSkill).scalar() or 0,
        }
    print("Table counts (tenant scoped where applicable):")
    for name, value in counts.items():
        print(f"  {name}: {value}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed Postgres with CSV fixtures in an idempotent fashion")
    parser.add_argument("--dir", type=Path, help="Directory containing seed CSVs", default=None)
    parser.add_argument("--file", type=Path, help="Path to a single CSV file", default=None)
    parser.add_argument("--tenant", type=str, help="Override tenant id", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Simulate actions without committing")
    parser.add_argument("--update", action="store_true", help="Update existing rows when data differs")
    parser.add_argument("--stats", action="store_true", help="Print table counts after seeding")
    args = parser.parse_args(argv)

    if not args.dir and not args.file:
        parser.error("one of --dir or --file is required")
    if args.dir and args.file:
        parser.error("choose either --dir or --file, not both")
    return args


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    tenant_id = args.tenant or settings.tenant_id
    context = SeederContext(tenant_id=tenant_id, dry_run=args.dry_run, allow_update=args.update)

    try:
        if args.dir:
            directory = args.dir
            if not directory.exists():
                raise SeederError(f"Seed directory '{directory}' does not exist")
            _process_directory(directory, context)
        else:
            file_path = args.file
            if file_path is None:
                raise SeederError("--file path is required")
            if not file_path.exists():
                raise SeederError(f"Seed file '{file_path}' does not exist")
            _process_file(file_path, context)
        if args.stats:
            _emit_table_counts(context)
    except SeederError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
