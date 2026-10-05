from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    login: str = Field(min_length=3, max_length=128)
    password: str = Field(min_length=8, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserResponse(BaseModel):
    id: UUID
    login: str
    display_name: str
    roles: list[str]
