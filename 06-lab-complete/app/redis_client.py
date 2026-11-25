"""
Kết nối Redis dùng chung cho rate limiter và cost guard.
"""
import logging
from typing import Optional
import redis
from app.config import settings

logger = logging.getLogger(__name__)

r: Optional[redis.Redis] = None


def get_redis() -> Optional[redis.Redis]:
    global r
    if not settings.redis_url:
        return None
    if r is None:
        try:
            r = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )
        except Exception:
            return None
    return r


def redis_healthy() -> bool:
    """GET /ready: Trả về True nếu Redis kết nối và phản hồi PING, False nếu lỗi."""
    if not settings.redis_url:
        return False
    try:
        client = get_redis()
        if client is None:
            return False
        return bool(client.ping())
    except Exception:
        return False
