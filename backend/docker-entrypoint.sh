#!/bin/sh
set -e

echo "==> [1/6] Waiting for PostgreSQL"
python scripts/wait_for_db.py

echo "==> [2/6] Applying database migrations"
flask --app run.py db upgrade

echo "==> [3/6] Seeding curriculum (idempotent)"
python scripts/seed_db.py

echo "==> [4/6] Initialising vector store (idempotent)"
python scripts/init_chroma.py

echo "==> [5/6] Ingesting classical Chinese texts (idempotent)"
python scripts/ingest_classical.py

echo "==> [6/6] Ingesting course materials (PDF) if present"
python scripts/ingest_documents.py --if-empty

echo "==> Starting gunicorn on :5000"
exec gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 2 \
  --threads 4 \
  --worker-class gthread \
  --timeout 300 \
  --graceful-timeout 60 \
  --access-logfile - \
  run:app
