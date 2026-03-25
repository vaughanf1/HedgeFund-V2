"""Inter-agent variance scoring for committee validity checks.

Variance scoring prevents sycophantic consensus by rejecting committee rounds
where all five personas converged to nearly identical confidence scores. A low
standard deviation indicates agents are not genuinely independent.

MINIMUM_VARIANCE_THRESHOLD defaults to 8.0 confidence points (std dev). This
means the committee is only valid when agents disagree meaningfully on how
confident they are — even if they agree on the direction (BUY/HOLD/PASS).

Threshold is configurable via the AGENT_VARIANCE_THRESHOLD environment variable.
"""

from __future__ import annotations

import logging
import os
import statistics
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.schemas import AgentVerdict

logger = logging.getLogger(__name__)

MINIMUM_VARIANCE_THRESHOLD = float(
    os.environ.get("AGENT_VARIANCE_THRESHOLD", "8.0")
)


def compute_variance_score(verdicts: list[AgentVerdict]) -> float:
    """Compute standard deviation of confidence scores across agent verdicts.

    Args:
        verdicts: List of AgentVerdict objects from five (or fewer) personas.

    Returns:
        Standard deviation of confidence scores (float).
        Returns 0.0 if fewer than two verdicts are provided.
    """
    scores = [v.confidence for v in verdicts]
    if len(scores) < 2:
        return 0.0
    return statistics.stdev(scores)


def is_committee_valid(verdicts: list[AgentVerdict]) -> bool:
    """Validate committee by checking variance is above minimum threshold.

    Args:
        verdicts: List of AgentVerdict objects from the five personas.

    Returns:
        True if variance >= MINIMUM_VARIANCE_THRESHOLD, False otherwise.
        A False result indicates agents converged sycophantically.
    """
    variance = compute_variance_score(verdicts)
    logger.info(
        "Inter-agent variance score: %.2f (threshold: %.2f)",
        variance,
        MINIMUM_VARIANCE_THRESHOLD,
    )
    return variance >= MINIMUM_VARIANCE_THRESHOLD
