"""Core data types for the ForgeDS knowledge base.

Defines the KnowledgeToken (atomic unit of documentation knowledge),
RelationType (edge categories), and Relation (weighted edge between tokens).
These mirror the SQLite schema in knowledge.db.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ContentType(Enum):
    """Classification of a knowledge token's content."""
    PROSE = "PROSE"
    CODE_EXAMPLE = "CODE_EXAMPLE"
    SIGNATURE = "SIGNATURE"
    TABLE_ROW = "TABLE_ROW"
    NOTE = "NOTE"
    PRO_TIP = "PRO_TIP"
    IMPORTANT = "IMPORTANT"
    VERY_IMPORTANT = "VERY_IMPORTANT"


class RelationType(Enum):
    """Edge types in the knowledge graph."""
    HIERARCHY = "HIERARCHY"              # Module > Page > Section > Token
    NEXT_SIBLING = "NEXT_SIBLING"        # Adjacent tokens in same section
    CROSS_REFERENCE = "CROSS_REFERENCE"  # In-text hyperlink to another page
    CALLOUT_NOTE = "CALLOUT_NOTE"        # "Note" callout
    CALLOUT_TIP = "CALLOUT_TIP"          # "Pro Tip" callout
    CALLOUT_IMPORTANT = "CALLOUT_IMPORTANT"  # "Important" callout
    CALLOUT_CRITICAL = "CALLOUT_CRITICAL"    # "Very Important" callout
    CROSS_MODULE = "CROSS_MODULE"        # Reference spanning modules
    FUNCTION_OF = "FUNCTION_OF"          # Token describes a function
    EXAMPLE_OF = "EXAMPLE_OF"            # Code example -> concept
    SUPERSEDES = "SUPERSEDES"            # Newer token replaces older
    LEARNED_FROM = "LEARNED_FROM"        # Shadow case learning → source token


# Default coupling weights for HRC residual field computation.
RELATION_WEIGHTS: dict[RelationType, float] = {
    RelationType.HIERARCHY: 1.0,
    RelationType.NEXT_SIBLING: 0.3,
    RelationType.CROSS_REFERENCE: 0.7,
    RelationType.CALLOUT_NOTE: 0.5,
    RelationType.CALLOUT_TIP: 0.6,
    RelationType.CALLOUT_IMPORTANT: 0.8,
    RelationType.CALLOUT_CRITICAL: 1.0,
    RelationType.CROSS_MODULE: 0.9,
    RelationType.FUNCTION_OF: 0.8,
    RelationType.EXAMPLE_OF: 0.6,
    RelationType.SUPERSEDES: 1.0,
    RelationType.LEARNED_FROM: 0.95,
}


