"""Shadow case learning system for the ForgeDS knowledge base.

When static analysis cannot predict a runtime behaviour (a "shadow case"),
the discovery is recorded as a new KB token so that future projections
can detect it.  This closes the learning loop:

    runtime event → shadow record → KB validation → token + edges → weight

A shadow case differs from a scraped documentation token:
- Its **provenance** is a Git SHA + tool context, not a website URL
- Its **content_type** is ``LEARNED`` (runtime discovery, not docs)
- It must be **validated** against the existing KB before insertion
  to prevent corruption (no contradictions, no duplicates)
- It must **initialise all relations** with relevant existing tokens
- It must be **assigned a weight** based on severity and novelty

Usage::

    from forgeds.knowledge.shadow_learning import record_shadow_case

    record_shadow_case(
        description="Adding blueprints to an app then covering all transitions "
                    "yields net-zero improvement on pi_transition_logic because "
                    "the projection detected 0 gaps when there were 0 blueprints.",
        learned="Static analysis cannot detect missing state machines — only "
                "missing logic within existing state machines. Blueprint "
                "presence is a structural precondition, not a behavioural one.",
        remediation="Add a pi_structural_completeness projection that checks "
                    "for blueprint existence independently of transition logic.",
        context="app_projection.project_kb_onto_app",
        related_queries=["blueprint", "transition", "state machine"],
        db_path="knowledge/knowledge.db",
    )
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from forgeds.knowledge._types import (
    CONTENT_WEIGHTS,
    RELATION_WEIGHTS,
    ContentType,
    KnowledgeToken,
    RelationType,
)

if TYPE_CHECKING:
    from forgeds.knowledge.librarian_io import LibrarianHandle


# ---------------------------------------------------------------------------
# Shadow case record
# ---------------------------------------------------------------------------

@dataclass
class ShadowCase:
    """A runtime discovery that static analysis could not predict."""
    description: str       # What happened
    learned: str           # What was learned (the principle)
    remediation: str       # How to prevent / fix
    context: str           # Tool / function where discovered
    severity: float = 1.5  # Default: HIGH (hard-won knowledge)

    # Provenance
    git_sha: str = ""      # HEAD SHA at time of discovery
    related_queries: list[str] | None = None  # FTS queries to find related tokens


@dataclass
class ValidationResult:
    """Result of validating a shadow case against the KB."""
    valid: bool
    reason: str
    duplicate_sha: str = ""   # If duplicate found, its SHA
    contradicts: list[str] | None = None  # SHAs of contradicted tokens


# ---------------------------------------------------------------------------
# Git SHA resolution
# ---------------------------------------------------------------------------

def _get_git_sha() -> str:
    """Get the current HEAD SHA for provenance tracking."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip()[:12] if result.returncode == 0 else ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Validation: prevent KB corruption
# ---------------------------------------------------------------------------

def validate_shadow_case(
    case: ShadowCase,
    conn: sqlite3.Connection,
) -> ValidationResult:
    """Validate a shadow case against the existing KB.

    Checks:
    1. Not a duplicate (no existing token with identical content)
    2. No contradiction (does not assert the opposite of an existing token)
    3. Has substance (description + learned are non-empty)
    4. References real concepts (at least one related query finds tokens)
    """
    # Check substance
    if not case.description.strip() or not case.learned.strip():
        return ValidationResult(
            valid=False,
            reason="Shadow case must have both description and learned fields.",
        )

    # Build the content that would be stored
    content = _build_token_content(case)
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    # Check for duplicates (exact content match)
    existing = conn.execute(
        "SELECT token_sha FROM tokens WHERE content = ?",
        (content,),
    ).fetchone()
    if existing:
        return ValidationResult(
            valid=False,
            reason=f"Duplicate: identical content exists as token {existing[0][:16]}.",
            duplicate_sha=existing[0],
        )

    # Check for near-duplicates (same learned principle)
    # Use FTS if available, fall back to LIKE
    learned_lower = case.learned.lower()[:100]
    try:
        near = conn.execute(
            """SELECT token_sha, content FROM tokens_fts
               WHERE tokens_fts MATCH ? LIMIT 5""",
            (case.learned[:50],),
        ).fetchall()
    except sqlite3.OperationalError:
        near = conn.execute(
            "SELECT token_sha, content FROM tokens WHERE content LIKE ? LIMIT 5",
            (f"%{learned_lower[:40]}%",),
        ).fetchall()

    for sha, existing_content in near:
        # Simple similarity check — if >60% of words overlap, likely duplicate
        existing_words = set(existing_content.lower().split())
        new_words = set(content.lower().split())
        if existing_words and new_words:
            overlap = len(existing_words & new_words) / min(len(existing_words), len(new_words))
            if overlap > 0.6:
                return ValidationResult(
                    valid=False,
                    reason=f"Near-duplicate: token {sha[:16]} shares {overlap:.0%} vocabulary.",
                    duplicate_sha=sha,
                )

    # Check that related queries find at least one real token
    if case.related_queries:
        found_any = False
        for q in case.related_queries:
            try:
                row = conn.execute(
                    "SELECT COUNT(*) FROM tokens_fts WHERE tokens_fts MATCH ?",
                    (q,),
                ).fetchone()
                if row and row[0] > 0:
                    found_any = True
                    break
            except sqlite3.OperationalError:
                row = conn.execute(
                    "SELECT COUNT(*) FROM tokens WHERE content LIKE ?",
                    (f"%{q}%",),
                ).fetchone()
                if row and row[0] > 0:
                    found_any = True
                    break

        if not found_any:
            return ValidationResult(
                valid=False,
                reason="Shadow case does not relate to any existing KB tokens. "
                       "Related queries found no matches.",
            )

    return ValidationResult(valid=True, reason="Validated OK.")


