"""News catalyst detector (SGNL-04).

Returns a signal dict when keyword-matching news articles exist in the last
48 hours for a given ticker, None otherwise.

IMPORTANT: Does NOT filter on sentiment column — sentiment is unpopulated
(research open question #1). Keyword-only filtering via ILIKE.
"""
from __future__ import annotations

import os

from sqlalchemy import text
from sqlalchemy.orm import Session

_RAW_KEYWORDS = os.environ.get(
    "NEWS_CATALYST_KEYWORDS",
    "earnings,surprise,partnership,acquisition,FDA,approval,revenue,upgrade",
)

NEWS_CATALYST_KEYWORDS: list[str] = [kw.strip() for kw in _RAW_KEYWORDS.split(",") if kw.strip()]

# Build ILIKE clause dynamically — ILIKE patterns cannot be parameterized as
# arrays in PostgreSQL, so we inject them as string literals into the query.
_ilike_clause = " OR ".join(
    f"headline ILIKE '%{kw}%'" for kw in NEWS_CATALYST_KEYWORDS
)

NEWS_CATALYST_SQL = text(
    f"""
    SELECT
        ticker,
        COUNT(*) AS recent_articles,
        MAX(timestamp) AS most_recent,
        EXTRACT(EPOCH FROM (NOW() - MAX(timestamp))) / 3600 AS hours_since_latest
    FROM news_items
    WHERE ticker = :ticker
      AND timestamp >= NOW() - INTERVAL '48 hours'
      AND ({_ilike_clause})
    GROUP BY ticker
    HAVING COUNT(*) >= 1
    """
)


def detect_news_catalyst(session: Session, ticker: str) -> dict | None:
    """Return a news catalyst signal dict if keyword-matching news found in 48h, else None."""
    row = session.execute(
        NEWS_CATALYST_SQL,
        {"ticker": ticker},
    ).fetchone()

    if row is None:
        return None

    recent_articles = int(row.recent_articles)
    hours_since_latest = float(row.hours_since_latest) if row.hours_since_latest is not None else 0.0

    # Base score: normalize so 3+ articles = max, then apply recency decay
    base_score = min(recent_articles / 3.0, 1.0)
    recency_decay = max(0.2, 1.0 - hours_since_latest / 48.0)
    score = base_score * recency_decay

    return {
        "signal_type": "news_catalyst",
        "ticker": ticker,
        "score": score,
        "detail": {
            "recent_articles": recent_articles,
            "hours_since_latest": hours_since_latest,
            "keywords_used": NEWS_CATALYST_KEYWORDS,
            "most_recent": str(row.most_recent) if row.most_recent is not None else None,
        },
    }
