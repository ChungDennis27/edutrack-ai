"""Run a small RAG evaluation against the local Chroma DSE collection.

Default mode is retrieval-only and never calls an LLM. Pass --live to make
real model requests and include mechanical answer checks in the report.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import create_app  # noqa: E402
from app.services.ai_engine import AIEngine  # noqa: E402
from app.services.chroma_store import init_chroma_store  # noqa: E402
from app.services.evaluation import (  # noqa: E402
    EvalCase,
    evaluate_retrieval_case,
    result_document,
    score_answer,
)
from app.services.llm_client import build_llm_client  # noqa: E402

DEFAULT_CASES = backend_root / "evaluation_cases.json"


def load_cases(path: Path) -> tuple[str, list[EvalCase]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = [
        EvalCase(
            id=item["id"],
            query=item["query"],
            subject=item.get("subject"),
            expected_terms=tuple(item.get("expected_terms", [])),
            expected_content_types=tuple(item.get("expected_content_types", [])),
            should_retrieve=item.get("should_retrieve", True),
            category=item.get("category", "retrieval"),
        )
        for item in data["cases"]
    ]
    return data.get("dataset", path.stem), cases


def markdown_report(report: dict) -> str:
    summary = report["summary"]
    lines = [
        f"# RAG evaluation: {report['dataset']}",
        "",
        f"Collection: `{report['collection']}` · top-k: {report['top_k']}",
        f"Status: {report['status']} · indexed chunks: {report['indexed_chunks']}",
        f"Cases: {summary['passed']}/{summary['case_count']} passed · "
        f"Raw evidence Recall@k: {summary['recall_at_k']:.2%} · "
        f"MRR: {summary['mean_reciprocal_rank']:.4f}",
        f"After similarity threshold: Recall@k {summary['threshold_recall_at_k']:.2%}",
        f"Wrong-subject hits: {summary['wrong_subject_hits']} · "
        f"Personal leaks: {summary['personal_leaks']}",
        "",
        "| Case | Category | Outcome | Evidence | Hits | MRR |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in report["cases"]:
        lines.append(
            f"| {row['case_id']} | {row['category']} | "
            f"{'PASS' if row['outcome_pass'] else 'FAIL'} | "
            f"{'PASS' if row['evidence_pass'] else 'FAIL'} | "
            f"{row['hit_count']} | {row['reciprocal_rank']:.4f} |"
        )
        if row.get("threshold_rejected_count"):
            lines.append(
                f"  - Best raw candidate relevance: {row['best_candidate_relevance']:.4f}; "
                f"{row['threshold_rejected_count']} candidate(s) filtered by similarity threshold."
            )
        if "answer_checks" in row:
            checks = row["answer_checks"]
            lines.append(
                f"\nAnswer checks: citation={checks['citation_pass']}, "
                f"abstention={checks['abstention_pass']}, "
                f"math-answer-leak={checks['math_answer_leak']} "
                "(manual review still required).\n"
            )
    lines.extend([
        "",
        f"> {report['status_reason']}" if report.get("status_reason") else "",
        "> This is a smoke test against the currently indexed collection, not a full syllabus benchmark. "
        "Live answer checks are heuristic; manually review answers before making quality claims.",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate EduTrack RAG using fixed cases")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="evaluation case JSON")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=0.65)
    parser.add_argument("--live", action="store_true", help="call the configured LLM (may incur API cost)")
    parser.add_argument("--output", type=Path, help="write a Markdown report to this path")
    args = parser.parse_args()
    if args.top_k < 1 or not 0 <= args.threshold <= 1:
        parser.error("--top-k must be positive and --threshold must be between 0 and 1")

    dataset, cases = load_cases(args.cases)
    app = create_app()
    with app.app_context():
        store = init_chroma_store(app.config)
        indexed_chunks = store.document_count
        llm = build_llm_client(app.config) if args.live else None
        if args.live and not llm.available:
            print("Live evaluation requested, but no LLM API key is configured.", file=sys.stderr)
            return 2
        engine = AIEngine(
            store,
            llm,
            top_k=args.top_k,
            similarity_threshold=args.threshold,
        ) if args.live else None

        rows = []
        for case in cases:
            where = {"subject": case.subject} if case.subject else None
            candidates = store._search(
                store._collection,
                query_text=case.query,
                n_results=args.top_k,
                where=where,
                similarity_threshold=0.0,
            )
            hits = [hit for hit in candidates if hit.relevance_score >= args.threshold]
            row = evaluate_retrieval_case(
                case,
                hits,
                candidates=candidates,
                top_k=args.top_k,
            )
            if engine is not None:
                answer = engine.chat(case.query, subject=case.subject)
                row["answer_checks"] = score_answer(
                    case,
                    answer.get("answer", ""),
                    answer.get("sources", []),
                )
            rows.append(row)

        report = result_document(
            rows,
            dataset=dataset,
            collection=store.collection_name,
            top_k=args.top_k,
            indexed_chunks=indexed_chunks,
        )

    output = markdown_report(report)
    print(output)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
        print(f"\nReport written to {args.output}")
    if report["status"] == "not_evaluated":
        print(
            "\nEvaluation not scored: the Chroma collection is empty. "
            "Run scripts/init_chroma.py and ingest verified materials first."
        )
        return 2
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
