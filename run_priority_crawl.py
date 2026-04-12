from __future__ import annotations

from sqlalchemy import or_, select

from app.core.db import SessionLocal
from app.crawlers.runner import run_source_crawl
from app.models.registry_sources import RegistrySource


PRIORITY_TIERS = ('Tier 1', 'Tier 2')


def main() -> None:
    db = SessionLocal()
    try:
        stmt = (
            select(RegistrySource)
            .where(RegistrySource.import_enabled.is_(True))
            .where(RegistrySource.source_status != 'Inactive')
            .where(RegistrySource.priority_tier.in_(PRIORITY_TIERS))
            .order_by(RegistrySource.priority_tier.asc(), RegistrySource.source_name.asc())
            .limit(20)
        )
        for source in db.execute(stmt).scalars().all():
            result = run_source_crawl(db, source)
            print(source.source_id, result.status, result.records_found, result.records_promoted)
    finally:
        db.close()


if __name__ == '__main__':
    main()
