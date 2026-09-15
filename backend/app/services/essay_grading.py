"""English Essay Grading service — simulates HKEAA DSE marking (C/L/O dimensions)."""
from __future__ import annotations

import logging

from app.services.llm_client import LLMClient, extract_json

logger = logging.getLogger(__name__)

ESSAY_GRADING_PROMPT = """你是一位 DSE 英文科閱卷員（Marker），嚴格按照 HKEAA 評分標準批改學生作文。

評分維度（各 1-7 分）：
1. Content (內容)：論點是否切題、是否有充分支持、例子是否相關
2. Language (語言)：詞彙豐富度、文法準確度、句式多樣性
3. Organization (組織)：段落結構、連貫性、過渡詞運用

你必須以以下 JSON 格式輸出（不要任何額外文字或 markdown）：
{
  "content_score": <1-7>,
  "content_feedback": "具體評語",
  "language_score": <1-7>,
  "language_feedback": "具體評語",
  "grammar_errors": [
    {
      "original": "原文錯誤片段",
      "corrected": "改正後",
      "error_type": "grammar|vocabulary|punctuation|spelling",
      "explanation": "錯誤原因"
    }
  ],
  "vocabulary_upgrades": [
    {
      "original": "學生用詞",
      "upgraded": "高級替換",
      "context": "用法說明"
    }
  ],
  "organization_score": <1-7>,
  "organization_feedback": "具體評語",
  "overall_score": <總分 1-21>,
  "overall_feedback": "整體評語（勉勵為主）",
  "strengths": ["優點1", "優點2"],
  "areas_for_improvement": ["改善方向1", "改善方向2"]
}
"""


class EssayGradingService:
    """Grades English essays using HKEAA DSE marking criteria."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def grade_essay(self, essay_text: str, task_type: str = "argumentative") -> dict:
        """Grade a DSE English essay with C/L/O scores and feedback."""
        if not self.llm.available:
            return {"error": "LLM API key not configured"}

        user_message = (
            f"Please grade the following DSE English essay "
            f"(Task type: {task_type}):\n\n{essay_text}"
        )

        try:
            raw_text = self.llm.complete(
                user_message,
                system=ESSAY_GRADING_PROMPT,
                max_tokens=8192,
                temperature=0.3,
                json_mode=True,
            )
            result = extract_json(raw_text)
            result["task_type"] = task_type
            result["word_count"] = len(essay_text.split())
            return result
        except ValueError as e:
            logger.error("Failed to parse essay grading JSON: %s", e)
            return {"error": f"Invalid grading output: {e}"}
        except Exception as e:  # noqa: BLE001 - surface a safe error to the client
            logger.error("Essay grading failed: %s", e)
            return {"error": str(e)}
