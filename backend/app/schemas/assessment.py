from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import APIModel


class AssessmentCriterionResponse(APIModel):
    id: UUID
    criterion_code: str
    section_code: str
    section_title: str
    name: str
    subject_type: str
    period_type: str
    input_type: str
    formula_type: str
    thresholds: dict
    score_mapping: dict
    applicability_rule: dict
    input_fields: list
    is_active: bool
    display_order: int
    version: int
    active_from: date


class AssessmentComputeRequest(BaseModel):
    period_type: str = Field(pattern="^(quarter|half_year|nine_months|year)$")
    period_year: int = Field(ge=2000, le=2100)
    period_index: int = Field(ge=1, le=4)
    department_id: UUID | None = None


class AssessmentCriterionResult(BaseModel):
    criterion_id: UUID
    criterion_code: str
    section_code: str
    section_title: str
    name: str
    subject_type: str
    period_type: str
    input_type: str
    formula_type: str
    score: int | None
    not_applicable: bool
    missing_input: bool
    fact: str | None
    threshold: str | None
    reason: str
    score_mapping: dict
    input_fields: list
    fact_values: dict
    fact_not_applicable: bool
    fact_comment: str | None


class AssessmentSummary(BaseModel):
    applicable_count: int
    not_applicable_count: int
    missing_input_count: int
    average_score: float | None
    verdict: str | None


class AssessmentComputeResponse(BaseModel):
    period_type: str
    period_year: int
    period_index: int
    period_from: date
    period_to: date
    department_id: UUID | None
    department_name: str | None
    subject_type: str
    summary: AssessmentSummary
    criteria: list[AssessmentCriterionResult]


class AssessmentFactSave(BaseModel):
    criterion_id: UUID
    period_type: str = Field(pattern="^(quarter|half_year|nine_months|year)$")
    period_year: int = Field(ge=2000, le=2100)
    period_index: int = Field(ge=1, le=4)
    department_id: UUID | None = None
    values: dict = Field(default_factory=dict)
    not_applicable: bool = False
    comment: str | None = None


class AssessmentFactResponse(APIModel):
    id: UUID
    criterion_id: UUID
    criterion_code: str | None = None
    period_year: int
    period_type: str
    period_index: int
    subject_type: str
    department_id: UUID | None
    values: dict
    not_applicable: bool
    comment: str | None
    updated_at: datetime


class AssessmentResultResponse(APIModel):
    id: UUID
    period_year: int
    period_type: str
    period_index: int
    subject_type: str
    department_id: UUID | None
    department_name: str | None = None
    average_score: float | None
    verdict: str | None
    applicable_count: int
    not_applicable_count: int
    missing_input_count: int
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime


class AssessmentResultDetail(AssessmentResultResponse):
    criteria_payload: list


class AssessmentResultSave(BaseModel):
    period_type: str = Field(pattern="^(quarter|half_year|nine_months|year)$")
    period_year: int = Field(ge=2000, le=2100)
    period_index: int = Field(ge=1, le=4)
    department_id: UUID | None = None
