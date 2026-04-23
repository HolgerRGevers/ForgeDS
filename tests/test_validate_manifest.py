"""Tests for forgeds.widgets.validate_manifest."""

from __future__ import annotations

import sys, os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from forgeds._shared.diagnostics import Severity
from forgeds.widgets.validate_manifest import validate_manifest_file

FIXTURES = Path(__file__).parent / "fixtures" / "widgets"


def test_good_manifest_returns_no_diagnostics():
    path = FIXTURES / "good_widget" / "plugin-manifest.json"
    diags = validate_manifest_file(str(path))
    assert diags == [], f"unexpected diagnostics: {diags}"


def test_bad_manifest_bad_version_produces_error():
    path = FIXTURES / "bad_widget_invalid_manifest" / "plugin-manifest.json"
    diags = validate_manifest_file(str(path))
    assert any(d.severity == Severity.ERROR for d in diags)
    assert any("version" in d.message.lower() for d in diags)


def test_bad_manifest_missing_required_produces_error():
    path = FIXTURES / "bad_widget_invalid_manifest" / "plugin-manifest.json"
    diags = validate_manifest_file(str(path))
    assert any("config" in d.message.lower() and "required" in d.message.lower() for d in diags)


def test_missing_file_produces_error():
    diags = validate_manifest_file(str(FIXTURES / "nonexistent" / "plugin-manifest.json"))
    assert len(diags) == 1
    assert diags[0].severity == Severity.ERROR
    assert "not found" in diags[0].message.lower() or "missing" in diags[0].message.lower()
