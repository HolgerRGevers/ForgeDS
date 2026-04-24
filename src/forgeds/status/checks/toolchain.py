"""Toolchain checks: Python / Node / ESLint version surface."""

from __future__ import annotations

import platform
import shutil
import subprocess

from forgeds._shared.config import load_config
from forgeds.status.checks import StatusCheck


def _capture_version(cmd: list[str], timeout: int = 10) -> tuple[bool, str]:
    """Run cmd --version; return (ok, output). OK means exit 0 + some output."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return (False, str(exc))
    output = (r.stdout or r.stderr or "").strip().splitlines()
    first = output[0] if output else ""
    return (r.returncode == 0, first)


def run(start: str | None = None) -> list[StatusCheck]:
    """Check Python / Node / ESLint. Node + ESLint only required if widgets declared."""
    checks: list[StatusCheck] = [StatusCheck(
        category="toolchain",
        id="python",
        status="ok",
        message=platform.python_version(),
        rule=None,
    )]

    cfg = load_config(start) if start is not None else load_config()
    widgets = cfg.get("widgets") or {}
    needs_node = bool(widgets)

    if not needs_node:
        checks.append(StatusCheck(
            category="toolchain",
            id="node",
            status="skip",
            message="no widgets declared — Node check skipped",
            rule=None,
        ))
        checks.append(StatusCheck(
            category="toolchain",
            id="eslint",
            status="skip",
            message="no widgets declared — ESLint check skipped",
            rule=None,
        ))
        return checks

    if shutil.which("node"):
        ok, ver = _capture_version(["node", "--version"])
        checks.append(StatusCheck(
            category="toolchain",
            id="node",
            status="ok" if ok else "fail",
            message=ver if ok else "node on PATH but --version failed",
            rule=None if ok else "STA004",
        ))
    else:
        checks.append(StatusCheck(
            category="toolchain",
            id="node",
            status="fail",
            message="node not on PATH (required by declared widgets)",
            rule="STA004",
        ))

    ok, ver = _capture_version(["npx", "--yes", "eslint", "--version"])
    if ok:
        checks.append(StatusCheck(
            category="toolchain",
            id="eslint",
            status="ok",
            message=ver,
            rule=None,
        ))
    else:
        checks.append(StatusCheck(
            category="toolchain",
            id="eslint",
            status="fail",
            message="ESLint not resolvable via npx (required for forgeds-lint-widgets)",
            rule="STA005",
        ))

    return checks
