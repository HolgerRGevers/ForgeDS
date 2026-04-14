"""Markdown-to-token parser for the ForgeDS knowledge base.

Reads raw_md/*.md files (with YAML frontmatter), splits them into
sections and paragraphs, classifies each block, computes SHA identities,
and writes tokens to the knowledge.db SQLite database.
"""

from __future__ import annotations

import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from forgeds.knowledge._callout_patterns import classify_block
from forgeds.knowledge._types import (
    SCHEMA_DDL,
    ContentType,
    KnowledgeToken,
    compute_token_sha,
)


# ---------------------------------------------------------------------------
# Frontmatter parsing (minimal — avoids external YAML dep)
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split YAML frontmatter from markdown body.

    Returns (metadata_dict, body_text).
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text

    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            val = val.strip().strip('"').strip("'")
            meta[key.strip()] = val

    body = text[m.end():]
    return meta, body


# ---------------------------------------------------------------------------
# Section / paragraph splitting
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)", re.MULTILINE)


def _split_sections(body: str) -> list[tuple[str, str, list[str]]]:
    """Split markdown body into (heading_level, heading_text, paragraphs).

    A "paragraph" is a non-empty block separated by blank lines within
    a section. Code fences are treated as single blocks.
    """
    sections: list[tuple[str, str, list[str]]] = []
    current_heading = ""
    current_level = ""
    current_lines: list[str] = []

    def flush() -> None:
        if current_lines:
            paras = _lines_to_paragraphs(current_lines)
            if paras:
                sections.append((current_level, current_heading, paras))

    for line in body.splitlines():
        hm = _HEADING_RE.match(line)
        if hm:
            flush()
            current_level = hm.group(1)
            current_heading = hm.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    flush()

    # If there's content before any heading, store under empty section
    if not sections and body.strip():
        paras = _lines_to_paragraphs(body.splitlines())
        if paras:
            sections.append(("", "", paras))

    return sections


def _lines_to_paragraphs(lines: list[str]) -> list[str]:
    """Group lines into paragraph blocks, keeping code fences intact."""
    paragraphs: list[str] = []
    current: list[str] = []
    in_fence = False

    for line in lines:
        if line.strip().startswith("```"):
            if in_fence:
                # End of code fence
                current.append(line)
                paragraphs.append("\n".join(current))
                current = []
                in_fence = False
            else:
                # Start of code fence — flush any pending paragraph
                if current and any(l.strip() for l in current):
                    paragraphs.append("\n".join(current))
                current = [line]
                in_fence = True
        elif in_fence:
            current.append(line)
        elif line.strip() == "":
            if current and any(l.strip() for l in current):
                paragraphs.append("\n".join(current))
            current = []
        else:
            current.append(line)

    if current and any(l.strip() for l in current):
        paragraphs.append("\n".join(current))

    return paragraphs


# ---------------------------------------------------------------------------
# Git SHA helper
# ---------------------------------------------------------------------------

def _git_sha() -> str:
    """Return the current HEAD SHA, or 'unknown' if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "unknown"


# ---------------------------------------------------------------------------
# DB initialisation
# ---------------------------------------------------------------------------

def init_db(db_path: Path) -> None:
    """Create the knowledge.db schema if it doesn't exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_DDL)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.close()


# ---------------------------------------------------------------------------
# Parse pipeline
# ---------------------------------------------------------------------------

