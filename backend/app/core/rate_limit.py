"""Sliding-window rate limiter for PayGuard AI.

Supports in-memory tracking for single-process environments and Redis-backed
distributed rate limiting for multi-worker production deployments.
Handles client IP extraction safely behind trusted reverse proxies to prevent spoofing.
"""

from collections import defaultdict
import hashlib
import logging
import threading
import time
from typing import Dict, List, Optional
import uuid
from fastapi import HTTPException, Request, status

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


def extract_client_ip(request: Request, trusted_proxies: Optional[List[str]] = None) -> str:
    """Extracts client IP safely.
    
    If request is from an explicitly trusted reverse proxy, the client IP is extracted
    from the X-Forwarded-For header. If the peer is not in trusted_proxies, X-Forwarded-For
    is strictly ignored to prevent client IP spoofing attacks.
    """
    peer_ip = request.client.host if request.client else "127.0.0.1"
    proxies = trusted_proxies if trusted_proxies is not None else settings.TRUSTED_PROXIES

    if peer_ip in proxies:
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            client_candidates = [ip.strip() for ip in xff.split(",") if ip.strip()]
            if client_candidates:
                return client_candidates[0]
    return peer_ip


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
            # Periodically prune stale keys from inactive clients to prevent unbounded memory growth
            if len(self._timestamps) > 500:
                stale_keys = [
                    k for k, ts_list in list(self._timestamps.items())
                    if not ts_list or ts_list[-1] <= window_start
                ]
                for k in stale_keys:
                    self._timestamps.pop(k, None)

            # Clean up timestamps older than window for active key
            timestamps = self._timestamps.get(key)
            if timestamps:
                valid_timestamps = [t for t in timestamps if t > window_start]
                if valid_timestamps:
                    self._timestamps[key] = valid_timestamps
                else:
                    self._timestamps.pop(key, None)
                    valid_timestamps = []
            else:
                valid_timestamps = []

            current_count = len(valid_timestamps)

            if current_count >= max_requests:
                # Earliest timestamp that will drop off
                earliest = valid_timestamps[0]
                retry_after = max(1, int(window_seconds - (now - earliest)))
                return False, 0, retry_after

            # Record this request
            if key not in self._timestamps:
                self._timestamps[key] = [now]
            else:
                self._timestamps[key].append(now)
            remaining = max_requests - current_count - 1
            return True, remaining, 0

    def reset(self):
        """Clears all tracked rate-limit keys (useful for unit testing)."""
        with self._lock:
            self._timestamps.clear()


class RateLimitBackendUnavailableError(RuntimeError):
    """Raised when Redis rate limiting is required by security policy but unavailable."""


def is_redis_required() -> bool:
    """Determines whether Redis is mandatory for rate limiting.

    In production (APP_ENV=='production'), Redis is required by default unless
    RATE_LIMIT_REQUIRE_REDIS is explicitly set to False. In development/test/staging,
    in-memory fallback is permitted unless RATE_LIMIT_REQUIRE_REDIS is explicitly True.
    """
    if settings.RATE_LIMIT_REQUIRE_REDIS is not None:
        return bool(settings.RATE_LIMIT_REQUIRE_REDIS)
    return (settings.APP_ENV or "").lower() == "production"


