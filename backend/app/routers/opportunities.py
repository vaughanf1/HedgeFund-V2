"""FastAPI endpoints for querying investment opportunity analysis results (Plan 03-04).

Provides two endpoints consumed by the Phase 4 frontend:
  GET /api/v1/opportunities            — ranked list of CIO decisions
  GET /api/v1/opportunities/{id}       — full breakdown with all agent verdicts

Results are sourced from the ``cio_decisions`` and ``agent_verdicts``
TimescaleDB tables written by the Phase 3 pipeline worker (Plan 03-02).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_session
from app.db.models import AgentVerdictRecord, CIODecisionRecord

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/opportunities", tags=["opportunities"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class OpportunitySummary(BaseModel):
    """Flat summary of a CIO decision — used in the opportunities list view."""

    opportunity_id: str
    conviction_score: int
    suggested_allocation_pct: float
    final_verdict: str
    risk_rating: str
    decided_at: str

    model_config = {"from_attributes": True}


class OpportunityDetail(BaseModel):
    """Full breakdown of a single opportunity — all verdicts + CIO decision."""

    opportunity_id: str
    decision: dict[str, Any]
    verdicts: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[OpportunitySummary])
async def list_opportunities(
    limit: int = Query(20, le=100),
    final_verdict: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[OpportunitySummary]:
    """Return CIO decisions ordered by conviction_score descending.

    Supports optional filtering by ``final_verdict`` (e.g. ``BUY``, ``SELL``,
    ``HOLD``, ``PASS``).  Results are paginated via the ``limit`` parameter
    (max 100).
    """
    stmt = (
        select(CIODecisionRecord)
        .order_by(desc(CIODecisionRecord.conviction_score))
        .limit(limit)
    )
    if final_verdict is not None:
        stmt = stmt.where(CIODecisionRecord.final_verdict == final_verdict)

    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    summaries: list[OpportunitySummary] = []
    for row in rows:
        try:
            decision_data = json.loads(row.decision_json)
            risk_rating = decision_data.get("risk_rating", "UNKNOWN")
        except (json.JSONDecodeError, AttributeError):
            logger.warning(
                "Failed to parse decision_json for opportunity %s", row.opportunity_id
            )
            risk_rating = "UNKNOWN"

        summaries.append(
            OpportunitySummary(
                opportunity_id=row.opportunity_id,
                conviction_score=row.conviction_score,
                suggested_allocation_pct=float(row.suggested_allocation_pct),
                final_verdict=row.final_verdict,
                risk_rating=risk_rating,
                decided_at=row.decided_at.isoformat(),
            )
        )

    return summaries


@router.get("/{opportunity_id}", response_model=OpportunityDetail)
async def get_opportunity_detail(
    opportunity_id: str,
    session: AsyncSession = Depends(get_session),
) -> OpportunityDetail:
    """Return the full analysis breakdown for a single opportunity.

    Includes:
    - The CIO decision (conviction score, allocation, verdict, full JSON)
    - All five agent verdicts (persona, verdict, confidence, full JSON)

    Raises HTTP 404 if the opportunity_id is not found in the database.
    """
    # --- CIO decision ---
    cio_stmt = select(CIODecisionRecord).where(
        CIODecisionRecord.opportunity_id == opportunity_id
    )
    cio_result = await session.execute(cio_stmt)
    cio_row = cio_result.scalars().first()

    if cio_row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Opportunity '{opportunity_id}' not found.",
        )

    try:
        decision_dict = json.loads(cio_row.decision_json)
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Failed to parse decision_json for opportunity %s", opportunity_id)
        decision_dict = {"raw": cio_row.decision_json}

    # --- Agent verdicts (all 5 personas) ---
    verdicts_stmt = (
        select(AgentVerdictRecord)
        .where(AgentVerdictRecord.opportunity_id == opportunity_id)
        .order_by(AgentVerdictRecord.persona)
    )
    verdicts_result = await session.execute(verdicts_stmt)
    verdict_rows = list(verdicts_result.scalars().all())

    verdict_dicts: list[dict[str, Any]] = []
    for vrow in verdict_rows:
        try:
            verdict_dicts.append(json.loads(vrow.verdict_json))
        except (json.JSONDecodeError, AttributeError):
            logger.warning(
                "Failed to parse verdict_json for opportunity %s persona %s",
                opportunity_id,
                vrow.persona,
            )
            verdict_dicts.append({"persona": vrow.persona, "raw": vrow.verdict_json})

    return OpportunityDetail(
        opportunity_id=opportunity_id,
        decision=decision_dict,
        verdicts=verdict_dicts,
    )
