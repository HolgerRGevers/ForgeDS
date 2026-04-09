#!/usr/bin/env python3
"""
Deluge Script Linter for Zoho Creator .dg files.

Static analysis tool that catches common Deluge scripting errors,
enforces project conventions, and validates field references.
Backed by a SQLite database of Deluge language data.

Usage:
    python -m forgeds.core.lint_deluge src/deluge/           # lint all .dg files
    python -m forgeds.core.lint_deluge path/to/file.dg       # lint one file

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

DB_PATH = get_db_dir() / "deluge_lang.db"

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}(:\d{2})?)?$")
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

_config = load_config()
_lint_cfg = _config.get("lint", {})
THRESHOLD_FALLBACK = _lint_cfg.get("threshold_fallback", "999.99")
DUAL_THRESHOLD_FALLBACK = _lint_cfg.get("dual_threshold_fallback", "5000.00")
DEMO_EMAIL_DOMAINS = set(_lint_cfg.get("demo_email_domains", ["yourdomain.com", "example.com", "placeholder.com"]))


# ============================================================
# Enums
# ============================================================

class FileType(str, Enum):
    FORM_WORKFLOW = "form-workflow"
    APPROVAL_SCRIPT = "approval-script"
    SCHEDULED = "scheduled"


# ============================================================
# Data classes
# ============================================================

@dataclass
class FieldAssignment:
    name: str
    value: str
    line: int
    separator: str  # "=" or ":"


@dataclass
class Block:
    block_type: str             # "insert" | "sendmail" | "invokeUrl"
    target_table: str | None
    start_line: int
    end_line: int
    fields: dict[str, FieldAssignment] = field(default_factory=dict)
    raw_lines: list[str] = field(default_factory=list)


# ============================================================
# Helper: create Diagnostic with shared dataclass field names
# ============================================================

def _diag(filename: str, line: int, severity: Severity, code: str, message: str) -> Diagnostic:
    """Create a Diagnostic using the shared dataclass signature."""
    return Diagnostic(file=filename, line=line, rule=code, severity=severity, message=message)


# ============================================================
# Database-backed lookup cache
# ============================================================

class DelugeDB:
    """Read-only cache of Deluge language data from SQLite."""

    def __init__(self, db_path: Path) -> None:
        if not db_path.exists():
            raise FileNotFoundError(
                f"Deluge language DB not found at {db_path}. "
                "Run: python -m forgeds.core.build_deluge_db"
            )
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._load_caches()

    def _query_set(self, sql: str) -> set[str]:
        return {row[0] for row in self._conn.execute(sql).fetchall()}

    def _load_caches(self) -> None:
        self.valid_statuses: set[str] = self._query_set(
            "SELECT value FROM valid_statuses"
        )
        self.valid_actions: set[str] = self._query_set(
            "SELECT value FROM valid_actions"
        )
        self.reserved_words: set[str] = self._query_set(
            "SELECT word FROM reserved_words"
        )
        self.zoho_variable_names: set[str] = self._query_set(
            "SELECT name FROM zoho_variables"
        )
        self.function_names: set[str] = self._query_set(
            "SELECT DISTINCT name FROM functions"
        )
        self.banned_functions: dict[str, str] = {
            row["pattern"]: row["message"]
            for row in self._conn.execute(
                "SELECT pattern, message FROM banned_patterns WHERE pattern_type = 'function'"
            ).fetchall()
        }
        self.banned_variables: dict[str, str] = {
            row["pattern"]: row["message"]
            for row in self._conn.execute(
                "SELECT pattern, message FROM banned_patterns WHERE pattern_type = 'variable'"
            ).fetchall()
        }

        # Form fields: { form_name: { field_link_name, ... } }
        self.form_fields: dict[str, set[str]] = {}
        for row in self._conn.execute("SELECT form_name, field_link FROM form_fields"):
            form = row["form_name"]
            if form not in self.form_fields:
                self.form_fields[form] = set()
            self.form_fields[form].add(row["field_link"])

        # Expense_claims fields (used for input.X validation)
        self.expense_fields: set[str] = self.form_fields.get("expense_claims", set())

        # Approval_history fields (used for insert validation)
        self.approval_history_fields: set[str] = self.form_fields.get(
            "approval_history", set()
        )

        # Sendmail required params
        row = self._conn.execute(
            "SELECT required_params FROM builtin_tasks WHERE name = 'sendmail'"
        ).fetchone()
        self.sendmail_required: set[str] = (
            set(row["required_params"].split(",")) if row and row["required_params"] else set()
        )

        # InvokeUrl required params
        row = self._conn.execute(
            "SELECT required_params FROM builtin_tasks WHERE name = 'invokeUrl'"
        ).fetchone()
        self.invoke_url_required: set[str] = (
            set(row["required_params"].split(",")) if row and row["required_params"] else set()
        )

    def close(self) -> None:
        self._conn.close()


# ============================================================
# File type detection
# ============================================================

def detect_file_type(filepath: str) -> FileType:
    """Determine script context from file path."""
    normalized = filepath.replace("\\", "/")
    if "/scheduled/" in normalized:
        return FileType.SCHEDULED
    if "/approval-scripts/" in normalized:
        return FileType.APPROVAL_SCRIPT
    return FileType.FORM_WORKFLOW


# ============================================================
# Comment handling
# ============================================================

def strip_comments(line: str) -> str:
    """Remove trailing // comments, respecting double-quoted strings."""
    in_string = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '"' and (i == 0 or line[i - 1] != '\\'):
            in_string = not in_string
        elif not in_string and line[i:i + 2] == '//':
            return line[:i]
        i += 1
    return line


