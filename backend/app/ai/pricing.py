"""Estimated cost of a model call.

List prices in USD per 1M tokens (input, output) for the paid tiers; verify
against the provider's pricing page and override with the LLM_PRICES setting
when they change. Models not listed (local Ollama models) cost nothing.
"""

import json
import logging
from functools import cache

from app.core.config import settings

log = logging.getLogger(__name__)

LIST_PRICES: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-embedding-001": (0.15, 0.0),
    "text-embedding-3-small": (0.02, 0.0),
    "gpt-4o-mini": (0.15, 0.60),
}


@cache
def _prices() -> dict[str, tuple[float, float]]:
    prices = dict(LIST_PRICES)
    if settings.LLM_PRICES:
        try:
            prices |= {k: tuple(v) for k, v in json.loads(settings.LLM_PRICES).items()}
        except (ValueError, TypeError):
            log.warning("Ignoring malformed LLM_PRICES setting")
    return prices


def list_price(model: str) -> tuple[float, float]:
    """Longest-prefix match, so dated variants ("gemini-2.5-flash-001") and
    "models/..." names resolve to their family's price."""
    name = model.removeprefix("models/")
    best = ""
    for key in _prices():
        if name.startswith(key) and len(key) > len(best):
            best = key
    return _prices()[best] if best else (0.0, 0.0)


def estimate_cost(
    model: str, input_tokens: int, output_tokens: int
) -> tuple[float, float]:
    """(billed cost, list-price cost) in USD."""
    price_in, price_out = list_price(model)
    list_cost = (input_tokens * price_in + output_tokens * price_out) / 1_000_000
    return (0.0 if settings.LLM_FREE_TIER else list_cost), list_cost
