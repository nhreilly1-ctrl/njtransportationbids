from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.opportunity_leads import OpportunityLead

router = APIRouter(prefix='/api/leads', tags=['leads'])


@router.get('')
def list_leads(db: Session = Depends(get_db)):
    stmt = select(OpportunityLead).order_by(OpportunityLead.created_at.desc())
    return db.execute(stmt).scalars().all()


@router.get('/{lead_id}')
def get_lead(lead_id: int, db: Session = Depends(get_db)):
    return db.get(OpportunityLead, lead_id)
