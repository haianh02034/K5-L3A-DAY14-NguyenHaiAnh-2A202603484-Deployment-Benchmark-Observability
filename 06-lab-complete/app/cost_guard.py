"""
Cost guard (tiêu chí 8).
"""
from datetime import datetime, timezone
from fastapi import HTTPException
from app.config import settings
from app.redis_client import get_redis

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

_mem_cost: float = 0.0


def _cost_key() -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"cost:daily:{today}"


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    global _mem_cost
    budget = min(settings.daily_budget_usd, settings.monthly_budget_usd)
    current_cost = _mem_cost

    client = get_redis()
    if client is not None:
        try:
            val = client.get(_cost_key())
            if val is not None:
                current_cost = float(val)
        except Exception:
            pass

    if current_cost >= budget:
        raise HTTPException(
            status_code=402,
            detail=f"Budget exceeded. Current spending: ${current_cost:.6f}, budget: ${budget:.6f}",
        )


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    global _mem_cost
    cost = (input_tokens / 1000.0) * PRICE_INPUT_PER_1K + (output_tokens / 1000.0) * PRICE_OUTPUT_PER_1K
    _mem_cost += cost

    client = get_redis()
    if client is not None:
        try:
            key = _cost_key()
            client.incrbyfloat(key, cost)
            client.expire(key, 86400 * 2)
        except Exception:
            pass
    return cost
