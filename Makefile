up:
	docker compose up --build

down:
	docker compose down

seed:
	docker compose exec web python scripts/apply_seed_sql.py /app/sql/002_seed_registry_sources_full.sql

health:
	curl http://localhost:10000/health
