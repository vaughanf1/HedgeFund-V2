"""CIO deterministic decision engine.

Translates a CommitteeReport into a CIODecision using pure deterministic rules —
no LLM call, no randomness. The output drives the Phase 4 portfolio manager.

Decision rules:
- conviction_score = round(weighted_conviction)
- allocation tiers: >=80 → 8%, >=65 → 5%, >=50 → 3%, >=35 → 1.5%, else 0%
  (asymmetric_flag applies a 1.5x multiplier, capped at 10%)
- risk_rating derived from variance_score
- time_horizon = statistical mode of individual agent time_horizon values
- key_catalysts = unique upside_scenario strings from BUY verdicts (up to 5)
- kill_conditions = risks from lower-confidence agents (up to 5)
- final_verdict:
    BUY + conviction >= 40 → INVEST
    BUY (any conviction) → MONITOR
    SPLIT + conviction >= 40 → MONITOR
    HOLD → MONITOR
    conviction >= 45 → MONITOR
    anything else → PASS
"""

from __future__ import annotations

import logging
import statistics
from typing import TYPE_CHECKING

from app.agents.schemas import CIODecision, CommitteeReport

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def make_cio_decision(report: CommitteeReport) -> CIODecision:
    """Derive a CIODecision from a CommitteeReport using deterministic rules.

    Args:
        report: Aggregated CommitteeReport from aggregate_committee().

    Returns:
        CIODecision with all fields populated.
    """
    conviction = round(report.weighted_conviction)

    # -----------------------------------------------------------------
    # Allocation tier
    # -----------------------------------------------------------------
    if conviction >= 80:
        base_allocation = 8.0
    elif conviction >= 65:
        base_allocation = 5.0
    elif conviction >= 50:
        base_allocation = 3.0
    elif conviction >= 35:
        base_allocation = 1.5
    else:
        base_allocation = 0.0

    if report.asymmetric_flag:
        suggested_allocation = min(base_allocation * 1.5, 10.0)
    else:
        suggested_allocation = base_allocation

    # -----------------------------------------------------------------
    # Risk rating from variance
    # -----------------------------------------------------------------
    variance = report.variance_score
    if variance > 25:
        risk_rating = "VERY_HIGH"
    elif variance > 15:
        risk_rating = "HIGH"
    elif variance > 8:
        risk_rating = "MEDIUM"
    else:
        risk_rating = "LOW"

    # -----------------------------------------------------------------
    # Time horizon: mode of agent time_horizon values
    # -----------------------------------------------------------------
    horizons = [v.time_horizon for v in report.verdicts if v.time_horizon]
    if horizons:
        try:
            time_horizon = statistics.mode(horizons)
        except statistics.StatisticsError:
            # Multiple modes — pick the first (deterministic)
            time_horizon = horizons[0]
    else:
        time_horizon = "unknown"

    # -----------------------------------------------------------------
    # Key catalysts: unique upside scenarios from BUY verdicts (up to 5)
    # -----------------------------------------------------------------
    key_catalysts: list[str] = []
    seen_catalysts: set[str] = set()
    for v in report.verdicts:
        if v.verdict == "BUY" and v.upside_scenario:
            if v.upside_scenario not in seen_catalysts:
                seen_catalysts.add(v.upside_scenario)
                key_catalysts.append(v.upside_scenario)
                if len(key_catalysts) >= 5:
                    break

    # -----------------------------------------------------------------
    # Kill conditions: risks from lower-confidence agents (up to 5)
    # Sorted ascending by confidence so lowest-conviction risks come first.
    # -----------------------------------------------------------------
    sorted_by_conf = sorted(report.verdicts, key=lambda v: v.confidence)
    kill_conditions: list[str] = []
    seen_kills: set[str] = set()
    for v in sorted_by_conf:
        for risk in v.risks:
            if risk not in seen_kills:
                seen_kills.add(risk)
                kill_conditions.append(risk)
                if len(kill_conditions) >= 5:
                    break
        if len(kill_conditions) >= 5:
            break

    # -----------------------------------------------------------------
    # Final verdict
    # -----------------------------------------------------------------
    consensus = report.consensus
    if consensus == "BUY" and conviction >= 40:
        final_verdict = "INVEST"
    elif consensus == "BUY":
        final_verdict = "MONITOR"
    elif consensus == "SPLIT" and conviction >= 40:
        final_verdict = "MONITOR"
    elif consensus == "HOLD":
        final_verdict = "MONITOR"
    elif conviction >= 45:
        final_verdict = "MONITOR"
    else:
        final_verdict = "PASS"

    decision = CIODecision(
        opportunity_id=report.opportunity_id,
        conviction_score=conviction,
        suggested_allocation_pct=round(suggested_allocation, 2),
        time_horizon=time_horizon,
        risk_rating=risk_rating,  # type: ignore[arg-type]
        key_catalysts=key_catalysts,
        kill_conditions=kill_conditions,
        final_verdict=final_verdict,  # type: ignore[arg-type]
    )

    logger.info(
        "CIO decision for %s — verdict=%s conviction=%d allocation=%.1f%% "
        "risk=%s horizon=%s",
        report.opportunity_id,
        final_verdict,
        conviction,
        suggested_allocation,
        risk_rating,
        time_horizon,
    )
    return decision
