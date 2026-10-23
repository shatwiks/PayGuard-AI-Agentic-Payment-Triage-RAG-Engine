"""Sliding-window in-memory rate limiter for PayGuard AI.

Protects against brute-force attacks, endpoint denial-of-service,
and uncontrolled API abuse.
"""

from collections import defaultdict
import threading
import time
from typing import Dict, List, Optional
from fastapi import HTTPException, Request, status

from backend.app.core.config import settings


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window in-memory rate limiter with stale key pruning."""

    def __init__(self):
        # Maps key -> list of timestamp floats
        self._timestamps: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, key: str, max_requests: int, window_seconds: int = 60) -> tuple[bool, int, int]:
        """Checks if a request under `key` is permitted.

        Returns:
            (allowed: bool, remaining: int, retry_after: int)
        """
        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            # Clean up timestamps older than window
            timestamps = self._timestamps[key]
            valid_timestamps = [t for t in timestamps if t > window_start]

            if not valid_timestamps and key in self._timestamps:
                # Prune dead key to prevent unbounded memory growth
                self._timestamps.pop(key, None)
                self._timestamps[key] = []
            else:
                self._timestamps[key] = valid_timestamps

            current_count = len(self._timestamps[key])

            if current_count >= max_requests:
                # Earliest timestamp that will drop off
                earliest = self._timestamps[key][0]
                retry_after = max(1, int(window_seconds - (now - earliest)))
                return False, 0, retry_after

            # Record this request
            self._timestamps[key].append(now)
            remaining = max_requests - current_count - 1
            return True, remaining, 0

    def reset(self):
        """Clears all tracked rate-limit keys (useful for unit testing)."""
        with self._lock:
            self._timestamps.clear()


limiter = SlidingWindowRateLimiter()


def rate_limit(action: str, max_requests: int, window_seconds: int = 60):
    """FastAPI dependency factory enforcing rate limits on endpoints."""
    async def dependency(request: Request):
        if not settings.RATE_LIMIT_ENABLED:
            return

        # Derive key: Prefer authenticated user if present in state, else client IP
        client_ip = request.client.host if request.client else "127.0.0.1"
        auth_header = request.headers.get("Authorization", "")
        key = f"{action}:{client_ip}"
        if auth_header.startswith("Bearer "):
            token_prefix = auth_header[7:20]
            key = f"{action}:{client_ip}:{token_prefix}"

        allowed, remaining, retry_after = limiter.is_allowed(
            key=key,
            max_requests=max_requests,
            window_seconds=window_seconds,
        )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for action '{action}'. Please retry in {retry_after} seconds.",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

    return dependency
