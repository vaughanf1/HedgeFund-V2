"""Redis-backed daily LLM spend tracker.

Tracks accumulated LLM spend per calendar day (UTC) and enforces a configurable
daily budget ceiling. All costs are stored in USD.

Key design decisions:
- Day boundary is UTC midnight to avoid timezone ambiguity across services.
- Redis key uses the format ``llm:spend:YYYY-MM-DD`` with a TTL of 25 hours so
  stale keys are cleaned up automatically.
- Costs are stored as strings with 6 decimal places of precision (sufficient for
  sub-cent accuracy on all current Anthropic models).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pricing table (USD per million tokens)
# Update when Anthropic changes pricing.
# ---------------------------------------------------------------------------
COST_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-haiku-4-5": {
        "input": 0.80,   # $0.80 / M input tokens
        "output": 4.00,  # $4.00 / M output tokens
    },
    "claude-sonnet-4-6": {
        "input": 3.00,   # $3.00 / M input tokens
        "output": 15.00, # $15.00 / M output tokens
    },
}

# Default daily spend ceiling in USD
DEFAULT_DAILY_LIMIT_USD: float = 10.0

# Redis key TTL: 25 hours ensures cleanup while surviving a brief clock drift
_KEY_TTL_SECONDS = 25 * 3600


def _today_key() -> str:
    """Return the Redis key for today's spend (UTC date)."""
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    return f"llm:spend:{today}"


def calculate_call_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate the USD cost of a completed LLM call.

    Args:
        model: Model identifier (must be in ``COST_PER_MTOK``).
        input_tokens: Number of input tokens consumed.
        output_tokens: Number of output tokens generated.

    Returns:
        Cost in USD as a float.

    Raises:
        KeyError: If *model* is not in the pricing table.
    """
    if model not in COST_PER_MTOK:
        raise KeyError(
            f"Model '{model}' not in pricing table. "
            f"Known models: {list(COST_PER_MTOK.keys())}"
        )
    pricing = COST_PER_MTOK[model]
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


class SpendTracker:
    """Tracks and enforces the daily LLM spend budget using Redis.

    Args:
        redis_client: A synchronous or async Redis client instance. Expected to
            support ``get``, ``incrbyfloat``, and ``expire`` methods. Pass a
            ``redis.Redis`` or ``redis.asyncio.Redis`` instance.
        daily_limit_usd: Maximum allowed spend per UTC calendar day.
    """

    def __init__(
        self,
        redis_client: Any,
        daily_limit_usd: float = DEFAULT_DAILY_LIMIT_USD,
    ) -> None:
        self._redis = redis_client
        self.daily_limit_usd = daily_limit_usd

    # ------------------------------------------------------------------
    # Synchronous interface
    # ------------------------------------------------------------------

    def get_current_spend(self) -> float:
        """Return the accumulated spend today (USD). Returns 0.0 if no spend yet."""
        raw = self._redis.get(_today_key())
        return float(raw) if raw is not None else 0.0

    def check_budget(self, projected_cost_usd: float = 0.0) -> tuple[bool, float]:
        """Check whether a call costing *projected_cost_usd* is within budget.

        Args:
            projected_cost_usd: Estimated cost of the upcoming call.

        Returns:
            ``(within_budget, remaining_usd)`` tuple.
        """
        current = self.get_current_spend()
        remaining = self.daily_limit_usd - current
        within = (current + projected_cost_usd) <= self.daily_limit_usd
        return within, remaining

    def record_spend(self, cost_usd: float) -> float:
        """Atomically add *cost_usd* to today's spend counter.

        Sets a TTL on the Redis key to ensure automatic expiry.

        Returns:
            The new running total for today (USD).
        """
        key = _today_key()
        new_total = self._redis.incrbyfloat(key, cost_usd)
        # Refresh TTL on every write so the key lives at least another 25 h
        self._redis.expire(key, _KEY_TTL_SECONDS)
        logger.info(
            "LLM spend recorded: +$%.6f, daily total: $%.6f / $%.2f limit",
            cost_usd,
            float(new_total),
            self.daily_limit_usd,
        )
        return float(new_total)

    def get_daily_summary(self) -> dict[str, float]:
        """Return a summary dict with current spend, limit, and remaining budget."""
        current = self.get_current_spend()
        return {
            "current_spend_usd": current,
            "daily_limit_usd": self.daily_limit_usd,
            "remaining_usd": max(0.0, self.daily_limit_usd - current),
            "utilisation_pct": (current / self.daily_limit_usd * 100) if self.daily_limit_usd > 0 else 0.0,
        }

    # ------------------------------------------------------------------
    # Async interface
    # ------------------------------------------------------------------

    async def async_get_current_spend(self) -> float:
        """Async variant of ``get_current_spend``."""
        raw = await self._redis.get(_today_key())
        return float(raw) if raw is not None else 0.0

    async def async_check_budget(self, projected_cost_usd: float = 0.0) -> tuple[bool, float]:
        """Async variant of ``check_budget``."""
        current = await self.async_get_current_spend()
        remaining = self.daily_limit_usd - current
        within = (current + projected_cost_usd) <= self.daily_limit_usd
        return within, remaining

    async def async_record_spend(self, cost_usd: float) -> float:
        """Async variant of ``record_spend``."""
        key = _today_key()
        new_total = await self._redis.incrbyfloat(key, cost_usd)
        await self._redis.expire(key, _KEY_TTL_SECONDS)
        logger.info(
            "LLM spend recorded: +$%.6f, daily total: $%.6f / $%.2f limit",
            cost_usd,
            float(new_total),
            self.daily_limit_usd,
        )
        return float(new_total)

    async def async_get_daily_summary(self) -> dict[str, float]:
        """Async variant of ``get_daily_summary``."""
        current = await self.async_get_current_spend()
        return {
            "current_spend_usd": current,
            "daily_limit_usd": self.daily_limit_usd,
            "remaining_usd": max(0.0, self.daily_limit_usd - current),
            "utilisation_pct": (current / self.daily_limit_usd * 100) if self.daily_limit_usd > 0 else 0.0,
        }
