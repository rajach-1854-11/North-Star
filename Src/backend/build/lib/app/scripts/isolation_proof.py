"""Generate tenant isolation proof artifacts.

This script inspects the backing PostgreSQL database and produces a JSON +
Markdown report demonstrating that tenant-scoped entities remain isolated.
It can be invoked as a module or imported programmatically.
"""

from __future__ import annotations

import argparse
import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pytest

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import SessionLocal
from app.domain import models as m


_TENANT_AWARE_MODELS: tuple[type[m.Base], ...] = (
    m.User,
    m.Project,
    m.Developer,
    m.AuditLog,
    m.Event,
    m.RouterStats,
    m.TenantMapperWeights,
    m.ABMapEdge,
)


def _iso_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_property_suite(skip: bool = False) -> dict[str, Any]:
    """Execute property-based tests guarding isolation invariants."""

    if skip:
        return {"status": "skipped", "exit_code": 0}

    exit_code = pytest.main(["-k", "policy_properties", "-q"])
    if exit_code == 0:
        status = "pass"
    elif exit_code == 5:  # no tests collected
        status = "not_found"
        exit_code = 0
    else:
        status = "fail"
    return {"status": status, "exit_code": exit_code}


def _table_counts(session: Session, model: type[m.Base]) -> tuple[dict[str, int], int]:
    column = getattr(model, "tenant_id", None)
    if column is None:
        raise ValueError(f"Model {model.__name__} does not expose a tenant_id column")

    stmt = select(column, func.count()).select_from(model).group_by(column)
    rows = session.execute(stmt).all()

    counts: dict[str, int] = {}
    null_count = 0
    for tenant_id, count in rows:
        if tenant_id is None:
            null_count = count
            counts["__null__"] = count
        else:
            counts[str(tenant_id)] = count
    return counts, null_count


def _check_result(name: str, passed: bool, details: str | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "details": details,
    }


def _run_alignment_checks(session: Session) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    # Developer ↔ user tenant alignment
    mismatched_devs = session.execute(
        select(func.count())
        .select_from(m.Developer)
        .join(m.User, m.User.id == m.Developer.user_id)
        .where(m.Developer.tenant_id != m.User.tenant_id)
    ).scalar_one()
    checks.append(
        _check_result(
            "Developer tenant matches user tenant",
            mismatched_devs == 0,
            None if mismatched_devs == 0 else f"{mismatched_devs} developer(s) span multiple tenants",
        )
    )

    # Assignment developer/project tenant alignment
    assignment_mismatches = session.execute(
        select(func.count())
        .select_from(m.Assignment)
        .join(m.Developer, m.Developer.id == m.Assignment.developer_id)
        .join(m.Project, m.Project.id == m.Assignment.project_id)
        .where(m.Developer.tenant_id != m.Project.tenant_id)
    ).scalar_one()
    checks.append(
        _check_result(
            "Assignment references align tenants",
            assignment_mismatches == 0,
            None
            if assignment_mismatches == 0
            else f"{assignment_mismatches} assignment(s) link developers and projects from different tenants",
        )
    )

    # Developer skill tenant alignment when tied to a project context
    skill_mismatches = session.execute(
        select(func.count())
        .select_from(m.DeveloperSkill)
        .join(m.Developer, m.Developer.id == m.DeveloperSkill.developer_id)
        .join(m.Project, m.Project.id == m.DeveloperSkill.project_id)
        .where(m.Project.tenant_id != m.Developer.tenant_id)
    ).scalar_one()
    checks.append(
        _check_result(
            "Developer skill project context is tenant aligned",
            skill_mismatches == 0,
            None
            if skill_mismatches == 0
            else f"{skill_mismatches} developer skill rows reference cross-tenant projects",
        )
    )

    # Event tenant alignment: both project and developer dimensions must agree
    event_project_mismatches = session.execute(
        select(func.count())
        .select_from(m.Event)
        .join(m.Project, m.Project.id == m.Event.project_id)
        .where(m.Event.tenant_id != m.Project.tenant_id)
    ).scalar_one()
    checks.append(
        _check_result(
            "Event project tenant alignment",
            event_project_mismatches == 0,
            None
            if event_project_mismatches == 0
            else f"{event_project_mismatches} event(s) reference projects in other tenants",
        )
    )

    event_developer_mismatches = session.execute(
        select(func.count())
        .select_from(m.Event)
        .join(m.Developer, m.Developer.id == m.Event.developer_id)
        .where(m.Event.tenant_id != m.Developer.tenant_id)
    ).scalar_one()
    checks.append(
        _check_result(
            "Event developer tenant alignment",
            event_developer_mismatches == 0,
            None
            if event_developer_mismatches == 0
            else f"{event_developer_mismatches} event(s) reference developers in other tenants",
        )
    )

    return checks


