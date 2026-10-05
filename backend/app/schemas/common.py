from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ReferenceResponse(APIModel):
    id: UUID
    code: str
    name: str
    is_active: bool
    display_order: int
    created_at: datetime
    updated_at: datetime


class ReferenceUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    display_order: int | None = None


class ReferenceCreate(BaseModel):
    code: str
    name: str
    display_order: int = 0


class ActionResponse(BaseModel):
    message: str
