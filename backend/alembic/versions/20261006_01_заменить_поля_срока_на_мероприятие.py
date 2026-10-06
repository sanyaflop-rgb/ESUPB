"""Заменить поля основания и источника срока на мероприятие по устранению

Revision ID: 20261006_01
Revises: 43594a0dc7a3
Create Date: 2026-10-06 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20261006_01'
down_revision: str | Sequence[str] | None = '43594a0dc7a3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column('violations', 'due_date_basis')
    op.drop_column('violations', 'due_date_source_text')
    op.add_column('violations', sa.Column('elimination_measure', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('violations', 'elimination_measure')
    op.add_column('violations', sa.Column('due_date_basis', sa.String(length=255), nullable=True))
    op.add_column('violations', sa.Column('due_date_source_text', sa.Text(), nullable=True))
