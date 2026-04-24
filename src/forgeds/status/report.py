"""Render forgeds-status output as text banner or JSON-v1 envelope."""

from __future__ import annotations

from forgeds._shared.envelope import derive_overall, status_envelope_v1
from forgeds.status.checks import StatusCheck

SECTION_TITLES = {
    "config_sanity": "Config Sanity",
    "db_freshness": "Database Freshness",
    "toolchain": "Toolchain",
    "lint_summary": "Lint Summary",
}

SECTION_ORDER = ["db_freshness", "config_sanity", "lint_summary", "toolchain"]

TOKEN = {
    "ok":   "OK  ",
    "warn": "WARN",
    "fail": "FAIL",
    "miss": "MISS",
    "skip": "SKIP",
}


def _overall_for_exit(checks: list[StatusCheck]) -> str:
    return derive_overall([c.status for c in checks])


def render_text(checks: list[StatusCheck]) -> str:
    lines: list[str] = ["ForgeDS Project Health Report", "=" * 30]
    for cat in SECTION_ORDER:
        group = [c for c in checks if c.category == cat]
        if not group:
            continue
        lines.append(f"{SECTION_TITLES[cat]}:")
        for c in group:
            rule_suffix = f"  [{c.rule}]" if c.rule else ""
            lines.append(f"  {TOKEN[c.status]} {c.id:<28} {c.message}{rule_suffix}")
        lines.append("")

    overall = _overall_for_exit(checks)
    exit_hint = {"ok": 0, "warn": 1, "fail": 2}[overall]
    lines.append(f"Overall: {overall.upper()} (exit {exit_hint})")
    return "\n".join(lines)


def render_json(checks: list[StatusCheck]) -> str:
    overall = _overall_for_exit(checks)
    return status_envelope_v1(
        tool="forgeds-status",
        overall=overall,
        checks=[c.to_dict() for c in checks],
    )


def exit_code(checks: list[StatusCheck]) -> int:
    overall = _overall_for_exit(checks)
    return {"ok": 0, "warn": 1, "fail": 2}[overall]
