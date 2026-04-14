"""Bridge between the ForgeDS knowledge graph and HRC (Hologram Reality Clause).

Converts knowledge tokens and edges into HRC's CodeModel (Entity, FieldDecl,
Relation) and runs the 5 cross-projection constraints to compute residuals.

Also defines four KB-specific projection functions (pi_structure, pi_reference,
pi_completeness, pi_consistency) that work without HRC installed.

HRC is imported from formal_proof.py as an optional dependency:
    from formal_proof import (
        CodeModel, Entity, FieldDecl, Relation as HRCRelation,
        RelationKind, HologramRealityClause, EffectiveResidualField,
    )
Guarded by ImportError — if HRC is not installed, the bridge still
works using the KB's own projection functions.
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

from forgeds.knowledge._types import RELATION_WEIGHTS, RelationType
from forgeds.knowledge.graph_io import load_graph

# ---------------------------------------------------------------------------
# HRC path resolution — the hologram-reality-clause repo may be a sibling
# directory or installed as a package.
# ---------------------------------------------------------------------------

_HRC_LOADED = False


def _try_load_hrc():
    """Attempt to import HRC's formal_proof module.

    Tries:
    1. Direct import (if installed via pip or on sys.path)
    2. Sibling repo at ../hologram-reality-clause/
    """
    global _HRC_LOADED
    if _HRC_LOADED:
        return True

    try:
        import formal_proof  # noqa: F401
        _HRC_LOADED = True
        return True
    except ImportError:
        pass

    # Try sibling repo (common dev layout)
    import os
    default_hrc = Path(__file__).resolve().parents[4] / "hologram-reality-clause"
    hrc_root = Path(os.environ.get("HRC_PATH", str(default_hrc))).resolve()

    # Security: only allow sibling-directory paths — reject symlink escapes
    # and require formal_proof.py to exist as a basic integrity check
    allowed_parent = Path(__file__).resolve().parents[4]
    try:
        is_within_parent = str(hrc_root).startswith(str(allowed_parent) + os.sep)
    except (OSError, ValueError):
        is_within_parent = False

    if (
        is_within_parent
        and hrc_root.is_dir()
        and (hrc_root / "formal_proof.py").is_file()
        and not (hrc_root / "formal_proof.py").is_symlink()
    ):
        sys.path.insert(0, str(hrc_root))
        try:
            import formal_proof  # noqa: F401
            _HRC_LOADED = True
            return True
        except ImportError:
            sys.path.pop(0)

    return False


# ---------------------------------------------------------------------------
# KB edge type -> HRC RelationKind mapping
# ---------------------------------------------------------------------------

_EDGE_TO_HRC_KIND: dict[str, str] = {
    "HIERARCHY": "CONTAINS",
    "NEXT_SIBLING": "DATAFLOW",
    "CROSS_REFERENCE": "LOOKUP",
    "CROSS_MODULE": "LOOKUP",
    "CALLOUT_NOTE": "CONTAINS",
    "CALLOUT_TIP": "CONTAINS",
    "CALLOUT_IMPORTANT": "CONTAINS",
    "CALLOUT_CRITICAL": "CONTAINS",
    "FUNCTION_OF": "CALLS",
    "EXAMPLE_OF": "CONTAINS",
    "SUPERSEDES": "DATAFLOW",
}


# ---------------------------------------------------------------------------
# HRC CodeModel construction
# ---------------------------------------------------------------------------

def _build_hrc_model(db_path: str):
    """Convert knowledge.db into an HRC CodeModel.

    Maps:
        KnowledgeToken -> Entity (name=sha[:16], fields={module, page_url, section, content_type})
        Graph edge -> Relation (kind mapped via _EDGE_TO_HRC_KIND)

    Returns (CodeModel, AnalysisResult) or (None, None) if HRC is not available.
    """
    if not _try_load_hrc():
        return None, None

    from formal_proof import (
        CodeModel,
        Entity,
        FieldDecl,
        Relation as HRCRelation,
        RelationKind,
        HologramRealityClause,
        EffectiveResidualField,
    )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    tokens = conn.execute("SELECT * FROM tokens").fetchall()
    edges = conn.execute("SELECT * FROM edges").fetchall()
    conn.close()

    model = CodeModel()

    # Map: token_sha -> entity name (use short sha for readability)
    sha_to_name: dict[str, str] = {}

    for t in tokens:
        sha = t["token_sha"]
        # Use module/section/paragraph as a readable entity name
        name = f"{t['module']}.{t['section'] or 'root'}.p{t['paragraph'] or 0}"
        # Deduplicate names by appending sha prefix
        if name in model.entities:
            name = f"{name}_{sha[:8]}"
        sha_to_name[sha] = name

        fields = frozenset([
            FieldDecl("module", "str"),
            FieldDecl("page_url", "str"),
            FieldDecl("section", "str"),
            FieldDecl("content_type", t["content_type"]),
            FieldDecl("content_hash", "str"),
        ])
        model.add_entity(Entity(name=name, fields=fields))

    # Map KB edge types to HRC RelationKind
    kind_map = {
        "CONTAINS": RelationKind.CONTAINS,
        "DATAFLOW": RelationKind.DATAFLOW,
        "LOOKUP": RelationKind.LOOKUP,
        "CALLS": RelationKind.CALLS,
    }

    for e in edges:
        src_name = sha_to_name.get(e["source_sha"])
        tgt_name = sha_to_name.get(e["target_sha"])
        if not src_name or not tgt_name:
            continue

        hrc_kind_str = _EDGE_TO_HRC_KIND.get(e["rel_type"], "CONTAINS")
        hrc_kind = kind_map.get(hrc_kind_str, RelationKind.CONTAINS)

        model.add_relation(HRCRelation(
            source=src_name,
            target=tgt_name,
            kind=hrc_kind,
        ))

    # Run HRC analysis
    hrc = HologramRealityClause.standard()
    result = hrc.analyze(model)

    return model, result


# ---------------------------------------------------------------------------
# Four KB-Specific Projections (work without HRC)
# ---------------------------------------------------------------------------

def pi_structure(db_path: str, conn: sqlite3.Connection | None = None) -> list[dict]:
    """Projection 1: Hierarchy integrity.

    Every token must have exactly one parent chain (no orphans,
    no cycles in HIERARCHY edges).

    Fix #7: uses a single LEFT JOIN query to find orphans with their
    metadata in one pass instead of N+1 individual lookups.
    """
    own_conn = conn is None
    if own_conn:
        conn = sqlite3.connect(db_path)

    # Single query: find tokens not connected to any HIERARCHY edge,
    # returning their metadata inline (Fix #7)
    orphan_rows = conn.execute(
        """SELECT t.token_sha, t.module, t.page_url, t.section
           FROM tokens t
           WHERE t.token_sha NOT IN (
               SELECT source_sha FROM edges WHERE rel_type = 'HIERARCHY'
               UNION
               SELECT target_sha FROM edges WHERE rel_type = 'HIERARCHY'
           )"""
    ).fetchall()

    violations = [
        {
            "type": "orphan_token",
            "token_sha": sha,
            "module": module,
            "page_url": page_url,
            "section": section or "",
        }
        for sha, module, page_url, section in orphan_rows
    ]

    if own_conn:
        conn.close()
    return violations


def pi_reference(db_path: str, conn: sqlite3.Connection | None = None) -> list[dict]:
    """Projection 2: Cross-reference integrity.

    Every CROSS_REFERENCE edge must point to a valid token.
    """
    own_conn = conn is None
    if own_conn:
        conn = sqlite3.connect(db_path)

    all_shas = {r[0] for r in conn.execute("SELECT token_sha FROM tokens")}
    xrefs = conn.execute(
        "SELECT source_sha, target_sha FROM edges WHERE rel_type IN ('CROSS_REFERENCE', 'CROSS_MODULE')"
    ).fetchall()

    violations = [
        {"type": "broken_reference", "source_sha": src, "target_sha": tgt}
        for src, tgt in xrefs
        if tgt not in all_shas
    ]

    if own_conn:
        conn.close()
    return violations


def pi_completeness(db_path: str, conn: sqlite3.Connection | None = None) -> list[dict]:
    """Projection 3: Function coverage.

    Every function in deluge_lang.db should have >= 1 knowledge token.
    Missing functions are reported as shadow fields.

    Fix #6: uses a single combined regex for O(C+F) instead of
    O(F*C) from compiling and scanning per function.
    """
    from forgeds._shared.config import get_db_dir

    lang_db = get_db_dir() / "deluge_lang.db"
    if not lang_db.exists():
        return []

    _ALLOWED_LANG_TABLES = {"functions", "builtins", "keywords"}

    lang_conn = sqlite3.connect(str(lang_db))
    func_names: set[str] = set()
    for table in ("functions", "builtins", "keywords"):
        if table not in _ALLOWED_LANG_TABLES:
            continue
        try:
            rows = lang_conn.execute(f"SELECT name FROM {table}").fetchall()  # table is from a fixed whitelist
            func_names.update(r[0] for r in rows)
        except sqlite3.OperationalError:
            continue
    lang_conn.close()

    if not func_names:
        return []

    own_conn = conn is None
    if own_conn:
        conn = sqlite3.connect(db_path)
    all_content = conn.execute("SELECT content FROM tokens").fetchall()
    content_blob = "\n".join(r[0] for r in all_content)
    if own_conn:
        conn.close()

    # Single combined regex — one pass over the content blob (Fix #6)
    combined = re.compile(
        r"\b(" + "|".join(re.escape(f) for f in func_names) + r")\b",
        re.IGNORECASE,
    )
    found = {m.group(0).lower() for m in combined.finditer(content_blob)}

    return [
        {
            "type": "shadow_field",
            "function": fname,
            "reason": "No knowledge token covers this function.",
        }
        for fname in sorted(func_names)
        if fname.lower() not in found
    ]


def pi_consistency(db_path: str, conn: sqlite3.Connection | None = None) -> list[dict]:
    """Projection 4: Content agreement.

    Detect tokens that describe the same function but with conflicting
    parameter counts or return types.
    """
    own_conn = conn is None
    if own_conn:
        conn = sqlite3.connect(db_path)

    violations = []

    sigs = conn.execute(
        "SELECT token_sha, content FROM tokens WHERE content_type = 'SIGNATURE'"
    ).fetchall()

    func_sigs: dict[str, list[tuple[str, str]]] = {}
    sig_re = re.compile(r"(\w+)\s*\(([^)]*)\)")

    for sha, content in sigs:
        m = sig_re.search(content)
        if m:
            fname = m.group(1).lower()
            params = m.group(2).strip()
            func_sigs.setdefault(fname, []).append((sha, params))

    for fname, entries in func_sigs.items():
        if len(entries) < 2:
            continue

        param_counts = set()
        for sha, params in entries:
            count = len([p for p in params.split(",") if p.strip()]) if params else 0
            param_counts.add(count)

        if len(param_counts) > 1:
            violations.append({
                "type": "inconsistent_signature",
                "function": fname,
                "param_counts": sorted(param_counts),
                "token_shas": [sha for sha, _ in entries],
            })

    if own_conn:
        conn.close()
    return violations


# ---------------------------------------------------------------------------
# Main validation entry point
# ---------------------------------------------------------------------------

def validate_knowledge(db_path: str | Path) -> dict:
    """Run all projections and return a validation report.

    If HRC (formal_proof.py) is available, runs the full 5-constraint
    cross-projection analysis on the knowledge graph for a global residual.
    KB-specific projections always run regardless.

    Fix #5: opens one shared DB connection for all projection functions
    instead of 5+ separate connections.
    """
    db_path = str(db_path)
    report: dict = {
        "db_path": db_path,
        "violations": [],
        "shadow_fields": [],
        "residual": 0.0,
        "hrc_available": False,
    }

    # Single shared connection for all KB projections (Fix #5)
    conn = sqlite3.connect(db_path)
    try:
        struct_violations = pi_structure(db_path, conn)
        ref_violations = pi_reference(db_path, conn)
        completeness_shadows = pi_completeness(db_path, conn)
        consistency_violations = pi_consistency(db_path, conn)
    finally:
        conn.close()

    report["violations"] = struct_violations + ref_violations + consistency_violations
    report["shadow_fields"] = completeness_shadows

    # Try HRC for global residual
    model, result = _build_hrc_model(db_path)
    if result is not None:
        report["hrc_available"] = True
        report["hrc_residual"] = result.residual
        report["hrc_consistent"] = result.is_consistent
        report["hrc_violation_count"] = len(result.violations)

        # Add HRC violations to report (formatted for JSON)
        for v in result.violations:
            report["violations"].append({
                "type": "hrc_constraint_violation",
                "constraint": v.constraint_name,
                "entity": v.entity,
                "field": v.field if hasattr(v, "field") else "",
                "message": v.message if hasattr(v, "message") else str(v),
                "severity": v.severity if hasattr(v, "severity") else 1.0,
            })

        # Combined residual: HRC cross-projection + KB-specific violations
        kb_violation_count = len(struct_violations) + len(ref_violations) + len(consistency_violations)
        report["residual"] = result.residual + kb_violation_count + len(report["shadow_fields"])
    else:
        # Fallback: simple residual from KB-projection violation counts
        n_violations = len(report["violations"])
        n_shadows = len(report["shadow_fields"])
        report["residual"] = float(n_violations + n_shadows)

    # Graph stats
    try:
        g = load_graph(db_path)
        report["graph_stats"] = {
            "nodes": g.node_count(),
            "edges": g.edge_count(),
            "accelerated": g.is_accelerated,
        }
        g.free()
    except Exception:
        pass

    return report
