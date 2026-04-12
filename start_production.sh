#!/usr/bin/env bash
set -euo pipefail

echo "[startup] starting NJ Bid Registry"
echo "[startup] APP_ENV=${APP_ENV:-unset}"
echo "[startup] PORT=${PORT:-10000}"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "[startup] ERROR: DATABASE_URL is not set"
  exit 1
fi

python - <<'PY'
import os, sys, time
import psycopg2

db = os.environ["DATABASE_URL"]
last_err = None
for i in range(30):
    try:
        conn = psycopg2.connect(db)
        conn.close()
        print("[startup] database connection OK")
        sys.exit(0)
    except Exception as e:
        last_err = e
        print(f"[startup] waiting for database... attempt {i+1}/30")
        time.sleep(2)
print(f"[startup] ERROR: database not reachable: {last_err}")
sys.exit(1)
PY

echo "[startup] running schema setup"
python scripts/apply_schema.py

if [ -f "/app/sql/002_seed_registry_sources_full.sql" ]; then
  echo "[startup] full seed SQL found"
  python scripts/apply_seed_sql.py /app/sql/002_seed_registry_sources_full.sql || true
fi

echo "[startup] launching app"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