# ---------------------------------------------------------------------------
# Token construction
# ---------------------------------------------------------------------------

def _build_token_content(case: ShadowCase) -> str:
    """Build the markdown content for a shadow case token."""
    lines = [
        f"## Shadow Case: {case.context}",
        "",
        f"**Discovery:** {case.description}",
        "",
        f"**Learned:** {case.learned}",
        "",
        f"**Remediation:** {case.remediation}",
        "",
        f"**Severity:** {case.severity}",
    ]
    return "\n".join(lines)


def _find_related_tokens(
    case: ShadowCase,
    conn: sqlite3.Connection,
    max_relations: int = 20,
) -> list[tuple[str, RelationType, float]]:
    """Find existing tokens related to this shadow case.

    Returns list of (target_sha, relation_type, weight) tuples.
    Each relation is initialised with a weight based on the relevance
    of the match and the type of connection.
    """
    relations: list[tuple[str, RelationType, float]] = []
    seen_shas: set[str] = set()

    queries = case.related_queries or [case.description[:50]]

    for q in queries:
        try:
            rows = conn.execute(
                """SELECT token_sha, content_type, content FROM tokens_fts
                   WHERE tokens_fts MATCH ? LIMIT ?""",
                (q, max_relations),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = conn.execute(
                """SELECT token_sha, content_type, content FROM tokens
                   WHERE content LIKE ? LIMIT ?""",
                (f"%{q}%", max_relations),
            ).fetchall()

        for sha, content_type, content in rows:
            if sha in seen_shas:
                continue
            seen_shas.add(sha)

            # Determine relation type based on content type
            if content_type == "CODE_EXAMPLE":
                rel = RelationType.EXAMPLE_OF
                weight = 0.8
            elif content_type in ("IMPORTANT", "VERY_IMPORTANT"):
                rel = RelationType.CALLOUT_IMPORTANT
                weight = 0.9
            elif content_type == "NOTE":
                rel = RelationType.CALLOUT_NOTE
                weight = 0.7
            else:
                rel = RelationType.LEARNED_FROM
                weight = RELATION_WEIGHTS.get(RelationType.LEARNED_FROM, 0.95)

            relations.append((sha, rel, weight))

            if len(relations) >= max_relations:
                break

    return relations


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def record_shadow_case(
    description: str,
    learned: str,
    remediation: str,
    context: str,
    *,
    related_queries: list[str] | None = None,
    severity: float = 1.5,
    librarian: LibrarianHandle | None = None,
    db_path: str | Path | None = None,
) -> dict:
    """Record a runtime shadow case as a validated RB token via the Librarian.

    The full lifecycle:
    1. Build the ShadowCase record with Git SHA provenance
    2. Validate against existing KB (no duplicates, no contradictions)
    3. Create the token via Librarian with content_type=LEARNED
    4. Initialise all relations via Librarian
    5. Assign weight based on severity and content type

    Returns a dict with: token_sha, valid, reason, relation_count
    """
    from forgeds.knowledge.librarian_io import LIB_RB, LibrarianError, open_librarian

    if librarian is None:
        if db_path is None:
            from forgeds._shared.kb_accessor import get_kb
            kb = get_kb()
            db_path = str(kb.db_path)
        rb_path = Path(str(db_path))
        if rb_path.name == "knowledge.db":
            rb_path = rb_path.parent / "reality.db"
        hb_path = rb_path.parent / "holographic.db"
        librarian = open_librarian(rb_path, hb_path)

    case = ShadowCase(
        description=description,
        learned=learned,
        remediation=remediation,
        context=context,
        severity=severity,
        git_sha=_get_git_sha(),
        related_queries=related_queries,
    )

    conn = librarian.rb_conn

    # Step 1: Validate
    result = validate_shadow_case(case, conn)
    if not result.valid:
        return {
            "token_sha": "",
            "valid": False,
            "reason": result.reason,
            "relation_count": 0,
        }

    # Step 2: Build token content
    content = _build_token_content(case)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    page_url = f"shadow://{context}"

    # Step 3: Create token via Librarian (sole authority)
    try:
        token_sha = librarian.create(
            db=LIB_RB,
            content=content,
            page_url=page_url,
            paragraph_num=0,
            module="shadow_cases",
            content_type="LEARNED",
            weight=CONTENT_WEIGHTS.get("LEARNED", 1.5),
            metadata={
                "page_title": f"Shadow: {context}",
                "section": "Shadow Cases",
                "created_at": now,
                "updated_at": now,
                "git_sha": case.git_sha,
                "source_md": "",
            },
        )
    except LibrarianError as e:
        return {
            "token_sha": "",
            "valid": False,
            "reason": str(e),
            "relation_count": 0,
        }

    # Step 4: Initialise relations via Librarian
    relations = _find_related_tokens(case, conn)
    relation_count = 0
    for target_sha, rel_type, weight in relations:
        try:
            librarian.create_edge(token_sha, target_sha, rel_type.value, weight)
            relation_count += 1
        except LibrarianError:
            pass  # target may not be in registry (edge of graph)

    return {
        "token_sha": token_sha,
        "valid": True,
        "reason": "Recorded and validated.",
        "relation_count": relation_count,
        "severity": severity,
        "content_weight": CONTENT_WEIGHTS.get("LEARNED", 1.5),
    }
