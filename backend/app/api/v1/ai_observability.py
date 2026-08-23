from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.crud import ai_observation as observation_crud
from app.db.session import get_db
from app.schemas.ai_observation import AIMetrics
from app.services.ai_observation_service import build_metrics, cutoff_for_days

router = APIRouter()


@router.get("/metrics", response_model=AIMetrics)
def metrics(days: int = Query(default=30, ge=1, le=90), db: Session = Depends(get_db)):

    return build_metrics(observation_crud.list_since(db, cutoff_for_days(days)), days)
