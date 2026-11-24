"""Deterministic evaluation helpers for RAG retrieval and tutor behavior."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class EvalCase:
    id: str
    query: str
    subject: str | None
    expected_terms: tuple[str, ...] = ()
    expected_content_types: tuple[str, ...] = ()
    should_retrieve: bool = True
    category: str = "retrieval"


def evaluate_retrieval_case(
    case: EvalCase,
    hits: list[Any],
    *,
    top_k: int,
    candidates: list[Any] | None = None,
) -> dict:
    """Score only observable retrieval properties; never judge model prose here."""
    candidates = candidates if candidates is not None else hits
    relevant = [
        hit for hit in hits
        if (hit.metadata or {}).get("subject") == case.subject
        and not (hit.metadata or {}).get("user_id")
        and (hit.metadata or {}).get("origin") != "user_upload"
    ]
    expected = [term.casefold() for term in case.expected_terms]
    def rank_expected(items: list[Any]) -> tuple[float, int | None]:
        ranked_relevant = [
            hit for hit in items
            if (hit.metadata or {}).get("subject") == case.subject
            and not (hit.metadata or {}).get("user_id")
            and (hit.metadata or {}).get("origin") != "user_upload"
        ]
        for rank, hit in enumerate(ranked_relevant, 1):
            haystack = f"{hit.text} {hit.metadata or {}}".casefold()
            if expected and all(term in haystack for term in expected):
                return 1.0 / rank, rank
        return 0.0, None

    reciprocal_rank, matched_at = rank_expected(candidates)
    threshold_reciprocal_rank, threshold_matched_at = rank_expected(hits)

    wrong_subject = [
        hit for hit in hits
        if (hit.metadata or {}).get("subject") != case.subject
    ]
    personal_leaks = [
        hit for hit in hits
        if (hit.metadata or {}).get("origin") == "user_upload"
        or (hit.metadata or {}).get("user_id")
    ]
    type_hits = [
        hit for hit in relevant
        if not case.expected_content_types
        or (hit.metadata or {}).get("content_type") in case.expected_content_types
    ]
    retrieved = bool(hits)
    expected_outcome = "retrieve" if case.should_retrieve else "abstain"
    outcome_pass = retrieved == case.should_retrieve
    candidate_matches = [
        hit for hit in candidates
        if (hit.metadata or {}).get("subject") == case.subject
        and not (hit.metadata or {}).get("user_id")
        and (hit.metadata or {}).get("origin") != "user_upload"
        and all(
            term in f"{hit.text} {hit.metadata or {}}".casefold()
            for term in expected
        )
    ] if expected else []
    evidence_pass = (not case.expected_terms) or bool(candidate_matches)
    threshold_evidence_pass = (not case.expected_terms) or threshold_matched_at is not None
    return {
        "case_id": case.id,
        "category": case.category,
        "query": case.query,
        "subject": case.subject,
        "expected_outcome": expected_outcome,
        "has_expected_evidence": bool(expected),
        "outcome_pass": outcome_pass,
        "evidence_pass": evidence_pass,
        "threshold_evidence_pass": threshold_evidence_pass,
        "hit_count": len(hits),
        "candidate_count": len(candidates),
        "threshold_rejected_count": max(0, len(candidates) - len(hits)),
        "best_candidate_relevance": round(
            max((float(hit.relevance_score) for hit in candidates), default=0.0), 4
        ),
        "relevant_hit_count": len(relevant),
        "top_k": top_k,
        "reciprocal_rank": round(reciprocal_rank, 4),
        "expected_match_rank": matched_at,
        "threshold_reciprocal_rank": round(threshold_reciprocal_rank, 4),
        "threshold_match_rank": threshold_matched_at,
        "content_type_pass": bool(type_hits) if case.expected_content_types else None,
        "wrong_subject_count": len(wrong_subject),
        "personal_leak_count": len(personal_leaks),
        "passed": outcome_pass and threshold_evidence_pass and not wrong_subject and not personal_leaks
        and (bool(type_hits) if case.expected_content_types else True),
        "hits": [
            {
                "id": hit.id,
                "subject": (hit.metadata or {}).get("subject"),
                "content_type": (hit.metadata or {}).get("content_type"),
                "relevance": round(float(hit.relevance_score), 4),
                "preview": " ".join((hit.text or "").split())[:180],
            }
            for hit in hits[:top_k]
        ],
        "candidates": [
            {
                "id": hit.id,
                "subject": (hit.metadata or {}).get("subject"),
                "content_type": (hit.metadata or {}).get("content_type"),
                "relevance": round(float(hit.relevance_score), 4),
                "preview": " ".join((hit.text or "").split())[:180],
            }
            for hit in candidates[:top_k]
        ],
    }


def score_answer(case: EvalCase, answer: str, sources: list[dict]) -> dict:
    """Mechanical answer checks for opt-in live runs; not a substitute for review."""
    text = answer or ""
    source_ids = {str(source.get("id")) for source in sources}
    cited_numbers = [int(n) for n in re.findall(r"資料\s*(\d+)", text)]
    citations_valid = all(1 <= number <= len(sources) for number in cited_numbers)
    cited = bool(cited_numbers)
    if case.category == "abstention":
        refused = any(term in text for term in ("資料不足", "未有足夠", "未能找到", "無相關資料"))
        return {
            "abstention_pass": refused,
            "citation_pass": not cited or citations_valid,
            "math_answer_leak": False,
            "manual_review_required": True,
        }

    math_leak = case.subject == "math" and bool(
        re.search(r"(?:最終答案|完整答案|答案是|答案：|所以答案)\s*[:：]?\s*[^\n。]+", text)
    )
    return {
        "abstention_pass": None,
        "citation_pass": cited and citations_valid,
        "math_answer_leak": math_leak,
        "manual_review_required": True,
    }


def summarize(rows: list[dict]) -> dict:
    total = len(rows)
    passed = sum(bool(row.get("passed")) for row in rows)
    retrieval_rows = [row for row in rows if row.get("category") != "abstention"]
    expected_rows = [row for row in rows if row.get("has_expected_evidence")]
    return {
        "case_count": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "recall_at_k": round(
            sum(row["evidence_pass"] for row in retrieval_rows) / len(retrieval_rows), 4
        ) if retrieval_rows else 0.0,
        "threshold_recall_at_k": round(
            sum(row.get("threshold_evidence_pass", row["evidence_pass"]) for row in retrieval_rows)
            / len(retrieval_rows), 4
        ) if retrieval_rows else 0.0,
        "mean_reciprocal_rank": round(
            sum(row["reciprocal_rank"] for row in expected_rows) / len(expected_rows), 4
        ) if expected_rows else 0.0,
        "threshold_mean_reciprocal_rank": round(
            sum(row.get("threshold_reciprocal_rank", row["reciprocal_rank"]) for row in expected_rows)
            / len(expected_rows), 4
        ) if expected_rows else 0.0,
        "wrong_subject_hits": sum(row["wrong_subject_count"] for row in rows),
        "personal_leaks": sum(row["personal_leak_count"] for row in rows),
        "live_generation": any("answer_checks" in row for row in rows),
        "manual_review_required": any("answer_checks" in row for row in rows),
    }


def result_document(
    rows: list[dict],
    *,
    dataset: str,
    collection: str,
    top_k: int,
    indexed_chunks: int | None = None,
) -> dict:
    return {
        "status": "not_evaluated" if indexed_chunks == 0 else "completed",
        "indexed_chunks": indexed_chunks,
        "status_reason": "The selected Chroma collection is empty." if indexed_chunks == 0 else None,
        "dataset": dataset,
        "collection": collection,
        "top_k": top_k,
        "summary": summarize(rows),
        "cases": rows,
    }
