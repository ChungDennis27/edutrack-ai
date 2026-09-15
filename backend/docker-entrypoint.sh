#!/bin/sh
set -e

echo "==> [1/5] Waiting for PostgreSQL"
python scripts/wait_for_db.py

echo "==> [2/5] Applying database migrations"
flask --app run.py db upgrade

echo "==> [3/5] Seeding curriculum (idempotent)"
python scripts/seed_db.py

echo "==> [4/5] Initialising vector store (idempotent)"
python scripts/init_chroma.py

echo "==> [5/5] Ingesting classical Chinese texts (idempotent)"
python scripts/ingest_classical.py

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