def parse_single_file(
    md_path: Path,
    raw_md_dir: Path,
    git_sha: str = "",
) -> tuple[list[KnowledgeToken], dict, str]:
    """Parse one .md file into KnowledgeTokens.

    Returns (tokens, frontmatter_meta, relative_path) so the caller
    does not need to re-read the file for metadata.
    """
    text = md_path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)

    url = meta.get("url", "")
    module = meta.get("module", "")
    page_title = meta.get("title", "")
    page_updated = meta.get("last_modified", "")

    # Relative path from raw_md root
    try:
        rel_path = str(md_path.relative_to(raw_md_dir))
    except ValueError:
        rel_path = str(md_path)

    if not git_sha:
        git_sha = _git_sha()

    tokens: list[KnowledgeToken] = []
    para_global = 0  # Global paragraph counter across sections

    sections = _split_sections(body)
    for _level, heading, paragraphs in sections:
        for para_text in paragraphs:
            stripped = para_text.strip()
            if not stripped:
                continue

            content_type = classify_block(stripped)
            token = KnowledgeToken.create(
                content=stripped,
                page_url=url,
                paragraph_num=para_global,
                content_type=content_type,
                module=module,
                page_title=page_title,
                section=heading,
                page_last_updated=page_updated,
                forgeds_git_sha=git_sha,
                source_md_path=rel_path,
            )
            tokens.append(token)
            para_global += 1

    return tokens, meta, rel_path


def _upsert_tokens(conn: sqlite3.Connection, tokens: list[KnowledgeToken]) -> int:
    """Insert or update tokens in the database. Returns count of rows affected."""
    if not tokens:
        return 0

    params = [
        (
            t.token_sha, t.revision, t.content, t.content_type.value,
            t.module, t.page_url, t.page_title, t.section,
            t.paragraph_num, t.page_last_updated,
            t.token_created_at, t.token_updated_at,
            t.forgeds_git_sha, t.source_md_path,
        )
        for t in tokens
    ]
    conn.executemany(
        """INSERT INTO tokens
            (token_sha, revision, content, content_type, module,
             page_url, page_title, section, paragraph, page_updated,
             created_at, updated_at, git_sha, source_md)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(token_sha) DO UPDATE SET
            revision = revision + 1,
            content = excluded.content,
            content_type = excluded.content_type,
            module = excluded.module,
            page_url = excluded.page_url,
            page_title = excluded.page_title,
            section = excluded.section,
            paragraph = excluded.paragraph,
            page_updated = excluded.page_updated,
            updated_at = excluded.updated_at,
            git_sha = excluded.git_sha,
            source_md = excluded.source_md""",
        params,
    )

    return len(tokens)


def _upsert_module(conn: sqlite3.Connection, meta: dict) -> None:
    """Insert or update the modules table entry (before pages for FK order)."""
    module = meta.get("module", "")
    url = meta.get("url", "")
    if not module:
        return

    conn.execute(
        """INSERT INTO modules (name, base_url, page_count)
           VALUES (?, ?, 1)
           ON CONFLICT(name) DO UPDATE SET
               page_count = (SELECT COUNT(*) FROM pages WHERE module = ?)""",
        (module, url.rsplit("/", 1)[0] if "/" in url else url, module),
    )


def _upsert_page(conn: sqlite3.Connection, meta: dict, md_rel_path: str) -> None:
    """Insert or update the pages table entry."""
    url = meta.get("url", "")
    if not url:
        return

    module = meta.get("module", "")
    title = meta.get("title", "")
    scraped_at = meta.get("scraped_at", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    conn.execute(
        """INSERT INTO pages (url, title, module, md_path, scraped_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(url) DO UPDATE SET
               title = excluded.title,
               module = excluded.module,
               md_path = excluded.md_path,
               scraped_at = excluded.scraped_at""",
        (url, title, module, md_rel_path, scraped_at),
    )


def parse_md_files(
    md_files: list[Path],
    db_path: Path,
    raw_md_dir: Path,
) -> int:
    """Parse multiple .md files and write tokens to knowledge.db.

    Returns total number of tokens stored.
    """
    git_sha = _git_sha()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA temp_store=MEMORY")
    total = 0

    try:
        for md_path in md_files:
            if md_path.name.startswith("_"):
                continue

            tokens, meta, rel_path = parse_single_file(md_path, raw_md_dir, git_sha)
            if tokens:
                # Insert module before page to respect FK order
                _upsert_module(conn, meta)
                _upsert_page(conn, meta, rel_path)
                total += _upsert_tokens(conn, tokens)

        conn.commit()
    finally:
        conn.close()

    return total
