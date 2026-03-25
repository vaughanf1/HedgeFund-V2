"""Signal quality gate (SGNL-07).

Rejects composite scores below the configurable threshold. Primary cost control
preventing unnecessary LLM calls in Phase 3.
"""
from __future__ import annotations

import os

QUALITY_GATE_THRESHOLD = float(os.environ.get("SIGNAL_QUALITY_GATE", "0.35"))


def passes_gate(composite_score: float) -> bool:
    """Return True if composite_score meets or exceeds the quality gate threshold."""
    return composite_score >= QUALITY_GATE_THRESHOLD
