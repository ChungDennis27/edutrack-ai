"""Weak-topic analysis and dashboard aggregation service."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import case, func

from app import db
from app.models import AttemptDetail, KnowledgePoint, QuizAttempt, Topic, TopicMastery


# Thresholds for weak-topic detection
MASTERY_WEAK_THRESHOLD = 50.0       # below 50% = weak
SLOW_ANSWER_THRESHOLD_SEC = 120     # > 2 min per question = slow
SLOW_CORRECT_PENALTY = 15.0         # reduce mastery score even if correct


@dataclass
class KnowledgePointStats:
    knowledge_point_id: int
    code: str
    name_zh: str
    name_en: str
    topic_name_zh: str
    total_attempts: int = 0
    correct_count: int = 0
    mastery_percent: float = 0.0
    avg_time_spent: float = 0.0
    slow_correct_count: int = 0
    is_weak: bool = False
    error_patterns: list[str] = field(default_factory=list)


@dataclass
class WeakTopicReport:
    user_id: int
    generated_at: datetime
    overall_mastery: float
    weak_topics: list[KnowledgePointStats]
    strong_topics: list[KnowledgePointStats]
    recommendations: list[dict]


class AnalyticsService:
    """Aggregates AttemptDetail data into mastery metrics and weak-topic reports."""

    @staticmethod
    def compute_mastery_percent(
        correct: int,
        total: int,
        slow_correct: int = 0,
    ) -> float:
        if total == 0:
            return 0.0
        base = (correct / total) * 100.0
        # Penalise slow-but-correct answers (potential weak understanding)
        penalty = (slow_correct / total) * SLOW_CORRECT_PENALTY
        return max(0.0, round(base - penalty, 1))

    @classmethod
    def aggregate_by_knowledge_point(cls, user_id: int) -> list[KnowledgePointStats]:
        """SQL aggregation of per-question attempt data grouped by knowledge point."""
        rows = (
            db.session.query(
                KnowledgePoint.id,
                KnowledgePoint.code,
                KnowledgePoint.name_zh,
                KnowledgePoint.name_en,
                Topic.name_zh.label("topic_name_zh"),
                func.count(AttemptDetail.id).label("total"),
                func.sum(case((AttemptDetail.is_correct == True, 1), else_=0)).label("correct"),  # noqa: E712
                func.avg(AttemptDetail.time_spent).label("avg_time"),
                func.sum(case((AttemptDetail.is_slow_but_correct == True, 1), else_=0)).label("slow_correct"),  # noqa: E712
            )
            .join(AttemptDetail, AttemptDetail.knowledge_point_id == KnowledgePoint.id)
            .join(QuizAttempt, QuizAttempt.id == AttemptDetail.attempt_id)
            .join(Topic, Topic.id == KnowledgePoint.topic_id)
            .filter(QuizAttempt.user_id == user_id)
            .group_by(
                KnowledgePoint.id,
                KnowledgePoint.code,
                KnowledgePoint.name_zh,
                KnowledgePoint.name_en,
                Topic.name_zh,
            )
            .all()
        )

        stats_list: list[KnowledgePointStats] = []
        for row in rows:
            total = int(row.total or 0)
            correct = int(row.correct or 0)
            slow = int(row.slow_correct or 0)
            mastery = cls.compute_mastery_percent(correct, total, slow)

            stats_list.append(
                KnowledgePointStats(
                    knowledge_point_id=row.id,
                    code=row.code,
                    name_zh=row.name_zh,
                    name_en=row.name_en,
                    topic_name_zh=row.topic_name_zh,
                    total_attempts=total,
                    correct_count=correct,
                    mastery_percent=mastery,
                    avg_time_spent=round(float(row.avg_time or 0), 1),
                    slow_correct_count=slow,
                    is_weak=mastery < MASTERY_WEAK_THRESHOLD,
                )
            )
        return stats_list

    @classmethod
    def classify_error_patterns(cls, user_id: int, knowledge_point_id: int) -> list[str]:
        """Collect AI-classified error patterns for a specific knowledge point."""
        patterns = (
            db.session.query(AttemptDetail.error_pattern)
            .join(QuizAttempt, QuizAttempt.id == AttemptDetail.attempt_id)
            .filter(
                QuizAttempt.user_id == user_id,
                AttemptDetail.knowledge_point_id == knowledge_point_id,
                AttemptDetail.is_correct == False,  # noqa: E712
                AttemptDetail.error_pattern.isnot(None),
            )
            .distinct()
            .all()
        )
        return [p[0] for p in patterns if p[0]]

    @classmethod
    def refresh_mastery_cache(cls, user_id: int) -> int:
        """Upsert TopicMastery records from latest attempt data."""
        stats = cls.aggregate_by_knowledge_point(user_id)
        updated = 0

        for s in stats:
            record = TopicMastery.query.filter_by(
                user_id=user_id,
                knowledge_point_id=s.knowledge_point_id,
            ).first()

            if not record:
                record = TopicMastery(user_id=user_id, knowledge_point_id=s.knowledge_point_id)
                db.session.add(record)

            record.mastery_percent = s.mastery_percent
            record.total_attempts = s.total_attempts
            record.correct_count = s.correct_count
            record.avg_time_spent = s.avg_time_spent
            record.is_weak = s.is_weak
            record.last_attempt_at = datetime.now(timezone.utc)
            updated += 1

        db.session.commit()
        return updated

    @classmethod
    def generate_weak_topic_report(cls, user_id: int) -> WeakTopicReport:
        """Full weak-topic analysis with recommendations."""
        stats = cls.aggregate_by_knowledge_point(user_id)

        for s in stats:
            s.error_patterns = cls.classify_error_patterns(user_id, s.knowledge_point_id)

        weak = sorted(
            [s for s in stats if s.is_weak],
            key=lambda x: x.mastery_percent,
        )
        strong = sorted(
            [s for s in stats if not s.is_weak],
            key=lambda x: x.mastery_percent,
            reverse=True,
        )[:5]

        overall = (
            round(sum(s.mastery_percent for s in stats) / len(stats), 1)
            if stats
            else 0.0
        )

        recommendations = []
        for w in weak[:5]:
            recommendations.append({
                "knowledge_point_id": w.knowledge_point_id,
                "name_zh": w.name_zh,
                "topic": w.topic_name_zh,
                "mastery_percent": w.mastery_percent,
                "message": cls._build_recommendation_message(w),
                "resource_query": f"{w.topic_name_zh} {w.name_zh} DSE 複習",
            })

        return WeakTopicReport(
            user_id=user_id,
            generated_at=datetime.now(timezone.utc),
            overall_mastery=overall,
            weak_topics=weak,
            strong_topics=strong,
            recommendations=recommendations,
        )

    @staticmethod
    def _build_recommendation_message(stats: KnowledgePointStats) -> str:
        parts = [f"「{stats.topic_name_zh} — {stats.name_zh}」掌握度僅 {stats.mastery_percent}%，建議加強複習。"]
        if stats.slow_correct_count > 0:
            parts.append(f"有 {stats.slow_correct_count} 題雖答對但用時過長，顯示理解尚未穩固。")
        if stats.error_patterns:
            parts.append(f"常見錯誤模式：{'、'.join(stats.error_patterns)}。")
        return " ".join(parts)

    @staticmethod
    def flag_slow_answers(time_spent: int, is_correct: bool) -> bool:
        """Mark answers that took too long as potential weak areas."""
        return is_correct and time_spent >= SLOW_ANSWER_THRESHOLD_SEC
