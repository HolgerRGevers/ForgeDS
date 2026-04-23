"""JSON v1 envelope serializers — single source of truth.

No other module may serialize the ForgeDS JSON envelope. Linters and
forgeds-status import from here. New fields on the envelope require a
version bump per CLAUDE.md's envelope versioning policy.
"""

from __future__ import annotations

import json
from typing import Iterable, Literal

from forgeds._shared.diagnostics import Diagnostic

ENVELOPE_VERSION = "1"
StatusToken = Literal["ok", "warn", "fail", "miss", "skip"]
OverallToken = Literal["ok", "warn", "fail"]


def to_json_v1(tool: str, diagnostics: Iterable[Diagnostic]) -> str:
    """Serialize a list of Diagnostics as the JSON-v1 envelope."""
    payload = {
        "tool": tool,
        "version": ENVELOPE_VERSION,
        "diagnostics": [
            {
                "file": d.file,
                "line": d.line,
                "rule": d.rule,
                "severity": d.severity.value.lower(),
                "message": d.message,
            }
            for d in diagnostics
        ],
    }
    return json.dumps(payload)


def status_envelope_v1(
    tool: str,
    overall: OverallToken,
    checks: list[dict],
) -> str:
    """Serialize a forgeds-status aggregate report as the JSON-v1 envelope.

    Each check dict must carry keys: category, id, status, message, rule (nullable).
    """
    payload = {
        "tool": tool,
        "version": ENVELOPE_VERSION,
        "overall": overall,
        "checks": checks,
    }
    return json.dumps(payload)


def derive_overall(check_statuses: list[str]) -> OverallToken:
    """Collapse per-check statuses into overall: miss->fail, skip->ok."""
    if any(s in ("fail", "miss") for s in check_statuses):
        return "fail"
    if any(s == "warn" for s in check_statuses):
        return "warn"
    return "ok"
