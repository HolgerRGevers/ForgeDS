"""Ingest Zoho Creator .ds application exports into the knowledge graph.

Parses .ds files using the existing DSParser, then creates knowledge
tokens via the Librarian for:
  - Application structure (forms, fields, relationships)
  - Blueprint definitions (stages, transitions, state machines)
  - Embedded Deluge scripts (workflows, scheduled tasks, approvals)
  - Cross-references to documentation tokens (function calls, API patterns)

The tokens go into the Reality Database (RB) alongside documentation
tokens, using module names like "app:Expense_Claim_Approval".

Usage:
    from forgeds.knowledge.app_ingest import ingest_ds_app
    stats = ingest_ds_app("path/to/App.ds", librarian_handle)

CLI:
    forgeds-kb-ingest path/to/App.ds [path/to/Other.ds ...]
"""

from __future__ import annotations

import re
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from forgeds.core.parse_ds_export import DSParser, FormDef, ScriptDef

if TYPE_CHECKING:
    from forgeds.knowledge.librarian_io import LibrarianHandle


# ---------------------------------------------------------------------------
# Token creation helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "unknown"


@dataclass
class IngestStats:
    """Statistics from a .ds ingest run."""
    app_name: str
    module: str
    forms: int = 0
    fields: int = 0
    scripts: int = 0
    blueprints: int = 0
    transitions: int = 0
    tokens_created: int = 0
    edges_created: int = 0


# ---------------------------------------------------------------------------
# Blueprint parser (extends DSParser)
# ---------------------------------------------------------------------------

@dataclass
class BlueprintStage:
    name: str


@dataclass
class BlueprintTransition:
    name: str
    display_name: str
    from_stage: str
    to_stage: str
    transition_type: str  # "normal", "conditional", etc.


@dataclass
class BlueprintDef:
    name: str
    display_name: str
    form: str
    stages: list[BlueprintStage]
    transitions: list[BlueprintTransition]


def _parse_blueprints(content: str) -> list[BlueprintDef]:
    """Extract Blueprint definitions from a .ds file."""
    blueprints: list[BlueprintDef] = []
    lines = content.splitlines()
    i = 0

    while i < len(lines):
        stripped = lines[i].strip()

        # Match: name as "Display Name" inside a blueprint block
        bm = re.match(r'(\w+)\s+as\s+"([^"]*)"', stripped)
        if bm and i + 1 < len(lines):
            # Check if this is a Blueprint (look for type = Blueprint nearby)
            name = bm.group(1)
            display = bm.group(2)
            form_name = ""
            stages: list[BlueprintStage] = []
            transitions: list[BlueprintTransition] = []
            is_blueprint = False

            j = i + 1
            brace_depth = 0
            in_block = False
            in_stages = False
            in_transitions = False

            while j < len(lines):
                line = lines[j].strip()

                if "{" in line:
                    brace_depth += line.count("{")
                    in_block = True
                if "}" in line:
                    brace_depth -= line.count("}")
                    if in_block and brace_depth <= 0:
                        break

                if line == "type = Blueprint":
                    is_blueprint = True

                fm = re.match(r"form\s*=\s*(\w+)", line)
                if fm:
                    form_name = fm.group(1)

                # Detect stages block
                if line == "stages":
                    in_stages = True
                    in_transitions = False
                elif line == "transitions":
                    in_transitions = True
                    in_stages = False

                # Parse stage names (quoted strings inside stages block)
                if in_stages and not in_transitions:
                    sm = re.match(r'"([^"]+)"', line)
                    if sm:
                        stages.append(BlueprintStage(name=sm.group(1)))

                # Parse transitions
                if in_transitions:
                    tm = re.match(r'(\w+)\s+as\s+"([^"]*)"', line)
                    if tm:
                        t_name = tm.group(1)
                        t_display = tm.group(2)
                        t_type = "normal"
                        t_from = ""
                        t_to = ""
                        # Look ahead for from/to stage
                        k = j + 1
                        while k < len(lines) and k < j + 10:
                            tl = lines[k].strip()
                            tfm = re.match(r'from stage\s*=\s*"([^"]*)"', tl)
                            if tfm:
                                t_from = tfm.group(1)
                            ttm = re.match(r'to stage\s*=\s*"([^"]*)"', tl)
                            if ttm:
                                t_to = ttm.group(1)
                            typ = re.match(r'type\s*=\s*(\w+)', tl)
                            if typ:
                                t_type = typ.group(1)
                            k += 1
                        if t_from and t_to:
                            transitions.append(BlueprintTransition(
                                name=t_name, display_name=t_display,
                                from_stage=t_from, to_stage=t_to,
                                transition_type=t_type,
                            ))

                j += 1

            if is_blueprint and form_name:
                blueprints.append(BlueprintDef(
                    name=name, display_name=display, form=form_name,
                    stages=stages, transitions=transitions,
                ))
        i += 1

    return blueprints


