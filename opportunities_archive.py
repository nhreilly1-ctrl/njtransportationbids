from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.core.db import Base


class OpportunityArchive(Base):
    __tablename__ = "opportunities_archive"

    archive_id = Column(Integer, primary_key=True, autoincrement=True)
    original_opportunity_id = Column(Integer, nullable=True, index=True)
    source_id = Column(String(80), nullable=True, index=True)
    title = Column(Text, nullable=False)
    owner_name = Column(String(255), nullable=False, index=True)
    owner_type = Column(String(64), nullable=True)
    county = Column(String(128), nullable=True, index=True)
    municipality = Column(String(128), nullable=True)
    category = Column(String(128), nullable=True)
    project_type = Column(String(128), nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    due_at = Column(DateTime(timezone=True), nullable=True)
    close_date = Column(DateTime(timezone=True), nullable=True)
    final_status = Column(String(64), nullable=False)
    archive_reason = Column(String(64), nullable=False)
    official_notice_url = Column(Text, nullable=True)
    official_procurement_url = Column(Text, nullable=True)
    lead_url = Column(Text, nullable=True)
    archived_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
