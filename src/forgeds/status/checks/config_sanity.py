"""Config-sanity checks: forgeds.yaml parse + custom_apis/widgets validation."""

from __future__ import annotations

from pathlib import Path

from forgeds._shared.config import find_project_root, load_config_with_diagnostics
from forgeds._shared.diagnostics import Severity
from forgeds.status.checks import StatusCheck

SEVERITY_TO_STATUS = {
    Severity.ERROR: "fail",
    Severity.WARNING: "warn",
    Severity.INFO: "ok",
}


def run(start: str | None = None) -> list[StatusCheck]:
    """Return status checks. If forgeds.yaml is missing or unparseable the
    first entry is STA001 (fail); caller may choose to early-abort on it."""
    root = find_project_root(start)
    config_path = root / "forgeds.yaml"

    if not config_path.exists():
        return [StatusCheck(
            category="config_sanity",
            id="forgeds.yaml",
            status="fail",
            message=f"forgeds.yaml not found under {root}",
            rule="STA001",
        )]

    try:
        cfg, cfg_diags = load_config_with_diagnostics(start=str(root))
    except Exception as exc:  # parser failure
        return [StatusCheck(
            category="config_sanity",
            id="forgeds.yaml",
            status="fail",
            message=f"forgeds.yaml failed to parse: {exc}",
            rule="STA001",
        )]

    checks: list[StatusCheck] = [StatusCheck(
        category="config_sanity",
        id="forgeds.yaml",
        status="ok",
        message=f"found at {config_path}",
        rule=None,
    )]

    if cfg_diags:
        for d in cfg_diags:
            checks.append(StatusCheck(
                category="config_sanity",
                id=f"custom_apis.{d.rule}",
                status=SEVERITY_TO_STATUS.get(d.severity, "warn"),
                message=d.message,
                rule=d.rule,
            ))
    else:
        checks.append(StatusCheck(
            category="config_sanity",
            id="custom_apis",
            status="ok",
            message=f"{len(cfg.get('custom_apis') or {})} declared, all well-formed",
            rule=None,
        ))

    return checks
