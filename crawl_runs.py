from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.core.db import Base


class CrawlRun(Base):
    __tablename__ = "crawl_runs"

    crawl_run_id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String(80), ForeignKey("registry_sources.source_id", ondelete="CASCADE"), nullable=False, index=True)
    crawl_stage = Column(String(32), nullable=False, default="notice_discovery")
    trigger_type = Column(String(32), nullable=False, default="scheduled")
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False)
    http_status = Column(Integer, nullable=True)
    records_found = Column(Integer, nullable=False, default=0)
    records_promoted = Column(Integer, nullable=False, default=0)
    parser_used = Column(String(64), nullable=True)
    source_url_checked = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    checksum_snapshot = Column(Text, nullable=True)
