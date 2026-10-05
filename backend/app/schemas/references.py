from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import APIModel, ReferenceCreate, ReferenceResponse, ReferenceUpdate


class ControlTypeResponse(ReferenceResponse):
    has_deadline_control: bool


class ControlTypeCreate(ReferenceCreate):
    has_deadline_control: bool = True


class ControlTypeUpdate(ReferenceUpdate):
    has_deadline_control: bool | None = None


class DepartmentResponse(ReferenceResponse):
    parent_id: UUID | None


class DepartmentCreate(ReferenceCreate):
    parent_id: UUID | None = None


class DepartmentUpdate(ReferenceUpdate):
    parent_id: UUID | None = None


class ObjectResponse(APIModel):
    id: UUID
    code: str
    name: str
    owner_department_id: UUID | None
    is_active: bool
    display_order: int


class ObjectCreate(ReferenceCreate):
    owner_department_id: UUID | None = None


class ObjectUpdate(ReferenceUpdate):
    owner_department_id: UUID | None = None


class PersonResponse(APIModel):
    id: UUID
    full_name: str
    position: str | None
    department_id: UUID | None
    is_active: bool
    display_order: int


class PersonCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    position: str | None = Field(default=None, max_length=255)
    department_id: UUID | None = None
    display_order: int = 0


class PersonUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    position: str | None = Field(default=None, max_length=255)
    department_id: UUID | None = None
    is_active: bool | None = None
    display_order: int | None = None


class ViolationTypeResponse(APIModel):
    id: UUID
    group_id: UUID
    code: str
    name: str
    severity: int
    is_active: bool
    display_order: int


class ViolationTypeCreate(BaseModel):
    group_id: UUID
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=2)
    severity: int = Field(ge=1, le=9)
    display_order: int = 0


class ViolationTypeUpdate(BaseModel):
    group_id: UUID | None = None
    name: str | None = Field(default=None, min_length=2)
    severity: int | None = Field(default=None, ge=1, le=9)
    is_active: bool | None = None
    display_order: int | None = None
