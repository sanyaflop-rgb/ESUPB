from datetime import date
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Entity


class AssessmentSubjectType(StrEnum):
    DEPARTMENT = "department"
    SERVICE = "service"


class AssessmentPeriodType(StrEnum):
    QUARTER = "quarter"
    HALF_YEAR = "half_year"
    NINE_MONTHS = "nine_months"
    YEAR = "year"


class AssessmentCriterion(Entity):
    """Конфигурация критерия оценки: правила хранятся в БД, а не в интерфейсе."""

    __tablename__ = "assessment_criteria"
    __table_args__ = (UniqueConstraint("criterion_code", "version", name="uq_assessment_criteria_code_version"),)

    criterion_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    section_code: Mapped[str] = mapped_column(String(16), nullable=False)
    section_title: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    subject_type: Mapped[str] = mapped_column(String(16), nullable=False)
    period_type: Mapped[str] = mapped_column(String(16), nullable=False)
    input_type: Mapped[str] = mapped_column(String(16), nullable=False)
    formula_type: Mapped[str] = mapped_column(String(32), nullable=False)
    thresholds: Mapped[dict] = mapped_column(JSON, nullable=False)
    score_mapping: Mapped[dict] = mapped_column(JSON, nullable=False)
    applicability_rule: Mapped[dict] = mapped_column(JSON, nullable=False)
    input_fields: Mapped[list] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    active_from: Mapped[date] = mapped_column(Date, nullable=False)


class AssessmentFact(Entity):
    """Исходный факт, введённый пользователем для ручного/смешанного критерия."""

    __tablename__ = "assessment_facts"
    __table_args__ = (
        UniqueConstraint(
            "criterion_id",
            "period_year",
            "period_type",
            "period_index",
            "subject_key",
            name="uq_assessment_fact_scope",
        ),
    )

    criterion_id: Mapped[UUID] = mapped_column(ForeignKey("assessment_criteria.id", ondelete="RESTRICT"), nullable=False, index=True)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_type: Mapped[str] = mapped_column(String(16), nullable=False)
    period_index: Mapped[int] = mapped_column(Integer, nullable=False)
    subject_type: Mapped[str] = mapped_column(String(16), nullable=False)
    department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), index=True)
    subject_key: Mapped[str] = mapped_column(String(96), nullable=False)
    values: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    not_applicable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    entered_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)


class AssessmentResult(Entity):
    """Зафиксированный итог оценки за период и объект оценки."""

    __tablename__ = "assessment_results"
    __table_args__ = (
        UniqueConstraint("period_year", "period_type", "period_index", "subject_key", name="uq_assessment_result_scope"),
    )

    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_type: Mapped[str] = mapped_column(String(16), nullable=False)
    period_index: Mapped[int] = mapped_column(Integer, nullable=False)
    subject_type: Mapped[str] = mapped_column(String(16), nullable=False)
    department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), index=True)
    subject_key: Mapped[str] = mapped_column(String(96), nullable=False)
    criteria_payload: Mapped[list] = mapped_column(JSON, nullable=False)
    average_score: Mapped[float | None] = mapped_column(nullable=True)
    verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)
    applicable_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    not_applicable_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    missing_input_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
