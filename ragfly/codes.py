"""Public-code translation at the SDK edge (English ↔ internal).

RAGfly catalog codes are OPAQUE internal identifiers that historically ended up in
Spanish (`VECTORIZADO`, `FACTURA`). The agentic frontier — MCP, SDK, CLI — speaks
ENGLISH: every catalog row has a stable public alias `codigo_*_en` (`VECTORIZED`,
`INVOICE`) that points to the SAME row.

The SDK talks English to the developer but the underlying REST API still speaks the
internal codes. This module fetches the `{internal: english}` map from
`GET /catalogo/public-codes` (the same source the MCP server uses) and translates at
the SDK edge: internal on the wire, English in your code.

The map only changes with a catalog migration, so it is fetched once and cached for
the client's lifetime. Translation is fail-open: an unknown code passes through
untouched, so the SDK never hides a value it can't map.
"""

from __future__ import annotations

from typing import Optional


class CodeTranslator:
    """Lazily fetches and caches the public-code map, and translates both ways."""

    def __init__(self, fetch_map):
        # fetch_map: () -> dict[str, dict[str, str]]  (domain -> {internal: english})
        self._fetch_map = fetch_map
        self._to_english: Optional[dict[str, dict[str, str]]] = None
        self._to_internal: Optional[dict[str, dict[str, str]]] = None

    def _ensure_loaded(self) -> None:
        if self._to_english is not None:
            return
        try:
            mapa = self._fetch_map() or {}
        except Exception:
            # If the map can't be fetched, degrade to identity (never break calls).
            mapa = {}
        self._to_english = {dom: dict(t) for dom, t in mapa.items()}
        self._to_internal = {
            dom: {en: internal for internal, en in t.items()}
            for dom, t in mapa.items()
        }

    def to_english(self, domain: str, internal_code: Optional[str]) -> Optional[str]:
        """internal → English. Unknown codes pass through. None → None."""
        if not internal_code:
            return internal_code
        self._ensure_loaded()
        return self._to_english.get(domain, {}).get(internal_code, internal_code)

    def to_internal(self, domain: str, public_code: Optional[str]) -> Optional[str]:
        """English → internal. Accepts an internal code too (bilingual during the
        transition). Unknown codes pass through. None → None."""
        if not public_code:
            return public_code
        self._ensure_loaded()
        table = self._to_internal.get(domain, {})
        if public_code in table:
            return table[public_code]
        # Already an internal code? (caller passed the internal one out of habit)
        if public_code in self._to_english.get(domain, {}):
            return public_code
        return public_code
