from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import ABMapEdge, TenantMapperWeights
from app.utils.hashing import hash_text


@dataclass
class MapperOut:
    skills_gap: List[Dict[str, Any]]
    curated_docs: List[Dict[str, Any]]
    narrative_md: str


class ABMapper:
    """
    Contrastive A→B mapper (per-tenant).
    - Learns term deltas from (A,B) concept pairs via simple additive delta.
    - Infers skills/doc deltas for a new target set weighted by hit.score and learnt weights.
    - Strictly tenant-scoped; honors allowed_targets to avoid cross-project leakage.
    """

    _STOP = {
        "the",
        "and",
        "a",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "is",
        "as",
        "by",
        "at",
        "or",
        "an",
        "be",
        "are",
        "from",
        "that",
        "this",
        "it",
        "we",
        "you",
        "they",
        "our",
    }

    _TOKEN_RE = re.compile(r"[A-Za-z0-9_/\.\-]{2,}")

    def __init__(
        self,
        tenant_id: str,
        *,
        session: Optional[Session] = None,
        session_factory: Optional[Callable[[], Session]] = None,
    ) -> None:
        self.tenant_id = tenant_id
        self._session = session
        self._session_factory = session_factory

    def _get_session(self) -> Tuple[Session, bool]:
        if self._session is not None:
            return self._session, False
        if self._session_factory is None:
            raise RuntimeError("ABMapper requires either a session or a session_factory")
        return self._session_factory(), True

    @classmethod
    def _concept_tokens(cls, text: str) -> List[str]:
        toks = [t.lower() for t in cls._TOKEN_RE.findall(text or "")]
        return [t for t in toks if t not in cls._STOP and len(t) >= 3]

    def fit(
        self,
        pairs: Sequence[tuple[Dict[str, Any], Dict[str, Any]]],
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        session, close_session = self._get_session()
        try:
            aggregate: Dict[str, float] = {}
            updates = 0

            for left, right in pairs:
                left_terms = set(map(str.lower, left.get("concepts", [])))
                right_terms = set(map(str.lower, right.get("concepts", [])))
                if not left_terms and not right_terms:
                    continue
                updates += 1
                universe = left_terms | right_terms
                for term in universe:
                    delta = float(term in right_terms) - float(term in left_terms)
                    aggregate[term] = aggregate.get(term, 0.0) + delta

            payload = {
                "weights": aggregate,
                "meta": meta or {},
                "version": 1,
            }

            stmt = select(TenantMapperWeights).where(TenantMapperWeights.tenant_id == self.tenant_id)
            existing = session.execute(stmt).scalars().first()
            if existing:
                existing.weights = payload
            else:
                session.add(TenantMapperWeights(tenant_id=self.tenant_id, weights=payload))
            session.commit()
            logger.info(
                "ABMapper.fit stored weights",
                tenant=self.tenant_id,
                terms=len(aggregate),
                updates=updates,
            )
        finally:
            if close_session:
                session.close()

    def infer(
        self,
        known_projects: Iterable[str],
        top_hits: Sequence[Any],
        *,
        allowed_targets: Optional[Iterable[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        top_k_skills: int = 10,
        top_k_docs: int = 8,
    ) -> MapperOut:
        session, close_session = self._get_session()
        allowed = {t for t in (allowed_targets or []) if t}
        known = [p for p in known_projects if p]

        try:
            stmt = select(TenantMapperWeights.weights).where(TenantMapperWeights.tenant_id == self.tenant_id)
            row = session.execute(stmt).scalars().first() or {"weights": {}}
            learnt_weights: Dict[str, float] = row.get("weights", {})
            learnt = learnt_weights.get("weights", learnt_weights)

            agg: Dict[str, float] = {}
            curated: List[Dict[str, Any]] = []

            def norm(score: float) -> float:
                if math.isnan(score):
                    return 0.0
                return max(0.0, min(1.0, score))

            for hit in top_hits:
                text = getattr(hit, "text", "") or ""
                project = str(getattr(hit, "source", "") or "")
                if allowed and project and project not in allowed:
                    continue

                chunk_id = getattr(hit, "chunk_id", "") or hash_text(text, namespace="abmap")
                score = float(getattr(hit, "score", 0.0))
                weight_score = norm(score)

                curated.append(
                    {
                        "project": project or "unknown",
                        "chunk_id": chunk_id,
                        "reason": "retrieved",
                        "score": score,
                    }
                )

                text_low = text.lower()
                for term, weight in learnt.items():
                    t = term.lower()
                    if len(t) < 3 or t in self._STOP:
                        continue
                    if t in text_low:
                        agg[t] = agg.get(t, 0.0) + (weight * weight_score)

            skills_gap = [
                {"skill": term, "delta": delta, "confidence": min(abs(delta), 1.0)}
                for term, delta in sorted(agg.items(), key=lambda kv: abs(kv[1]), reverse=True)
            ][:top_k_skills]

            narrative_lines: List[str] = []
            narrative_lines.append("### Rosetta Narrative")
            narrative_lines.append("")
            if known:
                narrative_lines.append(f"**Known projects:** {', '.join(known)}")
            if allowed:
                narrative_lines.append(f"**Scope:** {', '.join(sorted(allowed))}")
            narrative_lines.append("")

            narrative_lines.append("#### Key Divergences")
            if skills_gap:
                for gap in skills_gap[: min(5, len(skills_gap))]:
                    narrative_lines.append(
                        f"- **{gap['skill']}**: Δ={gap['delta']:.2f} (confidence {gap['confidence']:.2f})"
                    )
            else:
                narrative_lines.append("- No significant gaps detected.")
            narrative_lines.append("")

            narrative_lines.append("#### Curated Documents")
            if curated:
                for doc in curated[:top_k_docs]:
                    narrative_lines.append(
                        f"- {doc['project']} :: chunk `{doc['chunk_id']}` (score {doc['score']:.3f})"
                    )
            else:
                narrative_lines.append("- No eligible documents within your scope.")

            narrative_md = "\n".join(narrative_lines)

            if skills_gap and curated:
                to_project = next((d["project"] for d in curated if d["project"] and d["project"] not in known), curated[0]["project"])
                from_project = known[0] if known else "unknown"
                session.add(
                    ABMapEdge(
                        tenant_id=self.tenant_id,
                        from_project=from_project,
                        to_project=to_project,
                        topic="contrastive",
                        weight=float(skills_gap[0]["delta"]),
                        evidence_ids=[doc["chunk_id"] for doc in curated[:top_k_docs]],
                    )
                )
                session.commit()

            return MapperOut(
                skills_gap=skills_gap,
                curated_docs=curated[:top_k_docs],
                narrative_md=narrative_md,
            )

        finally:
            if close_session:
                session.close()
