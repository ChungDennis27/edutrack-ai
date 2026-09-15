"""Quiz generation and attempt logging routes."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import db
from app.models import AttemptDetail, KnowledgePoint, Question, QuizAttempt, Subject, Topic
from app.services.analytics import AnalyticsService
from app.services.llm_client import build_llm_client
from app.services.quiz_generator import QuizGenerationService

quizzes_bp = Blueprint("quizzes", __name__)


def _get_quiz_service() -> QuizGenerationService:
    return QuizGenerationService(llm=build_llm_client(current_app.config))


@quizzes_bp.route("/subjects", methods=["GET"])
@jwt_required()
def list_subjects():
    """List subjects with their topics for the quiz setup screen."""
    subjects = Subject.query.order_by(Subject.id).all()

    return jsonify({
        "subjects": [
            {
                "code": s.code.lower(),
                "name_zh": s.name_zh,
                "name_en": s.name_en,
                "topics": [
                    {
                        "id": t.id,
                        "name_zh": t.name_zh,
                        "name_en": t.name_en,
                        "syllabus_ref": t.syllabus_ref,
                    }
                    for t in sorted(s.topics, key=lambda x: x.sort_order)
                ],
            }
            for s in subjects
        ]
    })


@quizzes_bp.route("/generate", methods=["POST"])
@jwt_required()
def generate_quiz():
    """Generate a DSE-style quiz via AI (JSON Mode) and persist to DB."""
    data = request.get_json(silent=True) or {}
    subject_code = data.get("subject", "").lower()
    topic_id = data.get("topic_id")
    difficulty = data.get("difficulty", "level_4")
    num_questions = min(int(data.get("num_questions", 5)), 10)

    if subject_code not in ("chinese", "math", "english"):
        return jsonify({"error": "subject must be chinese, math, or english"}), 400

    subject = Subject.query.filter_by(code=subject_code.upper()).first()
    if not subject:
        return jsonify({"error": f"Subject '{subject_code}' not found. Run seed script first."}), 404

    topic = Topic.query.get(topic_id) if topic_id else None
    topic_name = topic.name_zh if topic else subject_code

    kp_codes = None
    if topic:
        kp_codes = [kp.code for kp in KnowledgePoint.query.filter_by(topic_id=topic.id).all()]

    try:
        service = _get_quiz_service()
        quiz = service.generate(
            subject=subject_code,
            topic=topic_name,
            difficulty=difficulty,
            num_questions=num_questions,
            knowledge_point_codes=kp_codes or None,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 502
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    # Persist questions and create attempt
    persisted_questions = []
    for q in quiz.questions:
        kp = None
        if q.knowledge_point_code:
            kp = KnowledgePoint.query.filter_by(code=q.knowledge_point_code).first()
        if not kp and topic:
            kp = KnowledgePoint.query.filter_by(topic_id=topic.id).first()

        question = Question(
            knowledge_point_id=kp.id if kp else None,
            question_type=q.question_type,
            difficulty=difficulty,
            stem=q.stem,
            options_json=json.dumps(q.options, ensure_ascii=False),
            correct_answer=q.correct_answer,
            explanation=q.explanation,
            source="ai_generated",
        )
        db.session.add(question)
        persisted_questions.append(question)

    db.session.flush()

    attempt = QuizAttempt(
        user_id=int(get_jwt_identity()),
        subject_id=subject.id,
        topic_id=topic.id if topic else None,
        title=quiz.title,
        difficulty=difficulty,
        total_questions=len(quiz.questions),
        status="in_progress",
        question_ids_json=json.dumps([q.id for q in persisted_questions]),
    )
    db.session.add(attempt)
    db.session.commit()

    return jsonify({
        "attempt_id": attempt.id,
        "title": quiz.title,
        "difficulty": difficulty,
        "total_questions": len(quiz.questions),
        "questions": [
            {
                "id": persisted_questions[i].id,
                "index": q.index,
                "stem": q.stem,
                "options": q.options,
                "knowledge_point_code": q.knowledge_point_code,
            }
            for i, q in enumerate(quiz.questions)
        ],
    }), 201


@quizzes_bp.route("/submit", methods=["POST"])
@jwt_required()
def submit_quiz():
    """Submit quiz answers — auto-grade and log to AttemptDetail."""
    data = request.get_json(silent=True) or {}
    attempt_id = data.get("attempt_id")
    answers = data.get("answers", {})
    time_per_question = data.get("time_per_question", {})

    if not attempt_id:
        return jsonify({"error": "attempt_id is required"}), 400

    user_id = int(get_jwt_identity())
    attempt = QuizAttempt.query.filter_by(id=attempt_id, user_id=user_id).first()
    if not attempt:
        return jsonify({"error": "Quiz attempt not found"}), 404

    if attempt.status == "completed":
        return jsonify({"error": "Quiz already submitted"}), 409

    question_ids = json.loads(attempt.question_ids_json or "[]")
    questions = {q.id: q for q in Question.query.filter(Question.id.in_(question_ids)).all()}

    correct_count = 0
    total_time = 0

    for qid in question_ids:
        question = questions.get(qid)
        if not question:
            continue

        q_id_str = str(qid)
        user_answer = answers.get(q_id_str, "").strip()
        time_spent = int(time_per_question.get(q_id_str, 0))
        total_time += time_spent

        is_correct = user_answer.upper() == question.correct_answer.upper()
        is_slow = AnalyticsService.flag_slow_answers(time_spent, is_correct)

        if is_correct:
            correct_count += 1

        detail = AttemptDetail(
            attempt_id=attempt.id,
            question_id=qid,
            knowledge_point_id=question.knowledge_point_id,
            user_answer=user_answer,
            is_correct=is_correct,
            time_spent=time_spent,
            is_slow_but_correct=is_slow,
        )
        db.session.add(detail)

    attempt.correct_count = correct_count
    attempt.score_percent = round((correct_count / attempt.total_questions) * 100, 1) if attempt.total_questions > 0 else 0
    attempt.total_time_spent = total_time
    attempt.status = "completed"
    attempt.completed_at = datetime.now(timezone.utc)

    db.session.commit()
    AnalyticsService.refresh_mastery_cache(user_id)

    return jsonify({
        "attempt_id": attempt.id,
        "score_percent": attempt.score_percent,
        "correct_count": correct_count,
        "total_questions": attempt.total_questions,
        "total_time_spent": total_time,
        "message": "Quiz submitted successfully",
    })


@quizzes_bp.route("/attempt/<int:attempt_id>/results", methods=["GET"])
@jwt_required()
def get_quiz_results(attempt_id: int):
    """Get detailed results for a completed quiz."""
    user_id = int(get_jwt_identity())
    attempt = QuizAttempt.query.filter_by(id=attempt_id, user_id=user_id).first()
    if not attempt:
        return jsonify({"error": "Quiz attempt not found"}), 404

    details = AttemptDetail.query.filter_by(attempt_id=attempt.id).all()

    results = []
    for d in details:
        q = Question.query.get(d.question_id)
        results.append({
            "question_id": d.question_id,
            "stem": q.stem if q else "",
            "options": json.loads(q.options_json) if q and q.options_json else {},
            "correct_answer": q.correct_answer if q else "",
            "user_answer": d.user_answer,
            "is_correct": d.is_correct,
            "time_spent": d.time_spent,
            "is_slow_but_correct": d.is_slow_but_correct,
            "explanation": q.explanation if q else "",
        })

    return jsonify({
        "attempt_id": attempt.id,
        "title": attempt.title,
        "score_percent": attempt.score_percent,
        "correct_count": attempt.correct_count,
        "total_questions": attempt.total_questions,
        "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None,
        "results": results,
    })
