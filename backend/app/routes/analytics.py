"""Analytics & weak-topic report routes."""
from dataclasses import asdict

from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.services.analytics import AnalyticsService

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/report", methods=["GET"])
@jwt_required()
def weak_topic_report():
    user_id = int(get_jwt_identity())
    AnalyticsService.refresh_mastery_cache(user_id)
    report = AnalyticsService.generate_weak_topic_report(user_id)

    return jsonify({
        "user_id": report.user_id,
        "generated_at": report.generated_at.isoformat(),
        "overall_mastery": report.overall_mastery,
        "weak_topics": [asdict(w) for w in report.weak_topics],
        "strong_topics": [asdict(s) for s in report.strong_topics],
        "recommendations": report.recommendations,
    })
