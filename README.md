# NJ Transportation Bid Registry - Production Repo

This is the merged production-ready repository for the New Jersey transportation bid registry MVP.

It combines:
- the v2 application starter kit wired to the real workbook structure
- the full `registry_sources` seed SQL with 135 sources
- Render deployment files
- production startup scripts
- deploy and DNS checklists

## What's included

- `app/` FastAPI app, models, routes, crawler skeleton, templates
- `sql/001_schema.sql` database schema
- `sql/002_seed_registry_sources_full.sql` full 135-row registry seed
- `scripts/start_production.sh` production startup entrypoint
- `scripts/apply_schema.py` schema loader
- `scripts/apply_seed_sql.py` seed loader
- `scripts/seed_registry.py` workbook/CSV registry importer
- `render.yaml` Render blueprint
- `Dockerfile` production container build
- `docs/` deployment and domain/DNS guides

## Quick local start

```bash
cp .env.example .env
docker compose up --build
```

If you are not using Docker locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Render deploy

1. Push this folder to GitHub.
2. Create a new Render Blueprint from the repo or create the database and web service manually.
3. Set secrets in the Render dashboard:
   - `SECRET_KEY`
   - `ADMIN_USERNAME`
   - `ADMIN_PASSWORD`
4. Deploy.
5. Verify `/health`.
6. Add your custom domain after the app and DB are working.

See:
- `docs/DEPLOY_SHEET_20_30_MIN.md`
- `docs/ENV_VAR_CHECKLIST.md`
- `docs/DOMAIN_DNS_CHECKLIST.md`

## Full registry seed

This repo includes the full `registry_sources` seed SQL:

- `sql/002_seed_registry_sources_full.sql`

It contains:
- 9 state/authority sources
- 21 county sources
- 105 municipal sources
- 135 total source rows

To load manually:

```bash
psql "$DATABASE_URL" -f sql/002_seed_registry_sources_full.sql
```

## Notes

This is ready to push and deploy as an MVP/beta stack.
You should still keep human review in the loop for parser tuning, duplicate handling, and promotion decisions before treating it as a fully automated public production system.