class RedisSlidingWindowRateLimiter:
    """Distributed sliding-window rate limiter backed by Redis sorted sets."""

    def __init__(self, redis_url: str, allow_fallback: Optional[bool] = None):
        self.redis_url = redis_url
        self.allow_fallback = (not is_redis_required()) if allow_fallback is None else allow_fallback
        self._redis_client = None
        self._fallback_limiter = SlidingWindowRateLimiter()
        self._init_client()

    def _init_client(self):
        try:
            import redis
            self._redis_client = redis.Redis.from_url(
                self.redis_url,
                socket_timeout=1.5,
                socket_connect_timeout=1.5,
                decode_responses=True,
            )
            # Ping to verify immediate connection
            self._redis_client.ping()
        except Exception as err:
            if self.allow_fallback:
                logger.warning("Redis rate limiter connection unavailable (%s); using in-memory fallback.", err)
            else:
                logger.error("Redis rate limiter connection unavailable (%s) and fallback is disabled by policy.", err)
            self._redis_client = None

    def is_allowed(self, key: str, max_requests: int, window_seconds: int = 60) -> tuple[bool, int, int]:
        if not self._redis_client:
            if not self.allow_fallback:
                raise RateLimitBackendUnavailableError(
                    "Redis rate limiter is required by policy but connection is unavailable."
                )
            return self._fallback_limiter.is_allowed(key, max_requests, window_seconds)

        now = time.time()
        window_start = now - window_seconds
        redis_key = f"ratelimit:{key}"

        try:
            pipe = self._redis_client.pipeline()
            pipe.zremrangebyscore(redis_key, 0, window_start)
            pipe.zcard(redis_key)
            pipe.zrange(redis_key, 0, 0, withscores=True)
            results = pipe.execute()

            current_count = results[1]
            oldest_items = results[2]

            if current_count >= max_requests:
                earliest_score = oldest_items[0][1] if oldest_items else window_start
                retry_after = max(1, int(window_seconds - (now - earliest_score)))
                return False, 0, retry_after

            pipe = self._redis_client.pipeline()
            member = f"{now}:{uuid.uuid4().hex[:8]}"
            pipe.zadd(redis_key, {member: now})
            pipe.expire(redis_key, window_seconds + 5)
            pipe.execute()

            remaining = max_requests - current_count - 1
            return True, remaining, 0
        except Exception as err:
            if not self.allow_fallback:
                logger.error("Redis operation failed (%s) and fallback is disabled; failing closed.", err)
                raise RateLimitBackendUnavailableError(
                    f"Redis rate limiter operation failed: {err}"
                ) from err
            logger.warning("Redis operation failed (%s); falling back to in-memory limiter.", err)
            return self._fallback_limiter.is_allowed(key, max_requests, window_seconds)

    def reset(self):
        if self._redis_client:
            try:
                keys = self._redis_client.keys("ratelimit:*")
                if keys:
                    self._redis_client.delete(*keys)
            except Exception:
                pass
        self._fallback_limiter.reset()


def get_rate_limiter():
    """Initializes appropriate limiter depending on configuration and environment policy."""
    require_redis = is_redis_required()
    if settings.REDIS_URL:
        return RedisSlidingWindowRateLimiter(
            settings.REDIS_URL,
            allow_fallback=not require_redis,
        )
    if require_redis:
        raise RateLimitBackendUnavailableError(
            "Redis rate limiting is required in production (or when RATE_LIMIT_REQUIRE_REDIS=True), "
            "but REDIS_URL is not configured."
        )
    return SlidingWindowRateLimiter()


limiter = SlidingWindowRateLimiter()
if settings.REDIS_URL:
    limiter = RedisSlidingWindowRateLimiter(
        settings.REDIS_URL,
        allow_fallback=not is_redis_required(),
    )


def rate_limit(action: str, max_requests: int, window_seconds: int = 60):
    """FastAPI dependency factory enforcing rate limits on endpoints."""
    async def dependency(request: Request):
        if not settings.RATE_LIMIT_ENABLED:
            return

        require_redis = is_redis_required()
        if require_redis and not settings.REDIS_URL:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiting backend is required in production but REDIS_URL is not configured.",
            )

        client_ip = extract_client_ip(request)
        auth_header = request.headers.get("Authorization", "")
        key = f"{action}:{client_ip}"
        if auth_header.startswith("Bearer ") and len(auth_header) > 7:
            raw_token = auth_header[7:].strip()
            token_digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()[:16]
            key = f"{action}:{client_ip}:{token_digest}"

        active_limiter = limiter
        if require_redis and isinstance(active_limiter, SlidingWindowRateLimiter):
            # Dynamically instantiate Redis limiter when production policy is active
            active_limiter = RedisSlidingWindowRateLimiter(
                settings.REDIS_URL,
                allow_fallback=False,
            )

        try:
            allowed, remaining, retry_after = active_limiter.is_allowed(
                key=key,
                max_requests=max_requests,
                window_seconds=window_seconds,
            )
        except RateLimitBackendUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiting service is unavailable. Request rejected by fail-safe security policy.",
            ) from exc

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