def generate_report(property_result: dict[str, Any] | None = None) -> dict[str, Any]:
    """Inspect the database and return an isolation report payload."""

    with SessionLocal() as session:
        # Pull tenant roster first (deterministic ordering)
        tenants = [
            {"id": tenant.id, "name": tenant.name}
            for tenant in session.execute(select(m.Tenant).order_by(m.Tenant.id)).scalars()
        ]

        table_counts: dict[str, dict[str, int]] = {}
        checks: list[dict[str, Any]] = []

        for model in _TENANT_AWARE_MODELS:
            counts, null_count = _table_counts(session, model)
            table_counts[model.__tablename__] = counts
            checks.append(
                _check_result(
                    f"{model.__tablename__} rows include tenant_id",
                    null_count == 0,
                    None if null_count == 0 else f"{null_count} row(s) missing tenant attribution",
                )
            )

        checks.extend(_run_alignment_checks(session))

        total_checks = len(checks)
        failed_checks = sum(1 for c in checks if c["status"] != "pass")

        report = {
            "generated_at": _iso_timestamp(),
            "isolation_report_dir": settings.isolation_report_dir,
            "tenants": tenants,
            "table_counts": table_counts,
            "checks": checks,
            "summary": {
                "total_checks": total_checks,
                "failed_checks": failed_checks,
            },
        }
        if property_result is not None:
            report["property_tests"] = property_result
        return report


