"""Committee aggregation with context-weighted voting and regime detection.

The committee aggregates five agent verdicts into a single CommitteeReport by:
1. Detecting the market regime (macro / fundamental / momentum / default).
2. Applying regime-specific influence weights to each persona's conviction.
3. Computing a weighted conviction score.
4. Determining consensus and dissent.

Regime weights implement the following principles:
- Macro regime (e.g. crisis, rate shocks): Dalio (1.5) > Cohen (1.0) > Ackman (0.9)
  > Munger (0.8) > Buffett (0.7)
- Fundamental regime (earnings, value plays): Buffett (1.5) > Munger (1.4)
  > Ackman (1.2) > Dalio (0.9) > Cohen (0.8)
- Momentum regime (trend, breakout): Cohen (1.5) > Dalio (1.2) > Ackman (1.0)
  > Munger (0.8) > Buffett (0.7)
- Default (mixed signals): all weights equal at 1.0
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.agents.schemas import AgentVerdict, CommitteeReport
from app.analysis.variance import compute_variance_score

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regime-based influence weights
# ---------------------------------------------------------------------------

REGIME_WEIGHTS: dict[str, dict[str, float]] = {
    "macro": {
        "buffett": 0.7,
        "munger": 0.8,
        "ackman": 0.9,
        "cohen": 1.0,
        "dalio": 1.5,
    },
    "fundamental": {
        "buffett": 1.5,
        "munger": 1.4,
        "ackman": 1.2,
        "cohen": 0.8,
        "dalio": 0.9,
    },
    "momentum": {
        "buffett": 0.7,
        "munger": 0.8,
        "ackman": 1.0,
        "cohen": 1.5,
        "dalio": 1.2,
    },
    "default": {
        "buffett": 1.0,
        "munger": 1.0,
        "ackman": 1.0,
        "cohen": 1.0,
        "dalio": 1.0,
    },
}


# ---------------------------------------------------------------------------
# Regime detection
# ---------------------------------------------------------------------------


def detect_regime(opportunity: dict) -> str:
    """Infer the dominant market regime from the opportunity's signal composition.

    Regime is inferred heuristically from signal_types present in the opportunity:
    - "macro" if macro-related signals are present (yield_curve, credit_spread,
      macro_divergence, liquidity_trap, sector_rotation)
    - "fundamental" if fundamental signals dominate (earnings_quality,
      insider_buying, fundamental_value, free_cash_flow)
    - "momentum" if momentum/technical signals dominate (momentum_breakout,
      price_momentum, volume_spike, relative_strength)
    - "default" if signals are mixed or unrecognised

    Args:
        opportunity: Opportunity dict from Phase 2 queue.

    Returns:
        One of "macro", "fundamental", "momentum", "default".
    """
    signal_types: list[str] = []

    # Extract signal types from various opportunity shapes
    if isinstance(opportunity.get("signals"), list):
        for sig in opportunity["signals"]:
            if isinstance(sig, dict):
                st = sig.get("signal_type", "")
                if st:
                    signal_types.append(st.lower())
            elif isinstance(sig, str):
                signal_types.append(sig.lower())

    # Also check a top-level signal_type key (single-signal opportunities)
    if opportunity.get("signal_type"):
        signal_types.append(str(opportunity["signal_type"]).lower())

    macro_keywords = {
        "yield_curve", "credit_spread", "macro_divergence",
        "liquidity_trap", "sector_rotation", "macro",
    }
    fundamental_keywords = {
        "earnings_quality", "insider_buying", "fundamental_value",
        "free_cash_flow", "value", "fundamental",
    }
    momentum_keywords = {
        "momentum_breakout", "price_momentum", "volume_spike",
        "relative_strength", "momentum", "breakout",
    }

    macro_count = sum(1 for s in signal_types if s in macro_keywords)
    fundamental_count = sum(1 for s in signal_types if s in fundamental_keywords)
    momentum_count = sum(1 for s in signal_types if s in momentum_keywords)

    counts = {"macro": macro_count, "fundamental": fundamental_count, "momentum": momentum_count}
    dominant = max(counts, key=lambda k: counts[k])

    if counts[dominant] == 0:
        regime = "default"
    else:
        regime = dominant

    logger.info(
        "Regime detected: %s (macro=%d fundamental=%d momentum=%d signals=%s)",
        regime,
        macro_count,
        fundamental_count,
        momentum_count,
        signal_types,
    )
    return regime


# ---------------------------------------------------------------------------
# Committee aggregation
# ---------------------------------------------------------------------------


def aggregate_committee(
    opportunity_id: str,
    verdicts: list[AgentVerdict],
    opportunity: dict,
    asymmetric_result: dict,
) -> CommitteeReport:
    """Aggregate five agent verdicts into a CommitteeReport.

    Steps:
    1. Detect regime from opportunity signals.
    2. Map each verdict to its regime-adjusted weight.
    3. Compute weighted conviction: sum(confidence * weight) / sum(weights).
    4. Tally BUY/HOLD/PASS votes to determine consensus.
    5. Identify dissenting agents (those not on the plurality side).
    6. Compute variance score.
    7. Attach asymmetric scoring result.

    Conviction is normalised to 0–100 float.

    Consensus rules:
    - BUY: >= 3 BUY votes
    - PASS: >= 3 PASS votes
    - HOLD: >= 3 HOLD votes
    - SPLIT: no single verdict has >= 3 votes

    Args:
        opportunity_id: Compound key ``ticker:detected_at``.
        verdicts: List of five AgentVerdict objects.
        opportunity: Raw opportunity dict for regime detection.
        asymmetric_result: Output from evaluate_asymmetric().

    Returns:
        CommitteeReport with all fields populated.
    """
    regime = detect_regime(opportunity)
    weights_map = REGIME_WEIGHTS.get(regime, REGIME_WEIGHTS["default"])

    # Weighted conviction
    total_weight = 0.0
    weighted_sum = 0.0
    for v in verdicts:
        w = weights_map.get(v.persona.lower(), 1.0)
        weighted_sum += v.confidence * w
        total_weight += w

    weighted_conviction = weighted_sum / total_weight if total_weight > 0 else 0.0

    # Vote tallies
    vote_counts: dict[str, int] = {"BUY": 0, "HOLD": 0, "PASS": 0}
    for v in verdicts:
        vote_counts[v.verdict] = vote_counts.get(v.verdict, 0) + 1

    plurality = max(vote_counts, key=lambda k: vote_counts[k])
    plurality_count = vote_counts[plurality]

    if plurality_count >= 3:
        consensus = plurality  # type: ignore[assignment]
    else:
        consensus = "SPLIT"

    # Dissent: agents whose verdict differs from the plurality
    if consensus != "SPLIT":
        dissent_agents = [v.persona for v in verdicts if v.verdict != plurality]
    else:
        # In a split, dissent is agents not on the top-two sides
        sorted_sides = sorted(vote_counts, key=lambda k: vote_counts[k], reverse=True)
        top_two = set(sorted_sides[:2])
        dissent_agents = [v.persona for v in verdicts if v.verdict not in top_two]

    variance_score = compute_variance_score(verdicts)

    report = CommitteeReport(
        opportunity_id=opportunity_id,
        verdicts=verdicts,
        consensus=consensus,  # type: ignore[arg-type]
        dissent_agents=dissent_agents,
        variance_score=round(variance_score, 4),
        weighted_conviction=round(weighted_conviction, 4),
        asymmetric_flag=asymmetric_result.get("is_asymmetric", False),
        asymmetric_justification=asymmetric_result.get("catalyst_justification"),
    )

    logger.info(
        "Committee report for %s — consensus=%s conviction=%.1f variance=%.2f "
        "asymmetric=%s dissent=%s regime=%s",
        opportunity_id,
        consensus,
        weighted_conviction,
        variance_score,
        report.asymmetric_flag,
        dissent_agents,
        regime,
    )
    return report
