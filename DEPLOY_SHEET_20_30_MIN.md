# 20–30 minute deploy sheet

This gets a private MVP online on Render with Postgres.

## 1. Put the repo in GitHub (3–5 minutes)
- Create a new GitHub repo.
- Upload this project.
- Confirm these files are at the root:
  - `render.yaml`
  - `Dockerfile`
  - `requirements.txt`
  - `app/`
  - `scripts/`
  - `sql/`

## 2. Create the database in Render (3–5 minutes)
- Sign in to Render.
- Use **New > Blueprint** if you want Render to read `render.yaml`, or create services manually. Render Blueprints are defined by a `render.yaml` file in the repo root. citeturn884376search0
- If creating manually, go to **New > Postgres**.
- Choose the same region you will use for the web service. Render recommends the same region to minimize latency and enable private-network communication. citeturn884376search3

## 3. Create the web service (5 minutes)
- In Render, create a **Web Service** from the GitHub repo.
- Render supports deploying a web service from a linked repo or Docker image. citeturn884376search4
- Use the Dockerfile in the repo.
- Confirm the health check path is `/health`.
- Confirm the app binds to `0.0.0.0` on port `10000`. citeturn884376search4

## 4. Set environment variables (2–3 minutes)
Set:
- `DATABASE_URL`
- `SECRET_KEY`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `APP_ENV=production`
- `PORT=10000`
- `HOST=0.0.0.0`

If you use the Blueprint file, keep secrets as placeholders and fill them in the Render dashboard. citeturn884376search1

## 5. Deploy and test (3–5 minutes)
- Click deploy.
- Wait for the service to build.
- Open:
  - `/health`
  - `/`
- Check logs if it fails. Render’s dashboard provides service logs for troubleshooting. citeturn884376search9

## 6. Seed the registry (2–5 minutes)
Option A:
- Include `sql/002_seed_registry_sources_full.sql` in the repo so startup applies it automatically.

Option B:
- Open a Render shell or job and run:
```bash
python scripts/apply_seed_sql.py /app/sql/002_seed_registry_sources_full.sql
```

## 7. Add the custom domain (5 minutes)
- In the service settings, add the custom domain. citeturn884376search2
- Create the required DNS records in Cloudflare.
- Verify the domain in Render.
- Wait for TLS to finish provisioning. Render automatically creates and renews TLS certificates for custom domains and redirects HTTP to HTTPS. citeturn884376search2

## 8. Final checks (1–2 minutes)
- Confirm:
  - the site loads
  - `/health` returns OK
  - the DB is connected
  - source seed is present
  - custom domain resolves

## Launch recommendation
- Start with the site private or low-profile.
- Tune parsers and admin review first.
- Then make the public listings page visible.
