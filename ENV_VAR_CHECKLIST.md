# Environment variable checklist

Set these in Render for the web service.

## Required
- `DATABASE_URL`
  - Source: Render Postgres connection string
  - In a Blueprint, this can come from `fromDatabase`.
- `SECRET_KEY`
  - Generate a long random string.
- `ADMIN_USERNAME`
  - Example: `admin`
- `ADMIN_PASSWORD`
  - Use a strong unique password.

## Recommended
- `APP_ENV=production`
- `PORT=10000`
- `HOST=0.0.0.0`
- `CRAWL_ENABLED=false`
- `LOG_LEVEL=info`

## Optional later
- `BASIC_AUTH_ENABLED=true`
- `SESSION_COOKIE_SECURE=true`
- `ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com`
- `SENTRY_DSN=...`
- `SMTP_HOST=...`
- `SMTP_USER=...`
- `SMTP_PASSWORD=...`

## Notes
- Render expects your web service to bind to host `0.0.0.0`. The default expected port is `10000`. citeturn884376search4
- Do not commit real secrets to `render.yaml`; Render recommends placeholders and then filling secret values in the dashboard. citeturn884376search1
- Use the Render Postgres internal URL for the app when the web service and database are in the same region. citeturn884376search3
