from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class Entity(Base):
    """Portable base for entities with UUID identifier and audit timestamps."""

    __abstract__ = True

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class ActiveReference(Entity):
    """Base for editable directories that retain inactive history."""

    __abstract__ = True

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False, index=True)
    display_order: Mapped[int] = mapped_column(default=0, nullable=False)
