from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import ActiveReference


class ControlType(ActiveReference):
    __tablename__ = "control_types"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    has_deadline_control: Mapped[bool] = mapped_column(default=True, nullable=False)


class InspectionKind(ActiveReference):
    __tablename__ = "inspection_kinds"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)


class Department(ActiveReference):
    __tablename__ = "departments"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"))


class ProductionObject(ActiveReference):
    __tablename__ = "objects"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT")
    )


class Person(ActiveReference):
    __tablename__ = "persons"

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[str | None] = mapped_column(String(255))
    department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"))


class ViolationGroup(ActiveReference):
    __tablename__ = "violation_groups"

    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class ViolationType(ActiveReference):
    __tablename__ = "violation_types"
    __table_args__ = (
        CheckConstraint("severity BETWEEN 1 AND 9", name="ck_violation_types_severity_range"),
        UniqueConstraint("group_id", "code", name="uq_violation_types_group_code"),
    )

    group_id: Mapped[UUID] = mapped_column(ForeignKey("violation_groups.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[int] = mapped_column(nullable=False)
