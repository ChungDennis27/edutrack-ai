"""Weak-topic micro lessons. Topic text from the client is ignored."""
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.services.chroma_store import init_chroma_store
from app.services.llm_client import build_llm_client
from app.services.micro_lesson import LessonError, LessonService

lessons_bp = Blueprint("lessons", __name__)


def _user_id() -> int:
    return int(get_jwt_identity())


def _knowledge_point_id():
    data = request.get_json(silent=True) or {}
    raw = data.get("knowledge_point_id")
    if raw is None or raw == "":
        raw = request.args.get("knowledge_point_id")
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise LessonError("knowledge_point_id 必須是數字") from None


def _service() -> LessonService:
    return LessonService(
        init_chroma_store(current_app.config),
        build_llm_client(current_app.config),
    )


@lessons_bp.route("", methods=["POST"])
@jwt_required()
def create_lesson():
    try:
        user_id = _user_id()
        knowledge_point_id = _knowledge_point_id()
        target = LessonService.resolve_target(user_id, knowledge_point_id)
        fresh = (request.get_json(silent=True) or {}).get("fresh") is True
        if not fresh:
            existing = LessonService.reusable_public(user_id, target.knowledge_point.id)
            if existing:
                return jsonify(existing)
        outcome = _service().generate(user_id, target)
    except LessonError as exc:
        return jsonify({"error": exc.message}), exc.status
    except ValueError:
        current_app.logger.exception("micro lesson output failed validation")
        return jsonify({"error": "課堂內容未能通過檢查，請再試一次"}), 502
    return jsonify(outcome.payload), outcome.status_code


@lessons_bp.route("/latest", methods=["GET"])
@jwt_required()
def latest_lesson():
    try:
        knowledge_point_id = _knowledge_point_id()
    except LessonError as exc:
        return jsonify({"error": exc.message}), exc.status
    payload = LessonService.latest_public(_user_id(), knowledge_point_id)
    if payload is None:
        return jsonify({"error": "未有課堂"}), 404
    return jsonify(payload)


@lessons_bp.route("/<int:lesson_id>", methods=["GET"])
@jwt_required()
def get_lesson(lesson_id: int):
    payload = LessonService.public_by_id(_user_id(), lesson_id)
    if payload is None:
        return jsonify({"error": "未有課堂"}), 404
    return jsonify(payload)
