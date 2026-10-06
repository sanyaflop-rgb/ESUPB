"""Сделать вид проверки необязательным

Revision ID: 20261006_04
Revises: 20261006_03
Create Date: 2026-10-06 21:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261006_04"
down_revision: str | Sequence[str] | None = "20261006_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("inspections") as batch_op:
        batch_op.alter_column("inspection_kind_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    raise RuntimeError("Откат требует вручную назначить вид проверки всем проверкам")
