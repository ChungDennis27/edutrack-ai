"""Math Step-by-Step Hint service — Method Marks guided problem solving."""
from __future__ import annotations

import json
import logging

from app.services.llm_client import LLMClient, extract_json
from app.services.prompt_rules import LATEX_FORMAT_RULE

logger = logging.getLogger(__name__)

MATH_HINT_PROMPT = """你是一位 DSE 數學科閱卷員。你的任務是引導學生逐步解題，而非直接給出答案。

嚴格規則：
1. 永遠不要直接給出最終答案或完整解答。
2. 根據 HKEAA「步驟分（Method Marks）」機制，循序漸進給出提示。
3. 每次只給一個 Hint，讓學生思考下一步。
4. 使用繁體中文（香港用語）解釋，數學公式用 LaTeX（$...$ 或 $$...$$）。
5. 若學生已給出部分正確步驟，給予肯定並引導下一步。
6. 若學生出錯，以提問方式引導他們發現錯誤，而非直接糾正。

輸出 JSON Schema：
{
  "hint_number": <第幾個提示>,
  "hint_text": "提示內容（可含 LaTeX）",
  "method_mark_target": "此提示對應的步驟分說明",
  "encouragement": "簡短鼓勵語",
  "is_final_hint": false,
  "next_step_question": "引導學生思考的問題"
}
""" + LATEX_FORMAT_RULE


class MathHintService:
    """Provides step-by-step hints for math problems using Method Marks approach."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def get_hint(
        self,
        problem: str,
        student_work: str = "",
        hint_history: list[str] | None = None,
        topic: str = "",
    ) -> dict:
        """Get the next hint for a math problem."""
        if not self.llm.available:
            return {"error": "LLM API key not configured"}

        parts = [f"題目：{problem}"]
        if topic:
            parts.append(f"課題：{topic}")
        if student_work:
            parts.append(f"學生目前作答：{student_work}")
        if hint_history:
            parts.append(
                f"已給出的提示：{json.dumps(hint_history, ensure_ascii=False)}"
            )

        parts.append("\n請給出下一個提示（hint），不要直接給答案。")
        user_message = "\n".join(parts)

        try:
            raw_text = self.llm.complete(
                user_message,
                system=MATH_HINT_PROMPT,
                max_tokens=4096,
                temperature=0.5,
                json_mode=True,
            )
            return extract_json(raw_text)
        except ValueError as e:
            logger.error("Failed to parse math hint JSON: %s", e)
            return {"error": f"Invalid hint output: {e}"}
        except Exception as e:  # noqa: BLE001
            logger.error("Math hint generation failed: %s", e)
            return {"error": str(e)}