# ---------------------------------------------------------------------------
# Token generators
# ---------------------------------------------------------------------------

def _make_app_overview_token(
    app_name: str, module: str, forms: list[FormDef],
    blueprints: list[BlueprintDef], scripts: list[ScriptDef],
    ds_path: str,
) -> dict:
    """Create an overview token summarising the entire application."""
    lines = [f"# {app_name}", ""]
    lines.append(f"Zoho Creator application with {len(forms)} form(s), "
                 f"{len(blueprints)} blueprint(s), {len(scripts)} script(s).")
    lines.append("")

    if forms:
        lines.append("## Forms")
        for form in forms:
            lines.append(f"- **{form.display_name}** (`{form.name}`): "
                         f"{len(form.fields)} fields")
    if blueprints:
        lines.append("")
        lines.append("## Blueprints")
        for bp in blueprints:
            lines.append(f"- **{bp.display_name}** on `{bp.form}`: "
                         f"{len(bp.stages)} stages, {len(bp.transitions)} transitions")
    if scripts:
        lines.append("")
        lines.append("## Scripts")
        for s in scripts:
            lines.append(f"- [{s.context}] **{s.display_name}** "
                         f"(`{s.form}` > {s.event})")

    content = "\n".join(lines)
    page_url = f"app://{module}/overview"
    return {
        "token_sha": "",  # Librarian computes SHA
        "content": content,
        "content_type": "PROSE",
        "module": module,
        "page_url": page_url,
        "page_title": app_name,
        "section": "Overview",
        "paragraph": 0,
        "source_md": ds_path,
    }


def _make_form_tokens(
    form: FormDef, module: str, ds_path: str, para_offset: int,
) -> list[dict]:
    """Create tokens for a form: schema overview + field table."""
    tokens: list[dict] = []
    page_url = f"app://{module}/forms/{form.name}"

    # Form overview
    lines = [f"## {form.display_name} (`{form.name}`)", ""]
    lines.append(f"Form with {len(form.fields)} field(s).")
    lines.append("")
    lines.append("| Link Name | Display Name | Type | Notes |")
    lines.append("|-----------|-------------|------|-------|")
    for f in form.fields:
        lines.append(f"| `{f.link_name}` | {f.display_name} | {f.field_type} | {f.notes or ''} |")

    content = "\n".join(lines)
    tokens.append({
        "token_sha": "",  # Librarian computes SHA
        "content": content,
        "content_type": "TABLE_ROW",
        "module": module,
        "page_url": page_url,
        "page_title": f"{form.display_name} — Schema",
        "section": "Fields",
        "paragraph": para_offset,
        "source_md": ds_path,
    })

    return tokens


def _make_blueprint_tokens(
    bp: BlueprintDef, module: str, ds_path: str, para_offset: int,
) -> list[dict]:
    """Create tokens for a Blueprint: state machine diagram + transitions."""
    tokens: list[dict] = []
    page_url = f"app://{module}/blueprints/{bp.name}"

    # State machine overview
    lines = [f"## Blueprint: {bp.display_name}", ""]
    lines.append(f"State machine on form `{bp.form}` with "
                 f"{len(bp.stages)} stages and {len(bp.transitions)} transitions.")
    lines.append("")

    # Stages
    lines.append("### Stages")
    for stage in bp.stages:
        lines.append(f"- {stage.name}")
    lines.append("")

    # Transitions as a table
    lines.append("### Transitions")
    lines.append("| Transition | From | To |")
    lines.append("|-----------|------|-----|")
    for t in bp.transitions:
        lines.append(f"| {t.display_name} (`{t.name}`) | {t.from_stage} | {t.to_stage} |")

    # Mermaid state diagram
    lines.append("")
    lines.append("### State Diagram")
    lines.append("```mermaid")
    lines.append("stateDiagram-v2")
    for t in bp.transitions:
        safe_from = t.from_stage.replace(" ", "_")
        safe_to = t.to_stage.replace(" ", "_")
        lines.append(f"    {safe_from} --> {safe_to}: {t.display_name}")
    lines.append("```")

    content = "\n".join(lines)
    tokens.append({
        "token_sha": "",  # Librarian computes SHA
        "content": content,
        "content_type": "PROSE",
        "module": module,
        "page_url": page_url,
        "page_title": f"Blueprint: {bp.display_name}",
        "section": "State Machine",
        "paragraph": para_offset,
        "source_md": ds_path,
    })

    return tokens


