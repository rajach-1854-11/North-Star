from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Sequence

from loguru import logger

from app.config import settings
from app.domain.schemas import RetrieveHit
from app.ports import retriever


DEFAULT_K = 5


@dataclass(slots=True)
class MetricSnapshot:
    dataset: str
    k: int
    dreln: float
    safety_leak: float
    ttfc: float
    total_tasks: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset": self.dataset,
            "k": self.k,
            "dRel@k": round(self.dreln, 4),
            "SafetyLeak@k": round(self.safety_leak, 4),
            "TTFC": round(self.ttfc, 4),
            "total_tasks": self.total_tasks,
        }


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Eval dataset not found: {path}")
    entries: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            entries.append(json.loads(line))
    return entries


def _similarity(hit: RetrieveHit, gold_terms: Sequence[str]) -> float:
    text = hit.text.lower()
    if not gold_terms:
        return 0.0
    score = 0.0
    for term in gold_terms:
        if not term:
            continue
        if term.lower() in text:
            score += 1.0
    return score / max(len(gold_terms), 1)


def _determine_leak(hit: RetrieveHit, allowed: Sequence[str]) -> bool:
    source = (hit.source or "").strip()
    return bool(source) and source not in allowed and source != "global"


def _time_to_first_correct(hits: Sequence[RetrieveHit], gold_terms: Sequence[str]) -> float:
    for index, hit in enumerate(hits, start=1):
        for term in gold_terms:
            if term and term.lower() in hit.text.lower():
                return float(index)
    return float(len(hits) + 1)


def _evaluate_dataset(
    dataset_name: str,
    tasks: Iterable[Dict[str, Any]],
    k: int,
) -> MetricSnapshot:
    similarities: List[float] = []
    leaks: List[float] = []
    ttfc_scores: List[float] = []
    total = 0

    for entry in tasks:
        total += 1
        tenant = entry.get("tenant", settings.tenant_id)
        query = entry["query"]
        targets = entry.get("targets") or ["global"]
        gold = entry.get("gold", [])

        user_claims = {
            "tenant_id": tenant,
            "accessible_projects": targets + ["global"],
            "role": "Eval",
        }
        payload = retriever.rag_search(
            tenant_id=tenant,
            user_claims=user_claims,
            query=query,
            targets=list(targets),
            k=k,
            strategy="qdrant",
        )
        hits: Sequence[RetrieveHit] = payload["results"]
        rel_scores = [_similarity(hit, gold_terms=gold) for hit in hits]
        similarities.append(mean(rel_scores) if rel_scores else 0.0)
        leaks.append(
            1.0
            if any(_determine_leak(hit, allowed=targets) for hit in hits)
            else 0.0
        )
        ttfc_scores.append(_time_to_first_correct(hits, gold))

    dreln = mean(similarities) if similarities else 0.0
    safety_leak = mean(leaks) if leaks else 0.0
    ttfc = mean(ttfc_scores) if ttfc_scores else float(k + 1)
    return MetricSnapshot(dataset=dataset_name, k=k, dreln=dreln, safety_leak=safety_leak, ttfc=ttfc, total_tasks=total)


def _render_markdown(out_path: Path, snapshot: MetricSnapshot) -> None:
    lines = [
        f"# Evaluation Report – {snapshot.dataset}",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| dRel@{snapshot.k} | {snapshot.dreln:.4f} |",
        f"| SafetyLeak@{snapshot.k} | {snapshot.safety_leak:.4f} |",
        f"| TimeToFirstCorrect | {snapshot.ttfc:.4f} |",
        f"| Total Tasks | {snapshot.total_tasks} |",
        "",
        "- Baseline router: static hybrid",
        "- Dataset: tasks from quick set",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def run_cli(args: argparse.Namespace) -> None:
    dataset = args.dataset
    k = args.k or DEFAULT_K
    out_dir = Path(args.out or "./artifacts/eval")
    out_dir.mkdir(parents=True, exist_ok=True)

    tasks_path = Path(settings.eval_data_dir) / "tasks.jsonl"
    tasks = _load_jsonl(tasks_path)
    snapshot = _evaluate_dataset(dataset, tasks, k)

    json_path = out_dir / f"{dataset}_metrics.json"
    json_path.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")

    md_path = out_dir / f"{dataset}_report.md"
    _render_markdown(md_path, snapshot)

    logger.info(
        "Eval harness completed",
        dataset=dataset,
        k=k,
        json=str(json_path),
        markdown=str(md_path),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="North Star evaluation harness")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Execute the evaluation harness")
    run_parser.add_argument("--dataset", default="quick", help="Dataset identifier to process")
    run_parser.add_argument("--k", type=int, default=DEFAULT_K, help="Top-k results to evaluate")
    run_parser.add_argument("--out", help="Output directory for artifacts")
    run_parser.set_defaults(func=run_cli)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()