def _render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Isolation Proof Report")
    lines.append("")
    lines.append(f"- Generated at: {report['generated_at']}")
    lines.append(f"- Output directory: `{report['isolation_report_dir']}`")
    lines.append(f"- Total checks: {report['summary']['total_checks']}")
    lines.append(f"- Failed checks: {report['summary']['failed_checks']}")
    lines.append("")

    if property_tests := report.get("property_tests"):
        lines.append("## Property test suite")
        lines.append(f"- Status: {property_tests.get('status', 'unknown')}")
        lines.append(f"- Exit code: {property_tests.get('exit_code', 'n/a')}")
        lines.append("")

    if report["tenants"]:
        lines.append("## Tenants")
        lines.append("| Tenant ID | Name |")
        lines.append("| --- | --- |")
        for tenant in report["tenants"]:
            lines.append(f"| {tenant['id']} | {tenant['name']} |")
        lines.append("")

    lines.append("## Checks")
    for check in report["checks"]:
        status = "✅" if check["status"] == "pass" else "❌"
        detail = f" — {check['details']}" if check.get("details") else ""
        lines.append(f"- {status} **{check['name']}**{detail}")
    lines.append("")

    lines.append("## Table row counts")
    for table_name, counts in sorted(report["table_counts"].items()):
        lines.append(f"### {table_name}")
        lines.append("| Tenant | Rows |")
        lines.append("| --- | ---: |")
        if counts:
            for tenant, count in sorted(counts.items()):
                label = tenant.replace("__null__", "(missing)")
                lines.append(f"| {label} | {count} |")
        else:
            lines.append("| (none) | 0 |")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _render_html(report: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape(str(value))

    lines = [
        "<html>",
        "  <head>",
        "    <meta charset='utf-8' />",
        "    <title>Isolation Proof Report</title>",
        "    <style>body{font-family:Arial,Helvetica,sans-serif;margin:2rem;}table{border-collapse:collapse;}th,td{border:1px solid #ddd;padding:0.5rem;}th{text-align:left;background:#f5f5f5;} .pass{color:#2a7;} .fail{color:#c33;}</style>",
        "  </head>",
        "  <body>",
        "    <h1>Isolation Proof Report</h1>",
        f"    <p><strong>Generated at:</strong> {esc(report['generated_at'])}</p>",
        f"    <p><strong>Output directory:</strong> {esc(report['isolation_report_dir'])}</p>",
        f"    <p><strong>Total checks:</strong> {esc(report['summary']['total_checks'])} &nbsp; | &nbsp; <strong>Failed:</strong> {esc(report['summary']['failed_checks'])}</p>",
    ]

    if property_tests := report.get("property_tests"):
        lines.append("    <section>")
        lines.append("      <h2>Property test suite</h2>")
        lines.append(
            f"      <p>Status: <strong>{esc(property_tests.get('status', 'unknown'))}</strong> (exit code {esc(property_tests.get('exit_code', 'n/a'))})</p>"
        )
        lines.append("    </section>")

    if report["tenants"]:
        lines.append("    <section>")
        lines.append("      <h2>Tenants</h2>")
        lines.append("      <table>")
        lines.append("        <tr><th>Tenant ID</th><th>Name</th></tr>")
        for tenant in report["tenants"]:
            lines.append(
                f"        <tr><td>{esc(tenant['id'])}</td><td>{esc(tenant['name'])}</td></tr>"
            )
        lines.append("      </table>")
        lines.append("    </section>")

    lines.append("    <section>")
    lines.append("      <h2>Checks</h2>")
    lines.append("      <ul>")
    for check in report["checks"]:
        css = "pass" if check["status"] == "pass" else "fail"
        detail = f" — {esc(check['details'])}" if check.get("details") else ""
        lines.append(
            f"        <li class='{css}'><strong>{esc(check['name'])}</strong>{detail}</li>"
        )
    lines.append("      </ul>")
    lines.append("    </section>")

    lines.append("    <section>")
    lines.append("      <h2>Table row counts</h2>")
    for table_name, counts in sorted(report["table_counts"].items()):
        lines.append(f"      <h3>{esc(table_name)}</h3>")
        lines.append("      <table>")
        lines.append("        <tr><th>Tenant</th><th>Rows</th></tr>")
        if counts:
            for tenant, count in sorted(counts.items()):
                label = tenant.replace("__null__", "(missing)")
                lines.append(f"        <tr><td>{esc(label)}</td><td>{esc(count)}</td></tr>")
        else:
            lines.append("        <tr><td>(none)</td><td>0</td></tr>")
        lines.append("      </table>")
    lines.append("    </section>")

    lines.append("  </body>")
    lines.append("</html>")
    return "\n".join(lines)


def write_report(report: dict[str, Any], output_dir: Path | None = None) -> list[Path]:
    base_dir = Path(output_dir or settings.isolation_report_dir)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = base_dir / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "isolation_report.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    md_path = out_dir / "isolation_report.md"
    md_path.write_text(_render_markdown(report), encoding="utf-8")

    html_path = out_dir / "isolation_report.html"
    html_path.write_text(_render_html(report), encoding="utf-8")

    return [json_path, md_path, html_path]


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate tenant isolation proof artifacts")
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path(settings.isolation_report_dir),
        help="Directory to write the isolation proof artifacts",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip running property-based isolation tests (useful for CI smoke or unit tests)",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    skip_tests = args.skip_tests or bool(os.environ.get("ISOLATION_PROOF_SKIP_TESTS"))
    property_result = run_property_suite(skip=skip_tests)
    report = generate_report(property_result if property_result["status"] != "skipped" else None)
    files = write_report(report, args.output_dir)
    for path in files:
        print(f"Wrote {path}")
    if property_result["exit_code"] != 0:
        print("ERROR: property-based tests failed", flush=True)
        return property_result["exit_code"]
    if report["summary"]["failed_checks"]:
        print("WARNING: one or more isolation checks failed", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
