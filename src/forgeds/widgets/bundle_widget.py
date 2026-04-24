"""forgeds-bundle-widget — produce an upload-ready widget ZIP.

Phase 2C Task 6. Validation chain per spec §6.2:

  1. widget-spec.yaml schema           (WSP via spec_loader)
  2. plugin-manifest.json schema       (WG004 via validate_manifest)
  3. Cross-refs                        (WSP003)
  4. Structural                        (index.html, index.js present)
  5. Ready-for-upload                  (TODO tokens, size limits — BND004/005)

Each step halts on ERROR, continues on WARNING. If `--skip-lint` is
absent, `forgeds-lint-widgets` is invoked as a subprocess against the
widget tree (not in-process), and its ERRORs halt / WARNINGs propagate.

Bundling uses `zet_shim.run_zet_pack()` by default. With `--no-zet`, a
stdlib `zipfile` fallback builds the same ZIP directly. The fallback
excludes `widget-spec.yaml` because the spec is authoring-only and not
needed at runtime.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

from forgeds._shared.config import load_config, find_project_root
from forgeds._shared.diagnostics import Diagnostic, Severity
from forgeds._shared.envelope import to_json_v1
from forgeds._shared.output_format import UnknownFormatError, resolve_format
from forgeds.widgets.spec_loader import load_spec, check_cross_refs
from forgeds.widgets.validate_manifest import validate_manifest_file
from forgeds.widgets.zet_shim import run_zet_pack


# UNVERIFIED size limits per spec §6.2 — sourced from Zoho community
# posts, not official docs. Flagged in rule docstring and user-facing
# diagnostic message.
_MANIFEST_SIZE_LIMIT_KB = 64
_JS_SIZE_LIMIT_MB = 2


def _diag(file: str, sev: Severity, code: str, message: str) -> Diagnostic:
    return Diagnostic(file=file, line=1, rule=code, severity=sev, message=message)


# ============================================================
# Widget resolution
# ============================================================


def _resolve_widget(config: dict, widget_name: str | None) -> tuple[str | None, dict | None, Diagnostic | None]:
    """Pick the target widget from forgeds.yaml `widgets:` block.

    Returns (name, widget_def, diag_or_None). If diag is non-None the
    caller should halt.
    """
    widgets = config.get("widgets") or {}
    if not isinstance(widgets, dict):
        return (None, None, _diag("forgeds.yaml", Severity.ERROR, "BND001",
                                  "widgets: block is not a dict"))
    if not widgets:
        return (None, None, _diag("forgeds.yaml", Severity.ERROR, "BND001",
                                  "no widgets declared in forgeds.yaml"))
    if widget_name is None:
        if len(widgets) == 1:
            name = next(iter(widgets))
            return (name, widgets[name], None)
        return (None, None, _diag("forgeds.yaml", Severity.ERROR, "BND001",
                                  f"multiple widgets declared ({sorted(widgets.keys())}); "
                                  "pass --widget to pick one"))
    if widget_name not in widgets:
        return (None, None, _diag("forgeds.yaml", Severity.ERROR, "BND001",
                                  f"widget {widget_name!r} not declared in forgeds.yaml"))
    return (widget_name, widgets[widget_name], None)


# ============================================================
# Validation steps
# ============================================================


def _validate_spec(spec_path: Path) -> tuple[dict, list[Diagnostic], bool]:
    """Step 1 — widget-spec.yaml schema. Returns (spec, diags, halt)."""
    spec, diags = load_spec(str(spec_path))
    has_err = any(d.severity == Severity.ERROR for d in diags)
    return (spec, diags, has_err)


def _validate_manifest(manifest_path: Path) -> tuple[dict | None, list[Diagnostic], bool]:
    """Step 2 — plugin-manifest.json schema."""
    diags = validate_manifest_file(str(manifest_path))
    has_err = any(d.severity == Severity.ERROR for d in diags)
    manifest = None
    if manifest_path.exists():
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
        except (OSError, json.JSONDecodeError):
            manifest = None
    return (manifest, diags, has_err)


def _validate_cross_refs(
    spec: dict, manifest: dict | None, directory_name: str, config: dict,
) -> tuple[list[Diagnostic], bool]:
    """Step 3 — cross-ref spec vs manifest vs directory name vs config."""
    diags = check_cross_refs(spec, manifest, directory_name, config)
    has_err = any(d.severity == Severity.ERROR for d in diags)
    return (diags, has_err)


def _validate_structural(widget_root: Path, manifest: dict | None) -> tuple[list[Diagnostic], bool]:
    """Step 4 — required files present, manifest-declared entry file exists."""
    diags: list[Diagnostic] = []
    required = ["index.html", "index.js"]
    for fname in required:
        if not (widget_root / fname).is_file():
            diags.append(_diag(str(widget_root / fname), Severity.ERROR, "BND001",
                               f"required widget file missing: {fname}"))

    # Check manifest's declared entry url exists (per Phase 1 schema)
    if manifest is not None:
        try:
            entries = manifest["config"]["widgets"]
            for e in entries:
                url = e.get("url")
                if url:
                    target = widget_root / url
                    if not target.exists():
                        diags.append(_diag(str(widget_root / url), Severity.ERROR, "BND001",
                                           f"manifest config.widgets[].url {url!r} "
                                           "does not exist on disk"))
        except (KeyError, TypeError):
            pass  # already reported by manifest validator

    return (diags, any(d.severity == Severity.ERROR for d in diags))


def _validate_ready_for_upload(widget_root: Path) -> list[Diagnostic]:
    """Step 5 — TODO tokens + size limits. WARNINGs only (non-halting)."""
    diags: list[Diagnostic] = []
    manifest_path = widget_root / "plugin-manifest.json"
    if manifest_path.exists():
        size_kb = manifest_path.stat().st_size / 1024
        if size_kb > _MANIFEST_SIZE_LIMIT_KB:
            diags.append(_diag(str(manifest_path), Severity.WARNING, "BND004",
                               f"plugin-manifest.json is {size_kb:.1f} KB "
                               f"(>{_MANIFEST_SIZE_LIMIT_KB} KB UNVERIFIED Zoho limit)"))
    for js_file in widget_root.rglob("*.js"):
        size_mb = js_file.stat().st_size / (1024 * 1024)
        if size_mb > _JS_SIZE_LIMIT_MB:
            diags.append(_diag(str(js_file), Severity.WARNING, "BND004",
                               f"{js_file.name} is {size_mb:.2f} MB "
                               f"(>{_JS_SIZE_LIMIT_MB} MB UNVERIFIED Zoho limit)"))
    # TODO-token scan in index.js
    idx_js = widget_root / "index.js"
    if idx_js.is_file():
        try:
            text = idx_js.read_text(encoding="utf-8")
            if "TODO:" in text or "TODO(" in text:
                diags.append(_diag(str(idx_js), Severity.WARNING, "BND005",
                                   "index.js contains TODO tokens (ship-as-skeleton)"))
        except (OSError, UnicodeDecodeError):
            pass
    return diags


def _run_lint(widget_root: Path) -> list[Diagnostic]:
    """Invoke forgeds-lint-widgets as a subprocess and surface findings.

    Sim finding F2: subprocess invocation, not in-process import --
    decouples bundler from lint internals and mirrors Phase 1 ESLint
    pattern.
    """
    diags: list[Diagnostic] = []
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "forgeds.widgets.lint_widgets",
             "--format", "json-v1", str(widget_root)],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        diags.append(_diag(str(widget_root), Severity.WARNING, "BND003",
                           f"lint subprocess failed: {exc}"))
        return diags

    # Parse JSON-v1 envelope from stdout
    stdout = (completed.stdout or "").strip()
    if not stdout:
        return diags
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        diags.append(_diag(str(widget_root), Severity.WARNING, "BND003",
                           "lint subprocess emitted non-JSON output"))
        return diags

    for d in payload.get("diagnostics", []):
        sev_str = d.get("severity", "info").upper()
        try:
            sev = Severity[sev_str]
        except KeyError:
            sev = Severity.INFO
        # Preserve the original rule/message from the lint output.
        # Map ERROR → BND001 aggregate for halting behaviour; pass
        # WARNINGs as BND003 for non-halting propagation.
        if sev == Severity.ERROR:
            diags.append(_diag(d.get("file", ""), Severity.ERROR, "BND001",
                               f"lint error propagated from {d.get('rule', '?')}: "
                               f"{d.get('message', '')}"))
        elif sev == Severity.WARNING:
            diags.append(_diag(d.get("file", ""), Severity.WARNING, "BND003",
                               f"lint warning propagated from {d.get('rule', '?')}: "
                               f"{d.get('message', '')}"))
    return diags


# ============================================================
# Bundling
# ============================================================


def _bundle_no_zet(widget_root: Path, zip_path: Path) -> None:
    """Pure-Python ZIP fallback. Excludes widget-spec.yaml + dotfiles."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(widget_root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(widget_root)
            # Skip authoring-only + hidden files
            parts = rel.parts
            if any(part.startswith(".") for part in parts):
                continue
            if parts[-1] == "widget-spec.yaml":
                continue
            zf.write(p, arcname=str(rel))


