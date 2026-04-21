"""Lightweight knowledge-base accessor for ForgeDS tools.

Provides a lazy, singleton-style interface that any tool can import to
query the knowledge base without pulling in the full ``knowledge/``
package at import time.  All ``forgeds.knowledge.*`` imports are deferred
to method bodies so that importing this module never triggers a cascade.

If ``knowledge.db`` does not exist, every method returns a graceful
empty / zero result — tools work identically to their pre-KB behaviour.

Usage::

    from forgeds._shared.kb_accessor import get_kb

    kb = get_kb()
    if kb.available():
        context = kb.query("sendmail pattern")
        residual = kb.compute_residual("app:My_App")
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path


class KBAccessor:
    """Lazy accessor for the ForgeDS knowledge graph."""

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = self._discover_db()
        self._db_path = db_path
        # Cached data (populated on first use)
        self._signatures: dict[str, dict] | None = None

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    @staticmethod
    def _discover_db() -> Path:
        """Find knowledge.db using the same logic as knowledge/cli.py."""
        from forgeds._shared.config import find_project_root, load_config

        root = find_project_root()
        cfg = load_config().get("knowledge", {})
        kb_dir = root / cfg.get("knowledge_dir", "knowledge")
        return kb_dir / "knowledge.db"

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def available(self) -> bool:
        """Return True if knowledge.db exists and is readable."""
        return self._db_path.is_file()

    @property
    def db_path(self) -> Path:
        return self._db_path

    # ------------------------------------------------------------------
    # Context retrieval
    # ------------------------------------------------------------------

    def query(
        self,
        query_str: str,
        *,
        module: str | None = None,
        max_words: int = 2048,
    ) -> str:
        """Retrieve context markdown from the KB.

        Returns ``""`` if the KB is unavailable or the query finds nothing.
        """
        if not self.available():
            return ""
        try:
            from forgeds.knowledge.retriever import retrieve_context

            result = retrieve_context(
                query_str,
                db_path=str(self._db_path),
                module=module,
                max_tokens=max_words,
            )
            return result.markdown
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Pattern retrieval
    # ------------------------------------------------------------------

    def get_patterns(self, pattern_name: str) -> list[str]:
        """Retrieve code-example snippets matching *pattern_name*.

        Searches CODE_EXAMPLE tokens via FTS and returns the raw content
        strings.  Returns ``[]`` if the KB is unavailable.
        """
        if not self.available():
            return []
        try:
            conn = sqlite3.connect(str(self._db_path))
            # Try FTS first
            try:
                rows = conn.execute(
                    """SELECT content FROM tokens
                       WHERE content_type = 'CODE_EXAMPLE'
                         AND token_sha IN (
                             SELECT token_sha FROM tokens_fts
                             WHERE tokens_fts MATCH ?
                         )
                       LIMIT 10""",
                    (pattern_name,),
                ).fetchall()
            except sqlite3.OperationalError:
                # FTS table may not exist — fall back to LIKE
                rows = conn.execute(
                    """SELECT content FROM tokens
                       WHERE content_type = 'CODE_EXAMPLE'
                         AND content LIKE ?
                       LIMIT 10""",
                    (f"%{pattern_name}%",),
                ).fetchall()
            conn.close()
            return [r[0] for r in rows]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Function signatures
    # ------------------------------------------------------------------

    def get_function_signatures(self) -> dict[str, dict]:
        """Extract function signatures from KB CODE_EXAMPLE tokens.

        Parses patterns like ``<var> = functionName(<p1>, <p2>)`` and
        ``<var> = <obj>.methodName(<p1>)`` from the deluge-functions module.

        Cached after first call.  Returns ``{}`` if KB is unavailable.
        """
        if self._signatures is not None:
            return self._signatures
        if not self.available():
            self._signatures = {}
            return self._signatures
        try:
            conn = sqlite3.connect(str(self._db_path))
            rows = conn.execute(
                """SELECT content FROM tokens
                   WHERE content_type = 'CODE_EXAMPLE'
                     AND module LIKE 'deluge%'"""
            ).fetchall()
            conn.close()

            sigs: dict[str, dict] = {}
            # Match: funcName(<params>) or .methodName(<params>)
            sig_re = re.compile(
                r"(?:^|[=\s.])(\w+)\s*\(([^)]*)\)",
                re.MULTILINE,
            )
            skip = {"if", "else", "for", "while", "info", "alert", "return",
                    "variable", "var", "input", "void", "null", "true", "false",
                    "each", "catch", "try", "throw", "break", "continue"}
            for (content,) in rows:
                for m in sig_re.finditer(content):
                    name = m.group(1).lower()
                    if name in skip or name.startswith("<") or name.isdigit():
                        continue
                    # Skip names that are purely numeric or too short
                    if len(name) < 2 or not name[0].isalpha():
                        continue
                    params_str = m.group(2).strip()
                    params = [p.strip() for p in params_str.split(",") if p.strip()] if params_str else []
                    # Keep the entry with the most parameters (overloads)
                    if name not in sigs or len(params) > sigs[name]["count"]:
                        sigs[name] = {"params": params, "count": len(params)}
            self._signatures = sigs
            return sigs
        except Exception:
            self._signatures = {}
            return self._signatures

    # ------------------------------------------------------------------
    # Projection / residual
    # ------------------------------------------------------------------

    def compute_residual(self, module: str) -> float:
        """Run app projections and return the residual.  Returns 0.0 on failure."""
        report = self.project(module)
        return report.residual if report else 0.0

    def project(self, module: str):
        """Run full KB projection on *module*.

        Returns a ``ProjectionReport`` or ``None`` if unavailable.
        """
        if not self.available():
            return None
        try:
            from forgeds.knowledge.app_projection import project_kb_onto_app

            return project_kb_onto_app(module, self._db_path)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Bulk helpers
    # ------------------------------------------------------------------

    def list_app_modules(self) -> list[str]:
        """Return all ``app:*`` module names in the KB."""
        if not self.available():
            return []
        try:
            conn = sqlite3.connect(str(self._db_path))
            rows = conn.execute(
                "SELECT DISTINCT module FROM tokens WHERE module LIKE 'app:%' ORDER BY module"
            ).fetchall()
            conn.close()
            return [r[0] for r in rows]
        except Exception:
            return []


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_accessor: KBAccessor | None = None


def get_kb(db_path: Path | None = None) -> KBAccessor:
    """Get or create the singleton KBAccessor."""
    global _accessor
    if _accessor is None or db_path is not None:
        _accessor = KBAccessor(db_path)
    return _accessor
