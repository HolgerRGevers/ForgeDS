"""Tests for widget-related hybrid rules (WG001-WG003)."""

from __future__ import annotations

import sys, os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from forgeds._shared.diagnostics import Severity
from forgeds.hybrid.lint_hybrid import check_wg001

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
