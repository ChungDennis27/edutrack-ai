"""Ingest the DSE classical Chinese texts into ChromaDB (idempotent).

Reads the curated texts from ``app/services/classical_texts.py``, chunks them
per paragraph (原文 + 譯文 + 注解 + 修辭 + 考核重點) and upserts them into the
vector store so the RAG tutor can retrieve them.

Usage:
    python scripts/ingest_classical.py                 # replace + ingest
    python scripts/ingest_classical.py --keep-existing # upsert without clearing
"""
import argparse
import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import create_app  # noqa: E402
from app.services.chroma_store import (  # noqa: E402
    ChromaVectorStore,
    DocumentChunk,
    init_chroma_store,
)
from app.services.classical_texts import CLASSICAL_TEXTS  # noqa: E402

CLASSICAL_FILTER = {"$and": [{"subject": "chinese"}, {"content_type": "classical_chinese"}]}


def build_chunks() -> list[DocumentChunk]:
    """One chunk per paragraph, carrying the passage-level context."""
    chunks: list[DocumentChunk] = []

    for text in CLASSICAL_TEXTS:
        for index, paragraph in enumerate(text["paragraphs"]):
            content = (
                f"【{text['title']}】\n"
                f"作者：{text['author']}（{text['dynasty']}）\n"
                f"出處：{text['source']}\n"
                f"原文：{paragraph['original']}\n"
                f"譯文：{paragraph['translation']}\n"
                f"注解：{paragraph['notes']}\n"
                f"修辭：{text['rhetoric']}\n"
                f"考核重點：{text['exam_tips']}"
            )
            metadata = {
                "subject": "chinese",
                "content_type": "classical_chinese",
                "passage_title": text["title"],
                "author": text["author"],
                "source": text["source"],
                "dynasty": text["dynasty"],
                "paragraph_index": index,
                "language": "zh-HK",
            }
            chunks.append(
                DocumentChunk(
                    id=ChromaVectorStore.make_id(content, metadata),
                    text=content,
                    metadata=metadata,
                )
            )

    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest classical Chinese texts into ChromaDB")
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Upsert without deleting existing classical_chinese chunks first",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        store = init_chroma_store(app.config)

        if not args.keep_existing:
            store.delete_where(CLASSICAL_FILTER)

        chunks = build_chunks()
        written = store.upsert_chunks(chunks)

        by_passage: dict[str, int] = {}
        for chunk in chunks:
            by_passage[chunk.metadata["passage_title"]] = (
                by_passage.get(chunk.metadata["passage_title"], 0) + 1
            )

        print(f"Ingested {written} chunks from {len(CLASSICAL_TEXTS)} passages.")
        for title, count in by_passage.items():
            print(f"  - {title}: {count} chunk(s)")
        print(f"Collection total: {store.document_count} documents.")


if __name__ == "__main__":
    main()
