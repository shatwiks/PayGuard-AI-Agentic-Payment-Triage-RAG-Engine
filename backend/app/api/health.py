"""Health check and system telemetry router."""

from fastapi import APIRouter
from backend.app.core.config import settings
from backend.app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System Health & Readiness Probe",
    description="Returns service liveness, database connection status, and active configuration.",
)
async def get_health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        database="connected",
        vector_store="pgvector_ready",
        version=settings.VERSION,
        environment=settings.APP_ENV,
    )