def is_comment_line(line: str) -> bool:
    """Check if line is a full-line comment."""
    stripped = line.strip()
    return stripped.startswith("//") or stripped.startswith("/*")


# ============================================================
# Block extractor (Pass 1)
# ============================================================

def extract_blocks(lines: list[str]) -> list[Block]:
    """Extract multi-line insert into/sendmail/invokeUrl blocks."""
    blocks: list[Block] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if is_comment_line(stripped):
            i += 1
            continue

        # Detect insert into
        insert_match = re.search(r"\binsert\s+into\s+(\w+)", stripped, re.IGNORECASE)
        if insert_match:
            block = _extract_bracket_block(
                lines, i, "insert", insert_match.group(1)
            )
            if block:
                blocks.append(block)
                i = block.end_line
                continue

        # Detect sendmail
        if re.search(r"\bsendmail\b", stripped, re.IGNORECASE):
            block = _extract_bracket_block(lines, i, "sendmail", None)
            if block:
                blocks.append(block)
                i = block.end_line
                continue

        # Detect invokeUrl
        if re.search(r"\binvokeUrl\b", stripped, re.IGNORECASE):
            block = _extract_bracket_block(lines, i, "invokeUrl", None)
            if block:
                blocks.append(block)
                i = block.end_line
                continue

        i += 1
    return blocks


def _extract_bracket_block(
    lines: list[str],
    start_idx: int,
    block_type: str,
    target_table: str | None,
) -> Block | None:
    """Extract a [...] delimited block starting near start_idx."""
    # Find opening [
    bracket_line: int | None = None
    for j in range(start_idx, min(start_idx + 3, len(lines))):
        if "[" in lines[j]:
            bracket_line = j
            break
    if bracket_line is None:
        return None

    # Collect until closing ]
    raw_lines: list[str] = []
    end_idx = bracket_line
    for j in range(bracket_line, len(lines)):
        raw_lines.append(lines[j])
        if "]" in lines[j] and j > bracket_line:
            end_idx = j
            break
        elif j == bracket_line and "]" in lines[j].split("[", 1)[-1]:
            end_idx = j
            break
        end_idx = j

    # Parse field assignments inside the block
    fields: dict[str, FieldAssignment] = {}
    for j in range(bracket_line + 1, end_idx + 1):
        line = lines[j].strip()
        if line.startswith(("]", "[")):
            continue
        if is_comment_line(line):
            continue

        eq_match = re.match(r"(\w+)\s*=\s*(.+?)(?:\s*$)", line)
        colon_match = re.match(r"(\w+)\s*:\s*(.+?)(?:\s*$)", line)

        if block_type == "insert":
            if eq_match:
                fname = eq_match.group(1)
                fields[fname] = FieldAssignment(
                    fname, eq_match.group(2).strip(), j + 1, "="
                )
            elif colon_match:
                fname = colon_match.group(1)
                fields[fname] = FieldAssignment(
                    fname, colon_match.group(2).strip(), j + 1, ":"
                )
        else:  # sendmail, invokeUrl
            if colon_match:
                fname = colon_match.group(1)
                fields[fname] = FieldAssignment(
                    fname, colon_match.group(2).strip(), j + 1, ":"
                )
            elif eq_match:
                fname = eq_match.group(1)
                fields[fname] = FieldAssignment(
                    fname, eq_match.group(2).strip(), j + 1, "="
                )

    return Block(
        block_type=block_type,
        target_table=target_table,
        start_line=start_idx + 1,
        end_line=end_idx + 1,
        fields=fields,
        raw_lines=raw_lines,
    )


