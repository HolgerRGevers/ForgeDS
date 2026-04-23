"""ESLint orchestrator for Zoho Creator widgets.

Shells out to `npx eslint` using the curated config at
`configs/.eslintrc.zoho.json`. Translates ESLint JSON output into
ForgeDS Diagnostic objects (rule prefix `JS:` signals foreign provenance).

Emits text format (matching other linters) by default; `--format json`
emits the v1 envelope intended for downstream verification agents.

Exit codes:
  0 clean, 1 warnings, 2 errors, 3 toolchain missing.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import sqlite3

from forgeds._shared.config import find_project_root, get_db_dir, load_config
from forgeds._shared.diagnostics import Diagnostic, Severity
from forgeds._shared.envelope import to_json_v1
from forgeds._shared.output_format import UnknownFormatError, resolve_format

CONFIG_PATH = Path(__file__).parent / "configs" / ".eslintrc.zoho.json"
ESLINT_CMD = ["npx", "--yes", "eslint"]  # --yes: auto-accept npx prompt

INSTALL_HINT = (
    "ESLint/Node not found. forgeds-lint-widgets requires Node >= 18 and ESLint 8+.\n"
    "  Install globally:      npm i -g eslint\n"
    "  Or per-project:        npm i --save-dev eslint\n"
)


def _mk_diag(file: str, line: int, rule: str, severity: str, message: str) -> Diagnostic:
    sev = {"ERROR": Severity.ERROR, "WARNING": Severity.WARNING, "INFO": Severity.INFO}[severity]
    return Diagnostic(file=file, line=line, rule=rule, severity=sev, message=message)


def _eslint_available() -> bool:
    try:
        r = subprocess.run(
            ESLINT_CMD + ["--version"],
            capture_output=True, text=True, timeout=15,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _translate_eslint(eslint_json: list[dict]) -> list[Diagnostic]:
    """Translate ESLint JSON output to ForgeDS Diagnostics.

    ESLint severity: 0=off (dropped), 1=warn, 2=error.
    """
    sev_map = {1: "WARNING", 2: "ERROR"}
    out: list[Diagnostic] = []
    for file_result in eslint_json:
        file_path = file_result.get("filePath", "<unknown>")
        for msg in file_result.get("messages", []):
            sev_num = msg.get("severity", 0)
            if sev_num not in sev_map:
                continue
            rule_id = msg.get("ruleId") or "unknown"
            out.append(_mk_diag(
                file=file_path,
                line=int(msg.get("line", 1)),
                rule=f"JS:{rule_id}",
                severity=sev_map[sev_num],
                message=str(msg.get("message", "")),
            ))
    return out


def _run_eslint_on(paths: list[str]) -> list[Diagnostic]:
    """Invoke ESLint and parse JSON output. Returns Diagnostics."""
    if not paths:
        return []
    cmd = ESLINT_CMD + ["-c", str(CONFIG_PATH), "--format", "json", "--no-eslintrc"] + paths
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode >= 2 and not r.stdout.strip():
        return [_mk_diag("<eslint>", 1, "JS:fatal", "ERROR", (r.stderr or "ESLint fatal error").strip())]
    try:
        parsed = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return [_mk_diag("<eslint>", 1, "JS:parse-error", "ERROR",
                         f"could not parse ESLint JSON output: {r.stdout[:200]!r}")]
    return _translate_eslint(parsed)


def _discover_js_files(widget_root: Path) -> list[str]:
    """Return .js files under widget_root (recursive)."""
    if not widget_root.is_dir():
        return []
    return [str(p) for p in sorted(widget_root.rglob("*.js"))]


def _known_sdk_methods() -> list[str]:
    """Read the full SDK-method catalog from zoho_widget_sdk.db.

    Returns an empty list when the DB is absent — the sidecar is still valid
    (the plugin falls back to hard-coded INVOKE_METHODS when knownSdkMethods
    is empty).
    """
    db = get_db_dir() / "zoho_widget_sdk.db"
    if not db.exists():
        return []
    try:
        conn = sqlite3.connect(str(db))
        rows = conn.execute(
            "SELECT namespace, name FROM sdk_methods ORDER BY namespace, name"
        ).fetchall()
        conn.close()
    except sqlite3.Error:
        return []
    return [f"{ns}.{name}" for ns, name in rows]


def write_sidecar(cfg: dict, project_root: Path) -> Path | None:
    """Write `.forgeds/eslint_plugin_manifest.json` for the plugin to read.

    Shape per spec §6.3. Returns the sidecar path, or None if no widgets
    are declared (nothing to describe).
    """
    widgets_cfg = cfg.get("widgets") or {}
    if not widgets_cfg:
        return None

    cache_dir = project_root / ".forgeds"
    cache_dir.mkdir(parents=True, exist_ok=True)
    sidecar_path = cache_dir / "eslint_plugin_manifest.json"

    known_methods = _known_sdk_methods()
    payload: dict = {"version": "1", "widgets": {}}
    for name, decl in widgets_cfg.items():
        if not isinstance(decl, dict):
            continue
        w_root = (project_root / (decl.get("root") or "")).resolve()
        entry_rel = decl.get("entry_point")
        entry = (w_root / entry_rel).resolve() if entry_rel else (w_root / "index.js").resolve()
        payload["widgets"][name] = {
            "root": str(w_root),
            "entryPoint": str(entry),
            "consumesApis": list(decl.get("consumes_apis") or []),
            "knownSdkMethods": known_methods,
        }
    sidecar_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return sidecar_path


def _emit(diagnostics: list[Diagnostic], fmt: str) -> None:
    if fmt == "json-v1":
        print(to_json_v1("forgeds-lint-widgets", diagnostics))
    else:
        for d in diagnostics:
            print(str(d))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lint Zoho Creator widget JavaScript via ESLint with a ForgeDS-curated config."
    )
    parser.add_argument("paths", nargs="*", help="Optional explicit file/dir paths. "
                        "If omitted, widget roots are discovered from forgeds.yaml config['widgets'].")
    parser.add_argument("--format", dest="format", default=None,
                        choices=["text", "json-v1"],
                        help="Output format (default: text; FORGEDS_OUTPUT env also honored).")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress INFO diagnostics.")
    parser.add_argument("--errors-only", action="store_true", help="Suppress WARNING and INFO diagnostics.")
    parser.add_argument("--no-args-discover", action="store_true",
                        help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    try:
        fmt = resolve_format(args.format)
    except UnknownFormatError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not _eslint_available():
        print(INSTALL_HINT, file=sys.stderr)
        return 3

    targets: list[str] = list(args.paths)
    cfg = load_config()
    root = find_project_root()
    if not targets and not args.no_args_discover:
        for _widget_name, decl in (cfg.get("widgets") or {}).items():
            w_root = root / decl.get("root", "")
            targets.extend(_discover_js_files(w_root))

    # Emit the Phase 2B sidecar manifest for the local ESLint plugin
    # before invoking ESLint. The plugin reads it via FORGEDS_ESLINT_SIDECAR.
    write_sidecar(cfg, root)

    diagnostics = _run_eslint_on(targets) if targets else []

    if args.quiet:
        diagnostics = [d for d in diagnostics if d.severity != Severity.INFO]
    if args.errors_only:
        diagnostics = [d for d in diagnostics if d.severity == Severity.ERROR]

    _emit(diagnostics, fmt=fmt)

    if any(d.severity == Severity.ERROR for d in diagnostics):
        return 2
    if any(d.severity == Severity.WARNING for d in diagnostics):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