def _make_script_tokens(
    script: ScriptDef, module: str, ds_path: str, para_offset: int,
) -> list[dict]:
    """Create tokens for an embedded Deluge script."""
    tokens: list[dict] = []
    page_url = f"app://{module}/scripts/{script.name}"

    # Script metadata
    meta = (f"**{script.display_name}**\n\n"
            f"- **Form:** `{script.form}`\n"
            f"- **Trigger:** {script.trigger}\n"
            f"- **Event:** {script.event}\n"
            f"- **Context:** {script.context}")
    tokens.append({
        "token_sha": "",  # Librarian computes SHA
        "content": meta,
        "content_type": "PROSE",
        "module": module,
        "page_url": page_url,
        "page_title": script.display_name,
        "section": "Metadata",
        "paragraph": para_offset,
        "source_md": ds_path,
    })

    # Script code
    code_content = f"```deluge\n{script.code}\n```"
    tokens.append({
        "token_sha": "",  # Librarian computes SHA
        "content": code_content,
        "content_type": "CODE_EXAMPLE",
        "module": module,
        "page_url": page_url,
        "page_title": script.display_name,
        "section": "Code",
        "paragraph": para_offset + 1,
        "source_md": ds_path,
    })

    return tokens


# ---------------------------------------------------------------------------
# Edge generators
# ---------------------------------------------------------------------------

def _build_app_edges(tokens: list[dict], module: str) -> list[tuple]:
    """Build graph edges between app tokens.

    Creates:
    - HIERARCHY: overview → forms/blueprints/scripts
    - NEXT_SIBLING: between forms, between transitions
    - EXAMPLE_OF: script code → script metadata
    """
    edges: list[tuple] = []
    by_page: dict[str, list[dict]] = {}
    overview_sha = None

    for t in tokens:
        page = t["page_url"]
        by_page.setdefault(page, []).append(t)
        if page.endswith("/overview"):
            overview_sha = t["token_sha"]

    # HIERARCHY: overview → all other tokens
    if overview_sha:
        for t in tokens:
            if t["token_sha"] != overview_sha:
                edges.append((overview_sha, t["token_sha"], "HIERARCHY", 1.0))

    # Within each page: NEXT_SIBLING and EXAMPLE_OF
    for page_url, page_tokens in by_page.items():
        sorted_tokens = sorted(page_tokens, key=lambda t: t["paragraph"])
        for i in range(len(sorted_tokens) - 1):
            a = sorted_tokens[i]
            b = sorted_tokens[i + 1]
            edges.append((a["token_sha"], b["token_sha"], "NEXT_SIBLING", 0.3))
            # Code follows metadata → EXAMPLE_OF
            if (a["content_type"] == "PROSE" and
                    b["content_type"] == "CODE_EXAMPLE"):
                edges.append((a["token_sha"], b["token_sha"], "EXAMPLE_OF", 0.6))

    return edges


# ---------------------------------------------------------------------------
# Cross-reference: link app tokens to documentation tokens
# ---------------------------------------------------------------------------

