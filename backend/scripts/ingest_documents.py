"""Ingest DSE course materials (PDF / TXT / MD) into ChromaDB.

Place files under ``backend/data/materials/<subject>/<source_type>/`` then run::

    python scripts/ingest_documents.py                 # ingest everything
    python scripts/ingest_documents.py --subject math  # one subject
    python scripts/ingest_documents.py --reset         # clear + re-ingest
    python scripts/ingest_documents.py --if-empty      # skip if already ingested

source_type folders: syllabus | past_papers | notes | exemplars | texts
Optional per-file metadata: ``<file>.pdf.meta.yml`` (YAML).
"""
import argparse
import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app import create_app  # noqa: E402
from app.services.chroma_store import init_chroma_store  # noqa: E402
from app.services.document_ingest import (  # noqa: E402
    ORIGIN,
    build_chunks,
    iter_documents,
)

DEFAULT_DIR = backend_root / "data" / "materials"
MATERIALS_FILTER = {"origin": ORIGIN}


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest course materials into ChromaDB")
    parser.add_argument("--dir", default=str(DEFAULT_DIR), help="materials root directory")
    parser.add_argument("--subject", help="only ingest one subject folder")
    parser.add_argument("--reset", action="store_true", help="delete existing material chunks first")
    parser.add_argument("--if-empty", action="store_true", help="skip if materials already ingested")
    parser.add_argument("--size", type=int, default=800, help="chunk size (characters)")
    parser.add_argument("--overlap", type=int, default=120, help="chunk overlap (characters)")
    args = parser.parse_args()

    materials_root = Path(args.dir).resolve()
    if not materials_root.exists():
        print(f"Materials directory not found: {materials_root}")
        print("Create it and add PDFs, e.g. data/materials/math/past_papers/.")
        return

    app = create_app()
    with app.app_context():
        store = init_chroma_store(app.config)

        if args.if_empty and store.count_where(MATERIALS_FILTER) > 0:
            print("Materials already ingested — skipping (--if-empty).")
            return

        if args.reset:
            store.delete_where(MATERIALS_FILTER)

        files = 0
        total_chunks = 0
        skipped = 0

        for path in iter_documents(materials_root, args.subject):
            try:
                chunks = build_chunks(path, materials_root, args.size, args.overlap)
            except Exception as exc:  # noqa: BLE001
                print(f"  ! skipped {path.name}: {exc}")
                skipped += 1
                continue

            if not chunks:
                print(f"  - {path.name}: no extractable text (scanned PDF? needs OCR)")
                skipped += 1
                continue

            store.upsert_chunks(chunks)
            files += 1
            total_chunks += len(chunks)
            rel = path.relative_to(materials_root)
            print(f"  + {rel.as_posix()}: {len(chunks)} chunk(s)")

        print(
            f"\nDone. files={files} chunks={total_chunks} skipped={skipped} "
            f"| collection total={store.document_count}"
        )


if __name__ == "__main__":
    main()
