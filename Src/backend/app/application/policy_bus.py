"""RBAC policy enforcement for agentic tool usage."""

from __future__ import annotations

from typing import Dict, List

from fastapi import HTTPException

ToolName = str
RoleName = str

TOOL_POLICY: Dict[ToolName, Dict[str, List[RoleName]]] = {
    "jira_epic": {"roles": ["PO"]},
    "confluence_page": {"roles": ["PO"]},
    "rag_search": {"roles": ["PO", "Dev"]},
}


def enforce(tool: ToolName, role: RoleName) -> None:
    """Ensure *role* has access to the requested *tool* or raise ``HTTPException``."""

    allowed = TOOL_POLICY.get(tool, {}).get("roles", [])
    if role not in allowed:
        raise HTTPException(status_code=403, detail=f"Access denied for tool={tool}")