# ============================================================
# Line-scoped rules (Pass 2)
# ============================================================

def check_dg001(db: DelugeDB, filename: str, line: str, lineno: int) -> list[Diagnostic]:
    """DG001: Banned function call."""
    diags: list[Diagnostic] = []
    for func, msg in db.banned_functions.items():
        if re.search(rf"\b{re.escape(func)}\s*\(", line):
            diags.append(_diag(filename, lineno, Severity.ERROR, "DG001", msg))
    return diags


def check_dg002(db: DelugeDB, filename: str, line: str, lineno: int) -> list[Diagnostic]:
    """DG002: Banned variable reference."""
    diags: list[Diagnostic] = []
    for var, msg in db.banned_variables.items():
        if re.search(rf"\b{re.escape(var)}\b", line):
            diags.append(_diag(filename, lineno, Severity.ERROR, "DG002", msg))
    return diags


def check_dg003(
    filename: str, line: str, lineno: int, file_type: FileType,
) -> list[Diagnostic]:
    """DG003: hoursBetween in scheduled scripts (Free Trial limitation)."""
    if file_type == FileType.SCHEDULED and re.search(r"\bhoursBetween\b", line):
        return [_diag(
            filename, lineno, Severity.ERROR, "DG003",
            "hoursBetween not available on Free Trial daily schedules. Use daysBetween.",
        )]
    return []


def check_dg004(
    db: DelugeDB, filename: str, line: str, lineno: int,
) -> list[Diagnostic]:
    """DG004: Unknown input.FieldName reference."""
    diags: list[Diagnostic] = []
    for match in re.finditer(r"\binput\.(\w+)", line):
        field_name = match.group(1)
        if field_name not in db.expense_fields:
            diags.append(_diag(
                filename, lineno, Severity.ERROR, "DG004",
                f"Unknown field 'input.{field_name}'. "
                "Valid fields: check docs/build-guide/field-link-names.md",
            ))
    return diags


def check_dg008(filename: str, line: str, lineno: int) -> list[Diagnostic]:
    """DG008: Single quotes used for text (not date/time)."""
    diags: list[Diagnostic] = []
    for match in re.finditer(r"'([^']*)'", line):
        content = match.group(1)
        if not content:
            continue
        if DATE_PATTERN.match(content) or TIME_PATTERN.match(content):
            continue
        diags.append(_diag(
            filename, lineno, Severity.ERROR, "DG008",
            f"Single quotes used for text '{content}'. "
            "Use double quotes for strings; single quotes are for dates/times only.",
        ))
    return diags


def check_dg011(
    db: DelugeDB, filename: str, line: str, lineno: int,
) -> list[Diagnostic]:
    """DG011: Unknown status value."""
    match = re.search(r'\.status\s*=\s*"([^"]*)"', line)
    if match:
        status = match.group(1)
        if status not in db.valid_statuses:
            return [_diag(
                filename, lineno, Severity.WARNING, "DG011",
                f'Unknown status value "{status}". '
                f"Valid: {', '.join(sorted(db.valid_statuses))}",
            )]
    return []


