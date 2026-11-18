"""Five-minute lesson for one weak knowledge point, grounded in DSE notes only."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlalchemy.orm import joinedload

from app import db
from app.models import KnowledgePoint, MicroLesson, Question, QuizAttempt, Topic
from app.services.analytics import AnalyticsService
from app.services.llm_client import LLMNotConfigured, extract_json
from app.services.prompt_rules import PLAIN_MATH_RULE
from app.services.retrieval_scope import is_personal

logger = logging.getLogger(__name__)

LESSON_MINUTES = 5
_DIFFICULTIES = {"level_3", "level_4", "level_5", "level_5pp"}
_SUBJECT_FILTER = {
    "MATH": "math",
    "CHI": "chinese",
    "CHIN": "chinese",
    "ENG": "english",
}
_LATEX_MARKERS = ("$", "\\frac", "\\sqrt", "\\pm", "\\(")
_ANSWER_PREFIXES = ("答案", "最終答案", "完整答案", "final answer")

LESSON_SYSTEM_PROMPT = """你是香港 DSE 補習導師。用已檢索的課程筆記，為一位學生準備一節約 5 分鐘的微課堂。

嚴格規則：
1. 只可使用提供的「參考資料」。不可捏造 DSE 評分標準、試題，或資料沒有寫的事實。
2. 如果參考資料不足以講清楚這個知識點，只輸出 {"insufficient": true}。
3. 否則只輸出一個 JSON 物件，不要 markdown 代碼塊。
4. 數學式用普通文字，不要 LaTeX。
5. 數學科的 example 只可給題目同 2 至 3 個步驟提示。禁止寫最終答案，禁止以「答案」開頭。
6. 檢查題 1 至 2 條，四選一，答案必須能從參考資料推出。
7. 使用繁體中文（香港用語）。講解要標明「資料 1」這類編號。
8. objective 只可一句。

