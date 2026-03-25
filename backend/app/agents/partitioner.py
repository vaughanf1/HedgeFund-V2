"""Data partitioner: enforces information asymmetry across investor personas.

Each persona is deliberately restricted to a subset of available data types.
This prevents sycophantic consensus — agents cannot converge to the same
conclusion if they cannot see the same signals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # FinancialSnapshot is defined in backend/app/schemas/financial.py (plan 01-02).
    # The TYPE_CHECKING guard prevents a hard import failure if that module is
    # not yet available. At runtime we use Any-typed lists; mypy sees the full type.
    from app.schemas.financial import FinancialSnapshot

# ---------------------------------------------------------------------------
# Canonical data-type taxonomy
# ---------------------------------------------------------------------------
# These string labels correspond to keys that will be present in a
# FinancialSnapshot (or equivalent dict representation) produced by plan 01-02.

DATA_TYPE_FUNDAMENTALS = "fundamentals"
DATA_TYPE_PRICE_ACTION = "price_action"
DATA_TYPE_NEWS = "news"
DATA_TYPE_INSIDER_TRADES = "insider_trades"

# ---------------------------------------------------------------------------
# Persona access control matrix
# ---------------------------------------------------------------------------
# Maps persona name -> frozenset of allowed data types.
# This is the single source of truth for information asymmetry.

PERSONA_DATA_ACCESS: dict[str, frozenset[str]] = {
    "buffett": frozenset({DATA_TYPE_FUNDAMENTALS}),
    "munger": frozenset({DATA_TYPE_FUNDAMENTALS, DATA_TYPE_NEWS}),
    "ackman": frozenset({DATA_TYPE_FUNDAMENTALS, DATA_TYPE_INSIDER_TRADES}),
    "cohen": frozenset({DATA_TYPE_PRICE_ACTION}),
    "dalio": frozenset({DATA_TYPE_PRICE_ACTION, DATA_TYPE_NEWS}),
}


class DataPartitioner:
    """Filters a collection of financial snapshots to only the fields a given
    persona is permitted to see.

    This class is the enforcement layer for information asymmetry. It is called
    immediately before persona rendering so that no restricted data ever reaches
    an LLM prompt.

    Usage::

        partitioner = DataPartitioner()
        context = partitioner.partition_for_persona("buffett", snapshots)
        # context contains only fundamentals — no price/news/insider data
    """

    # All recognised top-level data keys in a snapshot dict.
    _ALL_DATA_TYPES: frozenset[str] = frozenset(
        {
            DATA_TYPE_FUNDAMENTALS,
            DATA_TYPE_PRICE_ACTION,
            DATA_TYPE_NEWS,
            DATA_TYPE_INSIDER_TRADES,
        }
    )

    def __init__(self) -> None:
        self._access = PERSONA_DATA_ACCESS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_allowed_types(self, persona_name: str) -> frozenset[str]:
        """Return the set of data types this persona may access.

        Raises:
            ValueError: if *persona_name* is not recognised.
        """
        name = persona_name.lower().strip()
        if name not in self._access:
            raise ValueError(
                f"Unknown persona '{name}'. "
                f"Valid options: {sorted(self._access.keys())}"
            )
        return self._access[name]

    def partition_for_persona(
        self,
        persona_name: str,
        snapshots: list[Any],
    ) -> dict[str, Any]:
        """Build a persona-specific data context from a list of snapshots.

        Each snapshot is expected to be either a ``FinancialSnapshot`` instance
        (with a ``model_dump()`` method, i.e. a Pydantic model) or a plain dict.
        Keys not in the persona's allowed set are stripped before the context
        dict is returned.

        Args:
            persona_name: One of ``{"buffett", "munger", "ackman", "cohen", "dalio"}``.
            snapshots: List of ``FinancialSnapshot`` objects or equivalent dicts.

        Returns:
            A dict with only permitted data types, ready for JSON serialisation
            and injection into a persona prompt via ``PersonaLoader.render_persona``.
        """
        allowed = self.get_allowed_types(persona_name)
        restricted = self._ALL_DATA_TYPES - allowed

        partitioned: list[dict[str, Any]] = []
        for snap in snapshots:
            # Support both Pydantic models and plain dicts
            if hasattr(snap, "model_dump"):
                snap_dict: dict[str, Any] = snap.model_dump()
            elif hasattr(snap, "dict"):  # Pydantic v1 compat
                snap_dict = snap.dict()
            else:
                snap_dict = dict(snap)

            # Remove restricted top-level keys
            filtered = {
                k: v for k, v in snap_dict.items() if k not in restricted
            }
            partitioned.append(filtered)

        return {
            "persona": persona_name,
            "allowed_data_types": sorted(allowed),
            "snapshots": partitioned,
        }

    def partition_raw(
        self,
        persona_name: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Partition a raw dict (not a snapshot list) for a persona.

        Useful when callers have already assembled a flat data dict rather than
        a list of FinancialSnapshot objects.

        Args:
            persona_name: Persona identifier.
            data: Dict whose top-level keys are data-type labels.

        Returns:
            A filtered copy of *data* with restricted keys removed.
        """
        allowed = self.get_allowed_types(persona_name)
        restricted = self._ALL_DATA_TYPES - allowed
        return {k: v for k, v in data.items() if k not in restricted}
