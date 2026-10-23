"""PayGuard AI FastAPI Application Entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.router import api_router
from backend.app.core.config import settings
from backend.app.core.errors import register_error_handlers


def create_application() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        description=(
            "PayGuard AI is an AI-powered payment investigation backend that helps payment operations "
            "and support engineers investigate transaction issues using deterministic triage, "
            "PostgreSQL pgvector RAG, and grounded LLM reasoning."
        ),
    )

    # 1. Custom Security and Tracing Middlewares
    from backend.app.core.middleware import (
        RequestBodyLimitMiddleware,
        RequestIDMiddleware,
        SecurityHeadersMiddleware,
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        RequestBodyLimitMiddleware,
        max_body_bytes=settings.REQUEST_MAX_BODY_BYTES,
    )

    # 2. Set up CORS middleware
    if settings.BACKEND_CORS_ORIGINS:
        origins = [str(origin) for origin in settings.BACKEND_CORS_ORIGINS]
        # Prevent insecure wildcard with credentials
        allow_cred = True
        if "*" in origins:
            allow_cred = False

        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=allow_cred,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )

    # 3. Register standardized error handlers
    register_error_handlers(app)


    # Mount master API v1 router
    app.include_router(api_router, prefix=settings.API_V1_STR)

    return app


app = create_application()
