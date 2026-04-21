"""Public programmatic API for the ForgeDS knowledge base.

External programs import this module to request:
    1. Knowledge database creation (scrape + parse + build)
    2. Content tokenization (arbitrary text -> KB tokens)
    3. Hologram token creation + reality checks (projection)

The Librarian (C or Python fallback) is the sole authority for token
lifecycle: every create, destroy, and weight adjustment goes through it.

The Knowledge Base operates two databases:
    - **RB** (Reality Database) — permanent source of truth
    - **HB** (Holographic Database) — ephemeral projection tokens

Usage::

    from forgeds.knowledge.api import KnowledgeBase, HologramToken

    kb = KnowledgeBase("knowledge/reality.db")
    kb.init()
    kb.ingest("path/to/App.ds")
    result = kb.check("app:App")
    for h in result.holograms:
        print(f"[{h.severity_label}] {h.projection}: {h.message}")

    # After review, purge the holographic database
    kb.confirm_analysis()
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from forgeds.knowledge._types import (
    CONTENT_WEIGHTS,
    ContentType,
    KnowledgeToken,
    Relation,
    RelationType,
    RELATION_WEIGHTS,
    SCHEMA_DDL,
    _compute_token_sha,
)
from forgeds.knowledge.librarian_io import (
    LIB_HB,
    LIB_RB,
    LibrarianError,
    LibrarianHandle,
    open_librarian,
)


# ---------------------------------------------------------------------------
# HologramToken — a temporary token representing a reality-check gap
# ---------------------------------------------------------------------------

@dataclass
class HologramToken:
    """A temporary token representing a gap between app and KB reality.

    A hologram is what becomes visible when you project the KB (reality)
    onto an app (artifact).  Each HologramToken is a specific thing the
    KB says should exist but the app does not have.

    Hologram tokens live in the Holographic Database (HB) and are
    destroyed by the Librarian after analysis + user confirmation.

    Attributes:
        projection: Which HRC projection detected this gap.
        severity: Numeric weight (0.0-2.0).  CRITICAL=2.0, HIGH=1.5,
                  MEDIUM=1.0, LOW=0.5, INFO=0.2.
        entity: The app entity affected (form, transition, script).
        message: Human-readable description of what is missing.
        kb_pattern: What the KB says should be here.
        remediation: Suggested fix.
        token_sha: Deterministic SHA assigned by the Librarian.
        module: The app module this hologram belongs to.
        residual: This hologram's contribution to R(app).
    """

    projection: str
    severity: float
    entity: str
    message: str
    kb_pattern: str = ""
    remediation: str = ""
    module: str = ""
    token_sha: str = ""
    residual: float = 0.0

    def __post_init__(self) -> None:
        if self.residual == 0.0:
            self.residual = self.severity

    @property
    def severity_label(self) -> str:
        labels = {2.0: "CRITICAL", 1.5: "HIGH", 1.0: "MEDIUM", 0.5: "LOW", 0.2: "INFO"}
        return labels.get(self.severity, f"SEV:{self.severity}")

    @property
    def is_critical(self) -> bool:
        return self.severity >= 2.0

    @property
    def is_high(self) -> bool:
        return self.severity >= 1.5

    def to_dict(self) -> dict:
        return {
            "token_sha": self.token_sha,
            "projection": self.projection,
            "severity": self.severity,
            "severity_label": self.severity_label,
            "entity": self.entity,
            "message": self.message,
            "kb_pattern": self.kb_pattern,
            "remediation": self.remediation,
            "module": self.module,
            "residual": self.residual,
        }

    def promote(self, kb: KnowledgeBase) -> str:
        """Promote this hologram to a permanent shadow-case token in the RB.

        Records the gap as a LEARNED token via the shadow learning system
        so that future projections can detect the pattern.

        Returns the token SHA of the promoted token.
        """
        result = kb.learn(
            description=self.message,
            learned=f"Projection {self.projection} detected: {self.kb_pattern}",
            remediation=self.remediation,
            context=f"hologram.{self.projection}",
            severity=self.severity,
            related_queries=[self.entity.split(":")[-1], self.projection],
        )
        return result.get("token_sha", "")


# ---------------------------------------------------------------------------
# RealityCheck — result of projecting KB onto an app
# ---------------------------------------------------------------------------

@dataclass
class RealityCheck:
    """Result of a reality check (KB projection) on an app.

    Contains the hologram tokens (gaps) and the total residual R(app).
    R(app) = 0 means the app is fully grounded to the KB.
    R(app) > 0 means gaps exist — each hologram tells you what is missing.
    """

    module: str
    app_name: str
    holograms: list[HologramToken] = field(default_factory=list)
    residual: float = 0.0
    forms_analyzed: int = 0
    scripts_analyzed: int = 0

    @property
    def is_grounded(self) -> bool:
        return self.residual == 0.0

    @property
    def critical_count(self) -> int:
        return sum(1 for h in self.holograms if h.is_critical)

    @property
    def high_count(self) -> int:
        return sum(1 for h in self.holograms if h.is_high and not h.is_critical)

    def by_projection(self) -> dict[str, list[HologramToken]]:
        grouped: dict[str, list[HologramToken]] = {}
        for h in self.holograms:
            grouped.setdefault(h.projection, []).append(h)
        return grouped

    def by_entity(self) -> dict[str, list[HologramToken]]:
        grouped: dict[str, list[HologramToken]] = {}
        for h in self.holograms:
            grouped.setdefault(h.entity, []).append(h)
        return grouped

    def above(self, threshold: float) -> list[HologramToken]:
        return [h for h in self.holograms if h.severity >= threshold]

    def to_dict(self) -> dict:
        return {
            "module": self.module,
            "app_name": self.app_name,
            "residual": self.residual,
            "is_grounded": self.is_grounded,
            "forms_analyzed": self.forms_analyzed,
            "scripts_analyzed": self.scripts_analyzed,
            "hologram_count": len(self.holograms),
            "critical_count": self.critical_count,
            "holograms": [h.to_dict() for h in self.holograms],
        }


# ---------------------------------------------------------------------------
# KnowledgeBase — unified API for external programs
# ---------------------------------------------------------------------------

class KnowledgeBase:
    """Programmatic interface to the ForgeDS knowledge base.

    This is the main entry point for external programs.  It wraps the
    full KB lifecycle: creation, tokenization, retrieval, ingestion,
    and reality checks (HRC projection).

    Internally holds a :class:`LibrarianHandle` that is the sole
    authority for all token lifecycle operations.

    Args:
        db_path: Path to the Reality Database (``reality.db``).
                 Created on ``init()`` if it does not exist.
                 For backward compat, ``knowledge.db`` is accepted.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            db_path = self._discover_db()
        self._db_path = Path(db_path)

        # Derive HB path from RB path
        if self._db_path.name == "knowledge.db":
            # Backward compat: knowledge.db -> reality.db rename
            self._rb_path = self._db_path.parent / "reality.db"
        else:
            self._rb_path = self._db_path

        self._hb_path = self._rb_path.parent / "holographic.db"

        # Librarian is opened lazily on first use
        self._librarian: LibrarianHandle | None = None

    @staticmethod
    def _discover_db() -> Path:
        from forgeds._shared.config import find_project_root, load_config
        root = find_project_root()
        cfg = load_config().get("knowledge", {})
        kb_dir = root / cfg.get("knowledge_dir", "knowledge")
        return kb_dir / "reality.db"

    def _get_librarian(self) -> LibrarianHandle:
        """Get or create the Librarian handle (lazy initialization)."""
        if self._librarian is None:
            self._rb_path.parent.mkdir(parents=True, exist_ok=True)
            self._librarian = open_librarian(self._rb_path, self._hb_path)
        return self._librarian

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def db_path(self) -> Path:
        """Path to the Reality Database."""
        return self._rb_path

    @property
    def hb_path(self) -> Path:
        """Path to the Holographic Database."""
        return self._hb_path

    @property
    def librarian(self) -> LibrarianHandle:
        """The Librarian handle — sole token lifecycle authority."""
        return self._get_librarian()

    @property
    def exists(self) -> bool:
        if not self._rb_path.is_file():
            return False
        try:
            lib = self._get_librarian()
            return lib.count(LIB_RB) > 0
        except Exception:
            return False

    @property
    def stats(self) -> dict:
        if not self._rb_path.is_file():
            return {"tokens": 0, "edges": 0, "modules": 0, "app_modules": 0}
        try:
            lib = self._get_librarian()
            conn = lib.rb_conn
            tokens = lib.count(LIB_RB)
            edges = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            modules = conn.execute("SELECT COUNT(*) FROM modules").fetchone()[0]
            apps = conn.execute(
                "SELECT COUNT(DISTINCT module) FROM tokens WHERE module LIKE 'app:%'"
            ).fetchone()[0]
            hb_tokens = lib.count(LIB_HB)
            return {
                "tokens": tokens,
                "edges": edges,
                "modules": modules,
                "app_modules": apps,
                "hb_tokens": hb_tokens,
                "registry_size": lib.registry_size(),
            }
        except Exception:
            return {"tokens": 0, "edges": 0, "modules": 0, "app_modules": 0}

    # ------------------------------------------------------------------
    # 1. Database creation: init()
    # ------------------------------------------------------------------

    def create_db(self) -> None:
        """Ensure both databases exist with their schemas."""
        self._get_librarian()  # lib_open creates schemas

    def init(
        self,
        *,
        force_scrape: bool = False,
        follow_links: bool = False,
        parallel: bool = False,
    ) -> dict:
        """Create and populate the knowledge base from configured sources.

        Runs the full pipeline: scrape -> parse -> build (graph edges).
        """
        from forgeds.knowledge.scraper import scrape_sources, get_scrape_config
        from forgeds.knowledge.token_parser import parse_md_files
        from forgeds.knowledge.graph_builder import build_graph

        sources, raw_md_dir, delay, cfg_follow, cfg_parallel, cfg_depth = get_scrape_config()
        follow = follow_links or cfg_follow
        par = parallel or cfg_parallel
        depth = cfg_depth

        # Step 1: Scrape
        written = scrape_sources(
            sources, raw_md_dir,
            delay=delay, force=force_scrape,
            follow_links=follow, parallel=par, max_depth=depth,
        )

        # Step 2: Parse — passes Librarian for gated token creation
        lib = self._get_librarian()
        md_files = sorted(raw_md_dir.rglob("*.md"))
        md_files = [f for f in md_files if f.name != "_manifest.json"]
        token_count = parse_md_files(md_files, lib, raw_md_dir) if md_files else 0

        # Step 3: Build graph edges (via Librarian for edge creation)
        edge_count = build_graph(lib) if token_count > 0 else 0

        return {
            "pages_scraped": len(written),
            "files_parsed": len(md_files),
            "tokens_created": token_count,
            "edges_created": edge_count,
        }

    # ------------------------------------------------------------------
    # 2. Tokenizer: tokenize()
    # ------------------------------------------------------------------

    def tokenize(
        self,
        content: str,
        *,
        module: str = "custom",
        page_url: str = "",
        section: str = "",
        content_type: str = "PROSE",
        paragraph_num: int = 0,
        weight: float = 1.0,
    ) -> str:
        """Tokenize arbitrary content into a KB token via the Librarian.

        Returns the SHA of the created token.

        Raises LibrarianError if a token with the same SHA already exists.
        """
        import subprocess
        from datetime import datetime, timezone

        if not page_url:
            page_url = f"custom://{module}/{section or 'root'}"

        git_sha = ""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=5,
            )
            git_sha = result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            pass

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        lib = self._get_librarian()

        # Ensure module/page exist in RB
        conn = lib.rb_metadata_conn
        conn.execute(
            "INSERT OR IGNORE INTO modules (name, base_url, page_count) VALUES (?, ?, 0)",
            (module, page_url),
        )
        conn.execute(
            "INSERT OR IGNORE INTO pages (url, title, module, md_path, scraped_at) "
            "VALUES (?, ?, ?, '', ?)",
            (page_url, section, module, now),
        )
        conn.commit()

        sha = lib.create(
            db=LIB_RB,
            content=content,
            page_url=page_url,
            paragraph_num=paragraph_num,
            module=module,
            content_type=content_type,
            weight=weight,
            metadata={
                "page_title": "",
                "section": section,
                "page_updated": now,
                "created_at": now,
                "updated_at": now,
                "git_sha": git_sha,
                "source_md": "",
            },
        )
        return sha

    def tokenize_file(self, md_path: str | Path) -> int:
        """Parse a markdown file into KB tokens via the Librarian."""
        from forgeds.knowledge.token_parser import parse_md_files

        md_path = Path(md_path)
        lib = self._get_librarian()
        return parse_md_files([md_path], lib, md_path.parent)

    # ------------------------------------------------------------------
    # 3. Ingestion: ingest()
    # ------------------------------------------------------------------

    def ingest(self, ds_path: str | Path) -> dict:
        """Ingest a Zoho Creator .ds application export via the Librarian."""
        from forgeds.knowledge.app_ingest import ingest_ds_app

        lib = self._get_librarian()
        stats = ingest_ds_app(ds_path, lib)
        return {
            "app_name": stats.app_name,
            "module": stats.module,
            "forms": stats.forms,
            "fields": stats.fields,
            "scripts": stats.scripts,
            "blueprints": stats.blueprints,
            "transitions": stats.transitions,
            "tokens_created": stats.tokens_created,
            "edges_created": stats.edges_created,
        }

    # ------------------------------------------------------------------
    # 4. Reality check: check()
    # ------------------------------------------------------------------

    def check(self, module: str) -> RealityCheck:
        """Run the HRC reality check on an ingested app.

        Projects the KB onto the app's tokens.  Hologram tokens are
        created in the HB via the Librarian, then wrapped as
        HologramToken objects for inspection.

        Call ``confirm_analysis()`` after reviewing to purge the HB.
        """
        from forgeds.knowledge.app_projection import project_kb_onto_app

        lib = self._get_librarian()
        report = project_kb_onto_app(module, lib)

        holograms: list[HologramToken] = []
        for gap in report.gaps:
            # Create hologram in HB via Librarian
            content = f"{gap.projection}\x00{gap.entity}\x00{gap.message}"
            page_url = f"hologram://{module}"
            try:
                sha = lib.create(
                    db=LIB_HB,
                    content=content,
                    page_url=page_url,
                    paragraph_num=0,
                    module=module,
                    content_type="HOLOGRAM",
                    weight=gap.severity,
                    metadata={
                        "page_title": gap.projection,
                        "section": gap.entity,
                        "created_at": "",
                    },
                )
            except LibrarianError:
                # SHA collision — hologram already in HB (duplicate gap)
                sha = _compute_token_sha(content, page_url, 0)

            holograms.append(HologramToken(
                projection=gap.projection,
                severity=gap.severity,
                entity=gap.entity,
                message=gap.message,
                kb_pattern=gap.kb_pattern,
                remediation=gap.remediation,
                module=module,
                token_sha=sha,
            ))

        return RealityCheck(
            module=report.module,
            app_name=report.app_name,
            holograms=holograms,
            residual=report.residual,
            forms_analyzed=report.forms_analyzed,
            scripts_analyzed=report.scripts_analyzed,
        )

    def check_all(self) -> list[RealityCheck]:
        """Run reality checks on all ingested apps."""
        modules = self.list_apps()
        return [self.check(m) for m in modules]

    def confirm_analysis(self) -> int:
        """Confirm analysis results and purge all holographic tokens.

        Call this after reviewing ``check()`` results.  The Librarian
        destroys every HB token, revoking their SHAs.

        Returns the number of HB tokens destroyed.
        """
        lib = self._get_librarian()
        return lib.purge_hb()

    # ------------------------------------------------------------------
    # 5. Retrieval: retrieve() / query()
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        *,
        module: str | None = None,
        max_words: int = 4096,
    ):
        """Retrieve coherent context from the KB for a query."""
        from forgeds.knowledge.retriever import retrieve_context

        return retrieve_context(
            query,
            db_path=self._rb_path,
            module=module,
            max_words=max_words,
        )

    def query(self, term: str, *, module: str | None = None, limit: int = 20) -> list[dict]:
        """Search the KB for tokens matching a term.

        Returns JSON dicts — closed-world output via read-only conn.
        """
        lib = self._get_librarian()
        conn = lib.rb_conn
        conn.row_factory = sqlite3.Row

        try:
            conn.execute("SELECT 1 FROM tokens_fts LIMIT 0")
            fts_term = '"' + term.replace('"', '""') + '"'
            sql = """SELECT t.* FROM tokens t
                     JOIN tokens_fts f ON f.token_sha = t.token_sha
                     WHERE tokens_fts MATCH ?"""
            params: list = [fts_term]
            if module:
                sql += " AND t.module = ?"
                params.append(module)
            sql += " ORDER BY rank LIMIT ?"
            params.append(limit)
        except sqlite3.OperationalError:
            sql = "SELECT * FROM tokens WHERE content LIKE ?"
            params = [f"%{term}%"]
            if module:
                sql += " AND module = ?"
                params.append(module)
            sql += " ORDER BY module, page_url, paragraph LIMIT ?"
            params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        conn.row_factory = None
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # 6. Validation: validate()
    # ------------------------------------------------------------------

    def validate(self, *, use_premises: bool = True) -> dict:
        """Validate the KB's internal consistency via HRC projections.

        Args:
            use_premises: If True (default), enable premise queries so
                constraints can ask the KB to resolve ambiguities before
                declaring violations. Reduces false positives.
        """
        from forgeds.knowledge.hrc_bridge import validate_knowledge
        return validate_knowledge(str(self._rb_path), use_premises=use_premises)

    # ------------------------------------------------------------------
    # 7. Shadow learning: learn()
    # ------------------------------------------------------------------

    def learn(
        self,
        description: str,
        learned: str,
        remediation: str,
        context: str,
        *,
        related_queries: list[str] | None = None,
        severity: float = 1.5,
    ) -> dict:
        """Record a runtime shadow case as a new RB token via the Librarian."""
        from forgeds.knowledge.shadow_learning import record_shadow_case

        lib = self._get_librarian()
        return record_shadow_case(
            description=description,
            learned=learned,
            remediation=remediation,
            context=context,
            related_queries=related_queries,
            severity=severity,
            librarian=lib,
        )

    # ------------------------------------------------------------------
    # Closed-world output
    # ------------------------------------------------------------------

    def export_token(self, sha: str) -> dict | None:
        """Export a single token as a JSON dict (closed-world output)."""
        lib = self._get_librarian()
        return lib.export_token(sha)

    def export_hb(self) -> list[dict]:
        """Export all HB tokens as JSON (closed-world output)."""
        lib = self._get_librarian()
        return lib.export_hb()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def list_apps(self) -> list[str]:
        if not self._rb_path.is_file():
            return []
        lib = self._get_librarian()
        conn = lib.rb_conn
        rows = conn.execute(
            "SELECT DISTINCT module FROM tokens WHERE module LIKE 'app:%' ORDER BY module"
        ).fetchall()
        return [r[0] for r in rows]

    def list_modules(self) -> list[str]:
        if not self._rb_path.is_file():
            return []
        lib = self._get_librarian()
        conn = lib.rb_conn
        rows = conn.execute("SELECT name FROM modules ORDER BY name").fetchall()
        return [r[0] for r in rows]

    def close(self) -> None:
        """Close the Librarian and release all resources."""
        if self._librarian:
            self._librarian.close()
            self._librarian = None

    def __del__(self) -> None:
        self.close()
