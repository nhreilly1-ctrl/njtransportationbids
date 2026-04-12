from pathlib import Path
import os
import psycopg2

db = os.environ["DATABASE_URL"]
schema_path = Path("/app/sql/001_schema.sql")
if not schema_path.exists():
    print("[apply_schema] schema file not found, skipping")
    raise SystemExit(0)

sql = schema_path.read_text(encoding="utf-8")
with psycopg2.connect(db) as conn:
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
print("[apply_schema] schema applied")
