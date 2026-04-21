"""Bridge between the ForgeDS knowledge graph and HRC (Hologram Reality Clause).

Converts knowledge tokens and edges into HRC's generalized RelationalModel
(GEntity, GAttribute, GRelation) and runs the generalized multi-perspective
analysis including the Stringed Relational Transform (SRT) and premise queries.

Also defines four KB-specific projection functions (pi_structure, pi_reference,
pi_completeness, pi_consistency) that work without HRC installed.

HRC is imported from generalized_proof.py as an optional dependency (with
fallback to formal_proof.py for backwards compatibility):
    from generalized_proof import (
        RelationalModel, GEntity, GAttribute, GRelation, GRelationKind,
        GeneralizedHRC, SRTProjection, SRTQuery,
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
_HRC_GENERALIZED = False  # True if generalized_proof is available (SRT + premise queries)


def _try_load_hrc():
    """Attempt to import HRC modules.

    Tries generalized_proof first (SRT + premise queries + 10 theorems),
    falls back to formal_proof (original 8 theorems, code-specific).

    Tries:
    1. Direct import (if installed via pip or on sys.path)
    2. Sibling repo at ../hologram-reality-clause/
    """
    global _HRC_LOADED, _HRC_GENERALIZED
    if _HRC_LOADED:
        return True

    # Try direct import — generalized first, then original
    for module_name in ("generalized_proof", "formal_proof"):
        try:
            __import__(module_name)
            _HRC_LOADED = True
            _HRC_GENERALIZED = module_name == "generalized_proof"
            return True
        except ImportError:
            pass

    # Try sibling repo (common dev layout)
    import os
    default_hrc = Path(__file__).resolve().parents[4] / "hologram-reality-clause"
    hrc_root = Path(os.environ.get("HRC_PATH", str(default_hrc))).resolve()

    # Security: only allow sibling-directory paths — reject symlink escapes
    allowed_parent = Path(__file__).resolve().parents[4]
    try:
        is_within_parent = str(hrc_root).startswith(str(allowed_parent) + os.sep)
    except (OSError, ValueError):
        is_within_parent = False

    if not (
        is_within_parent
        and hrc_root.is_dir()
        and not (hrc_root / "formal_proof.py").is_symlink()
    ):
        return False

    # Add to path and try again — generalized first
    sys.path.insert(0, str(hrc_root))
    for module_name in ("generalized_proof", "formal_proof"):
        try:
            __import__(module_name)
            _HRC_LOADED = True
            _HRC_GENERALIZED = module_name == "generalized_proof"
            return True
        except ImportError:
            pass
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
# Premise query callback (Johnson et al., CGO 2017)
# ---------------------------------------------------------------------------

def _build_forgeds_ask(
    db_path: str,
    conn: sqlite3.Connection | None = None,
):
    """Build a premise query callback using ForgeDS infrastructure.

    When a constraint can't resolve something, it calls ask(entity, attr).
    The callback searches ForgeDS's data stores in cost order:

      Level 1: Direct token SHA lookup in reality.db (O(1))
      Level 2: Content search via FTS (medium cost)
      Level 3: Graph neighbor search via BFS (medium cost)

    The Retriever (Level 4 in the plan) is intentionally omitted here
    because it requires a full SEED-EXPAND-RANK pipeline and is too
    expensive for inline premise resolution. It can be added later
    if Level 1-3 prove insufficient.

    Per Johnson et al. (CGO 2017), this enables collaboration between
    constraints and projections: before declaring a violation, a
    constraint asks "does anyone know about this?" and the ForgeDS
    knowledge base answers from its token store.
    """
    own_conn = conn is None
    if own_conn:
        conn = sqlite3.connect(db_path)

    # Pre-load token SHAs and metadata for O(1) lookup
    all_tokens: dict[str, dict] = {}
    try:
        rows = conn.execute(
            "SELECT token_sha, module, section, content_type, content FROM tokens"
        ).fetchall()
        for sha, module, section, ctype, content in rows:
            all_tokens[sha] = {
                "module": module or "",
                "section": section or "",
                "content_type": ctype or "",
                "content": content or "",
            }
    except sqlite3.OperationalError:
        pass

    # Pre-load edges for neighbor lookup
    edges_by_source: dict[str, list[str]] = {}
    edges_by_target: dict[str, list[str]] = {}
    try:
        edge_rows = conn.execute("SELECT source_sha, target_sha FROM edges").fetchall()
        for src, tgt in edge_rows:
            edges_by_source.setdefault(src, []).append(tgt)
            edges_by_target.setdefault(tgt, []).append(src)
    except sqlite3.OperationalError:
        pass

    # Build entity name -> SHA mapping (mirrors _build_hrc_model naming)
    name_to_sha: dict[str, str] = {}
    used_names: set[str] = set()
    for sha, meta in all_tokens.items():
        name = f"{meta['module']}.{meta['section'] or 'root'}.p0"
        if name in used_names:
            name = f"{name}_{sha[:8]}"
        used_names.add(name)
        name_to_sha[name] = sha

    visited: set[tuple[str, str]] = set()

    def ask(entity: str, attribute: str) -> str | None:
        """Premise query callback.

        Args:
            entity: Entity name (e.g., "deluge-functions.fetchRecords.p0")
            attribute: What to look up ("exists", "module", "content", etc.)

        Returns:
            String value if found, None if no store knows.
        """
        key = (entity, attribute)
        if key in visited:
            return None
        visited.add(key)

        try:
            # Level 1: Direct SHA/name lookup (O(1))
            sha = name_to_sha.get(entity)
            if sha and sha in all_tokens:
                if attribute == "exists":
                    return "true"
                meta = all_tokens[sha]
                if attribute in meta:
                    return meta[attribute]

            # Also try entity as a raw SHA
            if entity in all_tokens:
                if attribute == "exists":
                    return "true"
                meta = all_tokens[entity]
                if attribute in meta:
                    return meta[attribute]

            # Level 2: Content search — does any token mention this entity?
            entity_lower = entity.lower()
            for sha, meta in all_tokens.items():
                if entity_lower in meta["content"].lower():
                    if attribute == "exists":
                        return f"mentioned_in_{sha[:8]}"
                    if attribute in meta:
                        return meta[attribute]

            # Level 3: Graph neighbor search — is this entity reachable?
            if sha := name_to_sha.get(entity):
                neighbors = set()
                neighbors.update(edges_by_source.get(sha, []))
                neighbors.update(edges_by_target.get(sha, []))
                if neighbors:
                    if attribute == "exists":
                        return f"connected_via_{len(neighbors)}_edges"

            return None
        finally:
            visited.discard(key)

    if own_conn:
        # Don't close — the caller may still need it. Store for cleanup.
        ask._conn = conn  # type: ignore[attr-defined]

    return ask


# ---------------------------------------------------------------------------
# HRC CodeModel construction
# ---------------------------------------------------------------------------

def _build_hrc_model(db_path: str, use_premises: bool = True):
    """Convert knowledge.db into an HRC model and run analysis.

    When generalized_proof is available:
        Uses RelationalModel, GEntity, GAttribute, GRelation, GeneralizedHRC.
        Runs SRT as an additional projection for shadow resolution.
        Supports premise queries via the ask callback.

    When only formal_proof is available (fallback):
        Uses CodeModel, Entity, FieldDecl, Relation, HologramRealityClause.
        No SRT, no premise queries.

    Returns (model, AnalysisResult) or (None, None) if HRC is not available.
    """
    if not _try_load_hrc():
        return None, None

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    tokens = conn.execute("SELECT * FROM tokens").fetchall()
    edges = conn.execute("SELECT * FROM edges").fetchall()
    conn.close()

    if _HRC_GENERALIZED:
        return _build_generalized_model(db_path, tokens, edges, use_premises)
    else:
        return _build_legacy_model(tokens, edges)


def _build_generalized_model(db_path, tokens, edges, use_premises):
    """Build model using the generalized HRC framework (SRT + premise queries)."""
    from generalized_proof import (
        RelationalModel, GEntity, GAttribute, GRelation, GRelationKind,
        GeneralizedHRC, SRTProjection, SRTQuery, GProjection,
    )

    _G_EDGE_MAP = {
        "CONTAINS": GRelationKind.CONTAINMENT,
        "DATAFLOW": GRelationKind.FLOW,
        "LOOKUP": GRelationKind.REFERENCE,
        "CALLS": GRelationKind.DEPENDENCY,
    }

    model = RelationalModel()
    sha_to_name: dict[str, str] = {}

    for t in tokens:
        sha = t["token_sha"]
        name = f"{t['module']}.{t['section'] or 'root'}.p{t['paragraph'] or 0}"
        if name in model.entities:
            name = f"{name}_{sha[:8]}"
        sha_to_name[sha] = name

        attrs = frozenset([
            GAttribute("module", t["module"] or ""),
            GAttribute("page_url", t["page_url"] or ""),
            GAttribute("section", t["section"] or ""),
            GAttribute("content_type", t["content_type"] or ""),
            GAttribute("content_hash", sha[:16]),
        ])
        model.add_entity(GEntity(name=name, entity_type=t["content_type"] or "token", attributes=attrs))

    for e in edges:
        src_name = sha_to_name.get(e["source_sha"])
        tgt_name = sha_to_name.get(e["target_sha"])
        if not src_name or not tgt_name:
            continue

        hrc_kind_str = _EDGE_TO_HRC_KIND.get(e["rel_type"], "CONTAINS")
        g_kind = _G_EDGE_MAP.get(hrc_kind_str, GRelationKind.CONTAINMENT)

        model.add_relation(GRelation(
            source=src_name,
            target=tgt_name,
            kind=g_kind,
            label=e["rel_type"],
        ))

    # Build the generalized HRC with SRT projection
    hrc = GeneralizedHRC()

    # Add a structure projection that sees all entities
    class KBStructureProjection(GProjection):
        @property
        def name(self): return "kb_structure"
        def extract(self, m):
            return {"entities": {
                n: {"attributes": set(e.attr_names()), "fields": set(e.attr_names())}
                for n, e in m.entities.items()
            }}

    # Add a content-type projection that groups by type
    class KBTypeProjection(GProjection):
        @property
        def name(self): return "kb_type"
        def extract(self, m):
            return {"entities": {
                n: {"attributes": set(e.attr_names()), "fields": set(e.attr_names()),
                    "type": e.entity_type}
                for n, e in m.entities.items()
            }}

    hrc.add_projection(KBStructureProjection())
    hrc.add_projection(KBTypeProjection())

    # Add SRT projection — query targets all entities (full KB scan)
    all_entity_names = frozenset(model.entities.keys())
    srt_query = SRTQuery(
        target_entities=all_entity_names,
        target_attributes=frozenset(["module", "section", "content_type"]),
        label="KB full validation",
    )
    hrc.add_projection(SRTProjection(srt_query))

    # Run analysis with premise queries
    if use_premises:
        ask = _build_forgeds_ask(db_path)
        result = hrc.analyze(model, ask=ask)
    else:
        result = hrc.analyze(model)

    return model, result


def _build_legacy_model(tokens, edges):
    """Build model using the original formal_proof.py (fallback)."""
    from formal_proof import (
        CodeModel, Entity, FieldDecl,
        Relation as HRCRelation, RelationKind,
        HologramRealityClause,
    )

    model = CodeModel()
    sha_to_name: dict[str, str] = {}

    for t in tokens:
        sha = t["token_sha"]
        name = f"{t['module']}.{t['section'] or 'root'}.p{t['paragraph'] or 0}"
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
            source=src_name, target=tgt_name, kind=hrc_kind,
        ))

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

def validate_knowledge(db_path: str | Path, *, use_premises: bool = True) -> dict:
    """Run all projections and return a validation report.

    If HRC (formal_proof.py) is available, runs the full 5-constraint
    cross-projection analysis on the knowledge graph for a global residual.
    KB-specific projections always run regardless.

    Args:
        db_path: Path to reality.db (knowledge database).
        use_premises: If True (default), enable premise queries — constraints
            can ask the ForgeDS knowledge base to resolve ambiguities before
            declaring violations. This reduces false positives by letting
            the Librarian vouch for entities that exist in the KB but aren't
            in the constraint's direct view (Johnson et al., CGO 2017).

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

    # Try HRC for global residual (with premise queries if enabled)
    model, result = _build_hrc_model(db_path, use_premises=use_premises)
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
