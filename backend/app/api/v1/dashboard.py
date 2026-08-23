from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.crud import dashboard as dashboard_crud
from app.db.session import get_db
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard_service import build_dashboard_summary

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db)):

    return build_dashboard_summary(dashboard_crud.get_snapshot(db))
