"""Tests for widget-related hybrid rules (WG001-WG003)."""

from __future__ import annotations

import sys, os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from forgeds._shared.diagnostics import Severity
from forgeds.hybrid.lint_hybrid import check_wg001, check_wg002, check_wg003

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


def test_wg003_flags_undeclared_consumes_api():
    widgets = {
        "some_widget": {
            "root": str(FIXTURES / "good_widget"),
            "consumes_apis": ["undeclared_api_name"],
        },
    }
    custom_apis = ["get_pending_claims", "approve_claim"]
    diags = check_wg003(widgets, custom_apis)
    assert len(diags) == 1
    assert diags[0].rule == "WG003"
    assert diags[0].severity == Severity.ERROR
    assert "undeclared_api_name" in diags[0].message
    assert "some_widget" in diags[0].message


def test_wg003_passes_when_all_apis_declared():
    widgets = {
        "some_widget": {
            "root": str(FIXTURES / "good_widget"),
            "consumes_apis": ["get_pending_claims"],
        },
    }
    diags = check_wg003(widgets, ["get_pending_claims", "approve_claim"])
    assert diags == []


def test_main_runs_wg_rules_end_to_end(monkeypatch, capsys):
    """lint_hybrid.main should exit non-zero when WG rules find issues.

    Refactored main() returns int so tests can capture the rc directly.
    """
    import forgeds.hybrid.lint_hybrid as lh

    def fake_load_config(*a, **kw):
        return {
            "custom_apis": ["get_pending_claims"],
            "widgets": {
                "ghost": {"root": "does/not/exist", "consumes_apis": ["bad_name"]},
            },
            "schema": {"mandatory_zoho_fields": [], "table_to_form": {}, "fk_relationships": [],
                       "upload_order": [], "exclude_fields": []},
            "lint": {"threshold_fallback": "999.99", "dual_threshold_fallback": "5000.00",
                     "demo_email_domains": []},
        }

    monkeypatch.setattr(lh, "load_config", fake_load_config)
    monkeypatch.setattr("sys.argv", ["forgeds-lint-hybrid"])

    try:
        rc = lh.main()
    except SystemExit as exc:
        rc = exc.code

    captured = capsys.readouterr()
    assert rc == 2
    assert "WG001" in captured.out or "WG003" in captured.out
