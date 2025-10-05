"""RBAC policy enforcement for agentic tool usage."""

from __future__ import annotations

from typing import Mapping, Set

from fastapi import HTTPException

ALLOWED_TOOLS: Mapping[str, Set[str]] = {
    "Admin": {
        "rag_search",
        "onboarding_generate",
        "jira_epic",
        "confluence_page",
        "skills_profile",
        "staffing_recommend",
        "publish_artifact",
    },
    "PO": {
        "rag_search",
        "onboarding_generate",
        "jira_epic",
        "confluence_page",
        "skills_profile",
        "staffing_recommend",
        "publish_artifact",
    },
    "BA": {
        "rag_search",
        "onboarding_generate",
        "jira_epic",
        "confluence_page",
        "skills_profile",
        "staffing_recommend",
        "publish_artifact",
    },
    "Dev": {
        "rag_search",
        "skills_profile",
    },
}


def enforce(tool: str, role: str) -> None:
    """Ensure *role* can execute *tool*; raise ``HTTPException`` otherwise."""

    allowed = ALLOWED_TOOLS.get(role, set())
    if tool not in allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "RBAC_DENIED",
                "message": f"{role} cannot run {tool}",
            },
        )
