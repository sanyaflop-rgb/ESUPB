"""Добавить подразделение и объект проверки

Revision ID: 20261006_03
Revises: 20261006_02
Create Date: 2026-10-06 20:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261006_03"
down_revision: str | Sequence[str] | None = "20261006_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("inspections") as batch_op:
        batch_op.add_column(sa.Column("department_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("object_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key("fk_inspections_department_id_departments", "departments", ["department_id"], ["id"], ondelete="RESTRICT")
        batch_op.create_foreign_key("fk_inspections_object_id_objects", "objects", ["object_id"], ["id"], ondelete="RESTRICT")
        batch_op.create_index("ix_inspections_department_id", ["department_id"], unique=False)
        batch_op.create_index("ix_inspections_object_id", ["object_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("inspections") as batch_op:
        batch_op.drop_index("ix_inspections_object_id")
        batch_op.drop_index("ix_inspections_department_id")
        batch_op.drop_constraint("fk_inspections_object_id_objects", type_="foreignkey")
        batch_op.drop_constraint("fk_inspections_department_id_departments", type_="foreignkey")
        batch_op.drop_column("object_id")
        batch_op.drop_column("department_id")
