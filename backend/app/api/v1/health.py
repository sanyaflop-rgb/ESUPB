from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["Служебное"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse, summary="Проверка доступности")
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="PK CONTROL API", version="0.1.0")
