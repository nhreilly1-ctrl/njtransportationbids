from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.opportunities_archive import OpportunityArchive
from app.models.opportunities_live import OpportunityLive



def archive_live_opportunity(db: Session, live: OpportunityLive, archive_reason: str, final_status: str) -> OpportunityArchive:
    archived = OpportunityArchive(
        original_opportunity_id=live.opportunity_id,
        source_id=live.source_id,
        title=live.title,
        owner_name=live.owner_name,
        owner_type=live.owner_type,
        county=live.county,
        municipality=live.municipality,
        category=live.category,
        project_type=live.project_type,
        posted_at=live.posted_at,
        due_at=live.due_at,
        final_status=final_status,
        archive_reason=archive_reason,
        official_notice_url=live.official_notice_url,
        official_procurement_url=live.official_procurement_url,
        lead_url=live.lead_url,
    )
    db.add(archived)
    db.delete(live)
    db.commit()
    db.refresh(archived)
    return archived
