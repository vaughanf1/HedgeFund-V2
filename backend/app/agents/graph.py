"""Single-node LangGraph graph for per-persona agent invocation.

Compiled once at import time. Invoked via asyncio.run(PERSONA_GRAPH.ainvoke(state))
from synchronous Celery tasks.

Graph topology: START -> run_persona -> END

The run_persona node:
1. Creates an async Redis client from state["redis_url"].
2. Calls llm_call_with_persona_parsed to get a validated AgentVerdict.
3. Closes the Redis client.
4. Returns {"verdict": <AgentVerdict>}.
"""

from __future__ import annotations

from typing import Any, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.schemas import AgentVerdict


class AgentState(TypedDict):
    """State passed through the persona graph.

    persona_name: One of {"buffett", "munger", "ackman", "cohen", "dalio"}.
    data_context: Full financial data dict — partitioner will filter per-persona.
    redis_url: Redis connection URL string (e.g. "redis://localhost:6379/0").
    verdict: Populated by run_persona_node; None on entry.
    """

    persona_name: str
    data_context: dict[str, Any]
    redis_url: str
    verdict: Optional[AgentVerdict]


async def run_persona_node(state: AgentState) -> dict[str, Any]:
    """LangGraph node: call the LLM for a single persona and return the verdict.

    Imports are deferred inside the function to avoid circular imports at
    module-load time (graph.py -> wrapper.py -> schemas.py -> graph.py would
    otherwise create a cycle if wrapper imported graph at module level).
    """
    # Deferred imports to avoid circular dependency
    import redis.asyncio as aioredis

    from app.llm.wrapper import llm_call_with_persona_parsed

    redis_client = aioredis.from_url(state["redis_url"])
    try:
        verdict = await llm_call_with_persona_parsed(
            persona_name=state["persona_name"],
            data_context=state["data_context"],
            redis_client=redis_client,
        )
    finally:
        await redis_client.aclose()

    return {"verdict": verdict}


def build_persona_graph():
    """Construct and compile the single-node persona StateGraph.

    Returns:
        A compiled LangGraph CompiledGraph that accepts AgentState and returns
        a dict containing the populated ``verdict`` field.
    """
    builder = StateGraph(AgentState)
    builder.add_node("run_persona", run_persona_node)
    builder.add_edge(START, "run_persona")
    builder.add_edge("run_persona", END)
    return builder.compile()


# Compiled once at import time — safe to import from Celery tasks.
# Invoke from sync context with:
#   asyncio.run(PERSONA_GRAPH.ainvoke(state))
PERSONA_GRAPH = build_persona_graph()
