from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.crawl_runs import CrawlRun

router = APIRouter(prefix='/api/crawls', tags=['crawls'])


@router.get('')
def list_crawls(db: Session = Depends(get_db)):
    stmt = select(CrawlRun).order_by(CrawlRun.started_at.desc())
    return db.execute(stmt).scalars().all()
