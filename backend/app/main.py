from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.inspections import router as inspections_router
from app.api.v1.references import router as references_router
from app.api.v1.users import router as users_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="PK CONTROL API",
    version="0.1.0",
    description="API единой системы учёта и анализа нарушений производственного контроля.",
    openapi_url="/api/openapi.json",
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(references_router, prefix="/api/v1")
app.include_router(inspections_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
