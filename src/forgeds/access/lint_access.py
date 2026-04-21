#!/usr/bin/env python3
"""
Access SQL Static Analysis Linter for .sql files.

Checks Access SQL DDL/DML for reserved-word collisions, deprecated types,
naming conventions, and structural issues.
Backed by a SQLite database of Access/VBA language data.

Usage:
    python -m forgeds.access.lint_access src/sql/         # lint all .sql files
    python -m forgeds.access.lint_access path/to/file.sql # lint one file

Exit codes:
    0 = clean (no issues)
    1 = warnings only
    2 = errors found
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from forgeds._shared.config import load_config, get_db_dir
from forgeds._shared.diagnostics import Severity, Diagnostic


# ============================================================
# Constants
# ============================================================

DB_PATH = get_db_dir() / "access_vba_lang.db"

# SQL statement starters (case-insensitive)
SQL_STATEMENT_STARTERS = re.compile(
    r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)\b", re.IGNORECASE
)

# Deprecated Jet data types: type -> (severity, message)
DEPRECATED_JET_TYPES: dict[str, tuple[str, str]] = {
    "SINGLE": (
        "WARN",
        "Deprecated Jet type SINGLE. Use DOUBLE for floating-point fields.",
    ),
    "BINARY": (
        "ERROR",
        "Deprecated Jet type BINARY. No Zoho equivalent exists.",
    ),
}

# PascalCase segment check: each underscore-delimited segment starts uppercase
PASCAL_SEGMENT_RE = re.compile(r"^[A-Z][a-zA-Z0-9]*$")


# ============================================================
# Enums
# ============================================================

class FileType(str, Enum):
    SQL_DDL = "SQL_DDL"
    SQL_DML = "SQL_DML"


# ============================================================
# Data classes
# ============================================================

@dataclass
class CreateTableBlock:
    table_name: str
    start_line: int
    end_line: int
    columns: list[ColumnDef] = field(default_factory=list)
    raw_lines: list[str] = field(default_factory=list)


@dataclass
class ColumnDef:
    name: str
    data_type: str
    full_text: str
    line: int
    has_autoincrement: bool = False


# ============================================================
# Helper: create Diagnostic with shared field names
# ============================================================

def _diag(filename: str, lineno: int, severity: Severity, code: str, message: str) -> Diagnostic:
    """Create a Diagnostic using the shared dataclass field order."""
    return Diagnostic(file=filename, line=lineno, rule=code, severity=severity, message=message)


# ============================================================
# Database-backed lookup cache
# ============================================================

class AccessDB:
    """Read-only cache of Access/VBA language data from SQLite."""

    def __init__(self, db_path: Path) -> None:
        if not db_path.exists():
            raise FileNotFoundError(
                f"Access VBA language DB not found at {db_path}. "
                "Run: python -m forgeds.access.build_access_vba_db"
            )
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._load_caches()

    def _query_set(self, sql: str) -> set[str]:
        return {row[0] for row in self._conn.execute(sql).fetchall()}

    def _load_caches(self) -> None:
        # Reserved SQL words (stored uppercase)
        self.reserved_words: set[str] = set()
        try:
            self.reserved_words = {
                w.upper() for w in self._query_set(
                    "SELECT word FROM reserved_words"
                )
            }
        except sqlite3.OperationalError:
            pass

        # Access data types (stored uppercase)
        self.access_data_types: set[str] = set()
        try:
            self.access_data_types = {
                t.upper() for t in self._query_set(
                    "SELECT type_name FROM access_data_types"
                )
            }
        except sqlite3.OperationalError:
            pass

        # Known table/field mappings: { table_name_upper: { field_upper, ... } }
        self.access_table_fields: dict[str, set[str]] = {}
        try:
            for row in self._conn.execute(
                "SELECT table_name, field_name FROM access_table_fields"
            ):
                tbl = row["table_name"].upper()
                if tbl not in self.access_table_fields:
                    self.access_table_fields[tbl] = set()
                self.access_table_fields[tbl].add(row["field_name"].upper())
        except sqlite3.OperationalError:
            pass

        # Known table names (for FK validation)
        self.known_tables: set[str] = set(self.access_table_fields.keys())

        # Banned patterns
        self.banned_patterns: dict[str, str] = {}
        try:
            for row in self._conn.execute(
                "SELECT pattern, message FROM banned_patterns_access"
            ).fetchall():
                self.banned_patterns[row["pattern"]] = row["message"]
        except sqlite3.OperationalError:
            pass

    def close(self) -> None:
        self._conn.close()


# ============================================================
# File type detection
# ============================================================

def detect_file_type(filepath: str, content: str) -> FileType:
    """Determine SQL file type from content."""
    upper = content.upper()
    if "CREATE TABLE" in upper or "ALTER TABLE" in upper or "DROP TABLE" in upper:
        return FileType.SQL_DDL
    return FileType.SQL_DML


# ============================================================
# Comment handling
# ============================================================

def strip_line_comment(line: str) -> str:
    """Remove trailing -- comments, respecting quoted strings."""
    in_single = False
    in_double = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double and line[i:i + 2] == "--":
            return line[:i]
        i += 1
    return line


def strip_block_comments(text: str) -> str:
    """Remove /* ... */ block comments from full text."""
    result: list[str] = []
    i = 0
    in_block = False
    while i < len(text):
        if not in_block:
            if text[i:i + 2] == "/*":
                in_block = True
                i += 2
                continue
            result.append(text[i])
        else:
            if text[i:i + 2] == "*/":
                in_block = False
                i += 2
                # Preserve newline so line numbers stay aligned
                result.append(" ")
                continue
        i += 1
    return "".join(result)


def is_comment_line(line: str) -> bool:
    """Check if a line is entirely a comment."""
    stripped = line.strip()
    return stripped.startswith("--") or stripped.startswith("/*")


def preprocess(text: str) -> list[str]:
    """Strip block comments and return lines with line comments intact."""
    cleaned = strip_block_comments(text)
    return cleaned.splitlines()


# ============================================================
# Block extractor (for CREATE TABLE)
# ============================================================

def extract_create_table_blocks(lines: list[str]) -> list[CreateTableBlock]:
    """Extract CREATE TABLE blocks with column definitions."""
    blocks: list[CreateTableBlock] = []
    i = 0
    while i < len(lines):
        stripped = strip_line_comment(lines[i]).strip()
        if is_comment_line(lines[i]):
            i += 1
            continue

        ct_match = re.match(
            r"CREATE\s+TABLE\s+\[?(\w[\w\s]*?)\]?\s*\(",
            stripped,
            re.IGNORECASE,
        )
        if not ct_match:
            # Also match CREATE TABLE name (\n on next line
            ct_match2 = re.match(
                r"CREATE\s+TABLE\s+\[?(\w[\w\s]*?)\]?\s*$",
                stripped,
                re.IGNORECASE,
            )
            if ct_match2:
                # Check if next non-empty line starts with (
                table_name = ct_match2.group(1).strip()
                start_line = i
                j = i + 1
                while j < len(lines) and not strip_line_comment(lines[j]).strip():
                    j += 1
                if j < len(lines) and strip_line_comment(lines[j]).strip().startswith("("):
                    block = _parse_create_table_body(
                        lines, table_name, start_line, j
                    )
                    if block:
                        blocks.append(block)
                        i = block.end_line
                        continue
            i += 1
            continue

        table_name = ct_match.group(1).strip()
        block = _parse_create_table_body(lines, table_name, i, i)
        if block:
            blocks.append(block)
            i = block.end_line
            continue

        i += 1
    return blocks


def _parse_create_table_body(
    lines: list[str],
    table_name: str,
    start_line: int,
    paren_line: int,
) -> CreateTableBlock | None:
    """Parse from opening ( to closing ) of a CREATE TABLE."""
    paren_depth = 0
    raw_lines: list[str] = []
    end_line = paren_line
    columns: list[ColumnDef] = []

    for j in range(paren_line, len(lines)):
        line_text = strip_line_comment(lines[j])
        raw_lines.append(lines[j])
        paren_depth += line_text.count("(") - line_text.count(")")

        # Parse column definitions (simple heuristic: name TYPE ...)
        col_stripped = line_text.strip().rstrip(",").strip()
        # Skip lines that are just ( or ) or CONSTRAINT
        if col_stripped and not col_stripped.startswith(("(", ")", "CONSTRAINT", "PRIMARY", "UNIQUE", "FOREIGN", "CHECK", "INDEX")):
            col_match = re.match(
                r"\[?(\w[\w\s]*?)\]?\s+(\w+)",
                col_stripped,
                re.IGNORECASE,
            )
            if col_match:
                col_name = col_match.group(1).strip()
                col_type = col_match.group(2).strip().upper()
                # Skip if the "column name" is actually a keyword like CREATE or TABLE
                if col_name.upper() not in ("CREATE", "TABLE", "ALTER", "ADD", "DROP", "MODIFY"):
                    has_auto = bool(
                        re.search(r"\bAUTOINCREMENT\b", col_stripped, re.IGNORECASE)
                    )
                    columns.append(ColumnDef(
                        name=col_name,
                        data_type=col_type,
                        full_text=col_stripped,
                        line=j + 1,
                        has_autoincrement=has_auto,
                    ))

        if paren_depth <= 0 and j > paren_line:
            end_line = j + 1
            break
        end_line = j + 1

    return CreateTableBlock(
        table_name=table_name,
        start_line=start_line + 1,
        end_line=end_line,
        columns=columns,
        raw_lines=raw_lines,
    )


# ============================================================
# Line-scoped rules (Pass 1)
# ============================================================

def check_av001(
    db: AccessDB, filename: str, line: str, lineno: int,
) -> list[Diagnostic]:
    """AV001: Table/field name is SQL reserved word without bracket escaping."""
    diags: list[Diagnostic] = []
    if not db.reserved_words:
        return diags

    # Check CREATE TABLE table_name
    ct_match = re.match(
        r"\s*CREATE\s+TABLE\s+(\w+)", line, re.IGNORECASE,
    )
    if ct_match:
        name = ct_match.group(1)
        if name.upper() in db.reserved_words:
            diags.append(_diag(
                filename, lineno, Severity.ERROR, "AV001",
                f"Table name '{name}' is a SQL reserved word. "
                f"Wrap in brackets: [{name}].",
            ))

    # Check ALTER TABLE table_name
    at_match = re.match(
        r"\s*ALTER\s+TABLE\s+(\w+)", line, re.IGNORECASE,
    )
    if at_match:
        name = at_match.group(1)
        if name.upper() in db.reserved_words:
            diags.append(_diag(
                filename, lineno, Severity.ERROR, "AV001",
                f"Table name '{name}' is a SQL reserved word. "
                f"Wrap in brackets: [{name}].",
            ))

    # Check INSERT INTO table_name
    ii_match = re.match(
        r"\s*INSERT\s+INTO\s+(\w+)", line, re.IGNORECASE,
    )
    if ii_match:
        name = ii_match.group(1)
        if name.upper() in db.reserved_words:
            diags.append(_diag(
                filename, lineno, Severity.ERROR, "AV001",
                f"Table name '{name}' is a SQL reserved word. "
                f"Wrap in brackets: [{name}].",
            ))

    # Check field definitions in column lines: field_name TYPE
    # Match unbracketed identifiers followed by a known data type
    col_match = re.match(r"\s*(\w+)\s+(\w+)", line)
    if col_match:
        field_name = col_match.group(1)
        possible_type = col_match.group(2).upper()
        # Only flag if the second word looks like a data type
        if possible_type in db.access_data_types or possible_type in (
            "LONG", "SHORT", "TEXT", "MEMO", "YESNO", "DATETIME",
            "CURRENCY", "DOUBLE", "SINGLE", "BYTE", "INTEGER",
            "COUNTER", "AUTOINCREMENT", "OLEOBJECT", "BINARY",
            "GUID", "DECIMAL", "FLOAT", "REAL", "CHAR", "VARCHAR",
            "BOOLEAN", "DATE", "TIME", "TIMESTAMP", "NUMBER",
            "NUMERIC", "BIGINT", "SMALLINT", "TINYINT", "BIT",
            "IMAGE", "VARBINARY", "NTEXT", "NCHAR", "NVARCHAR",
        ):
            if field_name.upper() in db.reserved_words:
                # Avoid duplicate with CREATE/ALTER/INSERT matches above
                if field_name.upper() not in (
                    "CREATE", "ALTER", "INSERT", "DROP", "SELECT",
                    "UPDATE", "DELETE", "TABLE", "INTO",
                ):
                    diags.append(_diag(
                        filename, lineno, Severity.ERROR, "AV001",
                        f"Field name '{field_name}' is a SQL reserved word. "
                        f"Wrap in brackets: [{field_name}].",
                    ))

    return diags


def check_av002(
    filename: str, line: str, lineno: int,
) -> list[Diagnostic]:
    """AV002: Deprecated Jet data type."""
    diags: list[Diagnostic] = []
    for dtype, (sev_str, msg) in DEPRECATED_JET_TYPES.items():
        if re.search(rf"\b{dtype}\b", line, re.IGNORECASE):
            severity = Severity.ERROR if sev_str == "ERROR" else Severity.WARNING
            diags.append(_diag(
                filename, lineno, severity, "AV002", msg,
            ))
    return diags


def check_av003(filename: str, line: str, lineno: int) -> list[Diagnostic]:
    """AV003: Name contains spaces (needs bracket escaping)."""
    diags: list[Diagnostic] = []

    # Check CREATE TABLE with space in name but no brackets
    ct_match = re.match(
        r"\s*CREATE\s+TABLE\s+(\w+\s+\w+)", line, re.IGNORECASE,
    )
    if ct_match:
        candidate = ct_match.group(1)
        # If second word is not a keyword like ( or a paren, it might be a spaced name
        # But this is hard to distinguish from CREATE TABLE Name (
        # So we look specifically for unbracketed multi-word names
        pass

    # Check for bracketed names that contain spaces (informational)
    for match in re.finditer(r"\[([^\]]+)\]", line):
        name = match.group(1)
        if " " in name:
            diags.append(_diag(
                filename, lineno, Severity.WARNING, "AV003",
                f"Name '[{name}]' contains spaces. "
                "Consider using PascalCase or underscores instead.",
            ))

    return diags


def check_av004(
    filename: str, line: str, lineno: int, raw_line: str,
) -> list[Diagnostic]:
    """AV004: Missing semicolon terminator."""
    diags: list[Diagnostic] = []
    stripped = line.strip()
    if not stripped:
        return diags

    # Only check lines that appear to be complete SQL statements
    # A complete statement ends a clause and is not part of a multi-line block
    # We check for lines that start with a SQL keyword and don't end with ;
    # But skip lines that are clearly continuations (start with comma, AND, OR, etc.)
    # This is checked more accurately at file level; here we check single-line statements
    if SQL_STATEMENT_STARTERS.match(stripped):
        # Single-line complete statements (contain both start keyword and don't have
        # an opening paren without closing, suggesting multi-line)
        open_parens = stripped.count("(")
        close_parens = stripped.count(")")
        if open_parens <= close_parens and not stripped.endswith(";"):
            # Check it looks like a complete statement (has a table name at minimum)
            words = stripped.split()
            if len(words) >= 3:
                diags.append(_diag(
                    filename, lineno, Severity.ERROR, "AV004",
                    "SQL statement does not end with a semicolon.",
                ))

    return diags


def check_av005(filename: str, line: str, lineno: int) -> list[Diagnostic]:
    """AV005: SELECT * usage."""
    if re.search(r"\bSELECT\s+\*", line, re.IGNORECASE):
        return [_diag(
            filename, lineno, Severity.WARNING, "AV005",
            "SELECT * found. Use an explicit column list instead.",
        )]
    return []


def check_av007(filename: str, line: str, lineno: int) -> list[Diagnostic]:
    """AV007: Table name not in PascalCase (segments separated by underscores)."""
    diags: list[Diagnostic] = []

    # Match CREATE TABLE [Name] or CREATE TABLE Name
    ct_match = re.match(
        r"\s*CREATE\s+TABLE\s+\[?(\w+)\]?",
        line,
        re.IGNORECASE,
    )
    if not ct_match:
        return diags

    table_name = ct_match.group(1)
    segments = table_name.split("_")
    for segment in segments:
        if not segment:
            continue
        if not PASCAL_SEGMENT_RE.match(segment):
            diags.append(_diag(
                filename, lineno, Severity.WARNING, "AV007",
                f"Table name '{table_name}' segment '{segment}' does not start "
                "with uppercase. Convention: PascalCase segments (e.g., GL_Accounts).",
            ))
            break  # One diagnostic per table name is enough

    return diags


def check_av008(filename: str, line: str, lineno: int) -> list[Diagnostic]:
    """AV008: AUTOINCREMENT on non-LONG field."""
    if not re.search(r"\bAUTOINCREMENT\b", line, re.IGNORECASE):
        return []

    # Check that LONG precedes AUTOINCREMENT
    if re.search(r"\bLONG\b", line, re.IGNORECASE):
        return []
    # Also accept COUNTER (Access synonym)
    if re.search(r"\bCOUNTER\b", line, re.IGNORECASE):
        return []

    return [_diag(
        filename, lineno, Severity.ERROR, "AV008",
        "AUTOINCREMENT used on a non-LONG field. "
        "AUTOINCREMENT requires LONG (or COUNTER) data type.",
    )]


def run_line_rules(
    db: AccessDB, filename: str, lines: list[str],
) -> list[Diagnostic]:
    """Run all line-scoped rules (Pass 1)."""
    diags: list[Diagnostic] = []
    for i, raw_line in enumerate(lines):
        lineno = i + 1
        if is_comment_line(raw_line):
            continue
        line = strip_line_comment(raw_line)

        diags.extend(check_av001(db, filename, line, lineno))
        diags.extend(check_av002(filename, line, lineno))
        diags.extend(check_av003(filename, line, lineno))
        diags.extend(check_av004(filename, line, lineno, raw_line))
        diags.extend(check_av005(filename, line, lineno))
        diags.extend(check_av007(filename, line, lineno))
        diags.extend(check_av008(filename, line, lineno))

    return diags


# ============================================================
# Block-scoped rules (Pass 2)
# ============================================================

def check_av006(
    db: AccessDB, filename: str, block: CreateTableBlock,
) -> list[Diagnostic]:
    """AV006: FK reference validation (_ID fields reference known tables)."""
    diags: list[Diagnostic] = []
    if not db.known_tables:
        return diags

    for col in block.columns:
        if not col.name.upper().endswith("_ID"):
            continue
        # Derive referenced table name: strip _ID suffix
        # e.g., Department_ID -> Department, GL_Account_ID -> GL_Account
        ref_table = col.name[:-3]  # Remove _ID
        if not ref_table:
            continue

        # Check if any known table matches (case-insensitive)
        # Also try common pluralisation: add "s" or "es"
        candidates = {
            ref_table.upper(),
            (ref_table + "s").upper(),
            (ref_table + "es").upper(),
        }
        found = False
        for candidate in candidates:
            if candidate in db.known_tables:
                found = True
                break
        if not found:
            diags.append(_diag(
                filename, col.line, Severity.ERROR, "AV006",
                f"Field '{col.name}' appears to reference table '{ref_table}' "
                f"(via _ID convention), but no matching table found in database. "
                f"Known tables: {', '.join(sorted(db.known_tables))}.",
            ))

    return diags


def run_block_rules(
    db: AccessDB, filename: str, blocks: list[CreateTableBlock],
) -> list[Diagnostic]:
    """Run all block-scoped rules (Pass 2)."""
    diags: list[Diagnostic] = []
    for block in blocks:
        diags.extend(check_av006(db, filename, block))
    return diags


# ============================================================
# File-scoped rules (Pass 3)
# ============================================================

def run_file_rules(
    db: AccessDB, filename: str, lines: list[str],
) -> list[Diagnostic]:
    """Run all file-scoped rules (Pass 3). Placeholder for future rules."""
    return []


# ============================================================
# Main pipeline
# ============================================================

def lint_file(db: AccessDB, filepath: str) -> list[Diagnostic]:
    """Run all lint passes on a single .sql file."""
    try:
        with open(filepath, encoding="utf-8") as f:
            raw_text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        return [_diag(filepath, 0, Severity.ERROR, "AV000", f"Cannot read file: {e}")]

    lines = preprocess(raw_text)
    file_type = detect_file_type(filepath, raw_text)

    # Pass 1: line rules
    diags = run_line_rules(db, filepath, lines)

    # Pass 2: block rules
    blocks = extract_create_table_blocks(lines)
    diags.extend(run_block_rules(db, filepath, blocks))

    # Pass 3: file rules
    diags.extend(run_file_rules(db, filepath, lines))

    return diags


def resolve_files(paths: list[str]) -> list[str]:
    """Expand directories to .sql files, pass through individual files."""
    files: list[str] = []
    for path in paths:
        if os.path.isdir(path):
            for root, _dirs, filenames in os.walk(path):
                for fn in sorted(filenames):
                    if fn.endswith(".sql"):
                        files.append(os.path.join(root, fn))
        elif os.path.isfile(path) and path.endswith(".sql"):
            files.append(path)
        else:
            print(
                f"Warning: skipping '{path}' (not a .sql file or directory)",
                file=sys.stderr,
            )
    return files


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Access SQL static analysis linter for .sql files",
        epilog="Exit codes: 0=clean, 1=warnings, 2=errors",
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to lint")
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="Only show errors and warnings, suppress info",
    )
    parser.add_argument(
        "--errors-only", action="store_true",
        help="Only show ERROR severity",
    )
    parser.add_argument(
        "--fix", action="store_true",
        help="Auto-fix placeholder (not yet implemented for Access SQL)",
    )
    args = parser.parse_args()

    files = resolve_files(args.paths)
    if not files:
        print("No .sql files found.", file=sys.stderr)
        sys.exit(0)

    db = AccessDB(DB_PATH)

    # Auto-fix placeholder
    if args.fix:
        print("Auto-fix not yet implemented for Access SQL. Linting only.\n")

    all_diags: list[Diagnostic] = []
    try:
        for filepath in files:
            all_diags.extend(lint_file(db, filepath))
    finally:
        db.close()

    # Filter by severity
    if args.errors_only:
        all_diags = [d for d in all_diags if d.severity == Severity.ERROR]
    elif args.quiet:
        all_diags = [d for d in all_diags if d.severity != Severity.INFO]

    # Sort and output
    severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
    all_diags.sort(key=lambda d: (d.file, d.line, severity_order[d.severity]))
    for diag in all_diags:
        print(diag)

    # Summary
    errors = sum(1 for d in all_diags if d.severity == Severity.ERROR)
    warnings = sum(1 for d in all_diags if d.severity == Severity.WARNING)
    infos = sum(1 for d in all_diags if d.severity == Severity.INFO)

    print(
        f"\n--- Linted {len(files)} file(s): "
        f"{errors} error(s), {warnings} warning(s), {infos} info(s) ---"
    )

    sys.exit(2 if errors > 0 else 1 if warnings > 0 else 0)


if __name__ == "__main__":
    main()
