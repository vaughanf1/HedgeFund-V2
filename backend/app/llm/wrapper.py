"""LLM call wrapper with Redis-backed cost gate.

ALL LLM calls MUST go through this wrapper.

This module is the single enforcement point for:
1. Pre-call budget checking — calls that would exceed the daily limit are
   rejected before any API request is made.
2. Post-call cost recording — exact token counts from the API response are
   used to calculate and record the true cost.
3. Consistent error handling — all API errors are wrapped in ``LLMCallError``.

Usage::

    import redis.asyncio as aioredis
    from app.llm.wrapper import llm_call, llm_call_with_persona

    redis_client = aioredis.from_url("redis://localhost:6379")

    result = await llm_call(
        model="claude-haiku-4-5",
        messages=[{"role": "user", "content": "Analyse AAPL"}],
        system="You are a financial analyst.",
        redis_client=redis_client,
    )
    print(result["content"])
"""

from __future__ import annotations

import logging
from typing import Any

import anthropic

from app.agents.loader import PersonaLoader
from app.agents.partitioner import DataPartitioner
from app.llm.exceptions import BudgetExceededError, LLMCallError
from app.llm.spend_tracker import (
    DEFAULT_DAILY_LIMIT_USD,
    COST_PER_MTOK,
    SpendTracker,
    calculate_call_cost,
)

logger = logging.getLogger(__name__)

# Default model used when none is specified
DEFAULT_MODEL = "claude-haiku-4-5"

# Conservative per-call cost estimate used for pre-flight budget check.
# This is ~2k input + ~500 output tokens at haiku pricing — a reasonable
# lower bound so the gate fires before spend goes significantly over budget.
_PREFLIGHT_ESTIMATE_USD = 0.003


async def llm_call(
    model: str,
    messages: list[dict[str, str]],
    system: str,
    redis_client: Any,
    daily_limit_usd: float = DEFAULT_DAILY_LIMIT_USD,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """Make a single LLM call through the cost gate.

    Checks budget before calling, records exact spend after, and raises
    ``BudgetExceededError`` if the pre-flight estimate would breach the limit.

    Args:
        model: Anthropic model identifier (must be in ``COST_PER_MTOK``).
        messages: List of message dicts with ``role`` and ``content`` keys.
        system: System prompt string.
        redis_client: An async Redis client (``redis.asyncio.Redis``).
        daily_limit_usd: Daily spend ceiling in USD.
        max_tokens: Maximum tokens in the model response.

    Returns:
        A dict with keys:
        - ``content``: The text content of the first response block.
        - ``input_tokens``: Token count for the input.
        - ``output_tokens``: Token count for the output.
        - ``cost_usd``: Exact cost of this call.
        - ``model``: Model used.

    Raises:
        BudgetExceededError: If the pre-flight cost estimate would exceed budget.
        LLMCallError: If the Anthropic API call fails.
        KeyError: If *model* is not in the pricing table.
    """
    tracker = SpendTracker(redis_client, daily_limit_usd=daily_limit_usd)

    # Pre-flight budget check
    within_budget, remaining = await tracker.async_check_budget(_PREFLIGHT_ESTIMATE_USD)
    if not within_budget:
        current = await tracker.async_get_current_spend()
        raise BudgetExceededError(
            current_spend_usd=current,
            limit_usd=daily_limit_usd,
            projected_cost_usd=_PREFLIGHT_ESTIMATE_USD,
        )

    logger.info(
        "Making LLM call: model=%s, remaining_budget=$%.4f",
        model,
        remaining,
    )

    # Make the API call
    try:
        client = anthropic.AsyncAnthropic()
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
    except anthropic.APIError as exc:
        raise LLMCallError(
            f"Anthropic API error during {model} call: {exc}",
            model=model,
            original_error=exc,
        ) from exc
    except Exception as exc:
        raise LLMCallError(
            f"Unexpected error during {model} call: {exc}",
            model=model,
            original_error=exc,
        ) from exc

    # Extract usage and calculate exact cost
    input_tokens: int = response.usage.input_tokens
    output_tokens: int = response.usage.output_tokens
    cost_usd = calculate_call_cost(model, input_tokens, output_tokens)

    # Record exact spend
    await tracker.async_record_spend(cost_usd)

    # Extract text content
    content = ""
    if response.content:
        first_block = response.content[0]
        if hasattr(first_block, "text"):
            content = first_block.text

    logger.info(
        "LLM call complete: model=%s, tokens=%d/%d, cost=$%.6f",
        model,
        input_tokens,
        output_tokens,
        cost_usd,
    )

    return {
        "content": content,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
        "model": model,
    }


async def llm_call_with_persona(
    persona_name: str,
    data_context: dict[str, Any],
    redis_client: Any,
    model: str = DEFAULT_MODEL,
    daily_limit_usd: float = DEFAULT_DAILY_LIMIT_USD,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """Convenience wrapper: render persona prompt and call LLM with cost gate.

    Partitions the data context for the persona, renders the system prompt,
    and calls ``llm_call``.

    Args:
        persona_name: One of ``{"buffett", "munger", "ackman", "cohen", "dalio"}``.
        data_context: Full data dict. The partitioner will strip fields the
            persona is not permitted to see.
        redis_client: An async Redis client.
        model: Anthropic model identifier.
        daily_limit_usd: Daily spend ceiling in USD.
        max_tokens: Maximum tokens in the model response.

    Returns:
        Same dict as ``llm_call`` with an additional ``persona`` key.

    Raises:
        BudgetExceededError: If the daily budget would be exceeded.
        LLMCallError: If the API call fails.
        ValueError: If *persona_name* is not recognised.
    """
    partitioner = DataPartitioner()
    loader = PersonaLoader()

    # Enforce information asymmetry: strip fields this persona cannot see
    partitioned = partitioner.partition_raw(persona_name, data_context)

    # Render the persona Markdown as the system prompt
    system_prompt = loader.render_persona(persona_name, partitioned)

    # Single-turn: ask the persona to analyse the data
    messages = [
        {
            "role": "user",
            "content": (
                "Analyse the data in your system prompt and return your "
                "verdict as a JSON object following your output format exactly."
            ),
        }
    ]

    result = await llm_call(
        model=model,
        messages=messages,
        system=system_prompt,
        redis_client=redis_client,
        daily_limit_usd=daily_limit_usd,
        max_tokens=max_tokens,
    )
    result["persona"] = persona_name
    return result