# Content-type weights for projection severity scaling.
# Structural tokens (blueprints, pages, dashboards) carry higher weight
# because they are foundational — an app without a page cannot load,
# an app without a blueprint has no state machine.
CONTENT_WEIGHTS: dict[str, float] = {
    # Structural (foundational — app cannot function without these)
    "BLUEPRINT": 2.0,
    "PAGE": 1.8,
    "DASHBOARD": 1.8,
    # Behavioural (operational — app works but is hollow without these)
    "CODE_EXAMPLE": 1.0,
    "SIGNATURE": 0.9,
    # Informational (documentation — completeness, not correctness)
    "PROSE": 0.5,
    "TABLE_ROW": 0.4,
    "NOTE": 0.6,
    "IMPORTANT": 1.0,
    "VERY_IMPORTANT": 1.2,
    "PRO_TIP": 0.5,
    # Learning (runtime shadow cases — high weight because hard-won)
    "LEARNED": 1.5,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_token_sha(content: str, page_url: str, paragraph_num: int) -> str:
    """Deterministic SHA-256 identity for a knowledge token."""
    raw = f"{content}\x00{page_url}\x00{paragraph_num}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class KnowledgeToken:
    """Atomic unit of documentation knowledge.

    Each token represents a single coherent idea extracted from a
    scraped documentation page. Identity is a SHA-256 of
    (content, page_url, paragraph_num).
    """
    # Identity
    token_sha: str
    revision: int = 1

    # Content
    content: str = ""
    content_type: ContentType = ContentType.PROSE

    # Hierarchy
    module: str = ""
    page_url: str = ""
    page_title: str = ""
    section: str = ""
    paragraph_num: int = 0

    # Timestamps
    page_last_updated: str = ""
    token_created_at: str = field(default_factory=_now_iso)
    token_updated_at: str = field(default_factory=_now_iso)

    # Provenance
    forgeds_git_sha: str = ""
    source_md_path: str = ""

    @classmethod
    def create(
        cls,
        content: str,
        page_url: str,
        paragraph_num: int,
        *,
        content_type: ContentType = ContentType.PROSE,
        module: str = "",
        page_title: str = "",
        section: str = "",
        page_last_updated: str = "",
        forgeds_git_sha: str = "",
        source_md_path: str = "",
    ) -> KnowledgeToken:
        """Factory that auto-computes the token SHA."""
        sha = compute_token_sha(content, page_url, paragraph_num)
        return cls(
            token_sha=sha,
            content=content,
            content_type=content_type,
            module=module,
            page_url=page_url,
            page_title=page_title,
            section=section,
            paragraph_num=paragraph_num,
            page_last_updated=page_last_updated,
            forgeds_git_sha=forgeds_git_sha,
            source_md_path=source_md_path,
        )


@dataclass
class Relation:
    """Weighted directed edge between two knowledge tokens."""
    source_sha: str
    target_sha: str
    rel_type: RelationType
    weight: float | None = None

    def __post_init__(self) -> None:
        if self.weight is None:
            self.weight = RELATION_WEIGHTS.get(self.rel_type, 0.5)


# ---------------------------------------------------------------------------
# SQLite DDL — used by graph_builder.py to initialise knowledge.db
# ---------------------------------------------------------------------------

SCHEMA_DDL = """\
CREATE TABLE IF NOT EXISTS modules (
    name     TEXT PRIMARY KEY,
    base_url TEXT NOT NULL,
    page_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pages (
    url        TEXT PRIMARY KEY,
    title      TEXT,
    module     TEXT NOT NULL REFERENCES modules(name),
    md_path    TEXT NOT NULL,
    scraped_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tokens (
    token_sha    TEXT PRIMARY KEY,
    revision     INTEGER NOT NULL DEFAULT 1,
    content      TEXT NOT NULL,
    content_type TEXT NOT NULL,
    module       TEXT NOT NULL,
    page_url     TEXT NOT NULL,
    page_title   TEXT,
    section      TEXT,
    paragraph    INTEGER,
    page_updated TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    git_sha      TEXT NOT NULL,
    source_md    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS edges (
    source_sha TEXT NOT NULL REFERENCES tokens(token_sha),
    target_sha TEXT NOT NULL REFERENCES tokens(token_sha),
    rel_type   TEXT NOT NULL,
    weight     REAL NOT NULL DEFAULT 0.5,
    PRIMARY KEY (source_sha, target_sha, rel_type)
);

CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_sha);
CREATE INDEX IF NOT EXISTS idx_tokens_module ON tokens(module);
CREATE INDEX IF NOT EXISTS idx_tokens_page   ON tokens(page_url);

CREATE VIRTUAL TABLE IF NOT EXISTS tokens_fts USING fts5(
    content, token_sha UNINDEXED, module UNINDEXED, content_type UNINDEXED,
    content='tokens', content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS tokens_ai AFTER INSERT ON tokens BEGIN
    INSERT INTO tokens_fts(rowid, content, token_sha, module, content_type)
    VALUES (new.rowid, new.content, new.token_sha, new.module, new.content_type);
END;

CREATE TRIGGER IF NOT EXISTS tokens_ad AFTER DELETE ON tokens BEGIN
    INSERT INTO tokens_fts(tokens_fts, rowid, content, token_sha, module, content_type)
    VALUES ('delete', old.rowid, old.content, old.token_sha, old.module, old.content_type);
END;

CREATE TRIGGER IF NOT EXISTS tokens_au AFTER UPDATE ON tokens BEGIN
    INSERT INTO tokens_fts(tokens_fts, rowid, content, token_sha, module, content_type)
    VALUES ('delete', old.rowid, old.content, old.token_sha, old.module, old.content_type);
    INSERT INTO tokens_fts(rowid, content, token_sha, module, content_type)
    VALUES (new.rowid, new.content, new.token_sha, new.module, new.content_type);
END;
"""
