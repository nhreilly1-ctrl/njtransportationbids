from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.filters import is_garbage_title, is_expired, clean_title
from app.models.opportunities_live import OpportunityLive
from app.models.opportunity_leads import OpportunityLead

PROMOTION_RULE_TEXT = (
    'Promote only if transport-related, official source found, verified, not duplicate, and open'
)



def should_promote(lead: OpportunityLead) -> bool:
    if is_garbage_title(lead.notice_title):
        return False
    if is_expired(lead.due_at):
        return False
    return (
        lead.verification_status == 'Verified'
        and (lead.official_status or '').lower() in {'open', 'open / upon contract', ''}
        and lead.promotion_decision in {'Promote', 'Review'}
        and (lead.official_url or lead.notice_url)
    )



def promote_to_live(db: Session, lead: OpportunityLead) -> OpportunityLive:
    clean = clean_title(lead.notice_title)
    live = OpportunityLive(
        lead_id=lead.lead_id,
        source_id=lead.source_id,
        title=clean,
        owner_name=lead.owner_name or '',
        owner_type=lead.owner_type,
        county=lead.county,
        municipality=lead.municipality,
        category=lead.category,
        project_type=lead.project_type,
        status=lead.official_status or 'Open',
        posted_at=lead.posted_at,
        due_at=lead.due_at,
        estimate_range=lead.estimate_range,
        official_notice_url=lead.notice_url,
        official_procurement_url=lead.official_url or lead.notice_url,
        lead_url=lead.notice_url,
        portal_url=lead.portal_url,
        promotion_rule=PROMOTION_RULE_TEXT,
        notes=lead.notes,
    )
    db.add(live)
    lead.promoted_flag = True
    lead.lead_status = 'promoted'
    db.commit()
    db.refresh(live)
    return live
