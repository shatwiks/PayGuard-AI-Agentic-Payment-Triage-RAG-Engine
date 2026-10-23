"""Production Security and Observability Middlewares for PayGuard AI.

Provides:
1. SecurityHeadersMiddleware: Adds OWASP recommended security headers.
2. RequestIDMiddleware: Injects and traces request correlation IDs (X-Request-ID).
3. RequestBodyLimitMiddleware: Rejects oversized request payloads (HTTP 413).
"""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects standard defensive HTTP security headers into all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Propagates or generates an X-Request-ID correlation trace header."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RequestBodyLimitMiddleware(BaseHTTPMiddleware):
    """Enforces strict maximum request body size limits to prevent memory exhaustion."""

    def __init__(self, app, max_body_bytes: int = 1_048_576):
        super().__init__(app)
        self.max_body_bytes = max_body_bytes

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > self.max_body_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "PAYLOAD_TOO_LARGE",
                                "message": f"Request body exceeds maximum allowed limit of {self.max_body_bytes} bytes.",
                            }
                        },
                    )
            except ValueError:
                pass
        return await call_next(request)