def check_dg013(filename: str, line: str, lineno: int) -> list[Diagnostic]:
    """DG013: Mixed && and || without parentheses."""
    if "&&" in line and "||" in line:
        return [_diag(
            filename, lineno, Severity.WARNING, "DG013",
            "Mixed && and || on same line. Creator evaluates OR before AND "
            "(opposite of most languages). Use explicit parentheses.",
        )]
    return []


def check_dg015_016(filename: str, line: str, lineno: int) -> list[Diagnostic]:
    """DG015/DG016: Hardcoded email addresses."""
    if "zoho.adminuserid" in line or "zoho.loginuserid" in line:
        return []
    diags: list[Diagnostic] = []
    for match in EMAIL_PATTERN.finditer(line):
        email = match.group(0)
        domain = email.split("@")[1].lower() if "@" in email else ""
        if any(d in domain for d in DEMO_EMAIL_DOMAINS) or "demo" in email.lower():
            diags.append(_diag(
                filename, lineno, Severity.WARNING, "DG015",
                f"Hardcoded demo/placeholder email '{email}'. "
                "Replace with role-based lookup for production.",
            ))
        else:
            diags.append(_diag(
                filename, lineno, Severity.INFO, "DG016",
                f"Hardcoded email '{email}'. Consider using role-based lookup.",
            ))
    return diags


def check_dg017(
    db: DelugeDB, filename: str, line: str, lineno: int,
) -> list[Diagnostic]:
    """DG017: Reserved word used as variable name."""
    # Match assignment patterns: word = value (but not == comparison)
    match = re.match(r"\s*(\w+)\s*=[^=]", line)
    if match:
        var_name = match.group(1)
        if var_name in db.reserved_words:
            return [_diag(
                filename, lineno, Severity.ERROR, "DG017",
                f"Reserved word '{var_name}' cannot be used as a variable name. "
                f"Reserved: {', '.join(sorted(db.reserved_words))}",
            )]
    return []


def check_dg018(
    db: DelugeDB, filename: str, line: str, lineno: int,
) -> list[Diagnostic]:
    """DG018: Unknown zoho system variable."""
    diags: list[Diagnostic] = []
    for match in re.finditer(r"\bzoho\.(\w+(?:\.\w+)*)", line):
        full_var = f"zoho.{match.group(1)}"
        if full_var not in db.zoho_variable_names:
            # Check if it's a banned variable (handled by DG002)
            if full_var in db.banned_variables:
                continue
            diags.append(_diag(
                filename, lineno, Severity.WARNING, "DG018",
                f"Unknown Zoho variable '{full_var}'. "
                f"Known: {', '.join(sorted(db.zoho_variable_names))}",
            ))
    return diags


def check_dg019(filename: str, line: str, lineno: int) -> list[Diagnostic]:
    """DG019: Added_User with zoho.adminuserid (must be zoho.adminuser or zoho.loginuser)."""
    if re.search(r"\bAdded_User\s*=\s*zoho\.adminuserid\b", line):
        return [_diag(
            filename, lineno, Severity.ERROR, "DG019",
            "Added_User only accepts zoho.loginuser or zoho.adminuser. "
            "zoho.adminuserid (email) is rejected by Creator. See discovery-log.md DL-001.",
        )]
    return []


def run_line_rules(
    db: DelugeDB, filename: str, lines: list[str], file_type: FileType,
) -> list[Diagnostic]:
    """Run all line-scoped rules."""
    diags: list[Diagnostic] = []
    for i, raw_line in enumerate(lines):
        lineno = i + 1
        if is_comment_line(raw_line):
            continue
        line = strip_comments(raw_line)

        diags.extend(check_dg001(db, filename, line, lineno))
        diags.extend(check_dg002(db, filename, line, lineno))
        diags.extend(check_dg003(filename, line, lineno, file_type))
        diags.extend(check_dg004(db, filename, line, lineno))
        diags.extend(check_dg008(filename, line, lineno))
        diags.extend(check_dg011(db, filename, line, lineno))
        diags.extend(check_dg013(filename, line, lineno))
        diags.extend(check_dg015_016(filename, line, lineno))
        diags.extend(check_dg017(db, filename, line, lineno))
        diags.extend(check_dg018(db, filename, line, lineno))
        diags.extend(check_dg019(filename, line, lineno))

    return diags


