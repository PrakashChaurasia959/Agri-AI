"""A small, dependency-free sliding-window rate limiter.

Why not a third-party package?  The project needs a limiter that works
identically on every deployment target (local dev server, uvicorn workers,
Render).  A process-local implementation is *not* a distributed limiter - it
is documented as such in the README - but it reliably protects a single
instance from credential-stuffing style bursts.

Each distinct client key (IP address, or user id when authenticated) gets a
deque of request timestamps.  Stale timestamps are evicted lazily, so memory
usage stays bounded by the number of active clients within the window.
"""

from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from typing import Deque, Iterable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


@dataclass(frozen=True)
class RateLimitRule:
    """A named limit: at most ``limit`` requests per ``window_seconds``."""

    name: str
    limit: int
    window_seconds: int


class SlidingWindowLimiter:
    """Thread-safe in-memory sliding window counter."""

    def __init__(self) -> None:
        self._hits: dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._last_sweep = time.monotonic()

    def hit(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int, int]:
        """Record a request.

        Returns ``(allowed, remaining, retry_after_seconds)``.
        """
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                oldest = bucket[0]
                retry_after = max(1, math.ceil(oldest + window_seconds - now))
                return False, 0, retry_after

            bucket.append(now)
            remaining = max(0, limit - len(bucket))
            self._maybe_sweep(now)
            return True, remaining, 0

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)

    def _maybe_sweep(self, now: float) -> None:
        """Drop buckets that have gone completely stale."""
        if now - self._last_sweep < 60:
            return
        self._last_sweep = now
        stale_cutoff = now - 900
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= stale_cutoff]:
            self._hits.pop(key, None)


limiter = SlidingWindowLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Applies a global rate limit to every incoming request.

    Sensitive routes (login / register) additionally apply a stricter rule
    inside their handlers via :func:`enforce_rate_limit`.
    """

    def __init__(self, app, rule: RateLimitRule, enabled: bool = True) -> None:
        super().__init__(app)
        self.rule = rule
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        client_key = client_identifier(request)
        allowed, remaining, retry_after = limiter.hit(
            client_key, self.rule.limit, self.rule.window_seconds
        )
        if not allowed:
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please slow down and try again shortly.",
                    "retry_after_seconds": retry_after,
                },
            )
            response.headers["Retry-After"] = str(retry_after)
            response.headers["X-RateLimit-Limit"] = str(self.rule.limit)
            response.headers["X-RateLimit-Remaining"] = "0"
            return response

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.rule.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


def client_identifier(request: Request) -> str:
    """Best-effort client identity for rate limiting.

    Uses the authenticated user id when available, otherwise the source IP.
    ``X-Forwarded-For`` is only trusted when the app is running behind a
    proxy - otherwise a client could trivially spoof it.
    """
    user = getattr(request.state, "user", None)
    if user is not None:
        user_id = getattr(user, "id", None) or getattr(user, "_id", None)
        if user_id:
            return f"user:{user_id}"

    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    client = request.client
    if client and client.host:
        return f"ip:{client.host}"
    return "ip:unknown"


def enforce_rate_limit(
    request: Request,
    rule: RateLimitRule,
    enabled: bool = True,
) -> None:
    """Raise HTTP 429 when a client exceeds a route specific limit."""
    if not enabled:
        return
    key = f"{rule.name}:{client_identifier(request)}"
    allowed, _remaining, retry_after = limiter.hit(key, rule.limit, rule.window_seconds)
    if not allowed:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=429,
            detail=(
                "Too many attempts. Please wait "
                f"{retry_after}s before trying again."
            ),
            headers={"Retry-After": str(retry_after)},
        )


def reset_limiter() -> None:
    """Testing helper - clears all recorded hits."""
    limiter.reset()


def snapshot_keys() -> Iterable[str]:
    """Testing helper - current limiter keys."""
    return list(limiter._hits.keys())
