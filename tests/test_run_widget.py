"""Tests for forgeds-run-widget (Phase 2B Task 4).

Fixture-driven: each widget under `tests/fixtures/widgets/runtime/` isolates
one rule code. Tests invoke the CLI as a subprocess so exit codes and
argv/env wiring are covered end-to-end.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "widgets" / "runtime"
FIXTURE_CFG = FIXTURE_DIR / "forgeds.yaml"


def _node_available() -> bool:
    return shutil.which("node") is not None


pytestmark = pytest.mark.skipif(not _node_available(), reason="Node not on PATH")


def _run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "forgeds.widgets.run_widget", *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd or FIXTURE_DIR),
        capture_output=True,
        text=True,
    )


def _parse_envelope(stdout: str) -> dict:
    line = stdout.strip().splitlines()[-1]
    return json.loads(line)


def _rules_by_widget(envelope: dict, widget_name: str) -> list[dict]:
    return [
        d for d in envelope["diagnostics"]
        if widget_name in (d.get("message") or "") or widget_name in (d.get("file") or "")
    ]


def test_run_widget_good_runtime_exits_clean():
    r = _run_cli("--widget", "good_runtime_widget", "--format", "json-v1")
    env = _parse_envelope(r.stdout)
    assert env["tool"] == "forgeds-run-widget"
    assert env["version"] == "1"
    good_diags = _rules_by_widget(env, "good_runtime_widget")
    # No WGR errors or warnings for the happy widget.
    for d in good_diags:
        assert d.get("rule", "").startswith("WGR") is False or d["severity"] == "info", d
    assert r.returncode == 0


def test_run_widget_undeclared_call_emits_wgr001_error():
    r = _run_cli("--widget", "bad_widget_undeclared_call", "--format", "json-v1")
    env = _parse_envelope(r.stdout)
    wgr001 = [d for d in env["diagnostics"] if d["rule"] == "WGR001" and d["severity"] == "error"]
    assert wgr001, env
    assert any("approve_claim" in d["message"] for d in wgr001)
    assert r.returncode == 2


def test_run_widget_unused_declaration_emits_wgr001_warning():
    r = _run_cli("--widget", "bad_widget_unused_declaration", "--format", "json-v1")
    env = _parse_envelope(r.stdout)
    wgr001w = [d for d in env["diagnostics"] if d["rule"] == "WGR001" and d["severity"] == "warning"]
    assert wgr001w, env
    assert any("approve_claim" in d["message"] for d in wgr001w)
    # Warning-only run → exit 1.
    assert r.returncode == 1


def test_run_widget_throws_in_init_emits_wgr002():
    r = _run_cli("--widget", "bad_widget_throws_in_init", "--format", "json-v1")
    env = _parse_envelope(r.stdout)
    wgr002 = [d for d in env["diagnostics"] if d["rule"] == "WGR002"]
    assert wgr002, env
    assert any("simulated widget init failure" in d["message"] for d in wgr002)
    assert r.returncode == 2


def test_run_widget_permission_mismatch_emits_wgr004():
    r = _run_cli("--widget", "bad_widget_permission_mismatch", "--format", "json-v1")
    env = _parse_envelope(r.stdout)
    wgr004 = [d for d in env["diagnostics"] if d["rule"] == "WGR004"]
    assert wgr004, env
    assert any("ZOHO.CREATOR.API.write" in d["message"] for d in wgr004)
    assert r.returncode == 2


def test_run_widget_missing_entry_emits_wgr_meta():
    r = _run_cli("--widget", "bad_widget_missing_entry", "--format", "json-v1")
    env = _parse_envelope(r.stdout)
    meta = [d for d in env["diagnostics"] if d["rule"] == "WGR-meta"]
    assert meta, env
    assert any("entry" in d["message"].lower() for d in meta)


def test_run_widget_timeout_emits_wgr_meta():
    r = _run_cli(
        "--widget", "bad_widget_timeout",
        "--format", "json-v1",
        "--timeout-ms", "300",
    )
    env = _parse_envelope(r.stdout)
    meta = [d for d in env["diagnostics"] if d["rule"] == "WGR-meta"]
    assert meta, env
    assert any("timeout" in d["message"].lower() for d in meta)


def test_run_widget_json_envelope_shape():
    r = _run_cli("--widget", "good_runtime_widget", "--format", "json-v1")
    env = _parse_envelope(r.stdout)
    assert set(env.keys()) >= {"tool", "version", "diagnostics"}
    assert env["tool"] == "forgeds-run-widget"
    assert env["version"] == "1"
    assert isinstance(env["diagnostics"], list)


def test_run_widget_batch_runs_all_widgets_when_no_filter():
    """One bad widget in the batch does not abort siblings."""
    r = _run_cli("--format", "json-v1", "--timeout-ms", "300")
    env = _parse_envelope(r.stdout)
    msgs = " | ".join(d.get("message", "") for d in env["diagnostics"])
    # Expect diagnostics from multiple bad widgets.
    assert "bad_widget_undeclared_call" in msgs or any(
        "approve_claim" in (d.get("message") or "") for d in env["diagnostics"]
    )
    assert "bad_widget_throws_in_init" in msgs or any(
        d["rule"] == "WGR002" for d in env["diagnostics"]
    )


def test_run_widget_text_mode_is_default():
    r = _run_cli("--widget", "good_runtime_widget")
    assert "good_runtime_widget" in r.stdout
    # Text mode emits human-readable lines, not a JSON envelope.
    assert not r.stdout.strip().startswith("{")


def test_run_widget_node_missing_exits_3(monkeypatch, tmp_path):
    """Simulate Node absence by invoking with a stripped PATH.

    On Windows, `shutil.which` also consults PATHEXT; we clear both so the
    lookup genuinely fails.
    """
    env = {**os.environ, "PATH": str(tmp_path), "PATHEXT": ""}
    cmd = [sys.executable, "-m", "forgeds.widgets.run_widget",
           "--widget", "good_runtime_widget", "--format", "json-v1"]
    r = subprocess.run(
        cmd, cwd=str(FIXTURE_DIR), capture_output=True, text=True, env=env,
    )
    assert r.returncode == 3, r.stdout + r.stderr
    assert "Node" in r.stderr or "node" in r.stderr
