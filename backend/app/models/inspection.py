from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Entity, utc_now


class InspectionState(StrEnum):
    DRAFT = "draft"
    EDITING = "editing"
    IN_PROGRESS = "in_progress"


class ViolationStatus(StrEnum):
    ELIMINATED = "eliminated"
    NOT_ELIMINATED = "not_eliminated"
    OVERDUE = "overdue"


class RepeatDecision(StrEnum):
    CONFIRMED = "confirmed"
    NOT_REPEAT = "not_repeat"
    DEFERRED = "deferred"


class Inspection(Entity):
    __tablename__ = "inspections"
    __table_args__ = (UniqueConstraint("control_type_id", "document_number_normalized", name="uq_inspection_control_number"),)

    control_type_id: Mapped[UUID] = mapped_column(ForeignKey("control_types.id", ondelete="RESTRICT"), nullable=False, index=True)
    inspection_kind_id: Mapped[UUID] = mapped_column(ForeignKey("inspection_kinds.id", ondelete="RESTRICT"), nullable=False)
    document_number: Mapped[str] = mapped_column(String(128), nullable=False)
    document_number_normalized: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    inspection_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(32), default=InspectionState.DRAFT, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)


class InspectionScope(Entity):
    __tablename__ = "inspection_scopes"

    inspection_id: Mapped[UUID] = mapped_column(ForeignKey("inspections.id", ondelete="RESTRICT"), nullable=False, index=True)
    department_id: Mapped[UUID] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False)
    object_id: Mapped[UUID] = mapped_column(ForeignKey("objects.id", ondelete="RESTRICT"), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)


class Violation(Entity):
    __tablename__ = "violations"

    inspection_id: Mapped[UUID] = mapped_column(ForeignKey("inspections.id", ondelete="RESTRICT"), nullable=False, index=True)
    inspection_scope_id: Mapped[UUID] = mapped_column(ForeignKey("inspection_scopes.id", ondelete="RESTRICT"), nullable=False, index=True)
    formulation: Mapped[str] = mapped_column(Text, nullable=False)
    violated_requirement: Mapped[str] = mapped_column(Text, nullable=False)
    violation_type_id: Mapped[UUID] = mapped_column(ForeignKey("violation_types.id", ondelete="RESTRICT"), nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    original_due_date: Mapped[date | None] = mapped_column(Date)
    due_date_basis: Mapped[str | None] = mapped_column(String(255))
    due_date_source_text: Mapped[str | None] = mapped_column(Text)
    document_received_date: Mapped[date | None] = mapped_column(Date)
    elimination_date: Mapped[date | None] = mapped_column(Date, index=True)
    eliminated_during_inspection: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    eliminated_late: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    days_overdue_at_elimination: Mapped[int | None] = mapped_column(Integer)
    annulled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    annulled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    annulled_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    annulment_reason: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)


class ViolationResponsibleDepartment(Entity):
    __tablename__ = "violation_responsible_departments"
    __table_args__ = (UniqueConstraint("violation_id", "department_id", name="uq_violation_responsible_department"),)

    violation_id: Mapped[UUID] = mapped_column(ForeignKey("violations.id", ondelete="RESTRICT"), nullable=False)
    department_id: Mapped[UUID] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False)


class ViolationResponsiblePerson(Entity):
    __tablename__ = "violation_responsible_persons"
    __table_args__ = (UniqueConstraint("violation_id", "person_id", name="uq_violation_responsible_person"),)

    violation_id: Mapped[UUID] = mapped_column(ForeignKey("violations.id", ondelete="RESTRICT"), nullable=False)
    person_id: Mapped[UUID] = mapped_column(ForeignKey("persons.id", ondelete="RESTRICT"), nullable=False)


class DeadlineChange(Entity):
    __tablename__ = "deadline_changes"

    violation_id: Mapped[UUID] = mapped_column(ForeignKey("violations.id", ondelete="RESTRICT"), nullable=False, index=True)
    old_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    new_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class DeadlineChangeRequest(Entity):
    __tablename__ = "deadline_change_requests"

    violation_id: Mapped[UUID] = mapped_column(ForeignKey("violations.id", ondelete="RESTRICT"), nullable=False, index=True)
    requested_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class RepeatLink(Entity):
    __tablename__ = "repeat_links"
    __table_args__ = (UniqueConstraint("source_violation_id", "candidate_violation_id", name="uq_repeat_link_pair"),)

    source_violation_id: Mapped[UUID] = mapped_column(ForeignKey("violations.id", ondelete="RESTRICT"), nullable=False)
    candidate_violation_id: Mapped[UUID] = mapped_column(ForeignKey("violations.id", ondelete="RESTRICT"), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), default=RepeatDecision.DEFERRED, nullable=False)
    decided_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
