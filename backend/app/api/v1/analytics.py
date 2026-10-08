from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.security import User
from app.schemas.analytics import AnalyticsResponse
from app.services.analytics import ANALYTICS_STATUS_FILTERS, build_analytics

router = APIRouter(tags=["analytics"])


@router.get("/analytics/summary", response_model=AnalyticsResponse)
def analytics_summary(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    control_type_id: UUID | None = Query(default=None),
    department_id: UUID | None = Query(default=None),
    object_id: UUID | None = Query(default=None),
    severity: int | None = Query(default=None, ge=1, le=9),
    violation_status: str | None = Query(default=None, alias="status"),
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> AnalyticsResponse:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Начало периода позже окончания")
    if violation_status is not None and violation_status not in ANALYTICS_STATUS_FILTERS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Неизвестный фильтр статуса")
    return build_analytics(
        database,
        date_from=date_from,
        date_to=date_to,
        control_type_id=control_type_id,
        department_id=department_id,
        object_id=object_id,
        severity=severity,
        status_filter=violation_status,
    )
