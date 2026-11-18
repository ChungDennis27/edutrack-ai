"""Unified AI engine: ChromaDB retrieval + LLM orchestration."""
from __future__ import annotations

import json
import logging
from typing import Generator

from app.services.chroma_store import ChromaVectorStore, RetrievalResult
from app.services.llm_client import LLMClient
from app.services.prompt_rules import PLAIN_MATH_RULE
from app.services.retrieval_scope import merge_by_relevance, normalize_scope, scope_note
from app.services.student_context import append_student_context, normalize_history

logger = logging.getLogger(__name__)

DSE_TUTOR_SYSTEM_PROMPT = """你是一位溫柔、引導式的香港 DSE 補習導師。

規則：
1. 課程內容只可根據提供的「參考資料」回答，不可捏造 DSE 評分標準或試題內容。標示為「我的筆記」的片段是這位學生自己上傳的檔案，可以引用，並註明來自學生筆記。
2. 若參考資料不足以回答課程問題，請誠實告知學生，並建議查閱 HKEAA 官方課程指引。若學生問自己的弱項、進度、錯題或待複習，而系統提示有學習背景，必須根據該背景回答，唔好話自己冇資料。
3. 數學題禁止直接給出完整答案，應以步驟提示（Hints）引導學生思考。
4. 文言文解釋須對照原文，說明字詞義、修辭手法及考核重點。
5. 使用繁體中文（香港用語），語氣親切但專業。
6. 可用 Markdown 排版（清單、粗體、標題）令答案易讀。
""" + PLAIN_MATH_RULE


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
        scope: str | None = None,
        user_id: str | int | None = None,
    ) -> list[RetrievalResult]:
        chosen = normalize_scope(scope)
        if chosen == "my_docs":
            if user_id is None:
                return []
            return self.vector_store.query_user_docs(
                query_text=query,
                user_id=user_id,
                top_k=self.top_k,
                subject_filter=subject,
                similarity_threshold=self.similarity_threshold,
            )
        dse_hits = self.vector_store.query(
            query_text=query,
            top_k=self.top_k,
            subject_filter=subject,
            similarity_threshold=self.similarity_threshold,
        )
        if chosen != "all" or user_id is None:
            return dse_hits
        own_hits = self.vector_store.query_user_docs(
            query_text=query,
            user_id=user_id,
            top_k=self.top_k,
            subject_filter=subject,
            similarity_threshold=self.similarity_threshold,
        )
        return merge_by_relevance([dse_hits, own_hits], self.top_k)

    @staticmethod
    def format_context(chunks: list[RetrievalResult]) -> str:
        if not chunks:
            return "（無相關參考資料）"
        parts = []
        for i, chunk in enumerate(chunks, 1):
            meta = chunk.metadata or {}
            if meta.get("origin") == "user_upload":
                label = f"我的筆記｜{meta.get('doc_title') or '筆記'}"
            else:
                label = str(meta.get("subject", "unknown"))
            parts.append(
                f"[資料 {i} | {label} | 相關度 {chunk.relevance_score:.2f}]\n{chunk.text}"
            )
        return "\n\n---\n\n".join(parts)

    def build_rag_prompt(
        self,
        user_query: str,
        subject: str | None = None,
        scope: str | None = None,
        user_id: str | int | None = None,
    ) -> tuple[str, list[RetrievalResult]]:
        chosen = normalize_scope(scope)
        chunks = self.retrieve_context(user_query, subject, chosen, user_id)
        context = self.format_context(chunks)
        user_message = f"""## 檢索範圍
{scope_note(chosen)}

## 參考資料
{context}

## 學生問題
{user_query}"""
        return user_message, chunks

    def chat_stream(
        self,
        user_query: str,
        subject: str | None = None,
        history: list | None = None,
        student_context: str | None = None,
        scope: str | None = None,
        user_id: str | int | None = None,
    ) -> Generator[str, None, None]:
        """Stream RAG-augmented tutor response via SSE-compatible chunks."""
        if not self.llm.available:
            yield json.dumps({"error": "LLM API key not configured"})
            return

        user_message, _ = self.build_rag_prompt(user_query, subject, scope, user_id)
        yield from self.llm.stream(
            user_message,
            system=append_student_context(DSE_TUTOR_SYSTEM_PROMPT, student_context),
            max_tokens=4096,
            history=normalize_history(history),
        )

    def chat(
        self,
        user_query: str,
        subject: str | None = None,
        history: list | None = None,
        student_context: str | None = None,
        scope: str | None = None,
        user_id: str | int | None = None,
    ) -> dict:
        """Non-streaming RAG chat — returns answer + source citations."""
        if not self.llm.available:
            return {"error": "LLM API key not configured", "sources": []}

        user_message, chunks = self.build_rag_prompt(user_query, subject, scope, user_id)
        answer = self.llm.complete(
            user_message,
            system=append_student_context(DSE_TUTOR_SYSTEM_PROMPT, student_context),
            max_tokens=4096,
            history=normalize_history(history),
        )

        return {
            "answer": answer,
            "sources": [
                {
                    "id": c.id,
                    "subject": c.metadata.get("subject"),
                    "content_type": c.metadata.get("content_type"),
                    "origin": c.metadata.get("origin") or "dse",
                    "relevance": round(c.relevance_score, 3),
                    "preview": c.text[:200],
                }
                for c in chunks
            ],
        }
