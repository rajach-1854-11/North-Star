from __future__ import annotations

from pathlib import Path

from app.scripts import isolation_proof


def test_isolation_report_generation(tmp_path: Path, client) -> None:
    report = isolation_proof.generate_report()

    assert report["summary"]["failed_checks"] == 0
    assert report["summary"]["total_checks"] > 0
    assert report["table_counts"]

    written = isolation_proof.write_report(report, tmp_path)
    assert len(written) == 3

    out_dir = written[0].parent
    assert out_dir.parent == tmp_path

    paths = {path.name: path for path in written}
    assert "isolation_report.json" in paths
    assert "isolation_report.md" in paths
    assert "isolation_report.html" in paths

    assert paths["isolation_report.json"].read_text(encoding="utf-8")
    assert paths["isolation_report.md"].read_text(encoding="utf-8")
    html_content = paths["isolation_report.html"].read_text(encoding="utf-8")
    assert "<html>" in html_content


def test_run_property_suite_skip() -> None:
    result = isolation_proof.run_property_suite(skip=True)
    assert result["status"] == "skipped"
    assert result["exit_code"] == 0
