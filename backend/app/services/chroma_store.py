"""ChromaDB initialization, ingestion, and RAG retrieval core."""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from app.services.retrieval_scope import PERSONAL_ORIGIN, is_personal, visible_to

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """A single RAG chunk with rich metadata for DSE content."""
    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    id: str
    text: str
    metadata: dict[str, Any]
    distance: float
    relevance_score: float  # 1 - distance (cosine)


class ChromaVectorStore:
    """
    Local ChromaDB wrapper for DSE knowledge base.

    Chunking strategy:
    - Chinese 文言文: split by paragraph (原文/譯文 pairs), preserve 篇名 metadata
    - Math: split by topic + step, keep LaTeX blocks intact (never split mid-formula)
    - English: split by exemplar paragraph with C/L/O marking scheme tags
    - Bilingual: use multilingual embedding model (paraphrase-multilingual-MiniLM)
    """

    def __init__(
        self,
        persist_dir: str,
        collection_name: str = "dse_knowledge_base",
        embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        user_collection_name: str = "user_knowledge_base",
    ):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self.user_collection_name = user_collection_name

        self._client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        # Separate collection so a private note cannot crowd out, or leak into, DSE search.
        self._user_collection = self._client.get_or_create_collection(
            name=user_collection_name,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def document_count(self) -> int:
        return self._collection.count()

    # ------------------------------------------------------------------
    # Chunking helpers
    # ------------------------------------------------------------------

    @staticmethod
    def make_id(text: str, metadata: dict) -> str:
        raw = text[:200] + json.dumps(metadata, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def chunk_classical_chinese(
        passage_title: str,
        original: str,
        translation: str,
        annotations: str = "",
        rhetoric: str = "",
    ) -> list[DocumentChunk]:
        """Split 文言文 by paragraph, keeping 原文/譯文 paired."""
        chunks: list[DocumentChunk] = []
        orig_paras = [p.strip() for p in original.split("\n\n") if p.strip()]
        trans_paras = [p.strip() for p in translation.split("\n\n") if p.strip()]

        for i, orig in enumerate(orig_paras):
            trans = trans_paras[i] if i < len(trans_paras) else ""
            text = f"【{passage_title}】\n原文：{orig}\n譯文：{trans}"
            if annotations:
                text += f"\n注解：{annotations}"
            if rhetoric:
                text += f"\n修辭：{rhetoric}"

            meta = {
                "subject": "chinese",
                "content_type": "classical_chinese",
                "passage_title": passage_title,
                "paragraph_index": i,
                "language": "zh-HK",
            }
            chunks.append(DocumentChunk(id=ChromaVectorStore.make_id(text, meta), text=text, metadata=meta))
        return chunks

    @staticmethod
    def chunk_math_content(
        topic: str,
        content: str,
        marking_scheme: str = "",
        dse_level: str = "level_4",
    ) -> list[DocumentChunk]:
        """
        Split math content by section headers.
        Preserves LaTeX blocks — sections starting with '$' or '$$' stay intact.
        """
        chunks: list[DocumentChunk] = []
        sections = content.split("\n## ")
        for i, section in enumerate(sections):
            section = section.strip()
            if not section:
                continue
            if i > 0:
                section = "## " + section

            text = f"【{topic}】\n{section}"
            if marking_scheme:
                text += f"\n\n評分標準：{marking_scheme}"

            meta = {
                "subject": "math",
                "content_type": "math_topic",
                "topic": topic,
                "dse_level": dse_level,
                "has_latex": "$" in section,
                "language": "zh-HK",
            }
            chunks.append(DocumentChunk(id=ChromaVectorStore.make_id(text, meta), text=text, metadata=meta))
        return chunks

    @staticmethod
    def chunk_english_exemplar(
        title: str,
        content: str,
        content_score: str = "",
        language_score: str = "",
        organization_score: str = "",
    ) -> list[DocumentChunk]:
        """Split English exemplars by paragraph with HKEAA C/L/O metadata."""
        chunks: list[DocumentChunk] = []
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

        for i, para in enumerate(paragraphs):
            text = f"【{title}】\n{para}"
            meta = {
                "subject": "english",
                "content_type": "exemplar",
                "title": title,
                "paragraph_index": i,
                "content_criteria": content_score,
                "language_criteria": language_score,
                "organization_criteria": organization_score,
                "language": "en-HK",
            }
            chunks.append(DocumentChunk(id=ChromaVectorStore.make_id(text, meta), text=text, metadata=meta))
        return chunks

    # ------------------------------------------------------------------
    # Write / Read
    # ------------------------------------------------------------------

    @staticmethod
    def _where_clause(filters: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not filters:
            return None
        if len(filters) == 1:
            return filters[0]
        return {"$and": filters}

    def _upsert(self, collection, collection_name: str, chunks: list[DocumentChunk], batch_size: int) -> int:
        if not chunks:
            return 0
        total = 0
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            collection.upsert(
                ids=[c.id for c in batch],
                documents=[c.text for c in batch],
                metadatas=[c.metadata for c in batch],
            )
            total += len(batch)
        logger.info("Upserted %d chunks into '%s'", total, collection_name)
        return total

    def upsert_chunks(self, chunks: list[DocumentChunk], batch_size: int = 50) -> int:
        """Insert or update DSE document chunks into ChromaDB."""
        return self._upsert(self._collection, self.collection_name, chunks, batch_size)

    def upsert_user_chunks(
        self,
        chunks: list[DocumentChunk],
        user_id: str | int,
        batch_size: int = 50,
    ) -> int:
        """Insert private notes. Refuses a chunk that is not tagged for this student."""
        owner = str(user_id)
        safe: list[DocumentChunk] = []
        for chunk in chunks:
            meta = dict(chunk.metadata)
            if str(meta.get("user_id") or "") != owner or meta.get("origin") != PERSONAL_ORIGIN:
                raise ValueError("user chunk is missing a matching user_id")
            meta["user_id"] = owner
            meta["origin"] = PERSONAL_ORIGIN
            safe.append(DocumentChunk(id=chunk.id, text=chunk.text, metadata=meta))
        return self._upsert(self._user_collection, self.user_collection_name, safe, batch_size)

    def _search(
        self,
        collection,
        query_text: str,
        n_results: int,
        where: dict[str, Any] | None,
        similarity_threshold: float,
    ) -> list[RetrievalResult]:
        if n_results <= 0 or not query_text.strip():
            return []
        try:
            available = (
                collection.count()
                if where is None
                else len(collection.get(where=where, include=[])["ids"])
            )
        except Exception:
            logger.exception("Chroma count failed")
            raise
        if available <= 0:
            return []

        results = collection.query(
            query_texts=[query_text],
            n_results=min(n_results, available),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        retrieved: list[RetrievalResult] = []
        if not results["ids"] or not results["ids"][0]:
            return retrieved

        for doc_id, doc, meta, dist in zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            relevance = 1.0 - dist
            if relevance >= similarity_threshold:
                retrieved.append(
                    RetrievalResult(
                        id=doc_id,
                        text=doc,
                        metadata=meta or {},
                        distance=dist,
                        relevance_score=relevance,
                    )
                )
        return retrieved

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        subject_filter: str | None = None,
        content_type_filter: str | None = None,
        similarity_threshold: float = 0.65,
    ) -> list[RetrievalResult]:
        """
        Semantic search over the shared DSE collection.
        Personal notes are stored separately and dropped here if one ever lands in this collection.
        """
        filters = []
        if subject_filter:
            filters.append({"subject": subject_filter})
        if content_type_filter:
            filters.append({"content_type": content_type_filter})
        hits = self._search(
            self._collection,
            query_text,
            top_k,
            self._where_clause(filters),
            similarity_threshold,
        )
        return [hit for hit in hits if not is_personal(hit.metadata)]

    def query_user_docs(
        self,
        query_text: str,
        user_id: str | int,
        top_k: int = 5,
        subject_filter: str | None = None,
        similarity_threshold: float = 0.65,
    ) -> list[RetrievalResult]:
        """Search one student's notes. The where-clause and a post-filter both require user_id."""
        owner = str(user_id)
        filters = [{"origin": PERSONAL_ORIGIN}, {"user_id": owner}]
        if subject_filter:
            filters.append({"subject": subject_filter})
        hits = self._search(
            self._user_collection,
            query_text,
            top_k,
            self._where_clause(filters),
            similarity_threshold,
        )
        return [hit for hit in hits if visible_to(hit.metadata, "my_docs", owner)]

    def delete_user_document(self, user_id: str | int, document_id: str | int) -> None:
        """Delete one student's chunks for one file. No-op when none match."""
        where = {
            "$and": [
                {"origin": PERSONAL_ORIGIN},
                {"user_id": str(user_id)},
                {"document_id": str(document_id)},
            ]
        }
        if self._user_collection.count() == 0:
            return
        matched = self._user_collection.get(where=where, include=[])
        if not matched["ids"]:
            return
        self._user_collection.delete(where=where)

    def count_where(self, where: dict[str, Any]) -> int:
        """Count chunks matching a metadata filter."""
        result = self._collection.get(where=where, include=[])
        return len(result["ids"])

    def delete_where(self, where: dict[str, Any]) -> None:
        """Delete chunks matching a metadata filter (no-op if none match)."""
        self._collection.delete(where=where)

    def delete_collection(self) -> None:
        self._client.delete_collection(self.collection_name)
        logger.info("Deleted collection '%s'", self.collection_name)


def init_chroma_store(app_config) -> ChromaVectorStore:
    """Factory: create ChromaVectorStore from Flask config."""
    return ChromaVectorStore(
        persist_dir=app_config["CHROMA_PERSIST_DIR"],
        collection_name=app_config["CHROMA_COLLECTION_NAME"],
        embedding_model=app_config["EMBEDDING_MODEL"],
        user_collection_name=app_config.get("CHROMA_USER_COLLECTION_NAME", "user_knowledge_base"),
    )


def seed_sample_dse_materials(store: ChromaVectorStore) -> int:
    """
    Seed minimal DSE sample content for development / demo.
    Replace with full syllabus ingestion pipeline in production.
    """
    all_chunks: list[DocumentChunk] = []

    # Sample 文言文
    all_chunks.extend(
        store.chunk_classical_chinese(
            passage_title="論仁",
            original="子曰：「不仁者，不可以久處約，不可以長處樂。」",
            translation="孔子說：「沒有仁德的人，不能長久處於貧困中，也不能長久處於安樂中。」",
            annotations="「約」指貧困；「樂」指安樂。",
            rhetoric="引用孔子語錄，闡述仁與處境的關係。",
        )
    )

    # Sample Math
    all_chunks.extend(
        store.chunk_math_content(
            topic="二次方程",
            content="## 求根公式\n一元二次方程 $ax^2+bx+c=0$ 的解為：\n$$x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$$\n## 判別式\n當 $\\Delta = b^2-4ac > 0$ 時，方程有兩個不等實根。",
            marking_scheme="M1: 正確列出判別式\nA1: 正確計算根的值",
            dse_level="level_4",
        )
    )

    # Sample English
    all_chunks.extend(
        store.chunk_english_exemplar(
            title="DSE English Paper 2 — Argumentative Essay Sample",
            content="In recent years, the debate over whether technology enhances or hinders education has intensified.\n\nProponents argue that digital tools provide unprecedented access to information.",
            content_score="Content: 4/7 — Ideas relevant but development could be deeper",
            language_score="Language: 5/7 — Good vocabulary range",
            organization_score="Organization: 4/7 — Clear paragraphing",
        )
    )

    return store.upsert_chunks(all_chunks)
