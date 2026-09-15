"""Inspect the ChromaDB vector store contents.

Usage:
    python scripts/inspect_chroma.py                 # list all documents
    python scripts/inspect_chroma.py --full          # print full text
    python scripts/inspect_chroma.py --subject math  # filter by subject
    python scripts/inspect_chroma.py --search "判別式" # semantic search demo
    python scripts/inspect_chroma.py --top-k 3
"""
import argparse
import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

# Windows consoles default to a legacy codepage that cannot print CJK text.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import create_app
from app.services.chroma_store import init_chroma_store


def truncate(text: str, limit: int = 120) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "…"


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect ChromaDB contents")
    parser.add_argument("--full", action="store_true", help="Print full document text")
    parser.add_argument("--subject", help="Filter by subject (chinese|math|english)")
    parser.add_argument("--search", help="Run a semantic search query instead of listing")
    parser.add_argument("--top-k", type=int, default=5, help="Results for --search")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        store = init_chroma_store(app.config)
        collection = store._collection  # noqa: SLF001 - inspection script

        print("=" * 72)
        print(f"Collection : {store.collection_name}")
        print(f"Persist dir: {store.persist_dir}")
        print(f"Documents  : {store.document_count}")
        print("=" * 72)

        if store.document_count == 0:
            print("Collection is empty. Run: python scripts/init_chroma.py")
            return

        # ---- Semantic search mode ----
        if args.search:
            print(f"\nQuery: {args.search!r}  (top {args.top_k})\n")
            results = collection.query(
                query_texts=[args.search],
                n_results=args.top_k,
                include=["documents", "metadatas", "distances"],
            )
            for i, (doc, meta, dist) in enumerate(
                zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                ),
                1,
            ):
                print(f"[{i}] relevance={1 - dist:.3f}  {meta}")
                print("    " + (doc if args.full else truncate(doc)))
                print()
            return

        # ---- List mode ----
        where = {"subject": args.subject} if args.subject else None
        data = collection.get(include=["documents", "metadatas"], where=where)

        ids = data["ids"]
        docs = data["documents"]
        metas = data["metadatas"]
        print(f"\nListing {len(ids)} document(s)"
              + (f" where subject={args.subject}" if args.subject else "") + "\n")

        for i, (doc_id, doc, meta) in enumerate(zip(ids, docs, metas), 1):
            meta_bits = " | ".join(f"{k}={v}" for k, v in (meta or {}).items())
            print(f"[{i}] {doc_id}")
            print(f"    metadata: {meta_bits}")
            print("    " + (doc if args.full else truncate(doc)))
            print()


if __name__ == "__main__":
    main()
