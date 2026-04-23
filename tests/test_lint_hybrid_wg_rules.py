"""Tests for widget-related hybrid rules (WG001-WG003)."""

from __future__ import annotations

import sys, os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from forgeds._shared.diagnostics import Severity
from forgeds.hybrid.lint_hybrid import check_wg001, check_wg002

FIXTURES = Path(__file__).parent / "fixtures" / "widgets"


def test_wg001_flags_missing_root():
    widgets = {
        "ghost_widget": {"root": "tests/fixtures/widgets/does_not_exist/", "consumes_apis": []},
    }
    diags = check_wg001(widgets, project_root=Path("."))
    assert len(diags) == 1
    assert diags[0].rule == "WG001"
    assert diags[0].severity == Severity.ERROR
    assert "ghost_widget" in diags[0].message


def test_wg001_passes_when_root_exists():
    widgets = {
        "good_widget": {"root": str(FIXTURES / "good_widget"), "consumes_apis": []},
    }
    diags = check_wg001(widgets, project_root=Path("."))
    assert diags == []


def test_wg002_flags_missing_manifest():
    widgets = {
        "bad_widget_missing_manifest": {
            "root": str(FIXTURES / "bad_widget_missing_manifest"),
            "consumes_apis": [],
        },
    }
    diags = check_wg002(widgets, project_root=Path("."))
    assert any(d.rule == "WG002" and "bad_widget_missing_manifest" in d.message for d in diags)


def test_wg002_flags_invalid_manifest():
    widgets = {
        "bad_widget_invalid_manifest": {
            "root": str(FIXTURES / "bad_widget_invalid_manifest"),
            "consumes_apis": [],
        },
    }
    diags = check_wg002(widgets, project_root=Path("."))
    assert any(d.rule == "WG002" and d.severity == Severity.ERROR for d in diags)


def test_wg002_passes_on_good_manifest():
    widgets = {
        "good_widget": {"root": str(FIXTURES / "good_widget"), "consumes_apis": []},
    }
    diags = check_wg002(widgets, project_root=Path("."))
    assert diags == []
