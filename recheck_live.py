from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.opportunities_live import OpportunityLive


def main() -> None:
    db = SessionLocal()
    try:
        stmt = select(OpportunityLive).where(OpportunityLive.due_date < date.today())
        for live in db.execute(stmt).scalars().all():
            live.status = "closed"
            live.archive_ready_flag = "yes"
        db.commit()
        print("Recheck complete")
    finally:
        db.close()


if __name__ == "__main__":
    main()
