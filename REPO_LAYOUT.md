# Render-ready repo layout

```text
your-repo/
├── app/
│   └── main.py
├── docs/
│   ├── DEPLOY_SHEET_20_30_MIN.md
│   ├── DOMAIN_DNS_CHECKLIST.md
│   └── ENV_VAR_CHECKLIST.md
├── scripts/
│   ├── apply_schema.py
│   ├── apply_seed_sql.py
│   └── start_production.sh
├── sql/
│   ├── 001_schema.sql
│   └── 002_seed_registry_sources_full.sql
├── Dockerfile
├── requirements.txt
└── render.yaml
```

## Notes
- Keep `render.yaml` at the repository root. Render’s Blueprint docs describe `render.yaml` as the default root file for connected services and databases. citeturn884376search0
- Keep secrets out of source control. Use Render dashboard secret values for `SECRET_KEY`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD`. citeturn884376search1
- Put the full seed SQL in `sql/` so the startup script can apply it automatically.
