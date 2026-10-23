"""Health check and system telemetry router with real database readiness probe."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System Health & Readiness Probe",
    description="Returns service liveness, verifies live database connectivity, and checks pgvector readiness.",
)
async def get_health(
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> HealthResponse:
    db_status = "connected"
    vector_status = "pgvector_ready"
    overall_status = "healthy"

    try:
        # Probe active database connection
        await db.execute(text("SELECT 1;"))
        # Verify vector extension availability if running PostgreSQL
        bind = db.bind
        dialect = bind.dialect.name if bind else ""
        if dialect == "postgresql":
            ext_check = await db.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector';")
            )
            if ext_check.scalar_one_or_none() is not None:
                vector_status = "pgvector_ready"
            else:
                vector_status = "pgvector_missing"
        else:
            vector_status = "sqlite_fallback_ready"
    except Exception as e:
        db_status = f"unhealthy: {str(e)[:100]}"
        vector_status = "unavailable"
        overall_status = "degraded"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=overall_status,
        database=db_status,
        vector_store=vector_status,
        version=settings.VERSION,
        environment=settings.APP_ENV,
    )
