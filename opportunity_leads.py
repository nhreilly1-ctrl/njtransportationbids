from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.core.db import Base


class OpportunityLead(Base):
    __tablename__ = "opportunity_leads"

    lead_id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String(80), ForeignKey("registry_sources.source_id", ondelete="CASCADE"), nullable=False, index=True)
    crawl_run_id = Column(Integer, ForeignKey("crawl_runs.crawl_run_id", ondelete="SET NULL"), nullable=True, index=True)
    owner_name = Column(String(255), nullable=True, index=True)
    owner_type = Column(String(64), nullable=True)
    county = Column(String(128), nullable=True, index=True)
    municipality = Column(String(128), nullable=True, index=True)
    region = Column(String(64), nullable=True)
    notice_title = Column(Text, nullable=False)
    category = Column(String(128), nullable=True)
    project_type = Column(String(128), nullable=True)
    notice_url = Column(Text, nullable=False)
    official_url = Column(Text, nullable=True)
    portal_url = Column(Text, nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    due_at = Column(DateTime(timezone=True), nullable=True, index=True)
    estimate_range = Column(String(128), nullable=True)
    official_status = Column(String(64), nullable=True)
    raw_text = Column(Text, nullable=True)
    transport_score = Column(Integer, nullable=False, default=0)
    confidence_score = Column(Integer, nullable=False, default=0)
    verification_status = Column(String(64), nullable=False, default="Unknown")
    promotion_decision = Column(String(16), nullable=False, default="Review")
    lead_status = Column(String(32), nullable=False, default="new")
    duplicate_hash = Column(String(128), nullable=True, index=True)
    promoted_flag = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