def _build_cross_references(
    app_tokens: list[dict], conn: sqlite3.Connection, module: str,
) -> list[tuple]:
    """Find Deluge function calls in app code and link to documentation.

    Scans CODE_EXAMPLE tokens for known function names (from the
    deluge-functions and deluge-integrations modules) and creates
    CROSS_MODULE edges.
    """
    edges: list[tuple] = []

    # Get all documentation token SHAs indexed by content keywords
    doc_tokens = conn.execute(
        """SELECT token_sha, content, module, page_url
           FROM tokens
           WHERE module IN ('deluge-functions', 'deluge-integrations',
                            'deluge-core', 'deluge-web')
             AND content_type = 'PROSE'
           LIMIT 5000"""
    ).fetchall()

    # Build a simple function name → doc token SHA map
    # Look for page titles that match function patterns
    func_map: dict[str, str] = {}
    for sha, content, mod, url in doc_tokens:
        # Extract function-like names from page URLs
        # e.g., ".../getPrefix.html" → "getPrefix"
        if ".html" in url:
            fname = url.rsplit("/", 1)[-1].replace(".html", "")
            if fname and not fname.startswith("v2"):
                func_map[fname.lower()] = sha

    # Scan app code tokens for function calls
    for t in app_tokens:
        if t["content_type"] != "CODE_EXAMPLE":
            continue
        code = t["content"].lower()
        for func_name, doc_sha in func_map.items():
            if func_name in code and len(func_name) > 3:
                edges.append((
                    t["token_sha"], doc_sha,
                    "CROSS_MODULE", 0.9,
                ))

    return edges


# ---------------------------------------------------------------------------
# Main ingest function
# ---------------------------------------------------------------------------

