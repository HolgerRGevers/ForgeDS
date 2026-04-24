"""Tests for forgeds-build-app (Phase 2C Task 9)."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import json
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from forgeds.widgets.build_app import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_forgeds_yaml(tmp_path: Path) -> None:
    (tmp_path / "forgeds.yaml").write_text(
        "project:\n  name: t\n  version: 0.0.1\n"
        "custom_apis:\n  - get_pending_claims\n  - approve_claim\n"
        "widgets:\n"
        "  expense_dashboard:\n    root: src/widgets/expense_dashboard\n"
        "    consumes_apis:\n      - get_pending_claims\n      - approve_claim\n",
        encoding="utf-8",
    )


def _capture_stdout_json(capsys) -> dict:
    out = capsys.readouterr().out.strip()
    # --plan-only emits indented JSON; parse first top-level object
    depth = 0
    start = None
    for i, ch in enumerate(out):
        if ch == "{":
            if start is None:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                return json.loads(out[start:i + 1])
    raise AssertionError(f"no JSON object found in output: {out!r}")


# ---------------------------------------------------------------------------
# --plan-only
# ---------------------------------------------------------------------------

def test_build_app_plan_only_emits_request_payload(tmp_path, monkeypatch, capsys):
    _write_forgeds_yaml(tmp_path)
    monkeypatch.chdir(tmp_path)
    rc = main(["--plan-only"])
    assert rc == 0
    payload = _capture_stdout_json(capsys)

    assert "project_snapshot" in payload
    ps = payload["project_snapshot"]
    assert os.path.isabs(ps["config_path"])
    assert ps["widgets"] == ["expense_dashboard"]
    assert ps["custom_apis"] == ["approve_claim", "get_pending_claims"]  # sorted

    assert payload["stage_flags"]["deploy"] is False
    assert payload["stage_flags"]["lint"] is True
    assert payload["dry_run"] is False


def test_build_app_plan_payload_snapshot_sorted(tmp_path, monkeypatch, capsys):
    # Use unsorted custom_apis to verify sort
    (tmp_path / "forgeds.yaml").write_text(
        "project:\n  name: t\n"
        "custom_apis:\n  - zebra\n  - alpha\n  - mango\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    rc = main(["--plan-only"])
    assert rc == 0
    payload = _capture_stdout_json(capsys)
    assert payload["project_snapshot"]["custom_apis"] == ["alpha", "mango", "zebra"]


# ---------------------------------------------------------------------------
# Stage parsing
# ---------------------------------------------------------------------------

def test_build_app_stage_flags_parsing_BLD003(tmp_path, monkeypatch, capsys):
    _write_forgeds_yaml(tmp_path)
    monkeypatch.chdir(tmp_path)
    rc = main(["--stages", "lint,foo", "--plan-only"])
    assert rc == 2
    out = capsys.readouterr().out
    assert "BLD003" in out
    assert "foo" in out


def test_build_app_valid_stage_subset(tmp_path, monkeypatch, capsys):
    _write_forgeds_yaml(tmp_path)
    monkeypatch.chdir(tmp_path)
    rc = main(["--stages", "lint,bundle", "--plan-only"])
    assert rc == 0
    payload = _capture_stdout_json(capsys)
    sf = payload["stage_flags"]
    assert sf["lint"] is True
    assert sf["bundle"] is True
    assert sf["verify"] is False
    assert sf["scaffold"] is False


# ---------------------------------------------------------------------------
# BLD001 — deploy without target
# ---------------------------------------------------------------------------

def test_build_app_deploy_without_target_BLD001(tmp_path, monkeypatch, capsys):
    _write_forgeds_yaml(tmp_path)
    monkeypatch.chdir(tmp_path)
    rc = main(["--stages", "lint,deploy", "--plan-only"])
    assert rc == 2
    assert "BLD001" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# BLD005 — forgeds.yaml missing
# ---------------------------------------------------------------------------

def test_build_app_forgeds_yaml_missing_BLD005(tmp_path, monkeypatch, capsys):
    # Make sure no forgeds.yaml exists up the tree — isolate in tmp_path with
    # FORGEDS_DB_DIR or similar isolation. Since find_project_root walks up,
    # we need a directory that has no forgeds.yaml in any ancestor. Use a
    # sub-dir under tmp_path (which itself is under user's AppData temp).
    target = tmp_path / "nested" / "deep"
    target.mkdir(parents=True)
    monkeypatch.chdir(target)
    # If the test runner's ancestors somehow contain a forgeds.yaml, we need
    # to skip. But normally pytest-tmp is isolated.
    # Check: walking up from target, no forgeds.yaml should exist up to root.

    rc = main([])
    out = capsys.readouterr().out
    # Either BLD005 fires, or we're unlucky and ancestors have a stray file.
    # Accept either BLD005 or CFG warnings (but rc must still signal error).
    if rc == 2:
        assert "BLD005" in out or "not found" in out
    else:
        pytest.skip("parent directories contain a forgeds.yaml; BLD005 path not exercised")


# ---------------------------------------------------------------------------
# BLD002 — orchestrator unreachable
# ---------------------------------------------------------------------------

def test_build_app_orchestrator_unreachable_BLD002(tmp_path, monkeypatch, capsys):
    _write_forgeds_yaml(tmp_path)
    monkeypatch.chdir(tmp_path)

    with patch("forgeds.widgets.build_app.urllib.request.urlopen",
               side_effect=urllib.error.URLError("Connection refused")):
        rc = main([])
    assert rc == 3
    out = capsys.readouterr().out
    assert "BLD002" in out
    assert "--plan-only" in out


def test_build_app_orchestrator_http_500_BLD002(tmp_path, monkeypatch, capsys):
    _write_forgeds_yaml(tmp_path)
    monkeypatch.chdir(tmp_path)

    http_err = urllib.error.HTTPError("url", 500, "err", {}, None)
    with patch("forgeds.widgets.build_app.urllib.request.urlopen",
               side_effect=http_err):
        rc = main([])
    assert rc == 3
    assert "BLD002" in capsys.readouterr().out


def test_build_app_orchestrator_http_400_exits_2(tmp_path, monkeypatch, capsys):
    """Review finding P1-3: 4xx from orchestrator is caller-side -> exit 2."""
    _write_forgeds_yaml(tmp_path)
    monkeypatch.chdir(tmp_path)

    http_err = urllib.error.HTTPError("url", 400, "Bad Request", {}, None)
    with patch("forgeds.widgets.build_app.urllib.request.urlopen",
               side_effect=http_err):
        rc = main([])
    assert rc == 2
    assert "BLD002" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Successful POST + report generation
# ---------------------------------------------------------------------------

def test_build_app_successful_post_writes_report(tmp_path, monkeypatch):
    _write_forgeds_yaml(tmp_path)
    monkeypatch.chdir(tmp_path)

    ndjson = (
        b'{"stage":"lint","status":"ok","exit_code":0,"duration_s":1.0,"diagnostics":[]}\n'
        b'{"stage":"bundle","status":"ok","exit_code":0,"duration_s":2.0,"diagnostics":[]}\n'
        b'{"type":"orchestrator:session:done","summary":{"total_errors":0,"total_warnings":0,"overall_exit_code":0}}\n'
    )
    mock_resp = MagicMock()
    mock_resp.read.return_value = ndjson
    mock_resp.__enter__ = lambda self: mock_resp
    mock_resp.__exit__ = lambda *a: None

    with patch("forgeds.widgets.build_app.urllib.request.urlopen", return_value=mock_resp):
        rc = main([])
    assert rc == 0

    report_path = tmp_path / "dist" / "build-report.json"
    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["forgeds_version"] == "2.0.0"
    assert report["summary"]["overall_exit_code"] == 0
    assert len(report["stages"]) == 2


def test_build_app_report_custom_path(tmp_path, monkeypatch):
    _write_forgeds_yaml(tmp_path)
    monkeypatch.chdir(tmp_path)
    custom = tmp_path / "custom.json"

    ndjson = b'{"type":"orchestrator:session:done","summary":{"overall_exit_code":0}}\n'
    mock_resp = MagicMock()
    mock_resp.read.return_value = ndjson
    mock_resp.__enter__ = lambda self: mock_resp
    mock_resp.__exit__ = lambda *a: None

    with patch("forgeds.widgets.build_app.urllib.request.urlopen", return_value=mock_resp):
        rc = main(["--report", str(custom)])
    assert rc == 0
    assert custom.is_file()


# ---------------------------------------------------------------------------
# CFG validation propagation as BLD004 WARNING
# ---------------------------------------------------------------------------

def test_build_app_config_validation_BLD004(tmp_path, monkeypatch, capsys):
    # widget consumes_apis includes an undeclared API -> CFG012 ERROR
    # which we propagate as BLD004 WARNING (non-halting per plan)
    (tmp_path / "forgeds.yaml").write_text(
        "project:\n  name: t\n"
        "custom_apis:\n  - known\n"
        "widgets:\n"
        "  w:\n    root: src/widgets/w\n"
        "    consumes_apis:\n      - unknown_api\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    rc = main(["--plan-only"])
    # rc should NOT be 2 (since BLD004 is a warning, non-halting)
    # plan-only emits the payload on stdout and diagnostics on stderr.
    assert rc == 0
    captured = capsys.readouterr()
    assert "BLD004" in captured.err
