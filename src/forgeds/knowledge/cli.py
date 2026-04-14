"""CLI entry points for the ForgeDS knowledge base.

Each *_main() function is wired to a console_scripts entry in
pyproject.toml and follows the ForgeDS convention of sys.exit(0/1/2).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from forgeds._shared.config import find_project_root, load_config


def _kb_config() -> dict:
    return load_config().get("knowledge", {})


def _raw_md_dir() -> Path:
    root = find_project_root()
    return root / _kb_config().get("raw_md_dir", "raw_md")


def _db_path() -> Path:
    """Return the knowledge directory path.

    Returns the directory's ``reality.db`` path (new convention).
    Falls back to ``knowledge.db`` if it exists for backward compat.
    """
    root = find_project_root()
    kb_dir = root / _kb_config().get("knowledge_dir", "knowledge")
    kb_dir.mkdir(parents=True, exist_ok=True)
    # Prefer reality.db; fall back to knowledge.db for migration
    rb = kb_dir / "reality.db"
    legacy = kb_dir / "knowledge.db"
    if not rb.exists() and legacy.exists():
        return legacy
    return rb


# ---------------------------------------------------------------------------
# forgeds-kb-scrape
# ---------------------------------------------------------------------------

def scrape_main() -> None:
    """Scrape Zoho documentation pages into raw_md/."""
    import logging

    parser = argparse.ArgumentParser(
        prog="forgeds-kb-scrape",
        description="Scrape Zoho docs into raw markdown files.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-scrape all pages, ignoring ETag/Last-Modified cache.",
    )
    parser.add_argument(
        "--url", action="append", default=[],
        help="Scrape a specific URL (can be repeated). Overrides forgeds.yaml sources.",
    )
    parser.add_argument(
        "--module", default="deluge",
        help="Module name for --url pages (default: deluge).",
    )
    parser.add_argument(
        "--follow-links", action="store_true", default=None,
        help="Crawl index pages and discover leaf documentation pages.",
    )
    parser.add_argument(
        "--parallel", action="store_true", default=None,
        help="Scrape modules in parallel threads with staggered starts.",
    )
    parser.add_argument(
        "--max-depth", type=int, default=None,
        help="Max crawl depth for --follow-links (default: 2).",
    )
    parser.add_argument(
        "--no-verify-domains", action="store_true",
        help="Skip domain equivalence verification.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable verbose logging.",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")

    from forgeds.knowledge.scraper import scrape_sources, get_scrape_config

    if args.url:
        sources = [{"url": u, "module": args.module} for u in args.url]
        raw_md_dir = _raw_md_dir()
        delay = float(_kb_config().get("scrape_delay", 2.0))
        follow_links = args.follow_links or False
        parallel = args.parallel or False
        max_depth = args.max_depth or 2
    else:
        sources, raw_md_dir, delay, cfg_follow, cfg_parallel, cfg_depth = get_scrape_config()
        follow_links = args.follow_links if args.follow_links is not None else cfg_follow
        parallel = args.parallel if args.parallel is not None else cfg_parallel
        max_depth = args.max_depth if args.max_depth is not None else cfg_depth

    if not sources:
        print("No sources configured. Add knowledge.sources to forgeds.yaml or use --url.", file=sys.stderr)
        sys.exit(1)

    mode_parts = []
    if follow_links:
        mode_parts.append(f"follow_links (depth={max_depth})")
    if parallel:
        mode_parts.append("parallel")
    mode_str = f" [{', '.join(mode_parts)}]" if mode_parts else ""

    print(f"Scraping {len(sources)} source(s) into {raw_md_dir}/{mode_str}")
    written = scrape_sources(
        sources, raw_md_dir,
        delay=delay,
        force=args.force,
        follow_links=follow_links,
        parallel=parallel,
        max_depth=max_depth,
        verify_domains=not args.no_verify_domains,
    )

    if written:
        print(f"Wrote {len(written)} file(s):")
        for p in written:
            print(f"  {p}")
    else:
        print("All pages up-to-date (304 Not Modified).")

    sys.exit(0)


# ---------------------------------------------------------------------------
# forgeds-kb-parse
# ---------------------------------------------------------------------------

def parse_main() -> None:
    """Parse raw_md/ files into knowledge tokens via the Librarian."""
    parser = argparse.ArgumentParser(
        prog="forgeds-kb-parse",
        description="Parse raw markdown into knowledge tokens.",
    )
    parser.add_argument(
        "files", nargs="*",
        help="Specific .md files to parse (default: all in raw_md/).",
    )
    args = parser.parse_args()

    from forgeds.knowledge.token_parser import parse_md_files
    from forgeds.knowledge.librarian_io import open_librarian

    raw_md_dir = _raw_md_dir()
    db_path = _db_path()
    rb_path = db_path if db_path.name == "reality.db" else db_path.parent / "reality.db"
    hb_path = rb_path.parent / "holographic.db"

    lib = open_librarian(rb_path, hb_path)

    if args.files:
        md_files = [Path(f) for f in args.files]
    else:
        md_files = sorted(raw_md_dir.rglob("*.md"))
        md_files = [f for f in md_files if f.name != "_manifest.json"]

    if not md_files:
        print(f"No .md files found in {raw_md_dir}/", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing {len(md_files)} file(s) into {rb_path}")
    count = parse_md_files(md_files, lib, raw_md_dir)
    print(f"Stored {count} token(s) via Librarian.")
    lib.close()
    sys.exit(0)


# ---------------------------------------------------------------------------
# forgeds-kb-build
# ---------------------------------------------------------------------------

def build_main() -> None:
    """Build the knowledge graph edges from parsed tokens."""
    parser = argparse.ArgumentParser(
        prog="forgeds-kb-build",
        description="Build relation edges in the knowledge graph.",
    )
    parser.parse_args()

    from forgeds.knowledge.graph_builder import build_graph
    from forgeds.knowledge.librarian_io import open_librarian

    db_path = _db_path()
    rb_path = db_path if db_path.name == "reality.db" else db_path.parent / "reality.db"
    hb_path = rb_path.parent / "holographic.db"

    actual_rb = rb_path if rb_path.exists() else db_path
    if not actual_rb.exists():
        print(f"Database not found at {actual_rb}. Run forgeds-kb-parse first.", file=sys.stderr)
        sys.exit(1)

    lib = open_librarian(actual_rb, hb_path)

    print(f"Building graph edges in {actual_rb}")
    edge_count = build_graph(lib)
    print(f"Created {edge_count} edge(s).")
    sys.exit(0)


# ---------------------------------------------------------------------------
# forgeds-kb-validate
# ---------------------------------------------------------------------------

def validate_main() -> None:
    """Validate knowledge graph consistency via HRC."""
    parser = argparse.ArgumentParser(
        prog="forgeds-kb-validate",
        description="Run HRC consistency checks on the knowledge graph.",
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Write validation report to file (default: stdout as JSON).",
    )
    args = parser.parse_args()

    from forgeds.knowledge.hrc_bridge import validate_knowledge

    db_path = _db_path()
    if not db_path.exists():
        print(f"Database not found at {db_path}. Run forgeds-kb-parse first.", file=sys.stderr)
        sys.exit(1)

    report = validate_knowledge(db_path)

    output = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(output)

    residual = report.get("residual", 0)
    if residual > 0:
        n_violations = len(report.get("violations", []))
        n_shadows = len(report.get("shadow_fields", []))
        print(f"\nResidual: {residual:.4f} — {n_violations} violation(s), {n_shadows} shadow field(s)", file=sys.stderr)
        sys.exit(1)

    print("\nKnowledge base is internally consistent (residual = 0).")
    sys.exit(0)


# ---------------------------------------------------------------------------
# forgeds-kb-query
# ---------------------------------------------------------------------------

def query_main() -> None:
    """Query the knowledge base for tokens by keyword, function, or module."""
    parser = argparse.ArgumentParser(
        prog="forgeds-kb-query",
        description="Search the knowledge base.",
    )
    parser.add_argument("term", help="Search term (function name, keyword, module).")
    parser.add_argument(
        "--module", "-m", default=None,
        help="Filter by module name.",
    )
    parser.add_argument(
        "--type", "-t", default=None,
        help="Filter by content type (PROSE, CODE_EXAMPLE, SIGNATURE, etc.).",
    )
    parser.add_argument(
        "--limit", "-n", type=int, default=20,
        help="Max results (default: 20).",
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Output as JSON.",
    )
    args = parser.parse_args()

    import sqlite3
    from forgeds.knowledge.librarian_io import open_librarian

    db_path = _db_path()
    rb_path = db_path if db_path.name == "reality.db" else db_path.parent / "reality.db"
    hb_path = rb_path.parent / "holographic.db"

    if not rb_path.exists() and not db_path.exists():
        print(f"Database not found at {rb_path}. Run forgeds-kb-parse first.", file=sys.stderr)
        sys.exit(1)

    actual_rb = rb_path if rb_path.exists() else db_path
    lib = open_librarian(actual_rb, hb_path)
    conn = lib.rb_conn
    conn.row_factory = sqlite3.Row

    # Try FTS5 first for fast full-text search (Fix #13), fall back to LIKE
    use_fts = False
    try:
        conn.execute("SELECT 1 FROM tokens_fts LIMIT 0")
        use_fts = True
    except sqlite3.OperationalError:
        pass

    if use_fts:
        # FTS5 match query — quote the term for safe matching
        fts_term = '"' + args.term.replace('"', '""') + '"'
        sql = """SELECT t.* FROM tokens t
                 JOIN tokens_fts f ON f.token_sha = t.token_sha
                 WHERE tokens_fts MATCH ?"""
        params: list = [fts_term]

        if args.module:
            sql += " AND t.module = ?"
            params.append(args.module)
        if args.type:
            sql += " AND t.content_type = ?"
            params.append(args.type)

        sql += " ORDER BY rank LIMIT ?"
        params.append(args.limit)
    else:
        sql = "SELECT * FROM tokens WHERE content LIKE ?"
        params = [f"%{args.term}%"]

        if args.module:
            sql += " AND module = ?"
            params.append(args.module)
        if args.type:
            sql += " AND content_type = ?"
            params.append(args.type)

        sql += " ORDER BY module, page_url, paragraph LIMIT ?"
        params.append(args.limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    if not rows:
        print(f"No tokens found matching '{args.term}'.")
        sys.exit(0)

    if args.as_json:
        print(json.dumps([dict(r) for r in rows], indent=2, ensure_ascii=False))
    else:
        for r in rows:
            print(f"[{r['content_type']}] {r['module']}/{r['section'] or '?'}")
            print(f"  SHA: {r['token_sha'][:12]}...  Page: {r['page_url']}")
            # Show first 120 chars of content
            preview = r["content"][:120].replace("\n", " ")
            if len(r["content"]) > 120:
                preview += "..."
            print(f"  {preview}")
            print()

    print(f"({len(rows)} result(s))")
    sys.exit(0)


# ---------------------------------------------------------------------------
# forgeds-kb-init — one-command pipeline: scrape + parse + build + validate
# ---------------------------------------------------------------------------

def init_main() -> None:
    """Initialise a complete knowledge base in one step.

    Runs: scrape -> parse -> build -> validate.
    This is the CLI equivalent of ``KnowledgeBase.init()``.
    """
    parser = argparse.ArgumentParser(
        prog="forgeds-kb-init",
        description="Initialise the knowledge base (scrape + parse + build + validate).",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force re-scrape all pages.",
    )
    parser.add_argument(
        "--follow-links", action="store_true",
        help="Crawl index pages and discover leaf pages.",
    )
    parser.add_argument(
        "--parallel", action="store_true",
        help="Scrape modules in parallel.",
    )
    parser.add_argument(
        "--skip-validate", action="store_true",
        help="Skip the validation step.",
    )
    args = parser.parse_args()

    from forgeds.knowledge.api import KnowledgeBase

    db_path = _db_path()
    rb_path = db_path if db_path.name == "reality.db" else db_path.parent / "reality.db"
    kb = KnowledgeBase(rb_path)

    print("Step 1/4: Scraping documentation sources...")
    result = kb.init(
        force_scrape=args.force,
        follow_links=args.follow_links,
        parallel=args.parallel,
    )

    print(f"  Pages scraped:  {result['pages_scraped']}")
    print(f"  Files parsed:   {result['files_parsed']}")
    print(f"  Tokens created: {result['tokens_created']}")
    print(f"  Edges created:  {result['edges_created']}")

    if result["tokens_created"] == 0:
        print("\nNo tokens created. Check forgeds.yaml knowledge.sources config.",
              file=sys.stderr)
        sys.exit(1)

    if args.skip_validate:
        print("\nKnowledge base initialised (validation skipped).")
        sys.exit(0)

    print("\nStep 4/4: Validating knowledge base consistency...")
    report = kb.validate()
    residual = report.get("residual", 0)
    n_violations = len(report.get("violations", []))
    n_shadows = len(report.get("shadow_fields", []))

    if residual > 0:
        print(f"  Residual: {residual:.4f} ({n_violations} violation(s), "
              f"{n_shadows} shadow field(s))")
    else:
        print("  Knowledge base is internally consistent.")

    stats = kb.stats
    print(f"\nKB ready: {stats['tokens']} tokens, {stats['edges']} edges, "
          f"{stats['modules']} modules")
    sys.exit(0)


if __name__ == "__main__":
    print("Use one of: forgeds-kb-init, forgeds-kb-scrape, forgeds-kb-parse, "
          "forgeds-kb-build, forgeds-kb-validate, forgeds-kb-query")
