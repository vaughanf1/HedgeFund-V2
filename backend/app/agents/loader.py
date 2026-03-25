"""Persona loader: reads and renders investor persona Markdown templates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

PERSONAS_DIR = Path(__file__).parent / "personas"

VALID_PERSONAS = {"buffett", "munger", "ackman", "cohen", "dalio"}


class PersonaLoader:
    """Loads investor persona prompt templates from Markdown files.

    Usage::

        loader = PersonaLoader()
        names = loader.list_personas()
        raw = loader.load_persona("buffett")
        rendered = loader.render_persona("buffett", {"fundamentals": {...}})
    """

    def __init__(self, personas_dir: Optional[Path] = None) -> None:
        self._dir = personas_dir or PERSONAS_DIR

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_personas(self) -> list[str]:
        """Return sorted list of available persona names (without extension)."""
        return sorted(
            p.stem
            for p in self._dir.glob("*.md")
            if p.stem in VALID_PERSONAS
        )

    def load_persona(self, name: str) -> str:
        """Return the raw Markdown content for *name*.

        Raises:
            ValueError: if *name* is not a recognised persona.
            FileNotFoundError: if the persona file is missing.
        """
        name = name.lower().strip()
        if name not in VALID_PERSONAS:
            raise ValueError(
                f"Unknown persona '{name}'. Valid options: {sorted(VALID_PERSONAS)}"
            )
        path = self._dir / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Persona file not found: {path}")
        return path.read_text(encoding="utf-8")

    def render_persona(self, name: str, data_context: dict) -> str:
        """Return the persona template with ``{{data_context_json}}`` replaced.

        Args:
            name: Persona identifier (e.g. ``"buffett"``).
            data_context: Dict of data partitioned for this persona. Will be
                serialised to indented JSON and injected into the template.

        Returns:
            Rendered Markdown string suitable for use as an LLM system prompt.
        """
        template = self.load_persona(name)
        context_json = json.dumps(data_context, indent=2, default=str)
        return template.replace("{{data_context_json}}", context_json)
