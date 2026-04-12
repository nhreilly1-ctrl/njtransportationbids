from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.opportunities_live import OpportunityLive

router = APIRouter(prefix='/api/opportunities', tags=['opportunities'])


@router.get('')
def list_opportunities(db: Session = Depends(get_db)):
    stmt = select(OpportunityLive).order_by(OpportunityLive.due_at.asc().nullslast(), OpportunityLive.owner_name.asc())
    return db.execute(stmt).scalars().all()


@router.get('/{opportunity_id}')
def get_opportunity(opportunity_id: int, db: Session = Depends(get_db)):
    return db.get(OpportunityLive, opportunity_id)
