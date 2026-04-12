from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.registry_sources import RegistrySource

router = APIRouter(prefix='/api/sources', tags=['sources'])


@router.get('')
def list_sources(db: Session = Depends(get_db)):
    stmt = select(RegistrySource).order_by(RegistrySource.source_level, RegistrySource.source_name)
    return db.execute(stmt).scalars().all()


@router.get('/{source_id}')
def get_source(source_id: str, db: Session = Depends(get_db)):
    return db.get(RegistrySource, source_id)
