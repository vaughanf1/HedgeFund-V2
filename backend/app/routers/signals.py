"""FastAPI router for detected signals (VIS-01, VIS-04).

Provides read-only endpoints for querying the detected_signals hypertable.
All responses include detected_at timestamps satisfying VIS-04.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_session
from app.db.models import DetectedSignal


class SignalResponse(BaseModel):
    detected_at: datetime
    ticker: str
    signal_type: str
    score: Decimal
    composite_score: Optional[Decimal]
    passed_gate: bool
    detail: Optional[str]

    model_config = {"from_attributes": True}


router = APIRouter(prefix="/api/v1/signals", tags=["signals"])


@router.get("", response_model=list[SignalResponse])
async def list_signals(
    ticker: Optional[str] = Query(None),
    signal_type: Optional[str] = Query(None),
    passed_gate: Optional[bool] = Query(None),
    limit: int = Query(50, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[DetectedSignal]:
    """List detected signals, ordered by detected_at descending.

    Supports optional filtering by ticker, signal_type, and passed_gate.
    """
    stmt = (
        select(DetectedSignal)
        .order_by(desc(DetectedSignal.detected_at))
        .limit(limit)
    )
    if ticker is not None:
        stmt = stmt.where(DetectedSignal.ticker == ticker)
    if signal_type is not None:
        stmt = stmt.where(DetectedSignal.signal_type == signal_type)
    if passed_gate is not None:
        stmt = stmt.where(DetectedSignal.passed_gate == passed_gate)

    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/{ticker}", response_model=list[SignalResponse])
async def signals_for_ticker(
    ticker: str,
    limit: int = Query(20, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[DetectedSignal]:
    """Return signals for a specific ticker, ordered by detected_at descending."""
    stmt = (
        select(DetectedSignal)
        .where(DetectedSignal.ticker == ticker)
        .order_by(desc(DetectedSignal.detected_at))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
