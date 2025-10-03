from __future__ import annotations

from typing import Any, Dict

import pytest

from app.config import settings
from app.ports import planner


@pytest.fixture(autouse=True)
def ensure_space(monkeypatch: pytest.MonkeyPatch) -> None:
    space = getattr(settings, "atlassian_space", None)
    if not space:
        monkeypatch.setattr(settings, "atlassian_space", "ENG", raising=False)


def test_placeholder_args_are_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: Dict[str, Dict[str, Any]] = {}

    def fake_epic(*, user_claims: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        captured["jira_epic"] = kwargs
        return {"args": kwargs}

    def fake_page(*, user_claims: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        captured["confluence_page"] = kwargs
        return {"args": kwargs}

    planner.register_tool("jira_epic", fake_epic)
    planner.register_tool("confluence_page", fake_page)

    plan = {
        "steps": [
            {
                "tool": "jira_epic",
                "args": {
                    "project_key": "${project}",
                    "summary": "TODO summary",
                    "description": "fill me later",
                },
            },
            {
                "tool": "confluence_page",
                "args": {
                    "space": "<space>",
                    "title": "<page>",
                    "html": "[html]",
                    "evidence": "TODO evidence",
                },
            },
        ],
        "output": {"summary": "PX onboarding readiness"},
        "_meta": {"task_prompt": "Prepare PX onboarding content"},
    }

    user_claims = {
        "role": "PO",
        "tenant_id": "tenant1",
        "accessible_projects": ["global", "PX"],
    }

    result = planner.execute_plan(plan, user_claims=user_claims)

    jira_args = captured["jira_epic"]
    assert jira_args["project_key"] == "PX"
    assert "todo" not in jira_args["summary"].lower()
    assert "fill me" not in jira_args["description"].lower()

    conf_args = captured["confluence_page"]
    assert conf_args["space"] == getattr(settings, "atlassian_space")
    assert "<" not in conf_args["title"]
    assert conf_args.get("html") in (None, "")
    assert "todo" not in conf_args["evidence"].lower()

    artifacts = result["artifacts"]
    assert "skipped" not in artifacts["step_1:jira_epic"]
    assert "skipped" not in artifacts["step_2:confluence_page"]