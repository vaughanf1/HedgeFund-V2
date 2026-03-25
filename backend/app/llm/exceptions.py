"""LLM-related exceptions for the HedgeFund V2 agent system."""

from __future__ import annotations


class BudgetExceededError(Exception):
    """Raised when the daily LLM spend limit would be exceeded by a call.

    Attributes:
        current_spend_usd: The current accumulated spend today.
        limit_usd: The configured daily limit.
        projected_cost_usd: The cost of the call that would have been made.
    """

    def __init__(
        self,
        current_spend_usd: float,
        limit_usd: float,
        projected_cost_usd: float,
    ) -> None:
        self.current_spend_usd = current_spend_usd
        self.limit_usd = limit_usd
        self.projected_cost_usd = projected_cost_usd
        super().__init__(
            f"Daily LLM budget exceeded: current=${current_spend_usd:.4f}, "
            f"limit=${limit_usd:.4f}, projected call cost=${projected_cost_usd:.4f}"
        )


class LLMCallError(Exception):
    """Raised when an LLM API call fails for a non-budget reason.

    Wraps underlying API errors (network failures, model errors, timeouts)
    to provide a consistent error surface throughout the application.

    Attributes:
        original_error: The underlying exception that caused the failure.
        model: The model that was being called.
    """

    def __init__(self, message: str, model: str = "", original_error: Exception | None = None) -> None:
        self.model = model
        self.original_error = original_error
        super().__init__(message)
