"""Context retriever for the ForgeDS knowledge graph.

Implements the SEED → EXPAND → RANK → ORDER → ASSEMBLE pipeline that
turns a user query into a coherent markdown context block suitable for
injecting into a Claude prompt.

Usage:
    from forgeds.knowledge.retriever import retrieve_context
    context = retrieve_context("invokeUrl OAuth", db_path="knowledge/knowledge.db")
    print(context.markdown)
    print(context.token_count)
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class RetrievedToken:
    """A token with retrieval metadata attached."""
    token_sha: str
    content: str
    content_type: str
    module: str
    page_url: str
    page_title: str
    section: str
    paragraph: int
    # Retrieval scoring
    seed_rank: float = 0.0       # FTS/LIKE rank (0 if expanded, not seed)
    edge_weight: float = 0.0     # Weight of the edge that brought us here
    expansion_depth: int = 0     # 0 = seed, 1 = direct neighbor, etc.


@dataclass
class RetrievalResult:
    """The assembled context returned by retrieve_context()."""
    markdown: str                           # Coherent markdown block
    tokens: list[RetrievedToken]            # Ordered tokens used
    token_count: int = 0                    # Approximate word count
    seed_count: int = 0                     # How many FTS hits seeded this
    expanded_count: int = 0                 # How many came from graph expansion
    modules_covered: list[str] = field(default_factory=list)
    pages_covered: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Edge weights for expansion priority
# ---------------------------------------------------------------------------

# How much we want to follow each edge type during expansion.
# Higher = more eagerly followed. 0 = never follow.
_EXPANSION_PRIORITY: dict[str, float] = {
    "HIERARCHY": 1.0,
    "NEXT_SIBLING": 0.5,
    "EXAMPLE_OF": 0.9,
    "CALLOUT_NOTE": 0.7,
    "CALLOUT_TIP": 0.7,
    "CALLOUT_IMPORTANT": 0.95,
    "CALLOUT_CRITICAL": 1.0,
    "CROSS_REFERENCE": 0.4,
    "CROSS_MODULE": 0.3,
    "FUNCTION_OF": 0.6,
}

# Content type priority for ranking when scores are equal.
_CONTENT_PRIORITY: dict[str, float] = {
    "IMPORTANT": 1.0,
    "VERY_IMPORTANT": 1.0,
    "SIGNATURE": 0.9,
    "CODE_EXAMPLE": 0.8,
    "PROSE": 0.7,
    "NOTE": 0.6,
    "PRO_TIP": 0.6,
    "TABLE_ROW": 0.4,
}


# ---------------------------------------------------------------------------
# STEP 1: SEED — find initial matching tokens via FTS5 or LIKE
# ---------------------------------------------------------------------------

def _seed_tokens(
    conn: sqlite3.Connection,
    query: str,
    module: str | None = None,
    max_seeds: int = 30,
) -> list[RetrievedToken]:
    """Find seed tokens matching the query via FTS5 (preferred) or LIKE."""
    seeds: list[RetrievedToken] = []

    # Try FTS5 first
    use_fts = False
    try:
        conn.execute("SELECT 1 FROM tokens_fts LIMIT 0")
        use_fts = True
    except sqlite3.OperationalError:
        pass

    if use_fts:
        # Split query into terms for FTS5 OR matching
        terms = query.strip().split()
        if len(terms) == 1:
            fts_query = '"' + terms[0].replace('"', '""') + '"'
        else:
            # Match any term, rank will sort by relevance
            fts_parts = ['"' + t.replace('"', '""') + '"' for t in terms]
            fts_query = " OR ".join(fts_parts)

        sql = """SELECT t.token_sha, t.content, t.content_type, t.module,
                        t.page_url, t.page_title, t.section, t.paragraph,
                        rank
                 FROM tokens t
                 JOIN tokens_fts f ON f.token_sha = t.token_sha
                 WHERE tokens_fts MATCH ?"""
        params: list = [fts_query]

        if module:
            sql += " AND t.module = ?"
            params.append(module)

        sql += " ORDER BY rank LIMIT ?"
        params.append(max_seeds)

        rows = conn.execute(sql, params).fetchall()
        for i, row in enumerate(rows):
            seeds.append(RetrievedToken(
                token_sha=row[0], content=row[1], content_type=row[2],
                module=row[3], page_url=row[4], page_title=row[5] or "",
                section=row[6] or "", paragraph=row[7] or 0,
                seed_rank=1.0 / (i + 1),  # Reciprocal rank
                expansion_depth=0,
            ))
    else:
        # LIKE fallback — match each term
        terms = query.strip().split()
        where_parts = ["content LIKE ?"] * len(terms)
        params = [f"%{t}%" for t in terms]

        sql = f"""SELECT token_sha, content, content_type, module,
                         page_url, page_title, section, paragraph
                  FROM tokens WHERE ({' OR '.join(where_parts)})"""

        if module:
            sql += " AND module = ?"
            params.append(module)

        sql += " ORDER BY module, page_url, paragraph LIMIT ?"
        params.append(max_seeds)

        rows = conn.execute(sql, params).fetchall()
        for i, row in enumerate(rows):
            seeds.append(RetrievedToken(
                token_sha=row[0], content=row[1], content_type=row[2],
                module=row[3], page_url=row[4], page_title=row[5] or "",
                section=row[6] or "", paragraph=row[7] or 0,
                seed_rank=1.0 / (i + 1),
                expansion_depth=0,
            ))

    return seeds


# ---------------------------------------------------------------------------
# STEP 2: EXPAND — follow graph edges to gather context
# ---------------------------------------------------------------------------

def _expand_seeds(
    conn: sqlite3.Connection,
    seeds: list[RetrievedToken],
    max_depth: int = 2,
    max_expanded: int = 150,
) -> list[RetrievedToken]:
    """Expand seed tokens by following graph edges.

    Uses a priority-weighted BFS: high-priority edges (HIERARCHY,
    EXAMPLE_OF, CALLOUT_*) are followed before low-priority ones
    (CROSS_REFERENCE, CROSS_MODULE).
    """
    seen_shas: set[str] = {s.token_sha for s in seeds}
    expanded: list[RetrievedToken] = []

    # Build frontier from seed SHAs
    # (sha, depth, inherited_score)
    frontier: list[tuple[str, int, float]] = [
        (s.token_sha, 0, s.seed_rank) for s in seeds
    ]

    while frontier and len(expanded) < max_expanded:
        current_sha, depth, parent_score = frontier.pop(0)

        if depth >= max_depth:
            continue

        # Get outgoing edges from current token
        rows = conn.execute(
            """SELECT e.target_sha, e.rel_type, e.weight,
                      t.content, t.content_type, t.module,
                      t.page_url, t.page_title, t.section, t.paragraph
               FROM edges e
               JOIN tokens t ON e.target_sha = t.token_sha
               WHERE e.source_sha = ?""",
            (current_sha,),
        ).fetchall()

        # Also get incoming edges (for reverse traversal — e.g., a code
        # example points TO the concept via EXAMPLE_OF, but we may have
        # found the concept and want to pull in its examples)
        rows += conn.execute(
            """SELECT e.source_sha, e.rel_type, e.weight,
                      t.content, t.content_type, t.module,
                      t.page_url, t.page_title, t.section, t.paragraph
               FROM edges e
               JOIN tokens t ON e.source_sha = t.token_sha
               WHERE e.target_sha = ?""",
            (current_sha,),
        ).fetchall()

        # Sort by expansion priority so we pick up high-value edges first
        candidates = []
        for row in rows:
            target_sha = row[0]
            if target_sha in seen_shas:
                continue
            rel_type = row[1]
            edge_weight = row[2]
            expansion_prio = _EXPANSION_PRIORITY.get(rel_type, 0.2)
            combined_score = parent_score * expansion_prio * edge_weight
            candidates.append((combined_score, target_sha, row, rel_type, edge_weight))

        # Take best candidates first
        candidates.sort(key=lambda c: -c[0])

        for score, target_sha, row, rel_type, edge_weight in candidates:
            if len(expanded) >= max_expanded:
                break
            if target_sha in seen_shas:
                continue

            seen_shas.add(target_sha)
            token = RetrievedToken(
                token_sha=target_sha, content=row[3], content_type=row[4],
                module=row[5], page_url=row[6], page_title=row[7] or "",
                section=row[8] or "", paragraph=row[9] or 0,
                edge_weight=edge_weight,
                expansion_depth=depth + 1,
            )
            expanded.append(token)

            # Add to frontier for further expansion
            frontier.append((target_sha, depth + 1, score))

    return expanded


# ---------------------------------------------------------------------------
# STEP 3: RANK — score and budget-cap tokens
# ---------------------------------------------------------------------------

def _rank_tokens(
    seeds: list[RetrievedToken],
    expanded: list[RetrievedToken],
    max_tokens: int,
) -> list[RetrievedToken]:
    """Score all tokens and return the top-N by budget.

    Budget is measured in approximate words (whitespace-split), not
    token count, since the output goes into a Claude prompt.
    """
    all_tokens = seeds + expanded

    def _score(t: RetrievedToken) -> float:
        # Seeds get a base boost
        base = t.seed_rank * 3.0 if t.seed_rank > 0 else 0.0
        # Edge weight contribution (how relevant the edge was)
        edge = t.edge_weight * 1.5
        # Content type priority
        ctype = _CONTENT_PRIORITY.get(t.content_type, 0.5)
        # Depth penalty — deeper expansions are less directly relevant
        depth_penalty = 1.0 / (1.0 + t.expansion_depth * 0.5)
        # Length bonus — longer content is usually more substantive
        length_bonus = min(len(t.content) / 500, 1.0) * 0.3
        return (base + edge + ctype + length_bonus) * depth_penalty

    scored = [(t, _score(t)) for t in all_tokens]
    scored.sort(key=lambda x: -x[1])

    # Budget cap by word count
    result: list[RetrievedToken] = []
    word_count = 0
    for token, _score_val in scored:
        words = len(token.content.split())
        if word_count + words > max_tokens and result:
            break
        result.append(token)
        word_count += words

    return result


# ---------------------------------------------------------------------------
# STEP 4: ORDER — restore reading flow
# ---------------------------------------------------------------------------

def _order_tokens(tokens: list[RetrievedToken]) -> list[RetrievedToken]:
    """Sort tokens by (module, page_url, section, paragraph) to
    restore the original reading order within each page."""
    return sorted(tokens, key=lambda t: (
        t.module,
        t.page_url,
        t.section,
        t.paragraph,
    ))


# ---------------------------------------------------------------------------
# STEP 5: ASSEMBLE — build coherent markdown
# ---------------------------------------------------------------------------

def _assemble_markdown(tokens: list[RetrievedToken]) -> str:
    """Convert ordered tokens into a coherent markdown document.

    Groups tokens by page and section, inserting headers to provide
    structure and attribution.
    """
    if not tokens:
        return ""

    parts: list[str] = []
    current_page = ""
    current_section = ""
    current_module = ""

    for token in tokens:
        # Module header
        if token.module != current_module:
            current_module = token.module
            current_page = ""
            current_section = ""
            parts.append(f"\n## [{current_module}]\n")

        # Page header
        if token.page_url != current_page:
            current_page = token.page_url
            current_section = ""
            title = token.page_title or _url_to_title(current_page)
            parts.append(f"\n### {title}\n")

        # Section header
        section = token.section or "(intro)"
        if section != current_section:
            current_section = section
            # Clean up section text (remove markdown link artifacts)
            clean_section = re.sub(r'\[?\]?\(?\)?', '', section).strip()
            if clean_section and clean_section != "(intro)":
                parts.append(f"\n#### {clean_section}\n")

        # Token content
        content = token.content.strip()
        if not content:
            continue

        # Add content type annotation for non-prose tokens
        if token.content_type == "NOTE":
            parts.append(f"> **Note:** {content}\n")
        elif token.content_type == "IMPORTANT":
            parts.append(f"> **Important:** {content}\n")
        elif token.content_type == "VERY_IMPORTANT":
            parts.append(f"> **Critical:** {content}\n")
        elif token.content_type == "PRO_TIP":
            parts.append(f"> **Tip:** {content}\n")
        elif token.content_type == "CODE_EXAMPLE":
            # Code blocks are already fenced in the content
            if content.startswith("```"):
                parts.append(f"{content}\n")
            else:
                parts.append(f"```\n{content}\n```\n")
        elif token.content_type == "TABLE_ROW":
            parts.append(f"{content}\n")
        else:
            parts.append(f"{content}\n")

    return "\n".join(parts).strip()


def _url_to_title(url: str) -> str:
    """Extract a readable title from a URL path."""
    path = url.rstrip("/").rsplit("/", 1)[-1]
    path = path.replace(".html", "").replace("-", " ").replace("_", " ")
    return path.title()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrieve_context(
    query: str,
    db_path: str | Path = "knowledge/knowledge.db",
    *,
    module: str | None = None,
    max_words: int = 4096,
    max_seeds: int = 20,
    max_expansion: int = 100,
    expansion_depth: int = 2,
) -> RetrievalResult:
    """Retrieve coherent context from the knowledge graph for a query.

    This is the main entry point. It runs the full pipeline:
    SEED → EXPAND → RANK → ORDER → ASSEMBLE.

    Args:
        query: Natural language query or keyword(s).
        db_path: Path to knowledge.db.
        module: Optional module filter (e.g., "deluge-functions").
        max_words: Approximate word budget for the assembled context.
        max_seeds: Maximum FTS seed tokens to retrieve.
        max_expansion: Maximum tokens to gather via graph expansion.
        expansion_depth: How many hops to follow from seed tokens.

    Returns:
        RetrievalResult with assembled markdown and metadata.
    """
    db_path = str(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = None  # We use positional access

    try:
        # Step 1: SEED
        seeds = _seed_tokens(conn, query, module=module, max_seeds=max_seeds)
        if not seeds:
            return RetrievalResult(
                markdown=f"No knowledge found for: {query}",
                tokens=[], token_count=0, seed_count=0,
            )

        # Step 2: EXPAND
        expanded = _expand_seeds(
            conn, seeds,
            max_depth=expansion_depth,
            max_expanded=max_expansion,
        )

        # Step 3: RANK
        ranked = _rank_tokens(seeds, expanded, max_words)

        # Step 4: ORDER
        ordered = _order_tokens(ranked)

        # Step 5: ASSEMBLE
        markdown = _assemble_markdown(ordered)

        # Compute stats
        modules_covered = sorted(set(t.module for t in ordered))
        pages_covered = sorted(set(t.page_url for t in ordered))
        word_count = len(markdown.split())
        seed_count = sum(1 for t in ordered if t.expansion_depth == 0)
        expanded_count = sum(1 for t in ordered if t.expansion_depth > 0)

        return RetrievalResult(
            markdown=markdown,
            tokens=ordered,
            token_count=word_count,
            seed_count=seed_count,
            expanded_count=expanded_count,
            modules_covered=modules_covered,
            pages_covered=pages_covered,
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def retrieve_main() -> None:
    """CLI for context retrieval — wired to forgeds-kb-retrieve."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="forgeds-kb-retrieve",
        description="Retrieve coherent context from the knowledge graph.",
    )
    parser.add_argument("query", help="Search query (keywords or natural language).")
    parser.add_argument(
        "--module", "-m", default=None,
        help="Filter by module name.",
    )
    parser.add_argument(
        "--max-words", "-w", type=int, default=4096,
        help="Approximate word budget (default: 4096).",
    )
    parser.add_argument(
        "--max-seeds", type=int, default=20,
        help="Maximum seed tokens from FTS (default: 20).",
    )
    parser.add_argument(
        "--depth", "-d", type=int, default=2,
        help="Graph expansion depth (default: 2).",
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Output metadata as JSON instead of markdown.",
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Show retrieval statistics after output.",
    )
    args = parser.parse_args()

    from forgeds.knowledge.cli import _db_path

    db_path = _db_path()
    if not db_path.exists():
        print(f"Database not found at {db_path}. Run forgeds-kb-parse first.",
              file=sys.stderr)
        sys.exit(1)

    result = retrieve_context(
        args.query,
        db_path=db_path,
        module=args.module,
        max_words=args.max_words,
        max_seeds=args.max_seeds,
        expansion_depth=args.depth,
    )

    if args.as_json:
        import json
        print(json.dumps({
            "query": args.query,
            "word_count": result.token_count,
            "seed_count": result.seed_count,
            "expanded_count": result.expanded_count,
            "total_tokens": len(result.tokens),
            "modules": result.modules_covered,
            "pages": result.pages_covered,
            "markdown": result.markdown,
        }, indent=2, ensure_ascii=False))
    else:
        print(result.markdown)

    if args.stats:
        print(f"\n--- Retrieval Stats ---", file=sys.stderr)
        print(f"Words:    {result.token_count}", file=sys.stderr)
        print(f"Seeds:    {result.seed_count}", file=sys.stderr)
        print(f"Expanded: {result.expanded_count}", file=sys.stderr)
        print(f"Modules:  {', '.join(result.modules_covered)}", file=sys.stderr)
        print(f"Pages:    {len(result.pages_covered)}", file=sys.stderr)

    sys.exit(0)
