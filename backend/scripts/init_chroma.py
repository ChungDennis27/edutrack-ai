"""ChromaDB initialization CLI script.

Usage:
    python scripts/init_chroma.py              # init + seed sample data
    python scripts/init_chroma.py --reset      # delete collection + reseed
    python scripts/init_chroma.py --stats      # show collection stats
"""
import argparse
import sys
from pathlib import Path

# Add backend root to path
backend_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_root))

from app import create_app
from app.services.chroma_store import init_chroma_store, seed_sample_dse_materials


def main():
    parser = argparse.ArgumentParser(description="Initialize ChromaDB for EduTrack AI")
    parser.add_argument("--reset", action="store_true", help="Delete and recreate collection")
    parser.add_argument("--stats", action="store_true", help="Show collection statistics")
    args = parser.parse_args()

    app = create_app()

    with app.app_context():
        store = init_chroma_store(app.config)

        if args.reset:
            print("Deleting existing collection...")
            store.delete_collection()
            store = init_chroma_store(app.config)

        if args.stats:
            count = store.document_count
            print(f"Collection: {store.collection_name}")
            print(f"Documents: {count}")
            print(f"Persist dir: {store.persist_dir}")
            return

        # Seed if empty
        if store.document_count == 0:
            print("Seeding sample DSE materials...")
            count = seed_sample_dse_materials(store)
            print(f"Seeded {count} document chunks.")
        else:
            print(f"Collection already has {store.document_count} documents. Use --reset to reseed.")

        print(f"\nChromaDB ready at: {store.persist_dir}")
        print(f"Collection: {store.collection_name}")
        print(f"Total documents: {store.document_count}")


if __name__ == "__main__":
    main()
