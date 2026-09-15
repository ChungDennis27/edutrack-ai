"""Unified AI engine: ChromaDB retrieval + LLM orchestration."""
from __future__ import annotations

import json
import logging
from typing import Generator

from app.services.chroma_store import ChromaVectorStore, RetrievalResult
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

DSE_TUTOR_SYSTEM_PROMPT = """你是一位溫柔、引導式的香港 DSE 補習導師。

規則：
1. 只根據提供的「參考資料」回答，不可捏造 DSE 評分標準或試題內容。
2. 若參考資料不足以回答，請誠實告知學生，並建議查閱 HKEAA 官方課程指引。
3. 數學題禁止直接給出完整答案，應以步驟提示（Hints）引導學生思考。
4. 文言文解釋須對照原文，說明字詞義、修辭手法及考核重點。
5. 使用繁體中文（香港用語），語氣親切但專業。
6. 數學公式使用 LaTeX 格式（$...$ 或 $$...$$）。
"""


class AIEngine:
    """Orchestrates RAG retrieval and LLM calls."""

    def __init__(
        self,
        vector_store: ChromaVectorStore,
        llm: LLMClient,
        top_k: int = 5,
        similarity_threshold: float = 0.65,
    ):
        self.vector_store = vector_store
        self.llm = llm
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold

    def retrieve_context(
        self,
        query: str,
        subject: str | None = None,
    ) -> list[RetrievalResult]:
        return self.vector_store.query(
            query_text=query,
            top_k=self.top_k,
            subject_filter=subject,
            similarity_threshold=self.similarity_threshold,
        )

    @staticmethod
    def format_context(chunks: list[RetrievalResult]) -> str:
        if not chunks:
            return "（無相關參考資料）"
        parts = []
        for i, chunk in enumerate(chunks, 1):
            subject = chunk.metadata.get("subject", "unknown")
            parts.append(
                f"[資料 {i} | {subject} | 相關度 {chunk.relevance_score:.2f}]\n{chunk.text}"
            )
        return "\n\n---\n\n".join(parts)

    def build_rag_prompt(
        self, user_query: str, subject: str | None = None
    ) -> tuple[str, list[RetrievalResult]]:
        chunks = self.retrieve_context(user_query, subject)
        context = self.format_context(chunks)
        user_message = f"""## 參考資料
{context}

## 學生問題
{user_query}"""
        return user_message, chunks

    def chat_stream(
        self,
        user_query: str,
        subject: str | None = None,
    ) -> Generator[str, None, None]:
        """Stream RAG-augmented tutor response via SSE-compatible chunks."""
        if not self.llm.available:
            yield json.dumps({"error": "LLM API key not configured"})
            return

        user_message, _ = self.build_rag_prompt(user_query, subject)
        yield from self.llm.stream(
            user_message,
            system=DSE_TUTOR_SYSTEM_PROMPT,
            max_tokens=4096,
        )

    def chat(self, user_query: str, subject: str | None = None) -> dict:
        """Non-streaming RAG chat — returns answer + source citations."""
        if not self.llm.available:
            return {"error": "LLM API key not configured", "sources": []}

        user_message, chunks = self.build_rag_prompt(user_query, subject)
        answer = self.llm.complete(
            user_message,
            system=DSE_TUTOR_SYSTEM_PROMPT,
            max_tokens=4096,
        )

        return {
            "answer": answer,
            "sources": [
                {
                    "id": c.id,
                    "subject": c.metadata.get("subject"),
                    "content_type": c.metadata.get("content_type"),
                    "relevance": round(c.relevance_score, 3),
                    "preview": c.text[:200],
                }
                for c in chunks
            ],
        }
