from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.inspection import InspectionState, RepeatDecision, ViolationStatus
from app.schemas.common import APIModel


class InspectionCreate(BaseModel):
    control_type_id: UUID
    inspection_kind_id: UUID
    document_number: str = Field(min_length=1, max_length=128)
    inspection_date: date
    comment: str | None = None


class InspectionUpdate(BaseModel):
    inspection_kind_id: UUID | None = None
    document_number: str | None = Field(default=None, min_length=1, max_length=128)
    inspection_date: date | None = None
    comment: str | None = None


class InspectionStateChange(BaseModel):
    state: InspectionState


class InspectionResponse(APIModel):
    id: UUID
    control_type_id: UUID
    inspection_kind_id: UUID
    document_number: str
    document_number_normalized: str
    inspection_date: date
    state: InspectionState
    comment: str | None
    created_by_id: UUID
    updated_by_id: UUID
    created_at: datetime
    updated_at: datetime


class InspectionScopeCreate(BaseModel):
    department_id: UUID
    object_id: UUID
    comment: str | None = None


class InspectionScopeResponse(APIModel):
    id: UUID
    inspection_id: UUID
    department_id: UUID
    object_id: UUID
    comment: str | None
    created_at: datetime
    updated_at: datetime


class ViolationCreate(BaseModel):
    inspection_scope_id: UUID
    formulation: str = Field(min_length=1)
    violated_requirement: str = Field(min_length=1)
    violation_type_id: UUID
    due_date: date | None = None
    due_date_basis: str | None = Field(default=None, max_length=255)
    due_date_source_text: str | None = None
    document_received_date: date | None = None
    responsible_department_ids: list[UUID] = Field(default_factory=list)
    responsible_person_ids: list[UUID] = Field(default_factory=list)


class ViolationUpdate(BaseModel):
    formulation: str | None = Field(default=None, min_length=1)
    violated_requirement: str | None = Field(default=None, min_length=1)
    violation_type_id: UUID | None = None
    responsible_department_ids: list[UUID] | None = None
    responsible_person_ids: list[UUID] | None = None


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
    violation_id: UUID
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
    inspection_scope_id: UUID
    formulation: str
    violated_requirement: str
    violation_type_id: UUID
    severity: int
    due_date: date | None
    original_due_date: date | None
    due_date_basis: str | None
    due_date_source_text: str | None
    document_received_date: date | None
    elimination_date: date | None
    eliminated_during_inspection: bool
    eliminated_late: bool
    days_overdue_at_elimination: int | None
    annulled: bool
    annulled_at: datetime | None
    annulled_by_id: UUID | None
    annulment_reason: str | None
    responsible_department_ids: list[UUID]
    responsible_person_ids: list[UUID]
    status: ViolationStatus | None
    created_by_id: UUID
    updated_by_id: UUID
    created_at: datetime
    updated_at: datetime
