"""Redis-backed fixed-window rate limiting.

Two layers, matching the limits in API.md:
- `RateLimitMiddleware`: blanket per-user limits on reads and writes.
- `rate_limit(...)` dependency: tighter per-route limits (auth, comments).

If Redis is unreachable the limiter fails open and logs, so an outage of the
cache never takes the API down with it.
"""

import logging
import time

from fastapi import HTTPException, Request, status
from jose import JWTError
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.security import decode_token

log = logging.getLogger(__name__)

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.REDIS_URL, socket_timeout=0.5)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def hit(key: str, limit: int, window_s: int) -> int | None:
    """Count one hit against `key`. Returns seconds until reset if over the
    limit, otherwise None."""
    if not settings.RATE_LIMIT_ENABLED:
        return None
    window = int(time.time() // window_s)
    redis_key = f"rl:{key}:{window}"
    try:
        r = get_redis()
        async with r.pipeline(transaction=True) as pipe:
            pipe.incr(redis_key)
            pipe.expire(redis_key, window_s)
            count, _ = await pipe.execute()
    except (RedisError, OSError) as exc:
        log.warning("rate limiter unavailable, failing open: %s", exc)
        return None
    if count > limit:
        return window_s - int(time.time()) % window_s
    return None


def client_ip(request: Request) -> str:
    hops = settings.TRUSTED_PROXY_HOPS
    if hops > 0:
        # Each trusted proxy appends the address it saw; anything to the left
        # of those entries came from the client and can be forged.
        chain = [
            ip.strip()
            for ip in request.headers.get("x-forwarded-for", "").split(",")
            if ip.strip()
        ]
        if len(chain) >= hops:
            return chain[-hops]
    return request.client.host if request.client else "unknown"


def _subject(request: Request) -> str:
    """Rate-limit identity: the user id from a valid bearer token, else the IP."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            return "u:" + decode_token(auth[7:])["sub"]
        except (JWTError, KeyError):
            pass
    return "ip:" + client_ip(request)


def rate_limit(scope: str, limit: int, window_s: int, per: str = "ip"):
    """FastAPI dependency factory. `per` is "ip" or "user"."""

    async def _dep(request: Request) -> None:
        ident = _subject(request) if per == "user" else "ip:" + client_ip(request)
        retry_after = await hit(f"{scope}:{ident}", limit, window_s)
        if retry_after is not None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests",
                headers={"Retry-After": str(retry_after)},
            )

    return _dep


class RateLimitMiddleware(BaseHTTPMiddleware):
    READ_LIMIT = 600
    WRITE_LIMIT = 60

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/"):
            is_write = request.method in ("POST", "PUT", "PATCH", "DELETE")
            limit = self.WRITE_LIMIT if is_write else self.READ_LIMIT
            scope = "w" if is_write else "r"
            retry_after = await hit(f"{scope}:{_subject(request)}", limit, 60)
            if retry_after is not None:
                return JSONResponse(
                    {"detail": "Too many requests"},
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )
        return await call_next(request)
