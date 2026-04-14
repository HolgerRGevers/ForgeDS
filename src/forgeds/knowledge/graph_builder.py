"""Knowledge graph edge builder.

Reads tokens from knowledge.db and infers relations:
- HIERARCHY edges (module -> page -> section -> token)
- NEXT_SIBLING edges (adjacent tokens in same section)
- CROSS_REFERENCE edges (hyperlinks between pages)
- CALLOUT_* edges (note/tip/important tokens)
- FUNCTION_OF edges (tokens mentioning known Deluge functions)
- EXAMPLE_OF edges (code examples linked to concept tokens)

All edges are written to the `edges` table in the same SQLite database.
"""

from __future__ import annotations

import bisect
import re
import sqlite3
from pathlib import Path

from forgeds.knowledge._types import RELATION_WEIGHTS, RelationType


# ---------------------------------------------------------------------------
# Link extraction
# ---------------------------------------------------------------------------

_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def _extract_links(content: str) -> list[str]:
    """Extract URLs from markdown-style links in token content."""
    return [url for _, url in _MD_LINK_RE.findall(content)]


# ---------------------------------------------------------------------------
# Batched edge collector (Fix #4)
# ---------------------------------------------------------------------------

class _EdgeBatch:
    """Collects edges in memory and flushes them in a single executemany."""

    def __init__(self) -> None:
        self._edges: list[tuple[str, str, str, float]] = []
        self._seen: set[tuple[str, str, str]] = set()

    def add(self, source: str, target: str, rel_type: RelationType) -> bool:
        """Stage an edge for batch insert. Returns True if new."""
        key = (source, target, rel_type.value)
        if key in self._seen:
            return False
        self._seen.add(key)
        weight = RELATION_WEIGHTS.get(rel_type, 0.5)
        self._edges.append((source, target, rel_type.value, weight))
        return True

    def flush(self, conn: sqlite3.Connection) -> int:
        """Write all staged edges to the database in one batch."""
        if not self._edges:
            return 0
        conn.executemany(
            "INSERT OR IGNORE INTO edges (source_sha, target_sha, rel_type, weight) VALUES (?, ?, ?, ?)",
            self._edges,
        )
        count = len(self._edges)
        self._edges.clear()
        self._seen.clear()
        return count


# ---------------------------------------------------------------------------
# Relation inference passes
# ---------------------------------------------------------------------------

def _build_hierarchy_and_sibling_edges(
    rows: list[tuple[str, str, str, str, int]],
    batch: _EdgeBatch,
) -> int:
    """Create HIERARCHY and NEXT_SIBLING edges from a single token scan.

    Combines Fix #8: one query serves both hierarchy and sibling logic.
    `rows` must be sorted by (page_url, section, paragraph).
    """
    count = 0

    # Group tokens by (page_url, section)
    groups: dict[tuple[str, str], list[str]] = {}
    prev_sha: str | None = None
    prev_key: tuple[str, str] | None = None

    for sha, _module, page_url, section, _para in rows:
        key = (page_url, section or "")
        groups.setdefault(key, []).append(sha)

        # NEXT_SIBLING: adjacent tokens in the same section
        if prev_sha and key == prev_key:
            if batch.add(prev_sha, sha, RelationType.NEXT_SIBLING):
                count += 1
        prev_sha = sha
        prev_key = key

    # HIERARCHY: first token in each section is the anchor
    for (_page, _section), shas in groups.items():
        if len(shas) < 2:
            continue
        anchor = shas[0]
        for child_sha in shas[1:]:
            if batch.add(anchor, child_sha, RelationType.HIERARCHY):
                count += 1

    return count


def _build_crossref_edges(
    tokens: list[tuple[str, str, str, str]],
    batch: _EdgeBatch,
) -> int:
    """Create CROSS_REFERENCE edges from hyperlinks in token content.

    Fix #2: uses an in-memory dict for module lookup instead of SQL queries.
    """
    # Build page_url -> first token SHA index for target resolution
    page_tokens: dict[str, list[str]] = {}
    # Build sha -> module dict for cross-module check (Fix #2)
    sha_to_module: dict[str, str] = {}

    for sha, content, module, page_url in tokens:
        page_tokens.setdefault(page_url, []).append(sha)
        sha_to_module[sha] = module

    count = 0
    for sha, content, module, page_url in tokens:
        links = _extract_links(content)
        for link_url in links:
            # Normalise — try to match against known page_urls
            targets = page_tokens.get(link_url, [])
            if not targets:
                # Try without trailing slash / fragment
                clean = link_url.split("#")[0].rstrip("/")
                targets = page_tokens.get(clean, [])

            for target_sha in targets[:1]:  # Link to first token on target page
                if target_sha != sha:
                    src_mod = sha_to_module.get(sha, "")
                    tgt_mod = sha_to_module.get(target_sha, "")
                    rel = RelationType.CROSS_MODULE if src_mod != tgt_mod else RelationType.CROSS_REFERENCE
                    if batch.add(sha, target_sha, rel):
                        count += 1

    return count


# Callout content types that should be linked to preceding tokens
_CALLOUT_TYPES = {"NOTE", "PRO_TIP", "IMPORTANT", "VERY_IMPORTANT"}

_CALLOUT_REL_MAP = {
    "NOTE": RelationType.CALLOUT_NOTE,
    "PRO_TIP": RelationType.CALLOUT_TIP,
    "IMPORTANT": RelationType.CALLOUT_IMPORTANT,
    "VERY_IMPORTANT": RelationType.CALLOUT_CRITICAL,
}


