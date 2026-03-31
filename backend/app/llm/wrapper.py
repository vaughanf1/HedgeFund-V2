"""LLM call wrapper with Redis-backed cost gate.

ALL LLM calls MUST go through this wrapper.

Uses OpenAI GPT-4o for structured agent analysis.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.agents.loader import PersonaLoader
from app.agents.partitioner import DataPartitioner
from app.agents.schemas import AgentVerdict
from app.llm.exceptions import BudgetExceededError, LLMCallError
from app.llm.spend_tracker import (
    DEFAULT_DAILY_LIMIT_USD,
    SpendTracker,
    calculate_call_cost,
)

logger = logging.getLogger(__name__)


def _make_strict_schema(schema: dict) -> dict:
    """Recursively add additionalProperties: false to all object-type nodes.

    OpenAI strict mode requires this at every level.
    """
    schema = dict(schema)  # shallow copy
    if schema.get("type") == "object":
        schema["additionalProperties"] = False
    if "properties" in schema:
        schema["properties"] = {
            k: _make_strict_schema(v) for k, v in schema["properties"].items()
        }
    if "items" in schema and isinstance(schema["items"], dict):
        schema["items"] = _make_strict_schema(schema["items"])
    if "$defs" in schema:
        schema["$defs"] = {
            k: _make_strict_schema(v) for k, v in schema["$defs"].items()
        }
    return schema

# Default model
DEFAULT_MODEL = "gpt-4o"

# Conservative per-call cost estimate for pre-flight budget check
_PREFLIGHT_ESTIMATE_USD = 0.005


async def llm_call(
    model: str,
    messages: list[dict[str, str]],
    system: str,
    redis_client: Any,
    daily_limit_usd: float = DEFAULT_DAILY_LIMIT_USD,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """Make a single LLM call through the cost gate."""
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

    logger.info("Making LLM call: model=%s, remaining_budget=$%.4f", model, remaining)

    try:
        client = AsyncOpenAI()
        response = await client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                *messages,
            ],
        )
    except Exception as exc:
        raise LLMCallError(
            f"OpenAI API error during {model} call: {exc}",
            model=model,
            original_error=exc,
        ) from exc

    # Extract usage and calculate cost
    usage = response.usage
    input_tokens = usage.prompt_tokens if usage else 0
    output_tokens = usage.completion_tokens if usage else 0
    cost_usd = calculate_call_cost(model, input_tokens, output_tokens)

    await tracker.async_record_spend(cost_usd)

    content = ""
    if response.choices:
        content = response.choices[0].message.content or ""

    logger.info(
        "LLM call complete: model=%s, tokens=%d/%d, cost=$%.6f",
        model, input_tokens, output_tokens, cost_usd,
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
    """Render persona prompt and call LLM with cost gate."""
    partitioner = DataPartitioner()
    loader = PersonaLoader()

    partitioned = partitioner.partition_raw(persona_name, data_context)
    system_prompt = loader.render_persona(persona_name, partitioned)

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


async def llm_call_with_persona_parsed(
    persona_name: str,
    data_context: dict[str, Any],
    redis_client: Any,
    model: str = DEFAULT_MODEL,
    daily_limit_usd: float = DEFAULT_DAILY_LIMIT_USD,
    max_tokens: int = 1024,
) -> AgentVerdict:
    """Call LLM with structured JSON output, return validated AgentVerdict."""
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
        "Making parsed LLM call: persona=%s, model=%s, remaining_budget=$%.4f",
        persona_name, model, remaining,
    )

    # Partition data and render persona prompt
    partitioner = DataPartitioner()
    loader = PersonaLoader()
    partitioned = partitioner.partition_raw(persona_name, data_context)
    system_prompt = loader.render_persona(persona_name, partitioned)

    # Build JSON schema for structured output (OpenAI strict mode compatible)
    verdict_schema = _make_strict_schema(AgentVerdict.model_json_schema())

    try:
        client = AsyncOpenAI()
        response = await client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "Analyse the data in your system prompt and return your verdict.",
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "AgentVerdict",
                    "strict": True,
                    "schema": verdict_schema,
                },
            },
        )
    except Exception as exc:
        raise LLMCallError(
            f"OpenAI API error during {model} parsed call for {persona_name}: {exc}",
            model=model,
            original_error=exc,
        ) from exc

    # Extract usage and calculate cost
    usage = response.usage
    input_tokens = usage.prompt_tokens if usage else 0
    output_tokens = usage.completion_tokens if usage else 0
    cost_usd = calculate_call_cost(model, input_tokens, output_tokens)

    await tracker.async_record_spend(cost_usd)

    logger.info(
        "Parsed LLM call complete: persona=%s, model=%s, tokens=%d/%d, cost=$%.6f",
        persona_name, model, input_tokens, output_tokens, cost_usd,
    )

    # Parse the JSON response into AgentVerdict
    raw_content = response.choices[0].message.content or "{}"
    try:
        parsed = json.loads(raw_content)
        # Ensure persona is set correctly
        parsed["persona"] = persona_name
        verdict = AgentVerdict(**parsed)
    except Exception as exc:
        raise LLMCallError(
            f"Failed to parse structured output for {persona_name}: {raw_content[:200]}",
            model=model,
            original_error=exc,
        ) from exc

    return verdict
