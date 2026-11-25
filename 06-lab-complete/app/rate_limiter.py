"""
Rate limiting (tiêu chí 7).
"""
import time
from fastapi import HTTPException
from app.config import settings
from app.redis_client import get_redis


def check_rate_limit(key: str) -> None:
    """Kiểm tra giới hạn request theo sliding window với Redis."""
    limit = settings.rate_limit_per_minute
    window = 60
    now = time.time()
    redis_key = f"rate_limit:{key}"

    client = get_redis()
    if client is not None:
        try:
            pipe = client.pipeline()
            pipe.zremrangebyscore(redis_key, 0, now - window)
            pipe.zcard(redis_key)
            results = pipe.execute()
            current_count = results[1]

            if current_count >= limit:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded ({limit} requests/minute)",
                    headers={"Retry-After": str(window)},
                )

            pipe = client.pipeline()
            pipe.zadd(redis_key, {f"{now}:{time.time_ns()}": now})
            pipe.expire(redis_key, window + 10)
            pipe.execute()
            return
        except HTTPException:
            raise
        except Exception:
            pass
