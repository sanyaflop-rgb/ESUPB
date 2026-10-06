"""Перевести устранение нарушений на индивидуальные меры

Revision ID: 20261006_02
Revises: 20261006_01
Create Date: 2026-10-06 14:00:00.000000

"""
from collections.abc import Sequence
from uuid import UUID, uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "20261006_02"
down_revision: str | Sequence[str] | None = "20261006_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "violation_measures",
        sa.Column("violation_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("elimination_measure", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("original_due_date", sa.Date(), nullable=True),
        sa.Column("elimination_date", sa.Date(), nullable=True),
        sa.Column("eliminated_during_inspection", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("eliminated_late", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("days_overdue_at_elimination", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["object_id"], ["objects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["violation_id"], ["violations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("violation_id", "department_id", "object_id", "person_id", name="uq_violation_measure_assignment"),
    )
    op.create_index(op.f("ix_violation_measures_violation_id"), "violation_measures", ["violation_id"], unique=False)
    op.create_index(op.f("ix_violation_measures_department_id"), "violation_measures", ["department_id"], unique=False)
    op.create_index(op.f("ix_violation_measures_object_id"), "violation_measures", ["object_id"], unique=False)
    op.create_index(op.f("ix_violation_measures_person_id"), "violation_measures", ["person_id"], unique=False)
    op.create_index(op.f("ix_violation_measures_due_date"), "violation_measures", ["due_date"], unique=False)
    op.create_index(op.f("ix_violation_measures_elimination_date"), "violation_measures", ["elimination_date"], unique=False)

    bind = op.get_bind()
    legacy_rows = bind.execute(sa.text("""
        SELECT v.id AS violation_id, s.department_id, s.object_id, rp.person_id,
               v.elimination_measure, v.due_date, v.original_due_date, v.elimination_date,
               v.eliminated_during_inspection, v.eliminated_late, v.days_overdue_at_elimination,
               v.created_at, v.updated_at
        FROM violations v
        JOIN inspection_scopes s ON s.id = v.inspection_scope_id
        JOIN violation_responsible_persons rp ON rp.violation_id = v.id
    """)).mappings()
    measures = []
    for row in legacy_rows:
        measures.append({
            "id": uuid4(),
            "violation_id": UUID(str(row["violation_id"])),
            "department_id": UUID(str(row["department_id"])),
            "object_id": UUID(str(row["object_id"])),
            "person_id": UUID(str(row["person_id"])),
            "elimination_measure": row["elimination_measure"] or "Устранить нарушение",
            "due_date": row["due_date"],
            "original_due_date": row["original_due_date"],
            "elimination_date": row["elimination_date"],
            "eliminated_during_inspection": row["eliminated_during_inspection"],
            "eliminated_late": row["eliminated_late"],
            "days_overdue_at_elimination": row["days_overdue_at_elimination"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        })
    if measures:
        op.bulk_insert(sa.table(
            "violation_measures",
            sa.column("id", sa.Uuid()), sa.column("violation_id", sa.Uuid()),
            sa.column("department_id", sa.Uuid()), sa.column("object_id", sa.Uuid()),
            sa.column("person_id", sa.Uuid()), sa.column("elimination_measure", sa.Text()),
            sa.column("due_date", sa.Date()), sa.column("original_due_date", sa.Date()),
            sa.column("elimination_date", sa.Date()), sa.column("eliminated_during_inspection", sa.Boolean()),
            sa.column("eliminated_late", sa.Boolean()), sa.column("days_overdue_at_elimination", sa.Integer()),
            sa.column("created_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)),
        ), measures)

    op.drop_table("deadline_change_requests")
    op.drop_table("deadline_changes")
    with op.batch_alter_table("violations") as batch_op:
        batch_op.drop_index("ix_violations_inspection_scope_id")
        batch_op.drop_index("ix_violations_due_date")
        batch_op.drop_index("ix_violations_elimination_date")
        batch_op.drop_column("inspection_scope_id")
        batch_op.drop_column("due_date")
        batch_op.drop_column("original_due_date")
        batch_op.drop_column("elimination_measure")
        batch_op.drop_column("elimination_date")
        batch_op.drop_column("eliminated_during_inspection")
        batch_op.drop_column("eliminated_late")
        batch_op.drop_column("days_overdue_at_elimination")
    op.drop_table("violation_responsible_persons")
    op.drop_table("violation_responsible_departments")
    op.drop_table("inspection_scopes")

    op.create_table(
        "deadline_changes",
        sa.Column("violation_measure_id", sa.Uuid(), nullable=False),
        sa.Column("old_due_date", sa.Date(), nullable=False),
        sa.Column("new_due_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("changed_by_id", sa.Uuid(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["violation_measure_id"], ["violation_measures.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_deadline_changes_violation_measure_id"), "deadline_changes", ["violation_measure_id"], unique=False)
    op.create_table(
        "deadline_change_requests",
        sa.Column("violation_measure_id", sa.Uuid(), nullable=False),
        sa.Column("requested_due_date", sa.Date(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("requested_by_id", sa.Uuid(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["resolved_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["violation_measure_id"], ["violation_measures.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_deadline_change_requests_violation_measure_id"), "deadline_change_requests", ["violation_measure_id"], unique=False)


def downgrade() -> None:
    raise RuntimeError("Откат индивидуальных мер требует ручной миграции данных и не поддерживается автоматически")
