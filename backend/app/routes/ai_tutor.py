"""RAG AI Tutor routes — streaming SSE chat + English essay grading."""
import json

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
from flask_jwt_extended import jwt_required

from app.services.ai_engine import AIEngine
from app.services.chroma_store import init_chroma_store
from app.services.classical_texts import list_classical_texts
from app.services.essay_grading import EssayGradingService
from app.services.llm_client import build_llm_client
from app.services.math_hint import MathHintService

ai_tutor_bp = Blueprint("ai_tutor", __name__)


def _get_engine() -> AIEngine:
    store = init_chroma_store(current_app.config)
    return AIEngine(
        vector_store=store,
        llm=build_llm_client(current_app.config),
        top_k=current_app.config["RAG_TOP_K"],
        similarity_threshold=current_app.config["RAG_SIMILARITY_THRESHOLD"],
    )


def _get_essay_grader() -> EssayGradingService:
    return EssayGradingService(llm=build_llm_client(current_app.config))


def _get_math_hint_service() -> MathHintService:
    return MathHintService(llm=build_llm_client(current_app.config))


@ai_tutor_bp.route("/query", methods=["POST"])
@jwt_required()
def chat_query():
    """Non-streaming RAG chat endpoint."""
    data = request.get_json(silent=True) or {}
    query = data.get("query", "").strip()
    subject = data.get("subject")  # chinese | math | english

    if not query:
        return jsonify({"error": "query is required"}), 400

    engine = _get_engine()
    result = engine.chat(query, subject)
    return jsonify(result)


@ai_tutor_bp.route("/stream", methods=["POST"])
@jwt_required()
def chat_stream():
    """SSE streaming RAG chat endpoint."""
    data = request.get_json(silent=True) or {}
    query = data.get("query", "").strip()
    subject = data.get("subject")

    if not query:
        return jsonify({"error": "query is required"}), 400

    engine = _get_engine()

    @stream_with_context
    def generate():
        for chunk in engine.chat_stream(query, subject):
            yield f"data: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return Response(generate(), mimetype="text/event-stream")


@ai_tutor_bp.route("/grade-essay", methods=["POST"])
@jwt_required()
def grade_essay():
    """Grade an English essay using HKEAA DSE criteria."""
    data = request.get_json(silent=True) or {}
    essay_text = data.get("essay", "").strip()
    task_type = data.get("task_type", "argumentative")

    if not essay_text:
        return jsonify({"error": "essay text is required"}), 400

    if len(essay_text.split()) < 50:
        return jsonify({"error": "Essay too short (minimum 50 words)"}), 400

    grader = _get_essay_grader()
    result = grader.grade_essay(essay_text, task_type)
    return jsonify(result)


@ai_tutor_bp.route("/math-hint", methods=["POST"])
@jwt_required()
def math_hint():
    """Get a step-by-step hint for a math problem (Method Marks approach)."""
    data = request.get_json(silent=True) or {}
    problem = data.get("problem", "").strip()
    student_work = data.get("student_work", "")
    hint_history = data.get("hint_history", [])
    topic = data.get("topic", "")

    if not problem:
        return jsonify({"error": "problem statement is required"}), 400

    service = _get_math_hint_service()
    result = service.get_hint(problem, student_work, hint_history, topic)
    return jsonify(result)


@ai_tutor_bp.route("/classical-texts", methods=["GET"])
@jwt_required()
def classical_texts():
    """List the DSE 12 designated 文言文 texts (curated sample set)."""
    return jsonify({"texts": list_classical_texts()})
