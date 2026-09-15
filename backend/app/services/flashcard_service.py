"""SM-2 Spaced Repetition Algorithm + Flashcard service."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app import db
from app.models import AttemptDetail, Flashcard, FlashcardReview, KnowledgePoint, Question

logger = logging.getLogger(__name__)


def sm2_algorithm(
    quality: int,
    ease_factor: float = 2.5,
    interval: int = 1,
    repetitions: int = 0,
) -> tuple[float, int, int]:
    """
    SuperMemo-2 (SM-2) algorithm implementation.

    Args:
        quality: 0-5 rating (0=complete blackout, 5=perfect recall)
        ease_factor: current ease factor (min 1.3)
        interval: current interval in days
        repetitions: count of consecutive correct recalls

    Returns:
        tuple of (new_ease_factor, new_interval_days, new_repetitions)
    """
    if quality >= 3:
        # Correct response
        if repetitions == 0:
            interval = 1
        elif repetitions == 1:
            interval = 6
        else:
            interval = round(interval * ease_factor)
        repetitions += 1
    else:
        # Incorrect response — reset
        repetitions = 0
        interval = 1

    # Update ease factor (never below 1.3)
    ease_factor = max(1.3, ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))

    return round(ease_factor, 2), interval, repetitions


class FlashcardService:
    """Service for flashcard CRUD and SM-2 review scheduling."""

    @staticmethod
    def get_due_cards(user_id: int, limit: int = 20) -> list[Flashcard]:
        """Get flashcards due for review today."""
        now = datetime.now(timezone.utc)
        return (
            Flashcard.query.filter(
                Flashcard.user_id == user_id,
                Flashcard.is_active == True,
                Flashcard.next_review_date <= now,
            )
            .order_by(Flashcard.next_review_date.asc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def review_card(flashcard_id: int, user_id: int, quality: int) -> Flashcard:
        """
        Process a flashcard review with SM-2 algorithm.

        Args:
            flashcard_id: ID of the flashcard being reviewed
            user_id: ID of the user (for ownership verification)
            quality: 0-5 SM-2 quality rating
                     0 = complete blackout
                     1 = incorrect, but remembered on seeing answer
                     2 = incorrect, but seemed easy to recall
                     3 = correct with serious difficulty
                     4 = correct with some hesitation
                     5 = perfect response

        Returns:
            Updated Flashcard instance
        """
        card = Flashcard.query.filter_by(id=flashcard_id, user_id=user_id).first()
        if not card:
            raise ValueError("Flashcard not found")

        quality = max(0, min(5, quality))

        old_ef = card.ease_factor
        old_interval = card.interval_days

        new_ef, new_interval, new_reps = sm2_algorithm(
            quality=quality,
            ease_factor=card.ease_factor,
            interval=card.interval_days,
            repetitions=card.repetitions,
        )

        # Update card
        card.ease_factor = new_ef
        card.interval_days = new_interval
        card.repetitions = new_reps
        card.last_reviewed_at = datetime.now(timezone.utc)
        card.next_review_date = datetime.now(timezone.utc) + timedelta(days=new_interval)

        # Log review
        review = FlashcardReview(
            flashcard_id=card.id,
            quality=quality,
            ease_factor_before=old_ef,
            ease_factor_after=new_ef,
            interval_before=old_interval,
            interval_after=new_interval,
        )
        db.session.add(review)
        db.session.commit()

        return card

    @staticmethod
    def create_card(
        user_id: int,
        front: str,
        back: str,
        knowledge_point_id: int | None = None,
        source: str = "manual",
    ) -> Flashcard:
        """Create a new flashcard."""
        card = Flashcard(
            user_id=user_id,
            knowledge_point_id=knowledge_point_id,
            front=front,
            back=back,
            source=source,
        )
        db.session.add(card)
        db.session.commit()
        return card

    @staticmethod
    def generate_from_wrong_answers(user_id: int) -> list[Flashcard]:
        """
        Auto-generate flashcards from a user's incorrect quiz answers.
        Creates one flashcard per unique knowledge point with wrong answers.
        """
        # Find knowledge points where user has wrong answers
        wrong_kp_ids = (
            db.session.query(AttemptDetail.knowledge_point_id)
            .join(Question, Question.id == AttemptDetail.question_id)
            .filter(
                AttemptDetail.is_correct == False,
                AttemptDetail.knowledge_point_id.isnot(None),
            )
            .distinct()
            .all()
        )

        created = []
        for (kp_id,) in wrong_kp_ids:
            kp = KnowledgePoint.query.get(kp_id)
            if not kp:
                continue

            # Check if card already exists for this KP
            existing = Flashcard.query.filter_by(
                user_id=user_id,
                knowledge_point_id=kp_id,
                source="wrong_answer",
            ).first()
            if existing:
                continue

            # Get a sample wrong question for context
            sample = (
                AttemptDetail.query.join(Question)
                .filter(
                    AttemptDetail.knowledge_point_id == kp_id,
                    AttemptDetail.is_correct == False,
                )
                .first()
            )

            front = f"【{kp.topic.name_zh}】{kp.name_zh}\n\n"
            if sample and sample.user_answer:
                front += f"你的錯誤答案：{sample.user_answer}\n\n"
            front += "請解釋此概念並說明正確解法。"

            back = f"知識點：{kp.name_zh}（{kp.name_en}）\n"
            if kp.dse_level_hint:
                back += f"DSE 水平：{kp.dse_level_hint}\n"
            if sample and sample.question:
                back += f"\n正確答案：{sample.question.correct_answer}\n"
                if sample.question.explanation:
                    back += f"\n解析：{sample.question.explanation}"

            card = Flashcard(
                user_id=user_id,
                knowledge_point_id=kp_id,
                front=front,
                back=back,
                source="wrong_answer",
            )
            db.session.add(card)
            created.append(card)

        if created:
            db.session.commit()
            logger.info("Created %d flashcards from wrong answers for user %d", len(created), user_id)

        return created
