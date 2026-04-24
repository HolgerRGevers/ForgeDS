"""forgeds-deploy-widget — upload a widget ZIP to Zoho Creator.

Phase 2C Task 8. Dry-run is the default posture; --confirm is gated
behind the §7.5 research spike until the publish endpoint is verified.

Safety rails:
- --confirm requires --target.
- --dry-run + --confirm is a conflicting-flag error (DPY002).
- --confirm exits 3 unless BOTH env vars set:
    FORGEDS_DEPLOY_SPIKE_OVERRIDE_TESTONLY == "1"
    PYTEST_CURRENT_TEST is set (pytest sets this automatically)
  Production runs have neither -> always exit 3 with a §7.5 pointer.

The access token is never printed; only the source name (e.g.
`env:ZOHO_ACCESS_TOKEN`, `config:zoho-api.yaml`) is surfaced via
DPY004 INFO diagnostics.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

from forgeds._shared.config import find_project_root, load_config
from forgeds._shared.diagnostics import Diagnostic, Severity
from forgeds._shared.envelope import to_json_v1
from forgeds._shared.oauth import OAuthResolutionError, resolve_access_token
from forgeds._shared.output_format import UnknownFormatError, resolve_format
from forgeds.widgets.publish_client import compose_url, upload_widget_zip
from forgeds.widgets.spec_loader import load_spec, write_deployment_block


def _diag(file: str, sev: Severity, code: str, message: str) -> Diagnostic:
    return Diagnostic(file=file, line=1, rule=code, severity=sev, message=message)


# ============================================================
# Spike gate
# ============================================================


SPIKE_OVERRIDE_ENV = "FORGEDS_DEPLOY_SPIKE_OVERRIDE_TESTONLY"
PYTEST_CTX_ENV = "PYTEST_CURRENT_TEST"


def _spike_gate_open() -> bool:
    """True only when BOTH the test-only env AND pytest context are set.

    This double-lock prevents a misconfigured CI (setting the override env
    alone) from bypassing the spike gate. Production runs never set
    PYTEST_CURRENT_TEST, so this always returns False for them.
    """
    override = os.environ.get(SPIKE_OVERRIDE_ENV, "")
    pytest_ctx = os.environ.get(PYTEST_CTX_ENV, "")
    return override == "1" and bool(pytest_ctx)


_SPIKE_MESSAGE = (
    "forgeds-deploy-widget --confirm is gated on the §7.5 research spike. "
    "Use --dry-run to preview the request. The publish endpoint shape is "
    "UNVERIFIED; see docs/superpowers/specs/2026-04-23-forgeds-widgets-"
    "phase2c-build-design.md §7.5."
)


# ============================================================
# Widget / ZIP resolution
# ============================================================


def _resolve_zip(
    project_root: Path,
    config: dict,
    widget_name: str | None,
    explicit_zip: str | None,
) -> tuple[Path | None, str | None, str | None, Diagnostic | None]:
    """Pick the ZIP + widget_name + version. Returns (zip_path, name, version, diag)."""
    if explicit_zip:
        zp = Path(explicit_zip).resolve()
        if not zp.is_file():
            return (None, None, None,
                    _diag(str(zp), Severity.ERROR, "DPY001",
                          f"--zip path does not exist: {zp}"))
        # widget_name from filename stem, version parsed best-effort
        name = widget_name
        version = None
        if "-" in zp.stem:
            guess_name, _, guess_ver = zp.stem.rpartition("-")
            if not name:
                name = guess_name
            version = guess_ver
        if name is None:
            name = zp.stem
        return (zp, name, version, None)

    widgets = config.get("widgets") or {}
    if not isinstance(widgets, dict) or not widgets:
        return (None, None, None,
                _diag("forgeds.yaml", Severity.ERROR, "DPY001",
                      "no widgets declared in forgeds.yaml"))
    if widget_name is None:
        if len(widgets) == 1:
            widget_name = next(iter(widgets))
        else:
            return (None, None, None,
                    _diag("forgeds.yaml", Severity.ERROR, "DPY001",
                          "multiple widgets declared; pass --widget to pick one"))
    if widget_name not in widgets:
        return (None, None, None,
                _diag("forgeds.yaml", Severity.ERROR, "DPY001",
                      f"widget {widget_name!r} not declared in forgeds.yaml"))

    # Read manifest version from the widget tree
    widget_def = widgets[widget_name]
    root_rel = (widget_def.get("root") or "").rstrip("/\\")
    widget_root = (project_root / root_rel).resolve() if root_rel \
        else (project_root / "src" / "widgets" / widget_name).resolve()

    manifest_path = widget_root / "plugin-manifest.json"
    version = "0.0.0"
    if manifest_path.exists():
        try:
            version = json.loads(manifest_path.read_text(encoding="utf-8")).get("version", "0.0.0")
        except (OSError, json.JSONDecodeError):
            pass

    zp = project_root / "dist" / "widgets" / f"{widget_name}-{version}.zip"
    if not zp.is_file():
        return (None, None, None,
                _diag(str(zp), Severity.ERROR, "DPY001",
                      f"expected ZIP not found: {zp}. "
                      "Run forgeds-bundle-widget first."))
    return (zp, widget_name, version, None)


# ============================================================
# Main
# ============================================================


def _emit_output(tool: str, diags: list[Diagnostic], fmt: str) -> None:
    if fmt == "json-v1":
        print(to_json_v1(tool, diags))
    else:
        for d in diags:
            print(str(d))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Upload a widget ZIP to Zoho Creator (dry-run default).",
    )
    parser.add_argument("--widget", help="Widget name (from forgeds.yaml).")
    parser.add_argument("--zip", help="Explicit ZIP path (overrides --widget lookup).")
    parser.add_argument("--target",
                        help="Deploy target identifier (creator:app-id=<ID>). "
                             "Required for --confirm.")
    parser.add_argument("--token",
                        help="Explicit OAuth access token (discouraged; bypasses "
                             "env/config resolution). Redacted in all logs.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the HTTP request that would be sent; send nothing. "
                             "This is the default when --confirm is absent.")
    parser.add_argument("--confirm", action="store_true",
                        help="Actually upload. Currently gated on the §7.5 research spike.")
    parser.add_argument("--non-interactive", action="store_true",
                        help="Skip the type-'deploy' confirmation prompt "
                             "(still requires --confirm).")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--format", choices=["text", "json-v1"], default=None)
    parser.add_argument("--config",
                        help="Path to OAuth config file (default: "
                             "<project-root>/config/zoho-api.yaml).")
    args = parser.parse_args(argv)

    try:
        fmt = resolve_format(args.format)
    except UnknownFormatError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    tool = "deploy_widget"
    diagnostics: list[Diagnostic] = []

    # Flag conflicts
    if args.dry_run and args.confirm:
        diagnostics.append(_diag("(flags)", Severity.ERROR, "DPY002",
                                 "--dry-run and --confirm are mutually exclusive"))
        _emit_output(tool, diagnostics, fmt)
        return 2

    if args.confirm and not args.target:
        diagnostics.append(_diag("(flags)", Severity.ERROR, "DPY001",
                                 "--confirm requires --target"))
        _emit_output(tool, diagnostics, fmt)
        return 2

    # Spike gate — only checked when --confirm is requested
    if args.confirm and not _spike_gate_open():
        diagnostics.append(_diag("(spike)", Severity.ERROR, "DPY001",
                                 _SPIKE_MESSAGE))
        _emit_output(tool, diagnostics, fmt)
        return 3

    # Resolve ZIP / widget name / version
    project_root = find_project_root()
    config = load_config()
    zp, widget_name, version, resolve_diag = _resolve_zip(
        project_root, config, args.widget, args.zip,
    )
    if resolve_diag is not None:
        diagnostics.append(resolve_diag)
        _emit_output(tool, diagnostics, fmt)
        return 2

    # Resolve OAuth source
    config_path = args.config or str(project_root / "config" / "zoho-api.yaml")
    try:
        token, source = resolve_access_token(
            explicit_token=args.token,
            config_path=config_path,
        )
    except OAuthResolutionError as exc:
        lines = ["; ".join([f"{n}: {r}" for n, r in exc.attempted_sources])]
        diagnostics.append(_diag("(oauth)", Severity.ERROR, "DPY003",
                                 "No OAuth source resolved. " + lines[0]))
        _emit_output(tool, diagnostics, fmt)
        return 2

    diagnostics.append(_diag("(oauth)", Severity.INFO, "DPY004",
                             f"OAuth source: {source}"))

    # If dry-run (default when --confirm absent): print and exit 0
    is_dry_run = args.dry_run or (not args.confirm)
    target_for_url = args.target or "creator:app-id=<unset>"
    url = compose_url(target_for_url) if args.target else "<unset>"
    if is_dry_run:
        if fmt == "text":
            print(f"[dry-run] method=POST url={url}")
            print(f"[dry-run] headers=Authorization: Zoho-oauthtoken <redacted>")
            print(f"[dry-run] headers=Content-Type: multipart/form-data; boundary=...")
            print(f"[dry-run] body: file={zp} (size={zp.stat().st_size} bytes); "
                  f"metadata={{name: {widget_name!r}, version: {version!r}}}")
        diagnostics.append(_diag("(dry-run)", Severity.INFO, "DPY004",
                                 f"would POST to {url} (body not sent)"))
        _emit_output(tool, diagnostics, fmt)
        return 0

    # --- From here on we are in --confirm mode and the spike gate is open ---

    if not args.non_interactive:
        print("=" * 50)
        print(f"About to DEPLOY widget {widget_name!r}")
        print(f"  version: {version}")
        print(f"  target:  {args.target}")
        print(f"  zip:     {zp} ({zp.stat().st_size} bytes)")
        print(f"  OAuth:   {source}")
        print("=" * 50)
        try:
            reply = input("Type 'deploy' to confirm: ")
        except (EOFError, KeyboardInterrupt):
            reply = ""
        if reply.strip() != "deploy":
            diagnostics.append(_diag("(confirm)", Severity.WARNING, "DPY004",
                                     "user did not type 'deploy'; aborting"))
            _emit_output(tool, diagnostics, fmt)
            return 1

    result = upload_widget_zip(
        zip_path=str(zp),
        widget_name=widget_name,
        version=version or "0.0.0",
        access_token=token,
        target=args.target,
    )
    diagnostics.extend(result.diagnostics)

    if not result.ok:
        _emit_output(tool, diagnostics, fmt)
        return 2

    # Success — write deployment block back to widget-spec.yaml
    try:
        widgets = config.get("widgets") or {}
        widget_def = widgets.get(widget_name, {})
        root_rel = (widget_def.get("root") or "").rstrip("/\\")
        widget_root = (project_root / root_rel).resolve() if root_rel \
            else (project_root / "src" / "widgets" / widget_name).resolve()
        spec_path = widget_root / "widget-spec.yaml"
        if spec_path.exists():
            write_deployment_block(str(spec_path), {
                "last_uploaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(
                    timespec="seconds"
                ).replace("+00:00", "Z"),
                "last_uploaded_version": version or "0.0.0",
                "last_uploaded_target": args.target,
            })
    except Exception as exc:
        diagnostics.append(_diag(str(spec_path), Severity.WARNING, "DPY004",
                                 f"upload succeeded but deployment block write failed: {exc}"))

    _emit_output(tool, diagnostics, fmt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
