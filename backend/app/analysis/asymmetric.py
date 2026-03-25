"""10X asymmetric bet detection layer.

Evaluates whether the committee's collective verdict signals a genuine asymmetric
opportunity — one where the potential upside (5x-10x) dramatically outweighs the
downside. This is distinct from a plain BUY signal: an asymmetric opportunity
requires both consensus (>=3 BUY votes) and high average conviction (>=70).

Used by run_committee in analyse_opportunity.py after all five agent verdicts arrive.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.schemas import AgentVerdict

logger = logging.getLogger(__name__)


def evaluate_asymmetric(verdicts: list[AgentVerdict], opportunity: dict) -> dict:
    """Evaluate whether the opportunity qualifies as a 10X asymmetric bet.

    An opportunity is asymmetric when:
    - At least 3 agents returned a BUY verdict.
    - The average confidence among BUY agents is >= 70.

    When asymmetric, the function extracts:
    - catalyst_justification: joined upside scenarios from BUY verdicts.
    - probability_score: normalised average BUY confidence (0.0–1.0).
    - payoff_multiple: "5x-10x" if avg_confidence >= 80, else "3x-5x".
    - required_conditions: list of upside scenarios from BUY verdicts.
    - risk_flags: deduplicated risks across all verdicts.

    Args:
        verdicts: List of AgentVerdict objects from the five personas.
        opportunity: Raw opportunity dict (used for logging context only).

    Returns:
        Dict with keys: is_asymmetric, catalyst_justification,
        probability_score, payoff_multiple, required_conditions, risk_flags.
    """
    ticker = opportunity.get("ticker", "UNKNOWN")

    buy_verdicts = [v for v in verdicts if v.verdict == "BUY"]
    buy_count = len(buy_verdicts)

    if buy_count > 0:
        avg_confidence = sum(v.confidence for v in buy_verdicts) / buy_count
    else:
        avg_confidence = 0.0

    is_asymmetric = buy_count >= 3 and avg_confidence >= 70

    if is_asymmetric:
        catalyst_justification = " | ".join(
            v.upside_scenario for v in buy_verdicts if v.upside_scenario
        )
        probability_score = avg_confidence / 100.0
        payoff_multiple = "5x-10x" if avg_confidence >= 80 else "3x-5x"
        required_conditions = [v.upside_scenario for v in buy_verdicts if v.upside_scenario]

        # Deduplicate risk flags across all verdicts (order-preserving)
        seen: set[str] = set()
        risk_flags: list[str] = []
        for v in verdicts:
            for risk in v.risks:
                if risk not in seen:
                    seen.add(risk)
                    risk_flags.append(risk)

        result = {
            "is_asymmetric": True,
            "catalyst_justification": catalyst_justification,
            "probability_score": probability_score,
            "payoff_multiple": payoff_multiple,
            "required_conditions": required_conditions,
            "risk_flags": risk_flags,
        }
        logger.info(
            "Asymmetric opportunity detected for %s — buy_count=%d avg_conf=%.1f payoff=%s",
            ticker,
            buy_count,
            avg_confidence,
            payoff_multiple,
        )
    else:
        result = {
            "is_asymmetric": False,
            "catalyst_justification": None,
            "probability_score": 0.0,
            "payoff_multiple": "1x",
            "required_conditions": [],
            "risk_flags": [],
        }
        logger.info(
            "No asymmetric opportunity for %s — buy_count=%d avg_conf=%.1f",
            ticker,
            buy_count,
            avg_confidence,
        )

    return result
