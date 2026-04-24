"""forgeds-build-app — thin entry to the Node Orchestrator Service.

Phase 2C Task 9.

Under the Phase 2 orchestration spec, this command:
  1. Validates forgeds.yaml (still Python, still stdlib-only).
  2. Builds a project snapshot (forms, widgets, custom_apis).
  3. Emits a `build-plan-request.json` to stdout (with --plan-only)
     OR POSTs the same payload to the Node Orchestrator Service.
  4. On POST: streams NDJSON events, assembles build-report.json per
     spec §8.5, writes to --report path.

The Node Orchestrator Service is designed but not yet implemented
(see 2026-04-23-forgeds-widgets-phase2-orchestration-design.md). If
unreachable, this command exits 3 with BLD002 pointing at --plan-only.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from forgeds._shared.config import find_project_root, load_config_with_diagnostics
from forgeds._shared.diagnostics import Diagnostic, Severity
from forgeds._shared.envelope import to_json_v1
from forgeds._shared.output_format import UnknownFormatError, resolve_format


ALLOWED_STAGES = ("lint", "verify", "scaffold", "bundle", "deploy")
DEFAULT_ORCHESTRATOR_URL = "http://127.0.0.1:9878"


def _diag(file: str, sev: Severity, code: str, message: str) -> Diagnostic:
    return Diagnostic(file=file, line=1, rule=code, severity=sev, message=message)


def _parse_stages(stages_arg: str | None) -> tuple[list[str], list[Diagnostic]]:
    """Parse `--stages a,b,c` with BLD003 for unknown tokens."""
    if not stages_arg:
        return (["lint", "verify", "scaffold", "bundle"], [])
    tokens = [s.strip() for s in stages_arg.split(",") if s.strip()]
    diags: list[Diagnostic] = []
    valid: list[str] = []
    for t in tokens:
        if t not in ALLOWED_STAGES:
            diags.append(_diag("(--stages)", Severity.ERROR, "BLD003",
                               f"unknown stage {t!r}; expected one of {list(ALLOWED_STAGES)}"))
        else:
            valid.append(t)
    return (valid, diags)


def _build_snapshot(project_root: Path, config: dict) -> dict:
    """Assemble the project snapshot for the plan-request body."""
    forms = sorted((config.get("schema", {}) or {}).get("table_to_form", {}).values())
    if not forms:
        # fallback: derive from seed-data-dir filenames if nothing else
        forms = []
    widgets_block = config.get("widgets") or {}
    widgets = sorted(widgets_block.keys()) if isinstance(widgets_block, dict) else []
    custom_apis_raw = config.get("custom_apis") or []
    if isinstance(custom_apis_raw, dict):
        custom_apis = sorted(custom_apis_raw.keys())
    elif isinstance(custom_apis_raw, list):
        custom_apis = sorted(x for x in custom_apis_raw if isinstance(x, str))
    else:
        custom_apis = []
    return {
        "config_path": str((project_root / "forgeds.yaml").resolve()),
        "forms": forms,
        "widgets": widgets,
        "custom_apis": custom_apis,
    }


def _build_plan_request(
    snapshot: dict,
    stage_flags: dict,
    dry_run: bool,
    collect_all: bool,
    prompt: str,
) -> dict:
    return {
        "prompt": prompt,
        "project_snapshot": snapshot,
        "stage_flags": stage_flags,
        "dry_run": dry_run,
        "collect_all": collect_all,
    }


def _post_to_orchestrator(
    url: str,
    payload: dict,
    timeout_s: int,
) -> tuple[bytes | None, Diagnostic | None, int]:
    """POST the plan request. Returns (raw_bytes, diag, exit_code_on_failure).

    Per spec §8.6:
      exit 2 — caller-side error (4xx, missing --target, etc.)
      exit 3 — toolchain / unreachable orchestrator (5xx, URLError, timeout)
    Review finding P1-3.
    """
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return (resp.read(), None, 0)
    except urllib.error.HTTPError as exc:
        if exc.code >= 500:
            return (None, _diag(url, Severity.ERROR, "BLD002",
                                f"orchestrator HTTP {exc.code}; use --plan-only to "
                                "preview dispatch."), 3)
        return (None, _diag(url, Severity.ERROR, "BLD002",
                            f"orchestrator HTTP {exc.code} (caller-side)"), 2)
    except (urllib.error.URLError, OSError) as exc:
        return (None, _diag(url, Severity.ERROR, "BLD002",
                            f"Node Orchestrator Service not reachable at {url} ({exc}). "
                            "Use --plan-only to preview dispatch. The orchestrator "
                            "is designed but not yet implemented; see "
                            "2026-04-23-forgeds-widgets-phase2-orchestration-design.md."),
                3)


def _assemble_report(
    ndjson_bytes: bytes,
    target: str | None,
    collect_all: bool,
) -> dict:
    """Parse NDJSON stream into a build-report.json per spec §8.5."""
    now = datetime.datetime.now(datetime.timezone.utc)
    stages: list[dict] = []
    widgets: list[dict] = []
    summary = {"total_errors": 0, "total_warnings": 0, "overall_exit_code": 0}
    started_at = now.isoformat(timespec="seconds").replace("+00:00", "Z")

    for line in ndjson_bytes.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        ev_name = evt.get("type") or evt.get("event") or ""
        if ev_name == "orchestrator:session:done":
            summary = evt.get("summary", summary)
        elif ev_name == "widget":
            widgets.append(evt.get("widget", {}))
        elif evt.get("stage"):
            stages.append(evt)

    finished = datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")

    return {
        "forgeds_version": "2.0.0",
        "started_at": started_at,
        "finished_at": finished,
        "target": target,
        "mode": "collect-all" if collect_all else "fail-fast",
        "stages": stages,
        "widgets": widgets,
        "summary": summary,
    }


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
        description="Orchestrate a widget build/verify/bundle/deploy pipeline.",
    )
    parser.add_argument("--stages",
                        help="Comma-separated stage list. Default: "
                             "lint,verify,scaffold,bundle (deploy omitted).")
    parser.add_argument("--plan-only", action="store_true",
                        help="Emit the build-plan-request payload to stdout; "
                             "do not contact the orchestrator.")
    parser.add_argument("--orchestrator-url", default=DEFAULT_ORCHESTRATOR_URL)
    parser.add_argument("--dry-run", action="store_true",
                        help="Propagated into the plan request; each stage respects it.")
    parser.add_argument("--force", action="store_true",
                        help="Propagated into the plan request (scaffold collision override).")
    parser.add_argument("--collect-all", action="store_true",
                        help="Run every dispatched stage regardless of predecessor status.")
    parser.add_argument("--fail-fast", action="store_true",
                        help="Default orchestrator posture; flag provided for explicitness.")
    parser.add_argument("--target",
                        help="Deploy target identifier. Required when 'deploy' is in --stages.")
    parser.add_argument("--report",
                        help="Destination for build-report.json. "
                             "Default: <project-root>/dist/build-report.json")
    parser.add_argument("--prompt", default="",
                        help="Natural-language prompt to forward to the orchestrator.")
    parser.add_argument("--timeout", type=int, default=300,
                        help="Orchestrator POST timeout in seconds.")
    parser.add_argument("--format", choices=["text", "json-v1"], default=None)
    args = parser.parse_args(argv)

    try:
        fmt = resolve_format(args.format)
    except UnknownFormatError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    tool = "build_app"
    diagnostics: list[Diagnostic] = []

    # Validate forgeds.yaml
    project_root = find_project_root()
    config_path = project_root / "forgeds.yaml"
    if not config_path.exists():
        diagnostics.append(_diag(str(config_path), Severity.ERROR, "BLD005",
                                 f"forgeds.yaml not found at {config_path}"))
        _emit_output(tool, diagnostics, fmt)
        return 2

    config, cfg_diags = load_config_with_diagnostics()
    # Propagate CFG diagnostics as BLD004 warnings (non-halting)
    for d in cfg_diags:
        if d.severity == Severity.ERROR:
            diagnostics.append(_diag(d.file, Severity.WARNING, "BLD004",
                                     f"config diagnostic {d.rule}: {d.message}"))
        elif d.severity == Severity.WARNING:
            diagnostics.append(_diag(d.file, Severity.WARNING, "BLD004",
                                     f"config diagnostic {d.rule}: {d.message}"))
        # INFO from config not propagated; it's too chatty for build-app

    # Parse stages
    stages, stage_diags = _parse_stages(args.stages)
    diagnostics.extend(stage_diags)
    if any(d.severity == Severity.ERROR for d in stage_diags):
        _emit_output(tool, diagnostics, fmt)
        return 2

    if "deploy" in stages and not args.target:
        diagnostics.append(_diag("(--stages)", Severity.ERROR, "BLD001",
                                 "--target is required when 'deploy' is in --stages"))
        _emit_output(tool, diagnostics, fmt)
        return 2

    # Snapshot + plan request
    snapshot = _build_snapshot(project_root, config)
    stage_flags = {name: (name in stages) for name in ALLOWED_STAGES}
    plan_request = _build_plan_request(
        snapshot=snapshot,
        stage_flags=stage_flags,
        dry_run=args.dry_run,
        collect_all=args.collect_all,
        prompt=args.prompt,
    )

    # --plan-only: emit and exit
    if args.plan_only:
        print(json.dumps(plan_request, indent=2))
        # Diagnostics: emit to stderr in text mode (so stdout stays clean
        # JSON for downstream consumers), or as a second envelope on
        # stdout in json-v1 mode.
        if fmt == "json-v1":
            _emit_output(tool, diagnostics, fmt)
        else:
            for d in diagnostics:
                print(str(d), file=sys.stderr)
        return 0

    # POST to orchestrator
    orch_url = args.orchestrator_url.rstrip("/") + "/orchestrate"
    raw, post_diag, post_exit = _post_to_orchestrator(orch_url, plan_request, args.timeout)
    if post_diag is not None:
        diagnostics.append(post_diag)
        _emit_output(tool, diagnostics, fmt)
        return post_exit

    # Assemble report
    report = _assemble_report(raw or b"", args.target, args.collect_all)
    report_path = Path(args.report) if args.report \
        else (project_root / "dist" / "build-report.json")
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except OSError as exc:
        diagnostics.append(_diag(str(report_path), Severity.WARNING, "BLD004",
                                 f"could not write build-report.json: {exc}"))

    _emit_output(tool, diagnostics, fmt)
    return int(report.get("summary", {}).get("overall_exit_code", 0))


if __name__ == "__main__":
    sys.exit(main())
