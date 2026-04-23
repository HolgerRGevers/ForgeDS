"""Lint-summary check: spawn each linter in JSON-v1 mode, aggregate counts."""

from __future__ import annotations

import json
import os
import subprocess
import sys

from forgeds._shared.config import load_config
from forgeds.status.checks import StatusCheck

LINTERS = [
    ("forgeds.core.lint_deluge",     "forgeds-lint",         "Deluge",  []),
    ("forgeds.access.lint_access",   "forgeds-lint-access",  "Access",  []),
    ("forgeds.hybrid.lint_hybrid",   "forgeds-lint-hybrid",  "Hybrid",  None),  # no positional paths
    ("forgeds.widgets.lint_widgets", "forgeds-lint-widgets", "Widgets", None),
]


def _invoke_linter(module: str, paths: list[str] | None) -> tuple[int, dict | None, str]:
    """Invoke a linter with FORGEDS_OUTPUT=json-v1.

    Returns (returncode, parsed_envelope_or_None, stderr).
    """
    env = os.environ.copy()
    env["FORGEDS_OUTPUT"] = "json-v1"
    cmd = [sys.executable, "-m", module]
    if paths is not None:
        if not paths:
            return (0, {"tool": module, "version": "1", "diagnostics": []}, "")
        cmd.extend(paths)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return (99, None, str(exc))
    parsed: dict | None = None
    if r.stdout.strip():
        try:
            parsed = json.loads(r.stdout.strip())
        except json.JSONDecodeError:
            parsed = None
    return (r.returncode, parsed, r.stderr)


def run(start: str | None = None) -> list[StatusCheck]:
    """Run all linters in json-v1 mode and summarize counts."""
    checks: list[StatusCheck] = []
    cfg = load_config(start) if start is not None else load_config()
    widgets = cfg.get("widgets") or {}

    for module, tool, label, default_paths in LINTERS:
        if module.endswith("lint_widgets") and not widgets:
            checks.append(StatusCheck(
                category="lint_summary",
                id=tool,
                status="skip",
                message="no widgets declared — skipped",
                rule=None,
            ))
            continue

        rc, env_obj, stderr = _invoke_linter(module, default_paths)

        if rc == 3 and tool == "forgeds-lint-widgets":
            checks.append(StatusCheck(
                category="lint_summary",
                id=tool,
                status="warn",
                message=f"{label}: toolchain unavailable (exit 3)",
                rule="STA005",
            ))
            continue

        if env_obj is None:
            checks.append(StatusCheck(
                category="lint_summary",
                id=tool,
                status="fail",
                message=f"{label} subprocess produced no parseable envelope "
                        f"(exit {rc}): {stderr.strip()[:200]}",
                rule="STA006",
            ))
            continue

        diags = env_obj.get("diagnostics") or []
        errs = sum(1 for d in diags if d.get("severity") == "error")
        warns = sum(1 for d in diags if d.get("severity") == "warning")

        if errs:
            status = "fail"
        elif warns:
            status = "warn"
        else:
            status = "ok"

        checks.append(StatusCheck(
            category="lint_summary",
            id=tool,
            status=status,
            message=f"{errs} error(s), {warns} warning(s)",
            rule=None,
        ))

    return checks
