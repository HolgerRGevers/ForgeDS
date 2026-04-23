"""forgeds-run-widget — Python orchestrator for the Phase 2B runtime harness.

Spawns the Node harness subprocess for each widget declared in forgeds.yaml,
parses the call log from stdout, and emits WGR### diagnostics describing
declared-vs-observed API drift, init throws, timeouts, and permission
mismatches.

Exit codes:
  0  clean (no WGR diagnostics)
  1  warnings only
  2  any error
  3  Node missing (matches Phase 1 widget-lint posture)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from forgeds._shared.config import (
    find_project_root,
    load_config_with_diagnostics,
    resolve_widget_entry_point,
)
from forgeds._shared.diagnostics import Diagnostic, Severity
from forgeds._shared.envelope import to_json_v1
from forgeds._shared.output_format import UnknownFormatError, resolve_format

HARNESS_PATH = Path(__file__).parent / "runtime" / "harness.js"

# Methods whose first string argument names a Custom API.
_INVOKE_METHODS = {
    "ZOHO.CREATOR.API.invokeCustomApi",
    "ZOHO.CREATOR.API.invokeApi",
    "ZOHO.CREATOR.API.invokeConnection",
    "ZOHO.CREATOR.API.callFunction",
}

INSTALL_HINT = (
    "Node not found. forgeds-run-widget requires Node >= 18.\n"
    "  Install from https://nodejs.org or via nvm/fnm.\n"
)


def _node_available() -> bool:
    return shutil.which("node") is not None


def _mk_diag(file: str, rule: str, severity: Severity, message: str, line: int = 1) -> Diagnostic:
    return Diagnostic(file=file, line=line, rule=rule, severity=severity, message=message)


def _read_manifest_permissions(manifest_path: Path) -> list[str] | None:
    if not manifest_path.exists():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    perms = data.get("permissions")
    if isinstance(perms, list) and all(isinstance(p, str) for p in perms):
        return perms
    return None


def _observed_custom_apis(call_log: list[dict]) -> list[str]:
    """Return Custom API names invoked via any invoke* family method."""
    out: list[str] = []
    for entry in call_log:
        method = entry.get("method")
        if method in _INVOKE_METHODS:
            args = entry.get("args") or []
            if args and isinstance(args[0], str):
                out.append(args[0])
    return out


def _run_harness_for_widget(
    entry_point: Path, widget_root: Path, widget_name: str, timeout_ms: int
) -> dict:
    """Invoke the Node harness and return the parsed stdout JSON.

    Returns a dict with at least `status` key; for catastrophic failures
    returns `{'status': 'harness_crashed', 'error': {...}}` so callers can
    emit WGR-meta without needing to branch on subprocess exceptions.
    """
    cmd = [
        "node", str(HARNESS_PATH),
        "--widget-root", str(widget_root),
        "--entry-point", str(entry_point),
        "--widget-name", widget_name,
        "--timeout-ms", str(timeout_ms),
    ]
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=(timeout_ms / 1000) + 5,
        )
    except subprocess.TimeoutExpired as exc:
        return {"status": "harness_crashed", "error": {"message": f"subprocess timeout: {exc}"}}

    stdout = (r.stdout or "").strip()
    if not stdout:
        return {
            "status": "harness_crashed",
            "error": {"message": (r.stderr or "no output from harness").strip()[:512]},
        }
    last_line = stdout.splitlines()[-1]
    try:
        return json.loads(last_line)
    except json.JSONDecodeError:
        return {
            "status": "harness_crashed",
            "error": {"message": f"non-JSON stdout: {last_line[:256]}"},
        }


def _diagnose_widget(
    widget_name: str,
    widget_def: dict,
    project_root: Path,
    timeout_ms: int,
) -> list[Diagnostic]:
    """Run one widget end-to-end and return its Diagnostic list."""
    diags: list[Diagnostic] = []

    root_rel = (widget_def.get("root") or "").rstrip("/\\")
    widget_root = (project_root / root_rel).resolve() if root_rel else project_root.resolve()
    entry_point = resolve_widget_entry_point(widget_def, project_root)
    manifest_path = widget_root / "plugin-manifest.json"

    file_ref = str(entry_point) if entry_point.exists() else str(widget_root)

    if not entry_point.exists():
        diags.append(_mk_diag(
            file_ref, "WGR-meta", Severity.ERROR,
            f"widget {widget_name!r}: entry point not found at {entry_point}. "
            "Add an index.js under the widget root, or set `entry_point` in "
            "forgeds.yaml.",
        ))
        return diags

    payload = _run_harness_for_widget(
        entry_point=entry_point,
        widget_root=widget_root,
        widget_name=widget_name,
        timeout_ms=timeout_ms,
    )

    status = payload.get("status")
    call_log: list[dict] = payload.get("callLog") or []
    permissions_observed: list[str] = payload.get("permissionsObserved") or []

    if status == "harness_crashed":
        msg = (payload.get("error") or {}).get("message") or "unknown harness failure"
        diags.append(_mk_diag(
            str(entry_point), "WGR-meta", Severity.ERROR,
            f"widget {widget_name!r}: harness crashed ({msg})",
        ))
        return diags

    if status == "timeout":
        diags.append(_mk_diag(
            str(entry_point), "WGR-meta", Severity.ERROR,
            f"widget {widget_name!r}: runtime timeout after {timeout_ms} ms",
        ))
        # Fall through — partial call log is still informative.

    if status == "throw":
        err = payload.get("error") or {}
        msg = (err.get("message") or "").strip() or "threw during init"
        diags.append(_mk_diag(
            str(entry_point), "WGR002", Severity.ERROR,
            f"widget {widget_name!r} threw during init: {msg}",
        ))

    # WGR001 — declared-vs-observed diff against Custom APIs
    declared = set(widget_def.get("consumes_apis") or [])
    observed = set(_observed_custom_apis(call_log))
    for api in sorted(observed - declared):
        diags.append(_mk_diag(
            str(entry_point), "WGR001", Severity.ERROR,
            f"widget {widget_name!r} invoked Custom API {api!r} but it is not in consumes_apis",
        ))
    for api in sorted(declared - observed):
        diags.append(_mk_diag(
            str(entry_point), "WGR001", Severity.WARNING,
            f"widget {widget_name!r} declares {api!r} in consumes_apis but never invoked it",
        ))

    # WGR004 — observed permissions must be ⊆ declared manifest permissions.
    manifest_perms = _read_manifest_permissions(manifest_path)
    if manifest_perms is not None:
        extra = sorted(set(permissions_observed) - set(manifest_perms))
        if extra:
            diags.append(_mk_diag(
                str(manifest_path), "WGR004", Severity.ERROR,
                f"widget {widget_name!r} invoked methods requiring "
                f"{extra!r} but plugin-manifest.json declares only {manifest_perms!r}",
            ))

    # WGR-meta — unknown SDK methods reached via Proxy fallback.
    for entry in call_log:
        if entry.get("responseKind") == "undeclared-method":
            diags.append(_mk_diag(
                str(entry_point), "WGR-meta", Severity.WARNING,
                f"widget {widget_name!r} invoked SDK method "
                f"{entry.get('method')!r} not present in zoho_widget_sdk.db "
                "(mock drift — regenerate via forgeds-build-widget-db + gen_sdk_mock)",
            ))

    return diags


def _render_text(widget_results: dict[str, list[Diagnostic]]) -> str:
    out: list[str] = []
    total_errors = 0
    total_warnings = 0
    for widget_name, diags in widget_results.items():
        out.append(f"=== forgeds-run-widget: {widget_name} ===")
        if not diags:
            out.append("  (clean)")
        for d in diags:
            sev = d.severity.value.upper()
            out.append(f"  {sev:<8} [{d.rule}] {d.message}")
            if d.severity is Severity.ERROR:
                total_errors += 1
            elif d.severity is Severity.WARNING:
                total_warnings += 1
    out.append("")
    out.append(
        f"Summary: {total_errors} error(s), {total_warnings} warning(s) "
        f"across {len(widget_results)} widget(s)"
    )
    return "\n".join(out)


def _exit_code(all_diags: list[Diagnostic], errors_only: bool) -> int:
    if any(d.severity is Severity.ERROR for d in all_diags):
        return 2
    if not errors_only and any(d.severity is Severity.WARNING for d in all_diags):
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="forgeds-run-widget",
        description="Run each widget under a mocked SDK and emit WGR diagnostics.",
    )
    parser.add_argument("--widget", help="Only run this widget (exact match).")
    parser.add_argument(
        "--format", choices=["text", "json-v1"], default=None,
        help="Output format (default: text; env FORGEDS_OUTPUT also honoured).",
    )
    parser.add_argument("--config", help="Path to forgeds.yaml (override auto-discover).")
    parser.add_argument("--timeout-ms", type=int, default=10000)
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("--errors-only", action="store_true")
    args = parser.parse_args()

    try:
        fmt = resolve_format(args.format)
    except UnknownFormatError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not _node_available():
        sys.stderr.write(INSTALL_HINT)
        return 3

    if args.config:
        config_path = Path(args.config).resolve()
        start = str(config_path.parent)
    else:
        start = None
    cfg, cfg_diags = load_config_with_diagnostics(start=start)

    project_root = Path(args.config).resolve().parent if args.config else find_project_root()

    widgets = cfg.get("widgets") or {}
    if args.widget:
        if args.widget not in widgets:
            sys.stderr.write(f"error: widget {args.widget!r} not declared in forgeds.yaml\n")
            return 2
        widgets = {args.widget: widgets[args.widget]}

    widget_results: dict[str, list[Diagnostic]] = {}
    for name, widget_def in widgets.items():
        widget_results[name] = _diagnose_widget(
            name, widget_def, project_root, args.timeout_ms
        )

    all_diags: list[Diagnostic] = []
    for diags in widget_results.values():
        all_diags.extend(diags)

    if fmt == "json-v1":
        print(to_json_v1("forgeds-run-widget", all_diags))
    else:
        print(_render_text(widget_results))

    return _exit_code(all_diags, args.errors_only)


if __name__ == "__main__":
    sys.exit(main())
