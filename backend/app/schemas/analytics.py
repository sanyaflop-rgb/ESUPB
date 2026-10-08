from datetime import date
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import APIModel


class AnalyticsSummary(BaseModel):
    total: int
    eliminated: int
    not_eliminated: int
    overdue: int
    due_soon: int
    eliminated_late: int
    heavy: int


class AnalyticsControlTypeItem(APIModel):
    control_type_id: UUID
    code: str
    name: str
    total: int
    eliminated: int
    not_eliminated: int
    overdue: int
    heavy: int


class AnalyticsSeverityItem(BaseModel):
    severity: int
    total: int


class AnalyticsDepartmentItem(APIModel):
    department_id: UUID
    name: str
    total: int
    eliminated: int
    not_eliminated: int
    overdue: int
    heavy: int


class AnalyticsObjectItem(APIModel):
    object_id: UUID
    name: str
    total: int
    heavy: int


class AnalyticsDynamicsPoint(BaseModel):
    month: str
    total: int
    by_control_type: dict[str, int]


class AnalyticsViolationTypeItem(APIModel):
    violation_type_id: UUID
    code: str
    name: str
    severity: int
    total: int


class AnalyticsResponse(BaseModel):
    period_from: date | None
    period_to: date | None
    summary: AnalyticsSummary
    by_control_type: list[AnalyticsControlTypeItem]
    by_severity: list[AnalyticsSeverityItem]
    by_department: list[AnalyticsDepartmentItem]
    by_object: list[AnalyticsObjectItem]
    dynamics: list[AnalyticsDynamicsPoint]
    by_violation_type: list[AnalyticsViolationTypeItem]
