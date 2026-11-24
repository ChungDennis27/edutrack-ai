from types import SimpleNamespace

from app.services.evaluation import (
    EvalCase,
    evaluate_retrieval_case,
    score_answer,
    summarize,
)


def _hit(text, *, subject="math", content_type="math_topic", **metadata):
    return SimpleNamespace(
        id=f"hit-{text[:5]}",
        text=text,
        metadata={"subject": subject, "content_type": content_type, **metadata},
        relevance_score=0.8,
    )


def test_retrieval_metrics_reward_expected_evidence_and_rank():
    case = EvalCase(
        id="disc",
        query="判別式",
        subject="math",
        expected_terms=("判別式", "實根"),
        expected_content_types=("math_topic",),
    )
    hits = [
        _hit("因式分解方法", content_type="math_topic"),
        _hit("判別式大於零時有兩個不等實根。", content_type="math_topic"),
    ]
    row = evaluate_retrieval_case(case, hits, top_k=5)
    assert row["passed"] is True
    assert row["expected_match_rank"] == 2
    assert row["reciprocal_rank"] == 0.5


def test_raw_candidates_distinguish_threshold_failure_from_missing_evidence():
    case = EvalCase(
        id="disc",
        query="判別式",
        subject="math",
        expected_terms=("判別式", "實根"),
        expected_content_types=("math_topic",),
    )
    candidate = _hit("判別式大於零時有兩個不等實根。", content_type="math_topic")
    row = evaluate_retrieval_case(case, [], candidates=[candidate], top_k=5)
    assert row["evidence_pass"] is True
    assert row["threshold_evidence_pass"] is False
    assert row["candidate_count"] == 1
    assert row["threshold_rejected_count"] == 1
    assert row["reciprocal_rank"] == 1.0
    assert row["threshold_reciprocal_rank"] == 0.0
    assert row["passed"] is False


def test_wrong_subject_and_private_chunks_are_reported_as_leaks():
    case = EvalCase(id="math", query="x", subject="math")
    hits = [
        _hit("wrong", subject="english"),
        _hit("private", origin="user_upload", user_id="12"),
    ]
    row = evaluate_retrieval_case(case, hits, top_k=5)
    assert row["wrong_subject_count"] == 1
    assert row["personal_leak_count"] == 1
    assert row["passed"] is False


def test_expected_abstention_fails_when_retrieval_returns_hits():
    case = EvalCase(
        id="unknown",
        query="未知內容",
        subject="math",
        should_retrieve=False,
        category="abstention",
    )
    assert evaluate_retrieval_case(case, [_hit("unrelated")], top_k=3)["passed"] is False
    assert evaluate_retrieval_case(case, [], top_k=3)["passed"] is True


def test_answer_checks_validate_citations_abstention_and_math_leaks():
    math_case = EvalCase(id="math", query="x", subject="math")
    leaked = score_answer(math_case, "答案是 x = 2。資料 9。", [{"id": "source"}])
    assert leaked["math_answer_leak"] is True
    assert leaked["citation_pass"] is False
    assert leaked["manual_review_required"] is True

    abstention_case = EvalCase(
        id="abstain", query="unknown", subject="math", category="abstention", should_retrieve=False
    )
    refused = score_answer(abstention_case, "現有資料不足以回答。", [])
    assert refused["abstention_pass"] is True


def test_summary_counts_metrics_without_claiming_live_quality():
    rows = [
        {
            "passed": True,
            "category": "grounded_answer",
            "evidence_pass": True,
            "reciprocal_rank": 1.0,
            "expected_match_rank": 1,
            "has_expected_evidence": True,
            "wrong_subject_count": 0,
            "personal_leak_count": 0,
        },
        {
            "passed": False,
            "category": "abstention",
            "evidence_pass": True,
            "reciprocal_rank": 0,
            "expected_match_rank": None,
            "has_expected_evidence": False,
            "wrong_subject_count": 1,
            "personal_leak_count": 0,
        },
    ]
    summary = summarize(rows)
    assert summary["case_count"] == 2
    assert summary["pass_rate"] == 0.5
    assert summary["mean_reciprocal_rank"] == 1.0
    assert summary["wrong_subject_hits"] == 1
    assert summary["live_generation"] is False


def test_empty_index_is_explicitly_marked_not_evaluated():
    from app.services.evaluation import result_document

    report = result_document(
        [], dataset="smoke", collection="dse_knowledge_base", top_k=5, indexed_chunks=0
    )
    assert report["status"] == "not_evaluated"
    assert report["indexed_chunks"] == 0
    assert "empty" in report["status_reason"]


def test_mrr_counts_missed_expected_evidence_as_zero():
    rows = [
        {"passed": True, "category": "grounded_answer", "evidence_pass": True,
         "reciprocal_rank": 1.0, "has_expected_evidence": True,
         "wrong_subject_count": 0, "personal_leak_count": 0},
        {"passed": False, "category": "grounded_answer", "evidence_pass": False,
         "reciprocal_rank": 0.0, "has_expected_evidence": True,
         "wrong_subject_count": 0, "personal_leak_count": 0},
    ]
    assert summarize(rows)["mean_reciprocal_rank"] == 0.5


def test_mrr_uses_candidate_ranking_and_threshold_mrr_is_separate():
    rows = [
        {"passed": False, "category": "grounded_answer", "evidence_pass": True,
         "threshold_evidence_pass": False, "reciprocal_rank": 1.0,
         "threshold_reciprocal_rank": 0.0, "has_expected_evidence": True,
         "wrong_subject_count": 0, "personal_leak_count": 0},
    ]
    summary = summarize(rows)
    assert summary["mean_reciprocal_rank"] == 1.0
    assert summary["threshold_mean_reciprocal_rank"] == 0.0
