from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import APIModel


class UserCreate(BaseModel):
    login: str = Field(min_length=3, max_length=128)
    display_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=12, max_length=256)
    role_codes: list[str] = Field(min_length=1)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=255)
    is_active: bool | None = None
    role_codes: list[str] | None = None


class UserResponse(APIModel):
    id: UUID
    login: str
    display_name: str
    is_active: bool
    roles: list[str]


class RoleResponse(APIModel):
    code: str
    name: str
    description: str | None
