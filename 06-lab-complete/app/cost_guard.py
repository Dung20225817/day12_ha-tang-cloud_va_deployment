"""Monthly budget guard backed by Redis."""
from datetime import datetime, timezone

import redis
from fastapi import HTTPException

from app.config import settings

INPUT_COST_PER_1K = 0.00015
OUTPUT_COST_PER_1K = 0.00060


def estimate_cost_usd(question: str, answer: str) -> float:
    """Estimate token cost for a request/response pair."""
    input_tokens = max(1, len(question.split()) * 2)
    output_tokens = max(1, len(answer.split()) * 2)
    input_cost = (input_tokens / 1000) * INPUT_COST_PER_1K
    output_cost = (output_tokens / 1000) * OUTPUT_COST_PER_1K
    return round(input_cost + output_cost, 6)


def _budget_key(user_id: str) -> str:
    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    return f"budget:{user_id}:{month_key}"


def get_monthly_spending(user_id: str, rds: redis.Redis) -> float:
    current = rds.get(_budget_key(user_id))
    return round(float(current or 0.0), 6)


def check_budget(user_id: str, estimated_cost: float, rds: redis.Redis) -> None:
    """Raise HTTP 402 if adding estimated_cost would exceed monthly budget."""
    if user_id in settings.admin_user_ids:
        return

    key = _budget_key(user_id)
    current = float(rds.get(key) or 0.0)
    projected = current + estimated_cost

    if projected > settings.monthly_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Monthly budget exceeded",
                "used_usd": round(current, 6),
                "requested_usd": round(estimated_cost, 6),
                "budget_usd": settings.monthly_budget_usd,
            },
        )

    pipe = rds.pipeline(transaction=True)
    pipe.incrbyfloat(key, estimated_cost)
    pipe.expire(key, 32 * 24 * 3600)
    pipe.execute()
