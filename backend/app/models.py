"""SQLAlchemy relational models for EduTrack AI (PostgreSQL)."""
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Users & Authentication
# ---------------------------------------------------------------------------


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120))
    form_level: Mapped[int | None] = mapped_column(Integer)  # e.g. 4, 5, 6
    target_subjects: Mapped[str | None] = mapped_column(Text)  # JSON array as text
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    quiz_attempts: Mapped[list["QuizAttempt"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    flashcards: Mapped[list["Flashcard"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    topic_mastery_records: Mapped[list["TopicMastery"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(
            password.encode("utf-8"), self.password_hash.encode("utf-8")
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "username": self.username,
            "display_name": self.display_name,
            "form_level": self.form_level,
            "target_subjects": self.target_subjects,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Curriculum Taxonomy (Subjects → Topics → Knowledge Points)
# ---------------------------------------------------------------------------


class Subject(db.Model):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # e.g. MATH, CHI, ENG
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    topics: Mapped[list["Topic"]] = relationship(back_populates="subject", cascade="all, delete-orphan")


class Topic(db.Model):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False, index=True)
    name_en: Mapped[str] = mapped_column(String(150), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(150), nullable=False)
    syllabus_ref: Mapped[str | None] = mapped_column(String(100))  # HKEAA syllabus code
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    subject: Mapped["Subject"] = relationship(back_populates="topics")
    knowledge_points: Mapped[list["KnowledgePoint"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )


class KnowledgePoint(db.Model):
    """Granular DSE knowledge unit — used for weak-topic analysis."""
    __tablename__ = "knowledge_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(200), nullable=False)
    dse_level_hint: Mapped[str | None] = mapped_column(String(20))  # e.g. "Level 4-5"

    topic: Mapped["Topic"] = relationship(back_populates="knowledge_points")
    questions: Mapped[list["Question"]] = relationship(back_populates="knowledge_point")
    mastery_records: Mapped[list["TopicMastery"]] = relationship(back_populates="knowledge_point")


# ---------------------------------------------------------------------------
# Question Bank
# ---------------------------------------------------------------------------


class Question(db.Model):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id"), nullable=False, index=True
    )
    question_type: Mapped[str] = mapped_column(String(20), nullable=False)  # mc | long | short
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)  # level_3 | level_4 | level_5pp
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[str | None] = mapped_column(Text)  # JSON array for MC
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(30), default="ai_generated")  # ai_generated | past_paper
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    knowledge_point: Mapped["KnowledgePoint"] = relationship(back_populates="questions")
    attempt_details: Mapped[list["AttemptDetail"]] = relationship(back_populates="question")


# ---------------------------------------------------------------------------
# Quiz Attempts & Per-Question Analytics
# ---------------------------------------------------------------------------


class QuizAttempt(db.Model):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    score_percent: Mapped[float] = mapped_column(Float, default=0.0)
    total_time_spent: Mapped[int] = mapped_column(Integer, default=0)  # seconds
    status: Mapped[str] = mapped_column(String(20), default="in_progress")  # in_progress | completed
    question_ids_json: Mapped[str | None] = mapped_column(Text)  # JSON array of question IDs in order
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="quiz_attempts")
    details: Mapped[list["AttemptDetail"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_quiz_attempts_user_started", "user_id", "started_at"),
    )


class AttemptDetail(db.Model):
    """Per-question attempt record — core data for weak-topic analysis."""
    __tablename__ = "attempt_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("quiz_attempts.id"), nullable=False, index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id"), nullable=False, index=True
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id"), nullable=False, index=True
    )
    user_answer: Mapped[str | None] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    time_spent: Mapped[int] = mapped_column(Integer, nullable=False)  # seconds per question
    is_slow_but_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    error_pattern: Mapped[str | None] = mapped_column(String(100))  # AI-classified error type
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    attempt: Mapped["QuizAttempt"] = relationship(back_populates="details")
    question: Mapped["Question"] = relationship(back_populates="attempt_details")
    knowledge_point: Mapped["KnowledgePoint"] = relationship()

    __table_args__ = (
        CheckConstraint("time_spent >= 0", name="ck_attempt_details_time_spent_nonneg"),
        Index("ix_attempt_details_kp_correct", "knowledge_point_id", "is_correct"),
    )


# ---------------------------------------------------------------------------
# Aggregated Mastery (Dashboard cache — refreshed by analytics service)
# ---------------------------------------------------------------------------


class TopicMastery(db.Model):
    __tablename__ = "topic_mastery"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    knowledge_point_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_points.id"), nullable=False, index=True
    )
    mastery_percent: Mapped[float] = mapped_column(Float, default=0.0)
    total_attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_time_spent: Mapped[float] = mapped_column(Float, default=0.0)
    is_weak: Mapped[bool] = mapped_column(Boolean, default=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped["User"] = relationship(back_populates="topic_mastery_records")
    knowledge_point: Mapped["KnowledgePoint"] = relationship(back_populates="mastery_records")

    __table_args__ = (
        UniqueConstraint("user_id", "knowledge_point_id", name="uq_user_knowledge_point"),
    )


# ---------------------------------------------------------------------------
# Flashcards & SM-2 Spaced Repetition
# ---------------------------------------------------------------------------


class Flashcard(db.Model):
    __tablename__ = "flashcards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    knowledge_point_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_points.id"))
    front: Mapped[str] = mapped_column(Text, nullable=False)
    back: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(30), default="ai_generated")  # ai | manual | wrong_answer

    # SM-2 algorithm parameters
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5)
    interval_days: Mapped[int] = mapped_column(Integer, default=1)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    next_review_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="flashcards")

    __table_args__ = (
        CheckConstraint("ease_factor >= 1.3", name="ck_flashcards_ease_factor_min"),
        Index("ix_flashcards_user_next_review", "user_id", "next_review_date"),
    )


class FlashcardReview(db.Model):
    """Historical log of each SM-2 review session."""
    __tablename__ = "flashcard_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    flashcard_id: Mapped[int] = mapped_column(ForeignKey("flashcards.id"), nullable=False, index=True)
    quality: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-5 SM-2 quality rating
    ease_factor_before: Mapped[float] = mapped_column(Float, nullable=False)
    ease_factor_after: Mapped[float] = mapped_column(Float, nullable=False)
    interval_before: Mapped[int] = mapped_column(Integer, nullable=False)
    interval_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        CheckConstraint("quality >= 0 AND quality <= 5", name="ck_flashcard_reviews_quality"),
    )