# ============================================================
# Main
# ============================================================


def _emit_output(tool: str, diags: list[Diagnostic], fmt: str) -> None:
    if fmt == "json-v1":
        print(to_json_v1(tool, diags))
    else:
        for d in diags:
            print(str(d))


def _resolve_widget_root(project_root: Path, widget_def: dict, widget_name: str) -> Path:
    root_rel = (widget_def.get("root") or "").rstrip("/\\")
    if root_rel:
        return (project_root / root_rel).resolve()
    # default
    return (project_root / "src" / "widgets" / widget_name).resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bundle a widget into an upload-ready ZIP.",
    )
    parser.add_argument("--widget", help="Widget name (from forgeds.yaml widgets: block).")
    parser.add_argument("--output", help="Directory for the output ZIP. "
                                         "Default: <project-root>/dist/widgets/")
    parser.add_argument("--no-zet", action="store_true",
                        help="Use the pure-Python ZIP fallback (skip zet pack).")
    parser.add_argument("--skip-lint", action="store_true",
                        help="Do not run forgeds-lint-widgets before bundling.")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite an existing output ZIP.")
    parser.add_argument("--verbose", action="store_true",
                        help="Pass -v to zet pack (no effect under --no-zet).")
    parser.add_argument("--format", choices=["text", "json-v1"], default=None)
    args = parser.parse_args(argv)

    try:
        fmt = resolve_format(args.format)
    except UnknownFormatError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    tool = "bundle_widget"

    diagnostics: list[Diagnostic] = []
    project_root = find_project_root()
    config = load_config()

    # Resolve target widget
    widget_name, widget_def, resolve_diag = _resolve_widget(config, args.widget)
    if resolve_diag is not None:
        diagnostics.append(resolve_diag)
        _emit_output(tool, diagnostics, fmt)
        return 2
    widget_root = _resolve_widget_root(project_root, widget_def, widget_name)
    if not widget_root.is_dir():
        diagnostics.append(_diag(str(widget_root), Severity.ERROR, "BND001",
                                 f"widget root {widget_root} does not exist"))
        _emit_output(tool, diagnostics, fmt)
        return 2

    # Step 1 — spec
    spec_path = widget_root / "widget-spec.yaml"
    spec, spec_diags, halt = _validate_spec(spec_path)
    diagnostics.extend(spec_diags)
    if halt:
        diagnostics.append(_diag(str(spec_path), Severity.ERROR, "BND001",
                                 "widget-spec validation failed; halting"))
        _emit_output(tool, diagnostics, fmt)
        return 2

    # Step 2 — manifest
    manifest_path = widget_root / "plugin-manifest.json"
    manifest, manifest_diags, halt = _validate_manifest(manifest_path)
    diagnostics.extend(manifest_diags)
    if halt:
        diagnostics.append(_diag(str(manifest_path), Severity.ERROR, "BND001",
                                 "plugin-manifest validation failed; halting"))
        _emit_output(tool, diagnostics, fmt)
        return 2

    # Step 3 — cross-refs
    cr_diags, halt = _validate_cross_refs(spec, manifest, widget_root.name, config)
    diagnostics.extend(cr_diags)
    if halt:
        _emit_output(tool, diagnostics, fmt)
        return 2

    # Step 4 — structural
    st_diags, halt = _validate_structural(widget_root, manifest)
    diagnostics.extend(st_diags)
    if halt:
        _emit_output(tool, diagnostics, fmt)
        return 2

    # Optional lint
    if not args.skip_lint:
        lint_diags = _run_lint(widget_root)
        diagnostics.extend(lint_diags)
        if any(d.severity == Severity.ERROR for d in lint_diags):
            _emit_output(tool, diagnostics, fmt)
            return 2

    # Step 5 — ready-for-upload (warnings only)
    diagnostics.extend(_validate_ready_for_upload(widget_root))

    # Output path
    output_dir = Path(args.output).resolve() if args.output else (project_root / "dist" / "widgets")
    version = (manifest or {}).get("version", "0.0.0")
    zip_path = output_dir / f"{widget_name}-{version}.zip"

    if zip_path.exists() and not args.force:
        diagnostics.append(_diag(str(zip_path), Severity.ERROR, "BND006",
                                 f"output {zip_path} exists (use --force)"))
        _emit_output(tool, diagnostics, fmt)
        return 2

    # Bundle
    if args.no_zet:
        try:
            _bundle_no_zet(widget_root, zip_path)
        except OSError as exc:
            diagnostics.append(_diag(str(zip_path), Severity.ERROR, "BND002",
                                     f"pure-Python ZIP failed: {exc}"))
            _emit_output(tool, diagnostics, fmt)
            return 2
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        result = run_zet_pack(str(widget_root), str(output_dir), verbose=args.verbose)
        if result.returncode == 3:
            diagnostics.append(_diag(str(widget_root), Severity.ERROR, "BND002",
                                     "zet not available. " + result.stderr))
            _emit_output(tool, diagnostics, fmt)
            return 3
        if result.returncode == 2:
            diagnostics.append(_diag(str(widget_root), Severity.ERROR, "BND002",
                                     f"zet pack failed: {result.stderr}"))
            _emit_output(tool, diagnostics, fmt)
            return 2
        if result.returncode != 0:
            diagnostics.append(_diag(str(widget_root), Severity.ERROR, "BND002",
                                     f"zet pack exited {result.returncode}: {result.stderr}"))
            _emit_output(tool, diagnostics, fmt)
            return 2
        if result.stderr.strip():
            diagnostics.append(_diag(str(widget_root), Severity.WARNING, "BND003",
                                     f"zet pack stderr: {result.stderr.strip()}"))
        # zet pack wrote to output_dir; rename to canonical name if needed.
        if not zip_path.exists():
            # Best-effort: look for any .zip that zet just produced and rename.
            candidates = sorted(output_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
            if candidates:
                candidates[0].rename(zip_path)

    _emit_output(tool, diagnostics, fmt)
    errors = any(d.severity == Severity.ERROR for d in diagnostics)
    warnings = any(d.severity == Severity.WARNING for d in diagnostics)
    return 2 if errors else (1 if warnings else 0)


if __name__ == "__main__":
    sys.exit(main())