# ============================================================
# Block-scoped rules (Pass 3)
# ============================================================

def check_dg006(filename: str, block: Block) -> list[Diagnostic]:
    """DG006: Missing Added_User in insert into approval_history."""
    if block.block_type != "insert" or block.target_table != "approval_history":
        return []
    if "Added_User" not in block.fields:
        return [_diag(
            filename, block.start_line, Severity.ERROR, "DG006",
            "Missing 'Added_User = zoho.loginuser' in insert into approval_history block.",
        )]
    return []


VALID_ADDED_USER_VALUES = {"zoho.loginuser", "zoho.adminuser"}


def check_dg007(filename: str, block: Block) -> list[Diagnostic]:
    """DG007: Wrong Added_User value (must be zoho.loginuser or zoho.adminuserid for scheduled)."""
    if block.block_type != "insert" or block.target_table != "approval_history":
        return []
    if "Added_User" in block.fields:
        val = block.fields["Added_User"].value.strip()
        if val not in VALID_ADDED_USER_VALUES:
            return [_diag(
                filename, block.fields["Added_User"].line, Severity.ERROR, "DG007",
                f"Added_User must be 'zoho.loginuser' (or 'zoho.adminuser' for scheduled tasks), got '{val}'.",
            )]
    return []


def check_dg009(filename: str, block: Block) -> list[Diagnostic]:
    """DG009: Colon instead of = in insert into blocks."""
    if block.block_type != "insert":
        return []
    diags: list[Diagnostic] = []
    for fa in block.fields.values():
        if fa.separator == ":":
            diags.append(_diag(
                filename, fa.line, Severity.ERROR, "DG009",
                f"Field '{fa.name}' uses ':' separator in insert block. "
                "Use '=' (colons are for sendmail).",
            ))
    return diags


def check_dg010(db: DelugeDB, filename: str, block: Block) -> list[Diagnostic]:
    """DG010: Missing required sendmail/invokeUrl params."""
    if block.block_type == "sendmail":
        required = db.sendmail_required
    elif block.block_type == "invokeUrl":
        required = db.invoke_url_required
    else:
        return []

    diags: list[Diagnostic] = []
    param_names = {k.lower().strip() for k in block.fields}
    for req in required:
        if req not in param_names:
            diags.append(_diag(
                filename, block.start_line, Severity.ERROR, "DG010",
                f"Missing required {block.block_type} parameter '{req}'.",
            ))
    return diags


def check_dg012(db: DelugeDB, filename: str, block: Block) -> list[Diagnostic]:
    """DG012: Unknown action_1 value in audit trail."""
    if block.block_type != "insert" or block.target_table != "approval_history":
        return []
    if "action_1" in block.fields:
        val = block.fields["action_1"].value.strip().strip('"')
        if val not in db.valid_actions:
            return [_diag(
                filename, block.fields["action_1"].line, Severity.WARNING, "DG012",
                f'Unknown action_1 value "{val}". '
                f"Valid: {', '.join(sorted(db.valid_actions))}",
            )]
    return []


def check_dg014(filename: str, lines: list[str]) -> list[Diagnostic]:
    """DG014: Threshold fallback not 999.99 (or 5000.00 for dual thresholds)."""
    diags: list[Diagnostic] = []
    valid_thresholds = {float(THRESHOLD_FALLBACK), float(DUAL_THRESHOLD_FALLBACK)}
    for i, raw_line in enumerate(lines):
        lineno = i + 1
        if is_comment_line(raw_line):
            continue
        line = strip_comments(raw_line)

        # Direct threshold assignment
        match = re.search(
            r"\bthreshold\w*\s*=\s*(\d+\.?\d*)", line, re.IGNORECASE,
        )
        if match:
            val = match.group(1)
            try:
                if float(val) not in valid_thresholds:
                    diags.append(_diag(
                        filename, lineno, Severity.WARNING, "DG014",
                        f"Threshold fallback value is {val}, "
                        f"expected {THRESHOLD_FALLBACK} (tier 1) or {DUAL_THRESHOLD_FALLBACK} (dual).",
                    ))
            except ValueError:
                pass

        # ifnull with threshold context
        if "ifnull" in line and "threshold" in line.lower():
            ifnull_match = re.search(
                r"ifnull\s*\([^,]+,\s*(\d+\.?\d*)\s*\)", line,
            )
            if ifnull_match:
                val = ifnull_match.group(1)
                try:
                    if float(val) not in valid_thresholds:
                        diags.append(_diag(
                            filename, lineno, Severity.WARNING, "DG014",
                            f"Threshold ifnull fallback is {val}, "
                            f"expected {THRESHOLD_FALLBACK} (tier 1) or {DUAL_THRESHOLD_FALLBACK} (dual).",
                        ))
                except ValueError:
                    pass

    return diags


