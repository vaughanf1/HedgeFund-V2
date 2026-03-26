"""Demo endpoint: simulate a full pipeline run with realistic data.

Publishes SSE events and persists to DB so the frontend renders
the complete flow: scanner → detectors → gate → agents → committee → CIO.

Trigger via POST /api/v1/demo/run
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_session
from app.db.models import AgentVerdictRecord, CIODecisionRecord, DetectedSignal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

_REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")


# ── Sample data ──────────────────────────────────────────────────────────────

DEMO_TICKERS = [
    {"ticker": "NVDA", "name": "NVIDIA", "thesis": "AI infrastructure spend accelerating"},
    {"ticker": "PLTR", "name": "Palantir", "thesis": "Government AI contract pipeline expanding"},
    {"ticker": "CRWD", "name": "CrowdStrike", "thesis": "Cybersecurity consolidation play"},
    {"ticker": "TSLA", "name": "Tesla", "thesis": "Energy storage + autonomy inflection"},
    {"ticker": "SMCI", "name": "Super Micro", "thesis": "AI server demand outpacing supply"},
]

PERSONAS = ["buffett", "munger", "ackman", "cohen", "dalio"]

PERSONA_STYLES = {
    "buffett": {"bias": "fundamental", "caution": 0.7},
    "munger": {"bias": "quality", "caution": 0.8},
    "ackman": {"bias": "activist", "caution": 0.4},
    "cohen": {"bias": "momentum", "caution": 0.3},
    "dalio": {"bias": "macro", "caution": 0.6},
}

SIGNAL_TYPES = [
    ("volume_spike", 0.7),
    ("price_breakout", 0.65),
    ("insider_cluster", 0.8),
    ("news_catalyst", 0.75),
    ("sector_momentum", 0.5),
]


def _gen_verdict(persona: str, ticker: str, thesis: str) -> dict:
    style = PERSONA_STYLES[persona]
    confidence = random.randint(40, 95)
    is_bullish = random.random() > style["caution"]
    verdict = "BUY" if is_bullish else random.choice(["HOLD", "PASS"])

    rationales = {
        "buffett": f"Strong cash flow generation and competitive moat. {thesis}.",
        "munger": f"Quality business with durable advantages. Inversion says: what could kill this? Not much.",
        "ackman": f"Concentrated bet opportunity. Activist catalyst: {thesis}.",
        "cohen": f"Momentum signals confirm institutional accumulation. Flow data supports near-term upside.",
        "dalio": f"Macro regime favourable. {thesis}. Risk parity allocation warranted.",
    }

    risks = {
        "buffett": ["Valuation stretched vs historical P/E", "Cyclical revenue exposure"],
        "munger": ["Management incentive misalignment", "Regulatory overhang"],
        "ackman": ["Concentrated position risk", "Catalyst timing uncertainty"],
        "cohen": ["Momentum reversal risk", "Short-term crowded trade"],
        "dalio": ["Macro regime shift", "Correlation risk in risk-off scenario"],
    }

    return {
        "persona": persona,
        "verdict": verdict,
        "confidence": confidence,
        "rationale": rationales.get(persona, f"Analysis of {ticker}: {thesis}"),
        "key_metrics_used": ["P/E ratio", "revenue growth", "insider activity", "volume profile"],
        "risks": risks.get(persona, ["General market risk"]),
        "upside_scenario": f"{ticker} reaches ${'%.0f' % (random.uniform(150, 500))} on {thesis.lower()}",
        "time_horizon": random.choice(["3-6 months", "6-12 months", "1-2 years", "12-18 months"]),
        "data_gaps": ["Limited international revenue breakdown"],
    }


def _gen_cio_decision(opportunity_id: str, verdicts: list[dict]) -> dict:
    buy_count = sum(1 for v in verdicts if v["verdict"] == "BUY")
    avg_confidence = sum(v["confidence"] for v in verdicts) / len(verdicts)
    conviction = int(avg_confidence * (0.6 + 0.4 * buy_count / len(verdicts)))

    if buy_count >= 3 and conviction >= 50:
        final_verdict = "INVEST"
    elif buy_count >= 2:
        final_verdict = "MONITOR"
    else:
        final_verdict = "PASS"

    alloc = min(10.0, max(0.0, conviction * 0.1))
    variance = max(0, max(v["confidence"] for v in verdicts) - min(v["confidence"] for v in verdicts))

    if variance > 25:
        risk = "HIGH"
    elif variance > 15:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    return {
        "opportunity_id": opportunity_id,
        "conviction_score": conviction,
        "suggested_allocation_pct": round(alloc, 1),
        "time_horizon": max(set(v["time_horizon"] for v in verdicts), key=lambda x: verdicts[0]["time_horizon"]),
        "risk_rating": risk,
        "key_catalysts": list(set(v["upside_scenario"] for v in verdicts if v["verdict"] == "BUY"))[:3],
        "kill_conditions": list(set(r for v in verdicts for r in v["risks"][:1] if v["confidence"] < 60))[:3],
        "final_verdict": final_verdict,
    }


async def _publish(r, event_type: str, payload: dict):
    """Publish event to Redis pipeline:events channel."""
    message = json.dumps({"event": event_type, "data": payload}, default=str)
    await r.publish("pipeline:events", message)


@router.post("/run")
async def run_demo(session: AsyncSession = Depends(get_session)):
    """Simulate a full pipeline run for 2-3 tickers with realistic delays."""
    import redis.asyncio as aioredis

    r = aioredis.from_url(_REDIS_URL)
    now = datetime.now(timezone.utc)
    results = []

    # Pick 2-3 random tickers
    selected = random.sample(DEMO_TICKERS, k=min(3, len(DEMO_TICKERS)))

    for stock in selected:
        ticker = stock["ticker"]
        thesis = stock["thesis"]
        opportunity_id = f"{ticker}:{now.isoformat()}"

        # 1. Simulate signal detection — persist to DB
        signals_fired = random.sample(SIGNAL_TYPES, k=random.randint(2, 4))
        composite = sum(s[1] for s in signals_fired) / len(signals_fired)

        for sig_type, score in signals_fired:
            record = DetectedSignal(
                detected_at=now,
                ticker=ticker,
                signal_type=sig_type,
                score=score,
                composite_score=composite,
                passed_gate=True,
                detail=json.dumps({"demo": True, "thesis": thesis}),
                source="demo",
            )
            session.add(record)

        await session.flush()

        # 2. Publish agent events with delays
        verdicts = []
        for persona in PERSONAS:
            await _publish(r, "AGENT_STARTED", {
                "opportunity_id": opportunity_id,
                "persona": persona,
                "ticker": ticker,
            })
            await asyncio.sleep(0.3)  # Stagger for visual effect

        # Agents "complete" with staggered delays
        for persona in PERSONAS:
            verdict = _gen_verdict(persona, ticker, thesis)
            verdicts.append(verdict)

            await _publish(r, "AGENT_COMPLETE", {
                "opportunity_id": opportunity_id,
                "persona": persona,
                "ticker": ticker,
                "verdict": verdict["verdict"],
                "confidence": verdict["confidence"],
            })

            # Persist verdict to DB
            vrecord = AgentVerdictRecord(
                analysed_at=now,
                opportunity_id=opportunity_id,
                persona=persona,
                verdict=verdict["verdict"],
                confidence=verdict["confidence"],
                verdict_json=json.dumps(verdict, default=str),
            )
            session.add(vrecord)

            await asyncio.sleep(random.uniform(0.2, 0.5))

        # 3. Committee complete
        await _publish(r, "COMMITTEE_COMPLETE", {
            "opportunity_id": opportunity_id,
            "consensus": "BUY" if sum(1 for v in verdicts if v["verdict"] == "BUY") >= 3 else "SPLIT",
            "weighted_conviction": sum(v["confidence"] for v in verdicts) / len(verdicts),
            "asymmetric_flag": any(v["confidence"] > 85 for v in verdicts),
            "dissent_agents": [v["persona"] for v in verdicts if v["verdict"] != "BUY"],
        })
        await asyncio.sleep(0.4)

        # 4. CIO decision
        decision = _gen_cio_decision(opportunity_id, verdicts)

        await _publish(r, "DECISION_MADE", {
            "opportunity_id": opportunity_id,
            "ticker": ticker,
            "decision": {
                "final_verdict": decision["final_verdict"],
                "conviction_score": decision["conviction_score"],
                "suggested_allocation_pct": decision["suggested_allocation_pct"],
                "risk_rating": decision["risk_rating"],
                "time_horizon": decision["time_horizon"],
                "key_catalysts": decision["key_catalysts"],
                "kill_conditions": decision["kill_conditions"],
            },
            "verdicts": verdicts,
        })

        # Persist CIO decision to DB
        cio_record = CIODecisionRecord(
            decided_at=now,
            opportunity_id=opportunity_id,
            conviction_score=decision["conviction_score"],
            suggested_allocation_pct=decision["suggested_allocation_pct"],
            final_verdict=decision["final_verdict"],
            decision_json=json.dumps(decision, default=str),
        )
        session.add(cio_record)

        results.append({
            "ticker": ticker,
            "opportunity_id": opportunity_id,
            "verdict": decision["final_verdict"],
            "conviction": decision["conviction_score"],
        })

        await asyncio.sleep(0.5)  # Gap between tickers

    await session.commit()
    await r.aclose()

    return {
        "status": "demo_complete",
        "opportunities_analysed": len(results),
        "results": results,
    }
