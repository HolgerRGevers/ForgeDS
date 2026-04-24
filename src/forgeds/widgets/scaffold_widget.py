"""forgeds-scaffold-widget — emit a widget source tree from widget-spec.yaml.

Phase 2C Task 4. Stdlib only; templates use `str.format_map()` (no Jinja).

Emits the 5-file widget tree at `<output>/<name>/`:
- `widget-spec.yaml`     (copy of input, canonicalised)
- `plugin-manifest.json` (minimal Phase 1-schema-valid)
- `index.js`             (spec-driven TODO stubs)
- `index.html`           (shell pointing at index.js + styles.css)
- `styles.css`           (empty, with header comment)

Design notes:
- The manifest shape follows the Phase 1 schema
  (`src/forgeds/widgets/configs/plugin-manifest.schema.json`), not the
  illustrative shape in Phase 2C spec §5.4. The spec's `widget_location`
  / `entry` fields are not present in the Phase 1 schema; using
  `config.widgets[]` + `url` keeps scaffolder output immediately valid
  against `forgeds-validate-widget-manifest`.
- Rule codes SCF001-004 emit under the Phase 2A envelope; source file
  label is the spec path for spec-related diagnostics and the target
  file path for write/collision diagnostics.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from forgeds._shared.diagnostics import Diagnostic, Severity
from forgeds._shared.envelope import to_json_v1
from forgeds._shared.output_format import UnknownFormatError, resolve_format
from forgeds.widgets.spec_loader import load_spec

TEMPLATES_DIR = Path(__file__).parent / "templates"

_CANONICAL_KEYS = (
    "name",
    "location",
    "description",
    "consumes_apis",
    "ui_primitives",
    "state_model",
    "events_bound",
    "deployment",
)


def _diag(file: str, sev: Severity, code: str, message: str) -> Diagnostic:
    return Diagnostic(file=file, line=1, rule=code, severity=sev, message=message)


# ============================================================
# Template rendering
# ============================================================


def _load_tmpl(name: str) -> str:
    return (TEMPLATES_DIR / f"{name}.tmpl").read_text(encoding="utf-8")


def _render_consumes_apis_block(apis: list[str]) -> str:
    if not apis:
        return "// (no consumes_apis declared)"
    stubs = []
    for api in apis:
        stubs.append(
            f"async function {api}(...args) {{\n"
            f"  // TODO: implement {api}\n"
            f"}}"
        )
    return "\n\n".join(stubs)


def _render_state_block(fields: list[str]) -> str:
    if not fields:
        return "// (no state_model declared)"
    inner = "\n".join(f"  {name}: null,  // TODO: type" for name in fields)
    return "const state = {\n" + inner + "\n};"


def _render_events_block(events: list[str]) -> str:
    if not events:
        return "// (no events_bound declared)"
    handlers = []
    for ev in events:
        handlers.append(
            f"function on{ev}(...args) {{\n"
            f"  // TODO: handle {ev}\n"
            f"}}"
        )
    return "\n\n".join(handlers)


def _render_templates(spec: dict) -> dict[str, str]:
    """Produce {filename: content} for the four .tmpl files + widget-spec.yaml."""
    ctx = defaultdict(str)
    ctx["name"] = spec.get("name", "")
    ctx["location"] = spec.get("location", "")
    ctx["description"] = spec.get("description", "")
    ctx["consumes_apis_block"] = _render_consumes_apis_block(spec.get("consumes_apis") or [])
    ctx["state_block"] = _render_state_block(spec.get("state_model") or [])
    ctx["events_block"] = _render_events_block(spec.get("events_bound") or [])

    out = {
        "plugin-manifest.json": _load_tmpl("plugin-manifest.json").format_map(ctx),
        "index.js":             _load_tmpl("index.js").format_map(ctx),
        "index.html":           _load_tmpl("index.html").format_map(ctx),
        "styles.css":           _load_tmpl("styles.css").format_map(ctx),
    }
    # The spec file is written in canonical form (not via .tmpl).
    out["widget-spec.yaml"] = _canonicalise_spec(spec)
    return out


def _canonicalise_spec(spec: dict) -> str:
    """Re-serialize the spec in canonical key order with 2-space indent.

    Keeps the loader's parsed dict output shape and re-emits it in a
    stable order. Unknown keys are appended at the end to stay forward-
    compatible.
    """
    lines: list[str] = []

    def _emit_value(key: str, val, indent: int = 0) -> list[str]:
        pad = "  " * indent
        if val is None:
            return [f"{pad}{key}: null"]
        if isinstance(val, bool):
            return [f"{pad}{key}: {'true' if val else 'false'}"]
        if isinstance(val, (int, float)):
            return [f"{pad}{key}: {val}"]
        if isinstance(val, str):
            # quote if contains YAML-significant characters
            if ":" in val or val != val.strip():
                return [f'{pad}{key}: "{val}"']
            return [f"{pad}{key}: {val}"]
        if isinstance(val, list):
            out = [f"{pad}{key}:"]
            for item in val:
                if isinstance(item, (str, int, float)):
                    out.append(f"{pad}  - {item}")
                else:
                    # unlikely in our schema, best-effort JSON on its own line
                    out.append(f"{pad}  - {json.dumps(item)}")
            return out
        if isinstance(val, dict):
            out = [f"{pad}{key}:"]
            for subk, subv in val.items():
                out.extend(_emit_value(subk, subv, indent + 1))
            return out
        return [f"{pad}{key}: {val}"]

    for key in _CANONICAL_KEYS:
        if key in spec:
            lines.extend(_emit_value(key, spec[key]))
    for key, val in spec.items():
        if key not in _CANONICAL_KEYS:
            lines.extend(_emit_value(key, val))
    return "\n".join(lines) + "\n"


# ============================================================
# Collision & idempotency handling
# ============================================================


def _existing_content_matches(path: Path, expected: str) -> bool:
    try:
        return path.read_text(encoding="utf-8") == expected
    except (OSError, UnicodeDecodeError):
        return False


# ============================================================
# Main
# ============================================================


def _find_default_spec(cwd: Path) -> tuple[Path | None, str]:
    """Find a lone widget-spec.yaml starting from cwd (non-recursive)."""
    hits = list(cwd.glob("widget-spec.yaml"))
    if len(hits) == 0:
        return (None, f"no widget-spec.yaml found in {cwd}")
    if len(hits) > 1:
        return (None, f"multiple widget-spec.yaml files found in {cwd}: {hits}")
    return (hits[0], "")


def _emit_output(tool: str, diags: list[Diagnostic], fmt: str) -> None:
    if fmt == "json-v1":
        print(to_json_v1(tool, diags))
    else:
        for d in diags:
            print(str(d))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold a widget source tree from a widget-spec.yaml.",
    )
    parser.add_argument("--spec", help="Path to widget-spec.yaml (default: autodetect in cwd).")
    parser.add_argument("--output", help="Parent directory for the scaffolded tree. "
                                         "Default: <cwd>/src/widgets/")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the file list without touching the filesystem.")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing files. Emits SCF002 WARNING per overwrite.")
    parser.add_argument("--verbose", action="store_true",
                        help="Include full file contents in stdout (dry-run/preview).")
    parser.add_argument("--format", choices=["text", "json-v1"], default=None,
                        help="Output format: text (default) or json-v1.")
    args = parser.parse_args(argv)

    try:
        fmt = resolve_format(args.format)
    except UnknownFormatError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    tool = "scaffold_widget"

    # Resolve spec path
    if args.spec:
        spec_path = Path(args.spec).resolve()
    else:
        found, err = _find_default_spec(Path.cwd())
        if found is None:
            diag = _diag(str(Path.cwd()), Severity.ERROR, "SCF003", err)
            _emit_output(tool, [diag], fmt)
            return 2
        spec_path = found.resolve()

    spec, spec_diags = load_spec(str(spec_path))
    if any(d.severity == Severity.ERROR for d in spec_diags):
        _emit_output(tool, spec_diags, fmt)
        return 2

    name = spec.get("name")
    if not name:
        # should be caught by spec loader, but belt-and-braces
        err = _diag(str(spec_path), Severity.ERROR, "SCF003",
                    "spec missing `name`; cannot determine output directory")
        _emit_output(tool, spec_diags + [err], fmt)
        return 2

    # Output dir
    if args.output:
        parent = Path(args.output).resolve()
    else:
        parent = (Path.cwd() / "src" / "widgets").resolve()
    target_dir = parent / name

    # Render all file contents
    rendered = _render_templates(spec)

    # Plan writes
    diagnostics: list[Diagnostic] = list(spec_diags)
    planned_paths: list[tuple[Path, str]] = [
        (target_dir / fname, content) for fname, content in rendered.items()
    ]

    # Dry-run: report and exit
    if args.dry_run:
        for path, content in planned_paths:
            size = len(content.encode("utf-8"))
            exists = "exists" if path.exists() else "new"
            print(f"[dry-run] {path}  ({size} bytes; {exists})")
            if args.verbose:
                print("--- begin ---")
                print(content)
                print("--- end ---")
        # dry-run never writes, never emits SCF001/002/004
        _emit_output(tool, diagnostics, fmt)
        warnings = any(d.severity == Severity.WARNING for d in diagnostics)
        errors = any(d.severity == Severity.ERROR for d in diagnostics)
        return 2 if errors else (1 if warnings else 0)

    # Collision / idempotency pass
    collisions: list[Path] = []
    drift: list[Path] = []
    for path, content in planned_paths:
        if path.exists():
            if _existing_content_matches(path, content):
                # no-op, not a collision
                continue
            if args.force:
                # will overwrite; emit SCF002 per file
                diagnostics.append(_diag(str(path), Severity.WARNING, "SCF002",
                                         f"--force: overwriting {path.name}"))
            else:
                collisions.append(path)
                drift.append(path)

    if collisions and not args.force:
        for p in collisions:
            diagnostics.append(_diag(str(p), Severity.ERROR, "SCF001",
                                     f"refusing to overwrite {p} (use --force)"))
        # Also surface SCF004 drift warnings so the user understands that existing
        # content differs from the scaffold baseline.
        for p in drift:
            diagnostics.append(_diag(str(p), Severity.WARNING, "SCF004",
                                     f"on-disk {p.name} differs from scaffolded baseline"))
        _emit_output(tool, diagnostics, fmt)
        return 2

    # Write
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        diagnostics.append(_diag(str(target_dir), Severity.ERROR, "SCF003",
                                 f"cannot create output directory: {exc}"))
        _emit_output(tool, diagnostics, fmt)
        return 2

    for path, content in planned_paths:
        try:
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            diagnostics.append(_diag(str(path), Severity.ERROR, "SCF003",
                                     f"cannot write file: {exc}"))
            _emit_output(tool, diagnostics, fmt)
            return 2

    _emit_output(tool, diagnostics, fmt)
    warnings = any(d.severity == Severity.WARNING for d in diagnostics)
    errors = any(d.severity == Severity.ERROR for d in diagnostics)
    return 2 if errors else (1 if warnings else 0)


if __name__ == "__main__":
    sys.exit(main())
