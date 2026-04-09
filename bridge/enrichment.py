"""Auto-enrichment module — error logging and lint pattern classification."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

ERRORS_FILE = "forgeds_errors.json"


def _errors_path() -> Path:
    """Return path to the errors log file (next to the bridge package)."""
    return Path(__file__).resolve().parent.parent / ERRORS_FILE


def log_error(error_data: dict) -> dict:
    """Append an error entry to forgeds_errors.json.

    Args:
        error_data: Dict with at least ``message`` key. Optional keys:
            ``source``, ``file``, ``line``, ``rule``.

    Returns:
        The stored entry (with ``timestamp`` added).
    """
    path = _errors_path()

    # Load existing entries
    entries: list[dict] = []
    if path.exists():
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            entries = []

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **error_data,
    }
    entries.append(entry)

    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    return entry


def classify_pattern(error: dict) -> dict:
    """Determine whether an error represents a new lint pattern.

    Args:
        error: Dict with ``message``, optional ``rule``, ``file``.

    Returns:
        Dict with ``is_new_pattern`` bool, ``category`` str, ``confidence`` float.
    """
    rule = error.get("rule", "")
    message = error.get("message", "")

    # Known categories from the Deluge linter
    known_rules = {
        "single-quote-string",
        "missing-null-guard",
        "loginuserrole-usage",
        "missing-added-user",
        "lpad-usage",
        "hoursBetween-usage",
        "threshold-value",
        "esg-missing",
        "carbon-factor-guard",
    }

    if rule in known_rules:
        return {
            "is_new_pattern": False,
            "category": "known_lint_rule",
            "confidence": 1.0,
        }

    # Heuristic: if the message mentions a Deluge keyword, it is likely lintable
    deluge_keywords = ["ifnull", "zoho.", "input.", "insert into", "sendmail", "alert"]
    for kw in deluge_keywords:
        if kw in message.lower():
            return {
                "is_new_pattern": True,
                "category": "potential_lint_rule",
                "confidence": 0.6,
            }

    return {
        "is_new_pattern": False,
        "category": "generic_error",
        "confidence": 0.3,
    }


def update_linter_db(pattern: dict) -> dict:
    """Placeholder for auto-updating the Deluge lint database.

    In a future iteration this will invoke ``forgeds-build-db`` with the
    new pattern injected. For now it just records intent.

    Args:
        pattern: Dict describing the new lint pattern.

    Returns:
        Status dict.
    """
    # TODO: invoke `forgeds-build-db` with enriched pattern data
    return {
        "status": "pending",
        "message": "Auto-update of linter DB is not yet implemented. Pattern recorded.",
        "pattern": pattern,
    }
