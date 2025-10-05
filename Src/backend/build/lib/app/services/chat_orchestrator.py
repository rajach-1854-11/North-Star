"""Unified chat orchestration for planner, tools, and response shaping."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from fastapi.encoders import jsonable_encoder
from loguru import logger

from app.agentic import tools as agent_tools
from app.domain.errors import ExternalServiceError
from app.domain.schemas import ChatAction, ChatMetadata, ChatQueryReq, ChatResp
from app.ports.planner import create_plan, execute_plan, list_tools
from app.ports import responder
from app.services import retrieval_diversity as diversity

_DEFAULT_TOOLS = ["rag_search", "jira_epic", "confluence_page"]


@dataclass
class RetrievalBatch:
    """Normalised view of a retrieval tool execution."""

    key: str
    index: int
    query: str
    targets: List[str]
    results: List[Dict[str, Any]]
    deduped: List[Dict[str, Any]]
    filtered: List[Dict[str, Any]]
    stats: Dict[str, Any]
    passes_gate: bool
    fallback_message: Optional[str]
    evidence: Optional[str]


class ChatOrchestrator:
    """Coordinate planner outputs, execute tools, and craft chat responses."""

    _tools_registered: bool = False

    def __init__(self, *, user_claims: Dict[str, Any]):
        self.user_claims = user_claims or {}
        self._ensure_tools_registered()

    @classmethod
    def _ensure_tools_registered(cls) -> None:
        if cls._tools_registered:
            return
        if hasattr(agent_tools, "register_all_tools"):
            try:
                agent_tools.register_all_tools()
            except Exception:  # pragma: no cover - defensive, should not trigger in tests
                logger.exception("Tool registration failed during chat orchestrator bootstrap")
            else:
                cls._tools_registered = True

    def handle(self, req: ChatQueryReq) -> ChatResp:
        """Entry point invoked by the route handler."""

        plan = self._build_plan(req)
        execution = execute_plan(copy.deepcopy(plan), self.user_claims)
        artifacts = execution.get("artifacts", {}) or {}
        batches = self._extract_retrieval_batches(req, plan, artifacts)

        reply_md = self._build_reply(req, plan, execution, batches)
        actions = self._build_actions(plan, batches)
        sources = self._collect_sources(batches)
        fallback_message = next((b.fallback_message for b in batches if b.fallback_message), None)

        payload_plan = jsonable_encoder(plan)
        payload_artifacts = jsonable_encoder(artifacts)
        payload_output = jsonable_encoder(execution.get("output", {}) or {})
        two_week_plan = payload_output.get("two_week_plan") if isinstance(payload_output, dict) else None

        return ChatResp(
            reply_md=reply_md,
            plan=payload_plan,
            artifacts=payload_artifacts,
            output=payload_output,
            actions=actions,
            sources=sources,
            two_week_plan=two_week_plan or [],
            pending_fields=None,
            message=fallback_message,
        )

    # ------------------------------------------------------------------
    # Planning helpers

    def _build_plan(self, req: ChatQueryReq) -> Dict[str, Any]:
        """Compose the planner request and guarantee minimum retrieval coverage."""

        allowed_tools = req.allowed_tools or list_tools() or list(_DEFAULT_TOOLS)
        prompt = self._compose_task_prompt(req)

        plan = create_plan(prompt, allowed_tools=allowed_tools)
        plan.setdefault("steps", [])
        plan.setdefault("output", {})
        plan.setdefault("_meta", {})

        meta = plan["_meta"]
        meta.update(
            {
                "requested_autonomy": req.autonomy,
                "history_turns": len(req.history or []),
            }
        )

        targets, include_rosetta, known_projects = self._derive_retrieval_targets(req)
        self._ensure_rag_steps(req, plan, targets, include_rosetta, known_projects)
        return plan

    def _compose_task_prompt(self, req: ChatQueryReq) -> str:
        """Flatten chat history and metadata into a concise planner prompt."""

        lines: List[str] = []
        metadata = req.metadata or ChatMetadata()
        if metadata.intent:
            lines.append(f"Intent: {metadata.intent.strip()}")
        if metadata.additional:
            hints = ", ".join(f"{k}={v}" for k, v in metadata.additional.items())
            lines.append(f"Context: {hints}")
        for msg in (req.history or [])[-5:]:  # last 5 turns for brevity
            role = msg.role.capitalize()
            content = msg.content.strip()
            if content:
                lines.append(f"{role}: {content}")
        lines.append(f"User: {req.prompt.strip()}")
        return "\n".join(lines)

    def _derive_retrieval_targets(
        self, req: ChatQueryReq
    ) -> tuple[List[str], bool, List[str]]:
        metadata = req.metadata or ChatMetadata()
        accessible = [
            str(project).strip()
            for project in self.user_claims.get("accessible_projects", [])
            if isinstance(project, str) and str(project).strip()
        ]
        default_targets = list(dict.fromkeys(metadata.targets or accessible))  # preserve order
        if not default_targets:
            default_targets = accessible or []
        lowered = {target.lower() for target in default_targets}
        if "global" not in lowered:
            default_targets.append("global")
        include_rosetta = bool(metadata.include_rosetta)
        known_projects = metadata.known_projects or accessible or default_targets
        return default_targets, include_rosetta, list(dict.fromkeys(known_projects or []))

    def _ensure_rag_steps(
        self,
        req: ChatQueryReq,
        plan: Dict[str, Any],
        targets: Sequence[str],
        include_rosetta: bool,
        known_projects: Sequence[str],
    ) -> None:
        steps = plan.setdefault("steps", [])
        rag_present = False
        defaults = {
            "query": req.prompt,
            "targets": list(targets),
            "k": 12,
            "strategy": "qdrant",
            "include_rosetta": include_rosetta,
            "known_projects": list(known_projects),
        }
        for step in steps:
            if step.get("tool") != "rag_search":
                continue
            rag_present = True
            args = step.setdefault("args", {}) or {}
            for key, value in defaults.items():
                args.setdefault(key, copy.deepcopy(value))
            step["args"] = args
        if not rag_present:
            steps.insert(0, {"tool": "rag_search", "args": copy.deepcopy(defaults)})

    # ------------------------------------------------------------------
    # Retrieval analysis helpers

    def _extract_retrieval_batches(
        self,
        req: ChatQueryReq,
        plan: Dict[str, Any],
        artifacts: Dict[str, Any],
    ) -> List[RetrievalBatch]:
        batches: List[RetrievalBatch] = []
        steps = plan.get("steps", [])
        for idx, step in enumerate(steps, start=1):
            if step.get("tool") != "rag_search":
                continue
            key = f"step_{idx}:rag_search"
            payload = artifacts.get(key)
            if not isinstance(payload, dict):
                continue
            raw_results = payload.get("results") or []
            results = [self._normalise_hit(hit) for hit in raw_results]
            deduped = diversity.dedupe_by_source(results)
            filtered = diversity.lexical_filter(deduped, k=6)
            passes_gate, stats = diversity.diversity_gate(results)
            batches.append(
                RetrievalBatch(
                    key=key,
                    index=idx,
                    query=str(step.get("args", {}).get("query") or req.prompt),
                    targets=list(step.get("args", {}).get("targets") or []),
                    results=results,
                    deduped=deduped,
                    filtered=filtered,
                    stats=stats,
                    passes_gate=passes_gate,
                    fallback_message=payload.get("fallback_message"),
                    evidence=payload.get("evidence"),
                )
            )
        return batches

    @staticmethod
    def _normalise_hit(hit: Any) -> Dict[str, Any]:
        if hasattr(hit, "model_dump"):
            data = hit.model_dump()
        elif hasattr(hit, "dict"):
            data = hit.dict()  # type: ignore[attr-defined]
        else:
            data = dict(hit) if isinstance(hit, dict) else {}
        return {
            "text": str(data.get("text") or ""),
            "score": float(data.get("score") or 0.0),
            "source": str(data.get("source") or ""),
            "chunk_id": str(data.get("chunk_id") or ""),
            "embedding": data.get("embedding"),
        }

    # ------------------------------------------------------------------
    # LLM answer construction helpers

    def _render_llm_answer(
        self,
        req: ChatQueryReq,
        plan: Dict[str, Any],
        execution: Dict[str, Any],
        batches: Sequence[RetrievalBatch],
    ) -> str:
        context_entries = self._top_context_entries(batches, limit=6)
        if not context_entries:
            return ""

        messages = self._build_llm_messages(req, plan, execution, context_entries)
        try:
            content = responder.generate_chat_response(messages, temperature=0.3, max_tokens=800)
        except ExternalServiceError:
            return ""
        except Exception:
            logger.exception("LLM response generation failed")
            return ""

        content = str(content or "").strip()
        if not content:
            return ""
        return f"**Answer**\n{content}"

    def _build_llm_messages(
        self,
        req: ChatQueryReq,
        plan: Dict[str, Any],
        execution: Dict[str, Any],
        context_entries: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        instruction = self._extract_plan_instruction(plan, execution)
        history_lines = self._compose_history_lines(req)
        context_block = self._format_context_block(context_entries)

        user_sections: List[str] = []
        if instruction:
            user_sections.append(f"Planner guidance:\n{instruction}")
        if history_lines:
            user_sections.append("Recent conversation:\n" + "\n".join(history_lines))
        user_sections.append(f"User question:\n{req.prompt.strip()}")
        user_sections.append("Context passages:\n" + context_block)
        user_sections.append(
            "Response requirements:\n"
            "- Base the answer strictly on the context passages.\n"
            "- If the information is missing, state that limitation clearly.\n"
            "- Provide an actionable, easy-to-scan narrative."
        )

        user_message = "\n\n".join(section for section in user_sections if section)

        system_message = (
            "You are North Star's product expert. Craft concise, factual answers for the user. "
            "Cite project names when relevant, and never fabricate details beyond the provided context."
        )

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]

    def _compose_history_lines(self, req: ChatQueryReq) -> List[str]:
        lines: List[str] = []
        for turn in (req.history or [])[-4:]:
            role = turn.role.capitalize()
            content = (turn.content or "").strip()
            if content:
                lines.append(f"{role}: {content}")
        return lines

    def _format_context_block(self, context_entries: Sequence[Dict[str, Any]]) -> str:
        formatted: List[str] = []
        for idx, entry in enumerate(context_entries, start=1):
            source = str(entry.get("source") or "Unknown")
            text = self._prepare_context_text(str(entry.get("text") or ""), limit=720)
            score = entry.get("score")
            score_part = f" (score {score:.2f})" if isinstance(score, (int, float)) else ""
            formatted.append(f"{idx}. [{source}]{score_part} {text}")
        return "\n".join(formatted)

    def _top_context_entries(
        self,
        batches: Sequence[RetrievalBatch],
        *,
        limit: int = 6,
    ) -> List[Dict[str, Any]]:
        hits: List[Dict[str, Any]] = []
        for batch in batches:
            hits.extend(batch.results or [])
        if not hits:
            return []

        def score_of(hit: Dict[str, Any]) -> float:
            value = hit.get("score")
            if isinstance(value, (int, float)):
                return float(value)
            return 0.0

        sorted_hits = sorted(hits, key=score_of, reverse=True)
        entries: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for hit in sorted_hits:
            chunk_id = str(hit.get("chunk_id") or "")
            key = chunk_id or f"{hit.get('source')}::{self._clip_sentence(hit.get('text') or '', 60)}"
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                {
                    "source": hit.get("source"),
                    "text": hit.get("text"),
                    "score": hit.get("score"),
                    "chunk_id": hit.get("chunk_id"),
                }
            )
            if len(entries) >= limit:
                break
        return entries

    def _extract_plan_instruction(self, plan: Dict[str, Any], execution: Dict[str, Any]) -> str:
        candidates: List[str] = []
        for container in (execution.get("output", {}), plan.get("output", {})):
            note = container.get("notes") if isinstance(container, dict) else None
            if isinstance(note, str):
                trimmed = note.strip()
                if trimmed and trimmed.lower() not in {"llm_plan", "fallback_heuristic_plan"}:
                    candidates.append(trimmed)

        meta_prompt = plan.get("_meta", {}).get("task_prompt") if isinstance(plan, dict) else None
        if isinstance(meta_prompt, str) and meta_prompt.strip():
            candidates.append(meta_prompt.strip())

        if candidates:
            ordered_unique = list(dict.fromkeys(candidates))
            return "\n".join(ordered_unique[:2])

        return "Use the provided context passages to answer the question."

    # ------------------------------------------------------------------
    # Response construction

    def _build_reply(
        self,
        req: ChatQueryReq,
        plan: Dict[str, Any],
        execution: Dict[str, Any],
        batches: List[RetrievalBatch],
    ) -> str:
        output = execution.get("output", {}) or {}
        summary = str(output.get("summary") or "").strip()
        if not summary:
            summary = self._infer_summary(batches) or "I compiled the available PX material below."

        sections: List[str] = []
        answer = self._render_llm_answer(req, plan, execution, batches)
        if answer:
            sections.append(answer.strip())
        elif summary:
            sections.append(f"**Quick take**\n{summary}")

        warning = self._render_diversity_warning(batches)
        if warning:
            sections.append(warning)

        key_snippets = self._build_key_snippets(batches)
        if key_snippets:
            sections.append("**Key snippets**\n" + "\n".join(key_snippets))

        next_steps = self._render_next_steps(output, batches)
        if next_steps:
            sections.append("**Suggested next steps**\n" + "\n".join(f"- {step}" for step in next_steps))

        diagnostics = self._render_diagnostics(batches)
        if diagnostics:
            sections.append(diagnostics)

        fallback_notes = [b.fallback_message for b in batches if b.fallback_message]
        for note in fallback_notes:
            sections.append(f"_ℹ️ {note}_")

        return "\n\n".join(part for part in sections if part).strip()

    def _render_diversity_warning(self, batches: Sequence[RetrievalBatch]) -> str:
        if not batches:
            return ""
        first = batches[0]
        if first.passes_gate:
            return ""
        stats = first.stats
        unique_sources = stats.get("unique_sources", 0)
        top_source = stats.get("top_source")
        total_hits = stats.get("total_hits", 0)
        share = stats.get("top_source_share", 0.0)
        share_pct = f"{share * 100:.0f}%" if isinstance(share, (int, float)) else "--"

        header = "⚠️ Retrieval came back from a single dominant source; I'll summarise what we have while flagging the gap."
        details = (
            f"{unique_sources} unique source(s), {total_hits} snippet(s) total. "
            + (f"`{top_source}` accounts for {share_pct}." if top_source else "")
        )
        recs = [
            "Break up the monolithic spec into smaller docs (exec summary, architecture, API, roadmap).",
            "Re-run embeddings so the retriever picks up the new chunks.",
            "Verify the remote retriever connectivity; fall back to local mode if remote is unavailable.",
        ]
        return "\n".join([header, details, "Next to unlock richer answers:"] + [f"- {line}" for line in recs])

    def _build_key_snippets(self, batches: Sequence[RetrievalBatch]) -> List[str]:
        bullets: List[str] = []
        for batch in batches:
            for hit in batch.filtered:
                snippet = self._clip_sentence(hit.get("text") or "", 220)
                source = hit.get("source") or "Unknown"
                score = hit.get("score")
                score_part = f" _(score {score:.2f})_" if isinstance(score, (int, float)) else ""
                bullets.append(f"- **{source}** — {snippet}{score_part}")
        return bullets[:6]

    def _render_next_steps(
        self, output: Dict[str, Any], batches: Sequence[RetrievalBatch]
    ) -> List[str]:
        steps: List[str] = []
        for gap in output.get("gaps", []) or []:
            if isinstance(gap, dict):
                topic = str(gap.get("topic") or gap.get("label") or "").strip()
                if topic:
                    steps.append(f"Investigate: {topic}")
        if not steps and not batches:
            steps.append("Add PX docs or run ingestion to seed the knowledge base.")
        return steps

    def _render_diagnostics(self, batches: Sequence[RetrievalBatch]) -> str:
        if not batches:
            return ""
        total_hits = sum(batch.stats.get("total_hits", 0) for batch in batches)
        unique_sources = len({hit.get("source") for batch in batches for hit in batch.results if hit.get("source")})
        unique_chunks = len({hit.get("chunk_id") for batch in batches for hit in batch.results if hit.get("chunk_id")})
        top_share = 0.0
        for batch in batches:
            share = batch.stats.get("top_source_share")
            if isinstance(share, (int, float)):
                top_share = max(top_share, share)
        return (
            f"_(snippets={total_hits}, unique_chunks={unique_chunks}, "
            f"unique_sources={unique_sources}, top_source_share={top_share:.2f})_"
        )

    def _infer_summary(self, batches: Sequence[RetrievalBatch]) -> str:
        sentences: List[str] = []

        for batch in batches:
            for hit in batch.filtered:
                sentences.extend(self._extract_sentences(hit.get("text") or ""))
        if not sentences:
            for batch in batches:
                for hit in batch.results:
                    sentences.extend(self._extract_sentences(hit.get("text") or ""))

        curated: List[str] = []
        seen: set[str] = set()
        for raw in sentences:
            sentence = raw.strip()
            if len(sentence) < 25:
                continue
            normalised = sentence.lower()
            if normalised in seen:
                continue
            seen.add(normalised)
            curated.append(sentence)
            if len(curated) >= 3:
                break

        if not curated:
            return ""
        if len(curated) == 1:
            return curated[0]
        return "\n".join(f"- {sentence}" for sentence in curated)

    # ------------------------------------------------------------------
    # Actions & sources helpers

    def _build_actions(self, plan: Dict[str, Any], batches: Sequence[RetrievalBatch]) -> List[ChatAction]:
        actions: List[ChatAction] = []
        for batch in batches:
            actions.append(
                ChatAction(
                    type="retrieval",
                    payload={
                        "step": batch.index,
                        "query": batch.query,
                        "targets": batch.targets,
                        "stats": batch.stats,
                        "diversity_pass": batch.passes_gate,
                        "top_hits": batch.filtered,
                    },
                )
            )
        return actions

    def _collect_sources(self, batches: Sequence[RetrievalBatch]) -> List[Dict[str, Any]]:
        sources: List[Dict[str, Any]] = []
        for batch in batches:
            for hit in batch.filtered:
                sources.append(
                    {
                        "text": self._clip_sentence(hit.get("text") or "", 320),
                        "score": hit.get("score"),
                        "source": hit.get("source"),
                        "chunk_id": hit.get("chunk_id"),
                    }
                )
        return sources

    # ------------------------------------------------------------------
    # Text helpers

    @staticmethod
    def _first_sentence(text: str) -> str:
        stripped = " ".join(text.split())
        for delimiter in [". ", "\n", "? ", "! "]:
            if delimiter in stripped:
                return stripped.split(delimiter, 1)[0].strip()
        return stripped[:240].strip()

    @staticmethod
    def _extract_sentences(text: str) -> List[str]:
        if not text:
            return []
        normalised = text.replace("\r", "\n")
        fragments = [frag.strip(" -*•") for frag in normalised.split("\n")]
        fragments = [frag for frag in fragments if frag]
        sentences: List[str] = []
        for fragment in fragments:
            split_parts = re.split(r"(?<=[.!?])\s+", fragment)
            for part in split_parts:
                cleaned = part.strip()
                if cleaned:
                    sentences.append(cleaned)
        if not sentences and fragments:
            sentences.extend(fragments)
        return sentences

    @staticmethod
    def _prepare_context_text(text: str, limit: int) -> str:
        stripped = " ".join(text.split())
        if len(stripped) <= limit:
            return stripped
        return stripped[: limit - 3].rstrip() + "..."

    @staticmethod
    def _clip_sentence(text: str, limit: int) -> str:
        stripped = " ".join(text.split())
        if len(stripped) <= limit:
            return stripped
        return stripped[: limit - 3].rstrip() + "..."


__all__ = ["ChatOrchestrator"]
