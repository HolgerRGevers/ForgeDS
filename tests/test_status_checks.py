"""Unit tests for individual status check modules."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from forgeds.status.checks import (
    StatusCheck,
    config_sanity,
    db_freshness,
    lint_summary,
    toolchain,
)

FIXTURES = Path(__file__).parent / "fixtures" / "status"


# ---------- config_sanity ----------

def test_config_sanity_reports_missing_yaml(tmp_path):
    checks = config_sanity.run(start=str(tmp_path))
    assert len(checks) == 1
    assert checks[0].rule == "STA001"
    assert checks[0].status == "fail"


def test_config_sanity_clean_project():
    checks = config_sanity.run(start=str(FIXTURES / "all_green"))
    # first check is forgeds.yaml found; rest must be clean
    rules = {c.rule for c in checks}
    assert "STA001" not in rules
    assert any(c.id == "forgeds.yaml" and c.status == "ok" for c in checks)


def test_config_sanity_surfaces_cfg_diagnostics():
    checks = config_sanity.run(start=str(FIXTURES / "config_only_warnings"))
    # CFG011 fires for Form-A; CFG012 fires for undeclared_api
    rules = {c.rule for c in checks}
    assert "CFG012" in rules


# ---------- db_freshness ----------

def test_db_freshness_reports_missing_dbs(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGEDS_DB_DIR", str(tmp_path))
    checks = db_freshness.run()
    statuses = {c.id: c.status for c in checks}
    assert statuses["deluge_lang.db"] == "miss"
    assert statuses["access_vba_lang.db"] == "miss"
    assert statuses["zoho_widget_sdk.db"] == "miss"


def test_db_freshness_reports_stale_db(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGEDS_DB_DIR", str(tmp_path))
    stale = tmp_path / "deluge_lang.db"
    stale.write_bytes(b"")
    old = time.time() - (40 * 86400)
    os.utime(stale, (old, old))
    checks = db_freshness.run()
    d = next(c for c in checks if c.id == "deluge_lang.db")
    assert d.status == "warn"
    assert d.rule == "STA003"


def test_db_freshness_fresh_db_is_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGEDS_DB_DIR", str(tmp_path))
    (tmp_path / "deluge_lang.db").write_bytes(b"")
    checks = db_freshness.run()
    d = next(c for c in checks if c.id == "deluge_lang.db")
    assert d.status == "ok"


# ---------- toolchain ----------

def test_toolchain_skips_node_when_no_widgets(monkeypatch):
    monkeypatch.setattr(toolchain, "load_config", lambda *a, **k: {"widgets": {}})
    checks = toolchain.run()
    statuses = {c.id: c.status for c in checks}
    assert statuses["python"] == "ok"
    assert statuses["node"] == "skip"
    assert statuses["eslint"] == "skip"


def test_toolchain_reports_node_missing_when_widgets_declared(monkeypatch):
    monkeypatch.setattr(toolchain, "load_config", lambda *a, **k: {"widgets": {"x": {}}})
    monkeypatch.setattr(toolchain.shutil, "which", lambda name: None)
    monkeypatch.setattr(toolchain, "_capture_version", lambda *a, **k: (False, "not found"))
    checks = toolchain.run()
    node = next(c for c in checks if c.id == "node")
    assert node.status == "fail"
    assert node.rule == "STA004"


def test_toolchain_reports_eslint_missing_when_widgets_declared(monkeypatch):
    monkeypatch.setattr(toolchain, "load_config", lambda *a, **k: {"widgets": {"x": {}}})
    monkeypatch.setattr(toolchain.shutil, "which", lambda name: "/usr/bin/" + name)
    calls = iter([(True, "v20.10.0"), (False, "eslint: not found")])
    monkeypatch.setattr(toolchain, "_capture_version", lambda *a, **k: next(calls))
    checks = toolchain.run()
    eslint = next(c for c in checks if c.id == "eslint")
    assert eslint.status == "fail"
    assert eslint.rule == "STA005"


# ---------- lint_summary ----------

def test_lint_summary_skips_widget_linter_without_widgets(monkeypatch):
    monkeypatch.setattr(lint_summary, "load_config", lambda *a, **k: {"widgets": {}})
    monkeypatch.setattr(lint_summary, "_invoke_linter",
                        lambda *a, **k: (0, {"tool": "", "version": "1", "diagnostics": []}, ""))
    checks = lint_summary.run()
    wcheck = next(c for c in checks if c.id == "forgeds-lint-widgets")
    assert wcheck.status == "skip"


def test_lint_summary_reports_error_counts(monkeypatch):
    monkeypatch.setattr(lint_summary, "load_config", lambda *a, **k: {"widgets": {}})

    def fake_invoke(module, paths):
        if "lint_deluge" in module:
            return (2, {"tool": "forgeds-lint", "version": "1", "diagnostics": [
                {"severity": "error"}, {"severity": "error"}, {"severity": "warning"},
            ]}, "")
        return (0, {"tool": "x", "version": "1", "diagnostics": []}, "")

    monkeypatch.setattr(lint_summary, "_invoke_linter", fake_invoke)
    checks = lint_summary.run()
    d = next(c for c in checks if c.id == "forgeds-lint")
    assert d.status == "fail"
    assert "2 error" in d.message


def test_lint_summary_flags_unparseable_envelope(monkeypatch):
    monkeypatch.setattr(lint_summary, "load_config", lambda *a, **k: {"widgets": {}})
    monkeypatch.setattr(lint_summary, "_invoke_linter",
                        lambda *a, **k: (1, None, "something broke"))
    checks = lint_summary.run()
    fails = [c for c in checks if c.status == "fail" and c.rule == "STA006"]
    assert len(fails) >= 1
