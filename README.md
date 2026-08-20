# NJ Transportation Bids

NJ Transportation Bids aggregates open and upcoming New Jersey transportation
construction and professional-services opportunities from official public sources.
The production application is a Flask site deployed on Render.

## What is in this repo

- `app/main.py` Flask application and canonical public routes
- `crawlers/notice_sources.py` configured source inventory
- `crawlers/notice_crawlers.py` source-specific parsers
- `crawlers/notice_runner.py` crawl, lifecycle, health, and persistence pipeline
- `data/notices/notices.json` canonical public opportunity feed
- `app/core/geography.py` conservative county normalization
- `app/core/deadlines.py` deadline and Eastern-time normalization
- `render.yaml` Render blueprint
- `Dockerfile` production container build
- `requirements.txt` Python dependencies
- `AGENTS.md` authoritative architecture and engineering workflow
- `docs/CLAUDE_WEB_HANDOFF.md` Claude Web collaboration contract

## Local run

```bash
cp .env.example .env
docker compose up --build
```

If you are not using Docker locally, use Python 3.11:

```bash
python -m venv .venv
# Activate .venv using the command for your shell.
pip install -r requirements.txt
flask --app app.main run --debug --port 10000
```

Run the focused regression suite from the repository root:

```bash
python -m unittest -v test_deadlines test_geography test_notice_pipeline test_parsers
python -m compileall -q app crawlers
```

## Data pipeline

GitHub Actions runs the crawler daily and weekly. The crawler commits updates under
`data/notices/` back to `main`; Render then deploys the updated application and data.

Production uses `DATA_BACKEND=file`, so `data/notices/notices.json` is the canonical
public dataset. PostgreSQL and older root registry modules remain available for legacy
admin/import paths but do not drive normal public opportunity pages.

## Render deploy

1. Push this folder to GitHub.
2. Create a new Render web service from the repo.
3. Configure the Render blueprint and environment variables.
4. Set `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and a strong `SECRET_KEY`.
5. Deploy and verify `/health`.
6. Add the custom domain in Render.
7. Point Cloudflare DNS at the Render hostname.

`docs/LAUNCH_CHECKLIST.md` is a legacy launch reference; verify its steps against the
current `render.yaml` and `AGENTS.md` before using it.

## Notes

The app exposes `/health` for Render health checks. Public records remain an independent
aggregation; users should always verify submission requirements and addenda with the
issuing agency.