JSON：
{
  "objective": "一句學習目標",
  "explanation": "概念講解，並標明資料編號",
  "example": {"prompt": "例題", "steps": ["提示"], "withheld": true},
  "checks": [
    {
      "stem": "題目",
      "options": {"A": "", "B": "", "C": "", "D": ""},
      "correct_answer": "A",
      "explanation": "點解，並指出資料編號"
    }
  ]
}
""" + PLAIN_MATH_RULE


class LessonError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass
class LessonTarget:
    knowledge_point: KnowledgePoint
    mastery_percent: float | None
    picked_weakest: bool


@dataclass
class LessonOutcome:
    payload: dict
    status_code: int


def chroma_subject(code: str | None) -> str | None:
    if not isinstance(code, str):
        return None
    return _SUBJECT_FILTER.get(code.strip().upper())


def pick_weakest(stats: list):
    """Lowest mastery. Ties prefer the point with more answered questions."""
    if not stats:
        return None
    return min(
        stats,
        key=lambda item: (item.mastery_percent, -item.total_attempts, item.knowledge_point_id),
    )


def _clip(value, limit: int) -> str:
    if not isinstance(value, str):
        raise ValueError("expected text")
    text = " ".join(value.split())
    if not text:
        raise ValueError("empty text")
    return text[:limit]


def _rejects_latex(text: str) -> None:
    lowered = text.lower()
    if any(marker.lower() in lowered for marker in _LATEX_MARKERS):
        raise ValueError("lesson used LaTeX")


def _leaks_final_answer(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip().lower()
        if stripped.startswith(_ANSWER_PREFIXES):
            return True
    return False


def _one_sentence(value) -> str:
    text = _clip(value, 180)
    for mark in ("。", "！", "？", "."):
        index = text.find(mark)
        if index != -1:
            return text[: index + 1]
    return text


def _checks(raw) -> list[dict]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("checks required")
    cleaned = []
    for item in raw[:2]:
        if not isinstance(item, dict):
            raise ValueError("check must be an object")
        options = item.get("options")
        if not isinstance(options, dict):
            raise ValueError("options required")
        cleaned_options = {key: _clip(options.get(key), 300) for key in ("A", "B", "C", "D")}
        answer = str(item.get("correct_answer", "")).strip().upper()
        if answer not in cleaned_options:
            raise ValueError("correct_answer must be A, B, C, or D")
        explanation = item.get("explanation") or "見課堂講解。"
        cleaned.append(
            {
                "stem": _clip(item.get("stem"), 500),
                "options": cleaned_options,
                "correct_answer": answer,
                "explanation": _clip(explanation, 500),
            }
        )
    return cleaned


def parse_lesson_payload(raw: str, *, math: bool) -> dict | None:
    """Return a lesson dict, or None when the model admits the notes are not enough."""
    data = extract_json(raw)
    if data.get("insufficient") is True:
        return None

    example = data.get("example") if isinstance(data.get("example"), dict) else {}
    steps_raw = example.get("steps") or []
    if not isinstance(steps_raw, list):
        raise ValueError("steps must be a list")
    steps = [_clip(step, 240) for step in steps_raw if isinstance(step, str) and step.strip()]
    if math and len(steps) < 2:
        raise ValueError("math lesson needs hint steps")
    steps = steps[:4]

    objective = _one_sentence(data.get("objective"))
    explanation = _clip(data.get("explanation"), 1200)
    prompt = _clip(example.get("prompt"), 600)
    checks = _checks(data.get("checks"))
    blob = "\n".join([objective, explanation, prompt, *steps])
    _rejects_latex(blob)
    if math and _leaks_final_answer(blob):
        raise ValueError("math example leaked the final answer")

    return {
        "objective": objective,
        "explanation": explanation,
        "example": {
            "prompt": prompt,
            "steps": steps,
            "withheld": True if math else bool(example.get("withheld")),
        },
        "checks": checks,
    }


def _difficulty(hint: str | None) -> str:
    return hint if hint in _DIFFICULTIES else "level_4"


def _load_kp(knowledge_point_id: int) -> KnowledgePoint | None:
    return (
        KnowledgePoint.query.options(joinedload(KnowledgePoint.topic).joinedload(Topic.subject))
        .filter_by(id=knowledge_point_id)
        .first()
    )


class LessonService:
    def __init__(self, store, llm, top_k: int = 4, similarity_threshold: float = 0.65):
        self.store = store
        self.llm = llm
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold

    @staticmethod
    def resolve_target(user_id: int, knowledge_point_id: int | None) -> LessonTarget:
        stats = AnalyticsService.aggregate_by_knowledge_point(user_id)
        if knowledge_point_id is None:
            weakest = pick_weakest(stats)
            if weakest is None:
                raise LessonError(
                    "未有測驗紀錄，未知邊個知識點最弱。請先完成一次測驗，或由分析頁揀一個弱項。",
                    409,
                )
            knowledge_point_id = weakest.knowledge_point_id
            picked = True
        else:
            picked = False

        kp = _load_kp(knowledge_point_id)
        if kp is None or kp.topic is None or kp.topic.subject is None:
            raise LessonError("找不到這個知識點", 404)
        matched = next((item for item in stats if item.knowledge_point_id == kp.id), None)
        return LessonTarget(
            knowledge_point=kp,
            mastery_percent=matched.mastery_percent if matched else None,
            picked_weakest=picked,
        )

    @staticmethod
    def reusable_public(user_id: int, knowledge_point_id: int) -> dict | None:
        lesson = _latest_lesson(user_id, knowledge_point_id)
        if lesson is None or lesson.attempt_id is None:
            return None
        attempt = QuizAttempt.query.filter_by(id=lesson.attempt_id, user_id=user_id).first()
        if attempt is None or attempt.status != "in_progress":
            return None
        return _public_lesson(lesson, attempt)

    @staticmethod
    def public_by_id(user_id: int, lesson_id: int) -> dict | None:
        lesson = MicroLesson.query.filter_by(id=lesson_id, user_id=user_id).first()
        if lesson is None:
            return None
        attempt = None
        if lesson.attempt_id is not None:
            attempt = QuizAttempt.query.filter_by(id=lesson.attempt_id, user_id=user_id).first()
        return _public_lesson(lesson, attempt)

    @staticmethod
    def latest_public(user_id: int, knowledge_point_id: int | None) -> dict | None:
        lesson = _latest_lesson(user_id, knowledge_point_id)
        if lesson is None:
            return None
        attempt = None
        if lesson.attempt_id is not None:
            attempt = QuizAttempt.query.filter_by(id=lesson.attempt_id, user_id=user_id).first()
        return _public_lesson(lesson, attempt)

    def generate(self, user_id: int, target: LessonTarget) -> LessonOutcome:
        kp = target.knowledge_point
        subject_code = chroma_subject(kp.topic.subject.code)
        label = f"{kp.topic.name_zh} — {kp.name_zh}"
        if not subject_code:
            return LessonOutcome(_insufficient(kp, "這個知識點未能對應 DSE 科目，所以不會生成課堂。"), 200)

        hits = self.store.query(
            query_text=f"{kp.topic.name_zh} {kp.name_zh} {kp.name_en} DSE",
            top_k=self.top_k,
            subject_filter=subject_code,
            similarity_threshold=self.similarity_threshold,
        )
        hits = [hit for hit in hits if not is_personal(getattr(hit, "metadata", None))]
        if not hits:
            return LessonOutcome(
                _insufficient(
                    kp,
                    f"資料庫未有足夠的 DSE 筆記可以講「{label}」。系統不會硬作內容，亦不會用私人筆記代替課程資料。",
                ),
                200,
            )

        if not getattr(self.llm, "available", False):
            raise LessonError("未設定 LLM API key，未能生成課堂", 503)

        numbered = _format_sources(hits)
        mastery = (
            f"這位學生在此知識點的掌握度約 {target.mastery_percent}%。"
            if target.mastery_percent is not None
            else "這位學生未有此知識點的作答紀錄。"
        )
        math = subject_code == "math"
        user_message = (
            f"科目：{subject_code}\n"
            f"課題：{kp.topic.name_zh}\n"
            f"知識點：{kp.name_zh}（{kp.name_en}）\n"
            f"{mastery}\n"
            f"數學例題必須只給步驟提示：{'是' if math else '否'}\n\n"
            f"## 參考資料\n{numbered}"
        )
        try:
            raw = self.llm.complete(
                user_message,
                system=LESSON_SYSTEM_PROMPT,
                max_tokens=1800,
                temperature=0.2,
                json_mode=True,
            )
        except LLMNotConfigured as exc:
            raise LessonError("未設定 LLM API key，未能生成課堂", 503) from exc

        parsed = parse_lesson_payload(raw, math=math)
        if parsed is None:
            return LessonOutcome(
                _insufficient(kp, f"檢索到的 DSE 筆記不足以講清「{label}」，所以不會硬作課堂。"),
                200,
            )

        sources = [_source_payload(hit) for hit in hits]
        attempt = _persist(user_id, kp, parsed, sources, subject_code)
        lesson = MicroLesson.query.filter_by(attempt_id=attempt.id, user_id=user_id).one()
        return LessonOutcome(_public_lesson(lesson, attempt), 201)


def _latest_lesson(user_id: int, knowledge_point_id: int | None) -> MicroLesson | None:
    query = MicroLesson.query.filter_by(user_id=user_id)
    if knowledge_point_id is not None:
        query = query.filter_by(knowledge_point_id=knowledge_point_id)
    return query.order_by(MicroLesson.created_at.desc(), MicroLesson.id.desc()).first()


def _insufficient(kp: KnowledgePoint, message: str) -> dict:
    return {
        "status": "insufficient",
        "message": message,
        "knowledge_point": {
            "id": kp.id,
            "name_zh": kp.name_zh,
            "topic": kp.topic.name_zh if kp.topic else "",
        },
    }


def _format_sources(hits) -> str:
    parts = []
    for index, hit in enumerate(hits, 1):
        text = (hit.text or "").strip()
        parts.append(f"[資料 {index}]\n{text[:800]}")
    return "\n\n".join(parts)


def _source_payload(hit) -> dict:
    meta = hit.metadata or {}
    return {
        "id": hit.id,
        "subject": meta.get("subject"),
        "content_type": meta.get("content_type"),
        "relevance": round(float(hit.relevance_score), 3),
        "preview": (hit.text or "")[:200],
    }


def _persist(user_id: int, kp: KnowledgePoint, parsed: dict, sources: list[dict], subject_code: str) -> QuizAttempt:
    questions = []
    for check in parsed["checks"]:
        question = Question(
            knowledge_point_id=kp.id,
            question_type="mc",
            difficulty=_difficulty(kp.dse_level_hint),
            stem=check["stem"],
            options_json=json.dumps(check["options"], ensure_ascii=False),
            correct_answer=check["correct_answer"],
            explanation=check["explanation"],
            source="lesson_check",
        )
        db.session.add(question)
        questions.append(question)
    db.session.flush()

    attempt = QuizAttempt(
        user_id=user_id,
        subject_id=kp.topic.subject_id,
        topic_id=kp.topic_id,
        title=f"微課堂：{kp.name_zh}"[:200],
        difficulty=_difficulty(kp.dse_level_hint),
        total_questions=len(questions),
        status="in_progress",
        question_ids_json=json.dumps([question.id for question in questions]),
    )
    db.session.add(attempt)
    db.session.flush()

    lesson = MicroLesson(
        user_id=user_id,
        knowledge_point_id=kp.id,
        attempt_id=attempt.id,
        objective=parsed["objective"],
        explanation=parsed["explanation"],
        example_json=json.dumps(parsed["example"], ensure_ascii=False),
        sources_json=json.dumps(sources, ensure_ascii=False),
    )
    db.session.add(lesson)
    db.session.commit()
    logger.info(
        "stored micro lesson for user %s kp %s subject %s",
        user_id,
        kp.id,
        subject_code,
    )
    return attempt


def _questions_for(attempt: QuizAttempt | None) -> list[Question]:
    if attempt is None:
        return []
    ids = json.loads(attempt.question_ids_json or "[]")
    if not ids:
        return []
    found = {question.id: question for question in Question.query.filter(Question.id.in_(ids)).all()}
    return [found[item] for item in ids if item in found]


def _public_lesson(lesson: MicroLesson, attempt: QuizAttempt | None) -> dict:
    kp = lesson.knowledge_point or _load_kp(lesson.knowledge_point_id)
    topic_name = kp.topic.name_zh if kp and kp.topic else ""
    subject_code = kp.topic.subject.code if kp and kp.topic and kp.topic.subject else ""
    example = json.loads(lesson.example_json or "{}")
    return {
        "status": "ready",
        "id": lesson.id,
        "duration_minutes": LESSON_MINUTES,
        "knowledge_point": {
            "id": lesson.knowledge_point_id,
            "name_zh": kp.name_zh if kp else "",
            "topic": topic_name,
            "subject": chroma_subject(subject_code) or "",
        },
        "objective": lesson.objective,
        "explanation": lesson.explanation,
        "example": {
            "prompt": example.get("prompt") or "",
            "steps": example.get("steps") or [],
            "withheld": bool(example.get("withheld")),
        },
        "sources": json.loads(lesson.sources_json or "[]"),
        "attempt_id": attempt.id if attempt else None,
        "attempt_status": attempt.status if attempt else None,
        "questions": [
            {
                "id": question.id,
                "index": index,
                "stem": question.stem,
                "options": json.loads(question.options_json or "{}"),
            }
            for index, question in enumerate(_questions_for(attempt), 1)
        ],
    }
