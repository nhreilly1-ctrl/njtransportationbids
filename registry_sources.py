from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.core.db import Base


class RegistrySource(Base):
    __tablename__ = "registry_sources"

    source_id = Column(String(80), primary_key=True)
    source_level = Column(String(32), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False, index=True)
    source_name = Column(String(255), nullable=False, index=True)
    county = Column(String(128), nullable=True, index=True)
    municipality = Column(String(128), nullable=True, index=True)
    region = Column(String(64), nullable=False, index=True)
    coverage_scope = Column(String(255), nullable=True)
    priority_tier = Column(String(32), nullable=True, index=True)
    priority_rank = Column(Integer, nullable=True)
    rank_area = Column(String(64), nullable=True)
    statewide_dos_directory = Column(Text, nullable=True)
    direct_legal_notice_url = Column(Text, nullable=True)
    effective_notice_entry_url = Column(Text, nullable=False)
    primary_procurement_url = Column(Text, nullable=False)
    verification_url_county_url = Column(Text, nullable=True)
    portal_type = Column(String(128), nullable=True)
    crawl_entry = Column(Text, nullable=False)
    verification_status = Column(String(64), nullable=False, default="Unknown")
    source_status = Column(String(32), nullable=False, default="Pinned")
    refresh_cadence = Column(String(32), nullable=False, default="Weekly")
    website_ready = Column(String(16), nullable=False, default="Yes")
    import_enabled = Column(Boolean, nullable=False, default=True, index=True)
    parser_hint = Column(String(64), nullable=False, default="Manual review")
    use_for = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    last_crawled_at = Column(DateTime(timezone=True), nullable=True)
    next_crawl_at = Column(DateTime(timezone=True), nullable=True)
    source_sheet = Column(String(64), nullable=True)
    source_row_number = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
