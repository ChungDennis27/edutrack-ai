"""Short-term chat history (L1) and mastery-aware student context (L2).

No new tables. Context is rebuilt per request from TopicMastery, recent wrong
AttemptDetail rows, and due flashcards. Callers must fail open: an empty
string means "no personalisation", and chat still works.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app import db
from app.models import (
    AttemptDetail,
    KnowledgePoint,
    Question,
    QuizAttempt,
    Topic,
    TopicMastery,
)
from app.services.analytics import MASTERY_WEAK_THRESHOLD

logger = logging.getLogger(__name__)

CONTEXT_CHAR_LIMIT = 1200
WEAK_LIMIT = 5
MISTAKE_LIMIT = 5
DUE_LIMIT = 5
HISTORY_MESSAGE_LIMIT = 12  # 6 user/assistant rounds
HISTORY_CHAR_LIMIT = 800

_CONTEXT_NOTE = (
    "【這位學生的學習背景】\n"
    "以下只用於調整講解深淺同例子。唔好每句都提「根據你的弱項」，"
    "亦唔好把呢段當成參考資料來源。錯題未附標準答案。\n"
)


@dataclass(frozen=True)
class WeakPoint:
    name_zh: str
    topic_name_zh: str
    mastery_percent: float


@dataclass(frozen=True)
class RecentMistake:
    knowledge_point: str
    stem: str
    user_answer: str


@dataclass(frozen=True)
class DueCard:
    front: str
    knowledge_point: str = ""


def _clip(text: str | None, limit: int) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[:limit]


def _pct(value: float) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.1f}"


def format_student_context(
    weak: list[WeakPoint],
    mistakes: list[RecentMistake],
    due: list[DueCard],
    *,
    limit: int = CONTEXT_CHAR_LIMIT,
) -> str:
    """Render a bounded Traditional Chinese brief. Empty input -> empty string."""
    parts: list[str] = []

    if weak:
        lines = [
            f"- {item.topic_name_zh}／{item.name_zh}：掌握 {_pct(item.mastery_percent)}%"
            for item in weak[:WEAK_LIMIT]
        ]
        parts.append("弱項：\n" + "\n".join(lines))

    if mistakes:
        lines = []
        for item in mistakes[:MISTAKE_LIMIT]:
            line = f"- [{_clip(item.knowledge_point, 40)}] {_clip(item.stem, 80)}"
            answer = _clip(item.user_answer, 40)
            if answer:
                line += f"（學生答案：{answer}）"
            lines.append(line)
        parts.append("近期錯題：\n" + "\n".join(lines))

    if due:
        lines = []
        for card in due[:DUE_LIMIT]:
            front = _clip(card.front, 80)
            point = _clip(card.knowledge_point, 40)
            lines.append(f"- [{point}] {front}" if point else f"- {front}")
        parts.append("待複習記憶卡：\n" + "\n".join(lines))

    text = "\n\n".join(parts).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def append_student_context(system_prompt: str, student_context: str | None) -> str:
    """Append the brief after the base tutor rules. Blank context is a no-op."""
    ctx = (student_context or "").strip()
    if not ctx:
        return system_prompt
    return system_prompt.rstrip() + "\n\n" + _CONTEXT_NOTE + ctx


def normalize_history(
    history,
    *,
    message_limit: int = HISTORY_MESSAGE_LIMIT,
    char_limit: int = HISTORY_CHAR_LIMIT,
) -> list[dict[str, str]]:
    """Keep the last N user/assistant turns, safe to place before the new query.

    Drops unknown roles, collapses consecutive same-role messages, drops a
    leading assistant turn, and drops a trailing user turn so the new query
    stays a user message (required by Anthropic's alternating-role API).
    """
    if not isinstance(history, list):
        return []

    cleaned: list[dict[str, str]] = []
    # Look slightly further back than the cap so invalid items do not crowd out real turns.
    for item in history[-40:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        text = content.strip()
        if not text:
            continue
        cleaned.append({"role": role, "content": text[:char_limit]})

    while cleaned and cleaned[0]["role"] != "user":
        cleaned.pop(0)

    alternated: list[dict[str, str]] = []
    for msg in cleaned:
        if alternated and alternated[-1]["role"] == msg["role"]:
            alternated[-1] = msg
        else:
            alternated.append(msg)

    while alternated and alternated[-1]["role"] == "user":
        alternated.pop()

    return alternated[-message_limit:]


def _load_weak_points(user_id: int) -> list[WeakPoint]:
    rows = (
        db.session.query(TopicMastery, KnowledgePoint, Topic)
        .join(KnowledgePoint, KnowledgePoint.id == TopicMastery.knowledge_point_id)
        .join(Topic, Topic.id == KnowledgePoint.topic_id)
        .filter(
            TopicMastery.user_id == user_id,
            TopicMastery.total_attempts > 0,
            TopicMastery.mastery_percent < MASTERY_WEAK_THRESHOLD,
        )
        .order_by(TopicMastery.mastery_percent.asc(), TopicMastery.total_attempts.desc())
        .limit(WEAK_LIMIT)
        .all()
    )
    return [
        WeakPoint(
            name_zh=kp.name_zh,
            topic_name_zh=topic.name_zh,
            mastery_percent=float(mastery.mastery_percent or 0),
        )
        for mastery, kp, topic in rows
    ]


def _load_recent_mistakes(user_id: int) -> list[RecentMistake]:
    rows = (
        db.session.query(AttemptDetail, KnowledgePoint, Question)
        .join(QuizAttempt, QuizAttempt.id == AttemptDetail.attempt_id)
        .join(KnowledgePoint, KnowledgePoint.id == AttemptDetail.knowledge_point_id)
        .join(Question, Question.id == AttemptDetail.question_id)
        .filter(
            QuizAttempt.user_id == user_id,
            AttemptDetail.is_correct == False,  # noqa: E712
        )
        .order_by(AttemptDetail.answered_at.desc(), AttemptDetail.id.desc())
        .limit(MISTAKE_LIMIT)
        .all()
    )
    return [
        RecentMistake(
            knowledge_point=kp.name_zh,
            stem=question.stem or "",
            user_answer=detail.user_answer or "",
        )
        for detail, kp, question in rows
    ]


def _load_due_cards(user_id: int) -> list[DueCard]:
    from app.services.flashcard_service import FlashcardService

    cards = FlashcardService.get_due_cards(user_id, limit=DUE_LIMIT)
    kp_ids = [card.knowledge_point_id for card in cards if card.knowledge_point_id]
    names: dict[int, str] = {}
    if kp_ids:
        points = KnowledgePoint.query.filter(KnowledgePoint.id.in_(kp_ids)).all()
        names = {point.id: point.name_zh for point in points}
    return [
        DueCard(
            front=card.front,
            knowledge_point=names.get(card.knowledge_point_id or -1, ""),
        )
        for card in cards
    ]


def build_student_context(user_id: int) -> str:
    """Compose the prompt brief for one student. Never raises."""
    try:
        return format_student_context(
            _load_weak_points(user_id),
            _load_recent_mistakes(user_id),
            _load_due_cards(user_id),
        )
    except Exception:
        logger.exception("Failed to build student context for user %s", user_id)
        db.session.rollback()
        return ""
