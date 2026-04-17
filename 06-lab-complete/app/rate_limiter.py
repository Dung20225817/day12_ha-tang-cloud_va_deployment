"""Redis sliding-window rate limiter."""
import time
import uuid

import redis
from fastapi import HTTPException

from app.config import settings


def check_rate_limit(user_id: str, rds: redis.Redis) -> None:
    """Enforce per-user request quota for the last 60 seconds."""
    if user_id in settings.admin_user_ids:
        return

    now_ms = int(time.time() * 1000)
    window_ms = 60_000
    reset_epoch = int((now_ms + window_ms) / 1000)
    key = f"rate:{user_id}"

    pipe = rds.pipeline(transaction=True)
    pipe.zremrangebyscore(key, 0, now_ms - window_ms)
    pipe.zcard(key)
    _, current_count = pipe.execute()

    if current_count >= settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "limit": settings.rate_limit_per_minute,
                "window_seconds": 60,
            },
            headers={
                "X-RateLimit-Limit": str(settings.rate_limit_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_epoch),
                "Retry-After": "60",
            },
        )

    member = f"{now_ms}-{uuid.uuid4().hex}"
    pipe = rds.pipeline(transaction=True)
    pipe.zadd(key, {member: now_ms})
    pipe.expire(key, 120)
    pipe.execute()
