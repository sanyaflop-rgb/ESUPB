from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.inspection import InspectionState, RepeatDecision, ViolationStatus
from app.schemas.common import APIModel


class InspectionCreate(BaseModel):
    control_type_id: UUID
    inspection_kind_id: UUID | None = None
    department_id: UUID | None = None
    object_id: UUID | None = None
    document_number: str = Field(min_length=1, max_length=128)
    inspection_date: date
    comment: str | None = None


class InspectionUpdate(BaseModel):
    inspection_kind_id: UUID | None = None
    department_id: UUID | None = None
    object_id: UUID | None = None
    document_number: str | None = Field(default=None, min_length=1, max_length=128)
    inspection_date: date | None = None
    comment: str | None = None


class InspectionStateChange(BaseModel):
    state: InspectionState


class InspectionResponse(APIModel):
    id: UUID
    control_type_id: UUID
    has_deadline_control: bool
    inspection_kind_id: UUID | None
    department_id: UUID | None
    object_id: UUID | None
    document_number: str
    document_number_normalized: str
    inspection_date: date
    state: InspectionState
    comment: str | None
    created_by_id: UUID
    updated_by_id: UUID
    created_at: datetime
    updated_at: datetime


class ImportResponsible(APIModel):
    raw: str
    name: str | None = None
    position: str | None = None
    person_id: UUID | None = None
    person_name: str | None = None


class ImportPreviewRow(APIModel):
    row_number: int
    values: dict[str, str]
    due_date: date | None
    responsible: ImportResponsible | None = None
    errors: list[str]


class ImportPreviewResponse(APIModel):
    file_name: str
    headers: list[str]
    mapping: dict[str, str]
    rows: list[ImportPreviewRow]
    valid_rows: int
    invalid_rows: int


class ViolationMeasureInput(BaseModel):
    department_id: UUID
    object_id: UUID
    person_id: UUID
    elimination_measure: str = Field(min_length=1)
    due_date: date | None = None


class ViolationMeasureUpdate(BaseModel):
    department_id: UUID | None = None
    object_id: UUID | None = None
    person_id: UUID | None = None
    elimination_measure: str | None = Field(default=None, min_length=1)


class ViolationMeasureResponse(APIModel):
    id: UUID
    violation_id: UUID
    department_id: UUID
    object_id: UUID
    person_id: UUID
    elimination_measure: str
    due_date: date | None
    original_due_date: date | None
    elimination_date: date | None
    eliminated_during_inspection: bool
    eliminated_late: bool
    days_overdue_at_elimination: int | None
    status: ViolationStatus
    created_at: datetime
    updated_at: datetime


class ImportConfirmRow(BaseModel):
    formulation: str = Field(min_length=1)
    violated_requirement: str = Field(min_length=1)
    violation_type_id: UUID
    document_received_date: date | None = None
    measures: list[ViolationMeasureInput] = Field(min_length=1)


class ImportConfirm(BaseModel):
    rows: list[ImportConfirmRow] = Field(min_length=1)


class ImportConfirmResponse(APIModel):
    created_violations: int
    created_measures: int


class ViolationCreate(BaseModel):
    formulation: str = Field(min_length=1)
    violated_requirement: str = Field(min_length=1)
    violation_type_id: UUID
    document_received_date: date | None = None
    measures: list[ViolationMeasureInput] = Field(min_length=1)


class ViolationUpdate(BaseModel):
    formulation: str | None = Field(default=None, min_length=1)
    violated_requirement: str | None = Field(default=None, min_length=1)
    violation_type_id: UUID | None = None
    document_received_date: date | None = None


class EliminationCreate(BaseModel):
    elimination_date: date
    eliminated_during_inspection: bool = False


class AnnulmentCreate(BaseModel):
    reason: str = Field(min_length=1)


class DeadlineChangeCreate(BaseModel):
    new_due_date: date
    reason: str = Field(min_length=1)


class DeadlineChangeResponse(APIModel):
    id: UUID
    violation_measure_id: UUID
    old_due_date: date
    new_due_date: date
    reason: str
    changed_by_id: UUID
    changed_at: datetime
    created_at: datetime


class RepeatDecisionUpdate(BaseModel):
    decision: RepeatDecision


class RepeatLinkResponse(APIModel):
    id: UUID
    source_violation_id: UUID
    candidate_violation_id: UUID
    decision: RepeatDecision
    decided_by_id: UUID | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ViolationResponse(APIModel):
    id: UUID
    inspection_id: UUID
    has_deadline_control: bool
    formulation: str
    violated_requirement: str
    violation_type_id: UUID
    severity: int
    document_received_date: date | None
    annulled: bool
    annulled_at: datetime | None
    annulled_by_id: UUID | None
    annulment_reason: str | None
    measures: list[ViolationMeasureResponse]
    status: ViolationStatus | None
    created_by_id: UUID
    updated_by_id: UUID
    created_at: datetime
    updated_at: datetime


class DeadlineControlItem(APIModel):
    measure_id: UUID
    violation_id: UUID
    inspection_id: UUID
    document_number: str
    inspection_date: date
    control_type_id: UUID
    control_type_code: str
    control_type_name: str
    department_id: UUID
    department_name: str
    object_id: UUID
    object_name: str
    person_id: UUID
    person_name: str
    person_position: str | None
    violation_formulation: str
    elimination_measure: str
    due_date: date | None
    original_due_date: date | None
    elimination_date: date | None
    eliminated_during_inspection: bool
    eliminated_late: bool
    days_overdue_at_elimination: int | None
    status: ViolationStatus
    days_overdue: int
    days_left: int | None
    due_soon: bool


class DeadlineControlSummary(APIModel):
    total: int
    overdue: int
    due_soon: int
    not_eliminated: int
    eliminated: int
    eliminated_late: int


class DeadlineTypeSummary(APIModel):
    """Счётчики по виду контроля: нарушения считаются один раз, статус — по совокупности мер."""

    control_type_id: UUID
    code: str
    name: str
    total: int
    overdue: int
    due_soon: int
    not_eliminated: int
    eliminated: int
    eliminated_late: int


class DeadlineControlResponse(APIModel):
    summary: DeadlineControlSummary
    types: list[DeadlineTypeSummary]
    items: list[DeadlineControlItem]