def ingest_ds_app(
    ds_path: str | Path,
    librarian: LibrarianHandle,
) -> IngestStats:
    """Ingest a single .ds application export via the Librarian.

    Parses the .ds file, creates tokens and edges through the Librarian
    (sole authority for token lifecycle), and inserts metadata into the
    Reality Database alongside documentation tokens.
    """
    from forgeds.knowledge.librarian_io import LIB_RB, LibrarianError

    ds_path = Path(ds_path)

    # Read and parse .ds
    content = ds_path.read_text(encoding="utf-8")
    parser = DSParser(content)
    parser.parse()

    app_name_match = re.search(r'application\s+"([^"]+)"', content)
    app_name = app_name_match.group(1) if app_name_match else ds_path.stem
    module = f"app:{ds_path.stem}"

    blueprints = _parse_blueprints(content)

    # Generate token dicts (SHAs will be computed by Librarian)
    now = _now_iso()
    git = _git_sha()
    all_tokens: list[dict] = []
    para = 0

    overview = _make_app_overview_token(
        app_name, module, parser.forms, blueprints, parser.scripts,
        str(ds_path),
    )
    overview.update({"created_at": now, "updated_at": now, "git_sha": git, "revision": 1})
    all_tokens.append(overview)
    para += 1

    for form in parser.forms:
        form_tokens = _make_form_tokens(form, module, str(ds_path), para)
        for t in form_tokens:
            t.update({"created_at": now, "updated_at": now, "git_sha": git, "revision": 1})
        all_tokens.extend(form_tokens)
        para += len(form_tokens)

    for bp in blueprints:
        bp_tokens = _make_blueprint_tokens(bp, module, str(ds_path), para)
        for t in bp_tokens:
            t.update({"created_at": now, "updated_at": now, "git_sha": git, "revision": 1})
        all_tokens.extend(bp_tokens)
        para += len(bp_tokens)

    for script in parser.scripts:
        script_tokens = _make_script_tokens(script, module, str(ds_path), para)
        for t in script_tokens:
            t.update({"created_at": now, "updated_at": now, "git_sha": git, "revision": 1})
        all_tokens.extend(script_tokens)
        para += len(script_tokens)

    # Clear previous ingest of this module via writable RB connection
    conn = librarian.rb_metadata_conn
    conn.execute("DELETE FROM edges WHERE source_sha IN "
                 "(SELECT token_sha FROM tokens WHERE module = ?)", (module,))
    conn.execute("DELETE FROM edges WHERE target_sha IN "
                 "(SELECT token_sha FROM tokens WHERE module = ?)", (module,))
    # Destroy existing tokens for this module via Librarian
    existing_shas = [r[0] for r in conn.execute(
        "SELECT token_sha FROM tokens WHERE module = ?", (module,)
    ).fetchall()]
    for sha in existing_shas:
        try:
            librarian.destroy(sha)
        except LibrarianError:
            pass

    conn.execute("DELETE FROM pages WHERE module = ?", (module,))
    conn.execute("DELETE FROM modules WHERE name = ?", (module,))

    # Insert module metadata
    page_urls = set(t["page_url"] for t in all_tokens)
    conn.execute(
        "INSERT INTO modules (name, base_url, page_count) VALUES (?, ?, ?)",
        (module, f"app://{module}", len(page_urls)),
    )

    for url in page_urls:
        title = next(t["page_title"] for t in all_tokens if t["page_url"] == url)
        conn.execute(
            "INSERT INTO pages (url, title, module, md_path, scraped_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (url, title, module, str(ds_path), now),
        )
    conn.commit()

    # Create tokens via Librarian (sole authority)
    created_count = 0
    for t in all_tokens:
        try:
            sha = librarian.create(
                db=LIB_RB,
                content=t["content"],
                page_url=t["page_url"],
                paragraph_num=t["paragraph"],
                module=t["module"],
                content_type=t["content_type"],
                weight=1.0,
                metadata={
                    "page_title": t["page_title"],
                    "section": t["section"],
                    "page_updated": now,
                    "created_at": t["created_at"],
                    "updated_at": t["updated_at"],
                    "git_sha": t["git_sha"],
                    "source_md": t["source_md"],
                },
            )
            t["token_sha"] = sha  # Update dict with Librarian-assigned SHA
            created_count += 1
        except LibrarianError:
            pass  # SHA collision — skip

    # Build edges (only between tokens that have SHAs)
    tokens_with_sha = [t for t in all_tokens if t["token_sha"]]
    app_edges = _build_app_edges(tokens_with_sha, module)

    edge_count = 0
    for src, tgt, rel, weight in app_edges:
        try:
            librarian.create_edge(src, tgt, rel, weight)
            edge_count += 1
        except LibrarianError:
            pass

    # Build cross-references to documentation
    xref_edges = _build_cross_references(tokens_with_sha, conn, module)
    for src, tgt, rel, weight in xref_edges:
        try:
            librarian.create_edge(src, tgt, rel, weight)
            edge_count += 1
        except LibrarianError:
            pass

    return IngestStats(
        app_name=app_name,
        module=module,
        forms=len(parser.forms),
        fields=sum(len(f.fields) for f in parser.forms),
        scripts=len(parser.scripts),
        blueprints=len(blueprints),
        transitions=sum(len(bp.transitions) for bp in blueprints),
        tokens_created=created_count,
        edges_created=edge_count,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def ingest_main() -> None:
    """CLI for .ds app ingestion — wired to forgeds-kb-ingest."""
    import argparse
    import sys

    from forgeds.knowledge.cli import _db_path
    from forgeds.knowledge.librarian_io import open_librarian

    parser = argparse.ArgumentParser(
        prog="forgeds-kb-ingest",
        description="Ingest Zoho Creator .ds exports into the knowledge graph.",
    )
    parser.add_argument(
        "ds_files", nargs="+",
        help="Path(s) to .ds export file(s).",
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Output stats as JSON.",
    )
    args = parser.parse_args()

    db_path = _db_path()
    rb_path = db_path.parent / "reality.db"
    hb_path = db_path.parent / "holographic.db"

    lib = open_librarian(rb_path, hb_path)

    all_stats: list[IngestStats] = []
    for ds_file in args.ds_files:
        path = Path(ds_file)
        if not path.exists():
            print(f"File not found: {ds_file}", file=sys.stderr)
            continue

        stats = ingest_ds_app(path, lib)
        all_stats.append(stats)

        if not args.as_json:
            print(f"\nIngested: {stats.app_name} ({stats.module})")
            print(f"  Forms:       {stats.forms}")
            print(f"  Fields:      {stats.fields}")
            print(f"  Scripts:     {stats.scripts}")
            print(f"  Blueprints:  {stats.blueprints}")
            print(f"  Transitions: {stats.transitions}")
            print(f"  Tokens:      {stats.tokens_created}")
            print(f"  Edges:       {stats.edges_created}")

    if args.as_json:
        import json
        print(json.dumps([{
            "app_name": s.app_name, "module": s.module,
            "forms": s.forms, "fields": s.fields,
            "scripts": s.scripts, "blueprints": s.blueprints,
            "transitions": s.transitions,
            "tokens": s.tokens_created, "edges": s.edges_created,
        } for s in all_stats], indent=2))

    total_tokens = sum(s.tokens_created for s in all_stats)
    total_edges = sum(s.edges_created for s in all_stats)
    print(f"\nTotal: {len(all_stats)} app(s), {total_tokens} tokens, {total_edges} edges")
    sys.exit(0)
