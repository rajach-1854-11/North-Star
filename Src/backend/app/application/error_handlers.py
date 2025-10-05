"""Centralised error rendering helpers for agentic flows."""

from __future__ import annotations

from typing import Any, Dict, Mapping


def render_tool_blocked(*, tool: str, suggestions: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    """Return a structured error payload for consent-blocked tools."""

    detail: Dict[str, Any] = {
        "code": "TOOL_BLOCKED",
        "message": f"Consent is required before '{tool}' can be executed.",
        "details": {
            "tool": tool,
        },
    }
    if suggestions:
        filtered = {k: v for k, v in suggestions.items() if v}
        if filtered:
            detail["details"]["suggestions"] = filtered
    return detail
