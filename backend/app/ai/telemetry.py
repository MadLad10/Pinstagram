"""Every model call is logged (one structured line) and stored in `llm_calls`.

Rows are written in their own session so logging never joins, commits or
rolls back the caller's transaction, and a logging failure never fails the
request.
"""

import logging
import uuid

from app.ai.pricing import estimate_cost
from app.ai.types import Usage
from app.db.session import AsyncSessionLocal
from app.models.llm_call import LLMCall

log = logging.getLogger("app.ai.calls")


async def record_call(
    *,
    purpose: str,
    provider: str,
    model: str,
    usage: Usage,
    latency_ms: int,
    status: str,
    user_id: uuid.UUID | None = None,
    error: BaseException | str | None = None,
) -> None:
    cost, list_cost = estimate_cost(model, usage.input_tokens, usage.output_tokens)
    error_text = None
    if error is not None:
        error_text = (
            error if isinstance(error, str) else f"{type(error).__name__}: {error}"
        )[:500]
    log.info(
        "llm_call purpose=%s provider=%s model=%s status=%s in=%d out=%d%s "
        "latency_ms=%d cost_usd=%.6f list_cost_usd=%.6f%s",
        purpose,
        provider,
        model,
        status,
        usage.input_tokens,
        usage.output_tokens,
        " (estimated)" if usage.estimated else "",
        latency_ms,
        cost,
        list_cost,
        f" error={error_text!r}" if error_text else "",
    )
    try:
        async with AsyncSessionLocal() as db:
            db.add(
                LLMCall(
                    purpose=purpose,
                    provider=provider,
                    model=model,
                    user_id=user_id,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    tokens_estimated=usage.estimated,
                    latency_ms=latency_ms,
                    cost_usd=cost,
                    list_cost_usd=list_cost,
                    status=status,
                    error=error_text,
                )
            )
            await db.commit()
    except Exception:
        log.warning("Could not store llm_call row", exc_info=True)