def run_block_rules(
    db: DelugeDB, filename: str, blocks: list[Block], lines: list[str],
) -> list[Diagnostic]:
    """Run all block-scoped rules."""
    diags: list[Diagnostic] = []
    for block in blocks:
        diags.extend(check_dg006(filename, block))
        diags.extend(check_dg007(filename, block))
        diags.extend(check_dg009(filename, block))
        diags.extend(check_dg010(db, filename, block))
        diags.extend(check_dg012(db, filename, block))
    diags.extend(check_dg014(filename, lines))
    return diags


# ============================================================
# File-scoped rules (Pass 4)
# ============================================================

def check_dg005(filename: str, lines: list[str]) -> list[Diagnostic]:
    """DG005: Query result used without null guard."""
    diags: list[Diagnostic] = []
    query_vars: dict[str, int] = {}
    guarded_vars: set[str] = set()
    guard_scopes: list[tuple[str, int]] = []
    brace_depth = 0

    for i, raw_line in enumerate(lines):
        lineno = i + 1
        if is_comment_line(raw_line):
            continue
        line = strip_comments(raw_line)

        brace_depth += line.count("{") - line.count("}")

        # Pop guard scopes when braces close
        while guard_scopes and brace_depth < guard_scopes[-1][1]:
            var = guard_scopes.pop()[0]
            guarded_vars.discard(var)

        # Detect query: var = TableName[criteria]
        q_match = re.match(r"\s*(\w+)\s*=\s*(\w+)\s*\[", line)
        if q_match:
            var_name = q_match.group(1)
            table_name = q_match.group(2)
            if table_name not in ("insert", "into", "if", "for", "while"):
                query_vars[var_name] = lineno

        # Detect null guard: if (var != null
        guard_match = re.search(r"if\s*\(\s*(\w+)\s*!=\s*null", line)
        if guard_match:
            var_name = guard_match.group(1)
            if var_name in query_vars:
                guarded_vars.add(var_name)
                guard_scopes.append((var_name, brace_depth))

        # Detect unguarded access: var.field
        for var_name, assign_line in query_vars.items():
            if var_name in guarded_vars or lineno == assign_line:
                continue
            if re.search(rf"\b{re.escape(var_name)}\.(\w+)", line):
                if guard_match and guard_match.group(1) == var_name:
                    continue
                diags.append(_diag(
                    filename, lineno, Severity.ERROR, "DG005",
                    f"Query result '{var_name}' accessed without null guard. "
                    f"Add: if ({var_name} != null && {var_name}.count() > 0)",
                ))
                guarded_vars.add(var_name)

    return diags


# ============================================================
# Auto-fix engine
# ============================================================

FIXABLE_RULES = {"DG006", "DG007", "DG008"}


