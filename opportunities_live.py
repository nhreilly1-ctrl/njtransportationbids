from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.core.db import Base


class OpportunityLive(Base):
    __tablename__ = "opportunities_live"

    opportunity_id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(Integer, ForeignKey("opportunity_leads.lead_id", ondelete="SET NULL"), nullable=True, unique=True)
    source_id = Column(String(80), ForeignKey("registry_sources.source_id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(Text, nullable=False)
    owner_name = Column(String(255), nullable=False, index=True)
    owner_type = Column(String(64), nullable=True)
    county = Column(String(128), nullable=True, index=True)
    municipality = Column(String(128), nullable=True, index=True)
    category = Column(String(128), nullable=True)
    project_type = Column(String(128), nullable=True)
    status = Column(String(64), nullable=False, default="Open", index=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    due_at = Column(DateTime(timezone=True), nullable=True, index=True)
    estimate_range = Column(String(128), nullable=True)
    official_notice_url = Column(Text, nullable=True)
    official_procurement_url = Column(Text, nullable=False)
    lead_url = Column(Text, nullable=True)
    portal_url = Column(Text, nullable=True)
    promotion_rule = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