def _build_callout_and_example_edges(
    all_tokens: list[tuple[str, str, str, str, int]],
    batch: _EdgeBatch,
) -> int:
    """Create CALLOUT_* and EXAMPLE_OF edges using an in-memory index.

    Fix #3: pre-builds a sorted index by (page_url, section, paragraph)
    and uses bisect for O(log n) lookups instead of N+1 SQL queries.
    """
    # Build index of non-callout tokens sorted by (page_url, section, paragraph)
    # Each entry: (page_url, section, paragraph, token_sha, content_type)
    non_callout_index: dict[tuple[str, str], list[tuple[int, str, str]]] = {}
    callout_tokens: list[tuple[str, str, str, str, int]] = []
    example_tokens: list[tuple[str, str, str, int]] = []

    for sha, content_type, page_url, section, para in all_tokens:
        key = (page_url, section or "")
        if content_type in _CALLOUT_TYPES:
            callout_tokens.append((sha, content_type, page_url, section or "", para))
        elif content_type == "CODE_EXAMPLE":
            example_tokens.append((sha, page_url, section or "", para))
        else:
            non_callout_index.setdefault(key, []).append((para, sha, content_type))

    # Sort each group by paragraph number for bisect
    for group in non_callout_index.values():
        group.sort()

    count = 0

    # CALLOUT edges: link to nearest preceding non-callout token in same section
    for sha, ctype, page_url, section, para in callout_tokens:
        key = (page_url, section)
        group = non_callout_index.get(key)
        if not group:
            continue
        # bisect to find the rightmost token with paragraph < para
        paras = [g[0] for g in group]
        idx = bisect.bisect_left(paras, para) - 1
        if idx >= 0:
            rel_type = _CALLOUT_REL_MAP.get(ctype, RelationType.CALLOUT_NOTE)
            if batch.add(group[idx][1], sha, rel_type):
                count += 1

    # EXAMPLE_OF edges: link CODE_EXAMPLE to nearest preceding PROSE token
    prose_index: dict[tuple[str, str], list[tuple[int, str]]] = {}
    for key, group in non_callout_index.items():
        prose_only = [(p, s) for p, s, ct in group if ct == "PROSE"]
        if prose_only:
            prose_index[key] = prose_only

    for sha, page_url, section, para in example_tokens:
        key = (page_url, section)
        group = prose_index.get(key)
        if not group:
            continue
        paras = [g[0] for g in group]
        idx = bisect.bisect_left(paras, para) - 1
        if idx >= 0:
            if batch.add(group[idx][1], sha, RelationType.EXAMPLE_OF):
                count += 1

    return count


def _build_function_edges(conn: sqlite3.Connection, batch: _EdgeBatch) -> int:
    """Create FUNCTION_OF edges for tokens that describe known Deluge functions.

    Cross-references against deluge_lang.db if available.
    """
    from forgeds._shared.config import get_db_dir

    db_dir = get_db_dir()
    lang_db = db_dir / "deluge_lang.db"

    if not lang_db.exists():
        return 0

    _ALLOWED_LANG_TABLES = {"functions", "builtins", "keywords"}

    lang_conn = sqlite3.connect(str(lang_db))
    try:
        func_names: set[str] = set()
        for table in ("functions", "builtins", "keywords"):
            if table not in _ALLOWED_LANG_TABLES:
                continue
            try:
                rows = lang_conn.execute(f"SELECT name FROM {table}").fetchall()  # table is from a fixed whitelist
                func_names.update(r[0] for r in rows)
            except sqlite3.OperationalError:
                continue
    finally:
        lang_conn.close()

    if not func_names:
        return 0

    # Find SIGNATURE tokens and link them
    count = 0
    sig_tokens = conn.execute(
        "SELECT token_sha, content FROM tokens WHERE content_type = 'SIGNATURE'"
    ).fetchall()

    for sha, content in sig_tokens:
        content_lower = content.lower()
        for func_name in func_names:
            if func_name.lower() in content_lower:
                if batch.add(sha, sha, RelationType.FUNCTION_OF):
                    count += 1
                break

    return count


# ---------------------------------------------------------------------------
# Main build entry point
# ---------------------------------------------------------------------------

def build_graph(db_path: Path) -> int:
    """Run all relation inference passes and write edges to knowledge.db.

    Returns total number of edges created.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA temp_store=MEMORY")

    # Fix #14: clear stale edges before rebuilding
    conn.execute("DELETE FROM edges")

    batch = _EdgeBatch()
    total = 0

    try:
        # Fix #8: single query for both hierarchy and sibling passes
        rows = conn.execute(
            "SELECT token_sha, module, page_url, section, paragraph "
            "FROM tokens ORDER BY page_url, section, paragraph"
        ).fetchall()

        total += _build_hierarchy_and_sibling_edges(rows, batch)

        # Fix #2 & #3: fetch tokens once for crossref, callout, and example passes
        all_tokens_crossref = conn.execute(
            "SELECT token_sha, content, module, page_url FROM tokens"
        ).fetchall()
        total += _build_crossref_edges(all_tokens_crossref, batch)

        # For callout/example passes, need content_type + position
        all_tokens_typed = conn.execute(
            "SELECT token_sha, content_type, page_url, section, paragraph FROM tokens"
        ).fetchall()
        total += _build_callout_and_example_edges(all_tokens_typed, batch)

        total += _build_function_edges(conn, batch)

        # Flush all accumulated edges in one batch
        batch.flush(conn)
        conn.commit()
    finally:
        conn.close()

    return total