def fix_file(db: DelugeDB, filepath: str) -> tuple[list[str], int]:
    """Apply auto-fixes to a file. Returns (fixed_lines, fix_count)."""
    try:
        with open(filepath, encoding="utf-8") as f:
            lines = [line.rstrip("\n\r") for line in f.readlines()]
    except (OSError, UnicodeDecodeError):
        return [], 0

    fix_count = 0

    # Fix DG008: single quotes for text -> double quotes
    for i, line in enumerate(lines):
        if is_comment_line(line):
            continue
        new_line = _fix_single_quotes(line)
        if new_line != line:
            lines[i] = new_line
            fix_count += 1

    # Fix DG006: add missing Added_User to approval_history inserts
    # Fix DG007: correct wrong Added_User value
    blocks = extract_blocks(lines)
    for block in blocks:
        if block.block_type != "insert" or block.target_table != "approval_history":
            continue

        if "Added_User" not in block.fields:
            # Insert Added_User before the closing ]
            insert_at = block.end_line - 1  # 0-based index of ] line
            indent = "    "
            # Find indentation from existing field lines
            for fa in block.fields.values():
                existing_line = lines[fa.line - 1]
                indent = existing_line[: len(existing_line) - len(existing_line.lstrip())]
                break
            lines.insert(insert_at, f"{indent}Added_User = zoho.loginuser")
            fix_count += 1
            # Adjust subsequent line numbers (blocks after this shift by 1)

        elif block.fields["Added_User"].value.strip() != "zoho.loginuser":
            # Fix wrong value
            fa = block.fields["Added_User"]
            line_idx = fa.line - 1
            lines[line_idx] = re.sub(
                r"Added_User\s*=\s*\S+",
                "Added_User = zoho.loginuser",
                lines[line_idx],
            )
            fix_count += 1

    return lines, fix_count


def _fix_single_quotes(line: str) -> str:
    """Replace single-quoted text strings with double quotes (not dates/times)."""
    def _replacer(m: re.Match[str]) -> str:
        content = m.group(1)
        if not content:
            return m.group(0)
        if DATE_PATTERN.match(content) or TIME_PATTERN.match(content):
            return m.group(0)
        return f'"{content}"'

    return re.sub(r"'([^']*)'", _replacer, line)


def apply_fixes(db: DelugeDB, files: list[str]) -> int:
    """Apply auto-fixes to all files. Returns total fix count."""
    total = 0
    for filepath in files:
        fixed_lines, count = fix_file(db, filepath)
        if count > 0:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(fixed_lines) + "\n")
            print(f"  Fixed {count} issue(s) in {filepath}")
            total += count
    return total


# ============================================================
# Main pipeline
# ============================================================

def lint_file(db: DelugeDB, filepath: str) -> list[Diagnostic]:
    """Run all lint passes on a single .dg file."""
    try:
        with open(filepath, encoding="utf-8") as f:
            raw_lines = f.readlines()
    except (OSError, UnicodeDecodeError) as e:
        return [_diag(filepath, 0, Severity.ERROR, "DG000", f"Cannot read file: {e}")]

    lines = [line.rstrip("\n\r") for line in raw_lines]
    file_type = detect_file_type(filepath)

    blocks = extract_blocks(lines)
    diags = run_line_rules(db, filepath, lines, file_type)
    diags.extend(run_block_rules(db, filepath, blocks, lines))
    diags.extend(check_dg005(filepath, lines))

    return diags


def resolve_files(paths: list[str]) -> list[str]:
    """Expand directories to .dg files, pass through individual files."""
    files: list[str] = []
    for path in paths:
        if os.path.isdir(path):
            for root, _dirs, filenames in os.walk(path):
                for fn in sorted(filenames):
                    if fn.endswith(".dg"):
                        files.append(os.path.join(root, fn))
        elif os.path.isfile(path) and path.endswith(".dg"):
            files.append(path)
        else:
            print(
                f"Warning: skipping '{path}' (not a .dg file or directory)",
                file=sys.stderr,
            )
    return files


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Deluge script linter for .dg files",
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
        help=f"Auto-fix fixable rules ({', '.join(sorted(FIXABLE_RULES))}), then re-lint",
    )
    args = parser.parse_args()

    files = resolve_files(args.paths)
    if not files:
        print("No .dg files found.", file=sys.stderr)
        sys.exit(0)

    db = DelugeDB(DB_PATH)

    # Auto-fix pass
    if args.fix:
        print("Auto-fixing...")
        total_fixes = apply_fixes(db, files)
        if total_fixes:
            print(f"Applied {total_fixes} fix(es). Re-linting...\n")
        else:
            print("No auto-fixable issues found.\n")

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
