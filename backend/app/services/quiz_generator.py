"""Quiz generation service — LLM JSON mode + structured output validation."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.services.llm_client import LLMClient, extract_json

logger = logging.getLogger(__name__)

QUIZ_SYSTEM_PROMPT = """你是一位香港 DSE 出卷專家。你的任務是根據學生選擇的課題和難度，生成高質量的 DSE 風格測驗卷。

嚴格規則：
1. 必須以 JSON 格式輸出，不得包含任何 markdown 代碼塊標記（如 ```json）。
2. 數學公式必須使用 LaTeX 格式（行內用 $...$，獨立公式用 $$...$$）。
3. 選項必須有 4 個（A/B/C/D），只有一個正確答案。
4. 難度對應：level_3 = 基礎（合格率附近），level_4 = 中等，level_5 = 挑戰（**級），level_5pp = 頂尖（5**級）。
5. 每題必須包含詳細解析，說明考核重點和常見錯誤。
6. 使用繁體中文（香港用語）。

輸出 JSON Schema：
{
  "title": "測驗標題",
  "subject": "chinese|math|english",
  "difficulty": "level_3|level_4|level_5|level_5pp",
  "questions": [
    {
      "index": 1,
      "question_type": "mc",
      "stem": "題目內容（可含 LaTeX）",
      "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
      "correct_answer": "A",
      "explanation": "詳細解析",
      "knowledge_point_code": "知識點代碼（如 MATH-QUAD-01）",
      "dse_level_hint": "Level 4-5"
    }
  ]
}
"""


@dataclass
class GeneratedQuestion:
    index: int
    question_type: str
    stem: str
    options: dict[str, str]
    correct_answer: str
    explanation: str
    knowledge_point_code: str
    dse_level_hint: str


@dataclass
class GeneratedQuiz:
    title: str
    subject: str
    difficulty: str
    questions: list[GeneratedQuestion] = field(default_factory=list)


class QuizGenerationService:
    """Generates DSE-style quizzes using the LLM with structured JSON output."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def generate(
        self,
        subject: str,
        topic: str,
        difficulty: str,
        num_questions: int = 5,
        knowledge_point_codes: list[str] | None = None,
    ) -> GeneratedQuiz:
        """Generate a quiz with validated JSON output from the LLM."""
        if not self.llm.available:
            raise RuntimeError("LLM API key not configured")

        user_prompt = self._build_prompt(
            subject, topic, difficulty, num_questions, knowledge_point_codes
        )
        raw_text = self.llm.complete(
            user_prompt,
            system=QUIZ_SYSTEM_PROMPT,
            max_tokens=8192,
            temperature=0.7,
            json_mode=True,
        )
        return self._parse_quiz_json(raw_text, subject, difficulty)

    def _build_prompt(
        self,
        subject: str,
        topic: str,
        difficulty: str,
        num_questions: int,
        knowledge_point_codes: list[str] | None = None,
    ) -> str:
        parts = [
            f"請生成一份 DSE {self._subject_zh(subject)} 科測驗。",
            f"課題：{topic}",
            f"難度：{self._difficulty_zh(difficulty)}",
            f"題目數量：{num_questions} 題（多項選擇題）",
        ]
        if knowledge_point_codes:
            parts.append(f"考核知識點：{', '.join(knowledge_point_codes)}")
        parts.append("\n請直接輸出 JSON，不要任何額外文字。")
        return "\n".join(parts)

    @staticmethod
    def _subject_zh(code: str) -> str:
        return {"chinese": "中文", "math": "數學", "english": "英文"}.get(code, code)

    @staticmethod
    def _difficulty_zh(code: str) -> str:
        return {
            "level_3": "Level 3（基礎）",
            "level_4": "Level 4（中等）",
            "level_5": "Level 5（挑戰）",
            "level_5pp": "Level 5++（頂尖）",
        }.get(code, code)

    def _parse_quiz_json(
        self, raw_text: str, subject: str, difficulty: str
    ) -> GeneratedQuiz:
        """Parse and validate the LLM's JSON output."""
        try:
            data = extract_json(raw_text)
        except ValueError as e:
            logger.error("Failed to parse quiz JSON: %s", e)
            raise ValueError(f"LLM output is not valid JSON: {e}") from e

        questions = []
        for q in data.get("questions", []):
            questions.append(
                GeneratedQuestion(
                    index=q.get("index", len(questions) + 1),
                    question_type=q.get("question_type", "mc"),
                    stem=q.get("stem", ""),
                    options=q.get("options", {}),
                    correct_answer=q.get("correct_answer", ""),
                    explanation=q.get("explanation", ""),
                    knowledge_point_code=q.get("knowledge_point_code", ""),
                    dse_level_hint=q.get("dse_level_hint", ""),
                )
            )

        return GeneratedQuiz(
            title=data.get("title", f"{subject} Quiz"),
            subject=data.get("subject", subject),
            difficulty=data.get("difficulty", difficulty),
            questions=questions,
        )
