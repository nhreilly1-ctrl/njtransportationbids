from pathlib import Path
import os, sys
import psycopg2

if len(sys.argv) < 2:
    print("usage: python scripts/apply_seed_sql.py /app/sql/002_seed_registry_sources_full.sql")
    raise SystemExit(1)

seed_path = Path(sys.argv[1])
if not seed_path.exists():
    print(f"[apply_seed_sql] file not found: {seed_path}")
    raise SystemExit(1)

db = os.environ["DATABASE_URL"]
sql = seed_path.read_text(encoding="utf-8")
with psycopg2.connect(db) as conn:
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
print(f"[apply_seed_sql] applied {seed_path.name}")
