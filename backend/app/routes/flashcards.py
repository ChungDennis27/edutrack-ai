"""Flashcard & SM-2 spaced repetition routes."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app import db
from app.models import Flashcard
from app.services.flashcard_service import FlashcardService

flashcards_bp = Blueprint("flashcards", __name__)


@flashcards_bp.route("/due", methods=["GET"])
@jwt_required()
def get_due_cards():
    """Get flashcards due for review today."""
    user_id = int(get_jwt_identity())
    cards = FlashcardService.get_due_cards(user_id)

    return jsonify({
        "count": len(cards),
        "cards": [
            {
                "id": c.id,
                "front": c.front,
                "back": c.back,
                "source": c.source,
                "ease_factor": c.ease_factor,
                "interval_days": c.interval_days,
                "repetitions": c.repetitions,
                "next_review_date": c.next_review_date.isoformat() if c.next_review_date else None,
                "knowledge_point_id": c.knowledge_point_id,
            }
            for c in cards
        ],
    })


@flashcards_bp.route("/review", methods=["POST"])
@jwt_required()
def review_card():
    """Submit a flashcard review with SM-2 quality rating."""
    data = request.get_json(silent=True) or {}
    flashcard_id = data.get("flashcard_id")
    quality = data.get("quality")

    if not flashcard_id or quality is None:
        return jsonify({"error": "flashcard_id and quality are required"}), 400

    try:
        quality = int(quality)
        if quality < 0 or quality > 5:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "quality must be an integer 0-5"}), 400

    user_id = int(get_jwt_identity())

    try:
        card = FlashcardService.review_card(flashcard_id, user_id, quality)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    return jsonify({
        "id": card.id,
        "ease_factor": card.ease_factor,
        "interval_days": card.interval_days,
        "repetitions": card.repetitions,
        "next_review_date": card.next_review_date.isoformat() if card.next_review_date else None,
        "message": "Review recorded",
    })


@flashcards_bp.route("/generate-from-mistakes", methods=["POST"])
@jwt_required()
def generate_from_mistakes():
    """Auto-generate flashcards from wrong quiz answers."""
    user_id = int(get_jwt_identity())
    created = FlashcardService.generate_from_wrong_answers(user_id)

    return jsonify({
        "created_count": len(created),
        "cards": [
            {
                "id": c.id,
                "front": c.front[:100] + "...",
                "knowledge_point_id": c.knowledge_point_id,
            }
            for c in created
        ],
    })


@flashcards_bp.route("/create", methods=["POST"])
@jwt_required()
def create_card():
    """Manually create a flashcard."""
    data = request.get_json(silent=True) or {}
    front = data.get("front", "").strip()
    back = data.get("back", "").strip()
    knowledge_point_id = data.get("knowledge_point_id")

    if not front or not back:
        return jsonify({"error": "front and back are required"}), 400

    user_id = int(get_jwt_identity())
    card = FlashcardService.create_card(
        user_id=user_id,
        front=front,
        back=back,
        knowledge_point_id=knowledge_point_id,
        source="manual",
    )

    return jsonify({
        "id": card.id,
        "front": card.front,
        "back": card.back,
        "next_review_date": card.next_review_date.isoformat() if card.next_review_date else None,
    }), 201


@flashcards_bp.route("/", methods=["GET"])
@jwt_required()
def list_cards():
    """List all active flashcards for the user."""
    user_id = int(get_jwt_identity())
    cards = Flashcard.query.filter_by(user_id=user_id, is_active=True).order_by(
        Flashcard.next_review_date.asc()
    ).all()

    return jsonify({
        "count": len(cards),
        "cards": [
            {
                "id": c.id,
                "front": c.front,
                "back": c.back,
                "source": c.source,
                "ease_factor": c.ease_factor,
                "interval_days": c.interval_days,
                "repetitions": c.repetitions,
                "next_review_date": c.next_review_date.isoformat() if c.next_review_date else None,
                "last_reviewed_at": c.last_reviewed_at.isoformat() if c.last_reviewed_at else None,
            }
            for c in cards
        ],
    })
