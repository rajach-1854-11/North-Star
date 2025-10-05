# FILE: backend/app/utils/evidence_builder.py
from __future__ import annotations
from typing import List, Dict, Set
from app.domain.schemas import RetrieveHit

def build_evidence_snippets(
    hits: List[RetrieveHit],
    max_chars: int = 4000,
    max_per_source: int = 3,
    max_snippet_len: int = 600,
) -> str:
    """
    Build a compact, LLM-friendly evidence string:
      - de-duplicates by chunk_id
      - caps number of snippets per source
      - trims whitespace and long snippets
      - respects an overall character budget (max_chars)
    """
    buf: List[str] = []
    used = 0
    seen_ids: Set[str] = set()
    per_source: Dict[str, int] = {}

    i = 1
    for h in hits:
        cid = h.chunk_id or ""
        if cid in seen_ids:
            continue
        seen_ids.add(cid)

        src = str(h.source or "")
        taken = per_source.get(src, 0)
        if taken >= max_per_source:
            continue

        snippet = " ".join((h.text or "").split())
        if len(snippet) > max_snippet_len:
            snippet = snippet[: max_snippet_len - 3] + "..."

        block = f"[{i}] ({src} • {cid[:8]}) score={h.score:.3f}\n{snippet}\n"
        if used + len(block) > max_chars:
            break

        buf.append(block)
        used += len(block)
        per_source[src] = taken + 1
        i += 1

    return "\n".join(buf)

def to_confluence_html(evidence: str) -> str:
    """Convert raw evidence text into basic Confluence storage HTML."""

    esc = (
        evidence.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    lines = [ln.strip() for ln in esc.split("\n") if ln.strip()]
    paras = "".join(f"<p>{line}</p>" for line in lines)
    return f"<h3>Evidence</h3>{paras}"

def to_jira_description(evidence: str) -> dict[str, object]:
    """Convert evidence text into Jira's Atlassian Document Format."""

    blocks = []
    for line in evidence.split("\n"):
        line = line.strip()
        if not line:
            continue
        blocks.append({"type": "paragraph", "content": [{"type": "text", "text": line}]})
    return {"type": "doc", "version": 1, "content": blocks}
