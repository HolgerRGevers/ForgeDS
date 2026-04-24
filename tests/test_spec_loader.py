"""Tests for widget-spec.yaml loader (Phase 2C Task 3)."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import builtins
import tempfile
from pathlib import Path

import pytest

from forgeds._shared.diagnostics import Severity
from forgeds.widgets.spec_loader import (
    load_spec,
    check_cross_refs,
    write_deployment_block,
)

FIXTURES = Path(__file__).parent / "fixtures" / "widgets_phase2c"


# ---------------------------------------------------------------------------
# load_spec
# ---------------------------------------------------------------------------

def test_load_spec_minimal_valid():
    spec, diags = load_spec(str(FIXTURES / "spec_minimal" / "widget-spec.yaml"))
    assert spec["name"] == "expense_dashboard"
    assert spec["location"] == "form_view"
    assert spec["consumes_apis"] == ["get_pending_claims", "approve_claim"]
    assert diags == []


def test_load_spec_full_valid():
    spec, diags = load_spec(str(FIXTURES / "spec_full" / "widget-spec.yaml"))
    assert spec["ui_primitives"] == ["card", "table", "modal"]
    assert spec["state_model"] == ["selectedClaim", "pendingList"]
    assert spec["events_bound"] == ["PageLoad", "RecordSave"]
    assert spec["deployment"]["last_uploaded_at"] is None
    assert diags == []


def test_load_spec_missing_file_WSP001(tmp_path):
    missing = tmp_path / "does-not-exist.yaml"
    spec, diags = load_spec(str(missing))
    assert spec == {}
    assert len(diags) == 1
    assert diags[0].rule == "WSP001"
    assert diags[0].severity == Severity.ERROR


def test_load_spec_missing_name_WSP002():
    spec, diags = load_spec(str(FIXTURES / "spec_missing_name" / "widget-spec.yaml"))
    rules = [d.rule for d in diags]
    assert "WSP002" in rules
    missing_name = [d for d in diags if d.rule == "WSP002" and "name" in d.message]
    assert len(missing_name) == 1


def test_load_spec_bad_location_WSP002():
    spec, diags = load_spec(str(FIXTURES / "spec_bad_location" / "widget-spec.yaml"))
    enum_diags = [d for d in diags if d.rule == "WSP002" and "enum" in d.message]
    assert len(enum_diags) == 1


def test_load_spec_decorative_wrong_type_WSP005(tmp_path):
    """When a decorative field is the wrong type, warn but don't halt."""
    p = tmp_path / "widget-spec.yaml"
    p.write_text(
        "name: w\n"
        "location: form_view\n"
        "description: d\n"
        "consumes_apis:\n"
        "  - api_a\n"
        "ui_primitives: card\n",  # string instead of list
        encoding="utf-8",
    )
    spec, diags = load_spec(str(p))
    # spec should still load
    assert spec["name"] == "w"
    # a WSP005 WARNING should fire for the decorative field
    wsp005 = [d for d in diags if d.rule == "WSP005"]
    assert len(wsp005) >= 1
    assert wsp005[0].severity == Severity.WARNING


# ---------------------------------------------------------------------------
# write_deployment_block (atomic, in-place)
# ---------------------------------------------------------------------------

def test_write_deployment_block_roundtrip(tmp_path):
    """Load a spec, write a deployment block, reload, verify."""
    src = FIXTURES / "spec_minimal" / "widget-spec.yaml"
    p = tmp_path / "widget-spec.yaml"
    p.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    original = p.read_text(encoding="utf-8")
    write_deployment_block(str(p), {
        "last_uploaded_at": "2026-04-23T18:20:00Z",
        "last_uploaded_version": "0.0.1",
        "last_uploaded_target": "creator:app-id=abc123",
    })
    after = p.read_text(encoding="utf-8")

    # Author-written section (everything before `deployment:`) unchanged
    # Since minimal fixture has no deployment: block, the append path is exercised.
    assert after.startswith(original)

    # Reload and verify
    spec, diags = load_spec(str(p))
    assert diags == []
    assert spec["deployment"]["last_uploaded_at"] == "2026-04-23T18:20:00Z"
    assert spec["deployment"]["last_uploaded_version"] == "0.0.1"
    assert spec["deployment"]["last_uploaded_target"] == "creator:app-id=abc123"


def test_write_deployment_block_replaces_existing(tmp_path):
    """If a deployment: block already exists, replace only that block."""
    src = FIXTURES / "spec_full" / "widget-spec.yaml"
    p = tmp_path / "widget-spec.yaml"
    p.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    original_lines = p.read_text(encoding="utf-8").splitlines()
    # find `deployment:` index in original
    dep_idx = next(i for i, l in enumerate(original_lines) if l.startswith("deployment:"))
    prefix_original = "\n".join(original_lines[:dep_idx])

    write_deployment_block(str(p), {
        "last_uploaded_at": "2026-04-23T18:20:00Z",
        "last_uploaded_version": "0.0.2",
        "last_uploaded_target": "creator:app-id=xyz",
    })

    after_text = p.read_text(encoding="utf-8")
    # Prefix preserved exactly
    assert after_text.startswith(prefix_original)
    # New deployment values present
    assert "2026-04-23T18:20:00Z" in after_text
    assert "0.0.2" in after_text
    # Reload and verify
    spec, diags = load_spec(str(p))
    assert spec["deployment"]["last_uploaded_version"] == "0.0.2"


def test_write_deployment_block_atomic_on_write_failure(tmp_path, monkeypatch):
    """Mid-write failure must leave original file byte-for-byte intact."""
    src = FIXTURES / "spec_minimal" / "widget-spec.yaml"
    p = tmp_path / "widget-spec.yaml"
    p.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    original = p.read_text(encoding="utf-8")
    original_bytes = p.read_bytes()

    real_open = builtins.open
    tmp_path_str = str(tmp_path)

    def flaky_open(path, *args, **kwargs):
        mode = args[0] if args else kwargs.get("mode", "r")
        # Only fail on write-opens against the tmp sibling file
        if str(path).endswith(".forgeds-tmp") and "w" in mode:
            raise OSError("simulated write failure")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", flaky_open)

    with pytest.raises(OSError):
        write_deployment_block(str(p), {
            "last_uploaded_at": "x",
            "last_uploaded_version": "y",
            "last_uploaded_target": "z",
        })

    # Original intact
    assert p.read_bytes() == original_bytes
    # No tmp leftover
    leftovers = list(tmp_path.glob("*.forgeds-tmp"))
    assert leftovers == []


# ---------------------------------------------------------------------------
# check_cross_refs
# ---------------------------------------------------------------------------

def test_cross_ref_name_mismatch_WSP003():
    spec = {"name": "a", "consumes_apis": []}
    manifest = {"name": "b", "version": "0.0.1", "config": {"widgets": []}}
    diags = check_cross_refs(spec, manifest, directory_name="a", config={})
    wsp003 = [d for d in diags if d.rule == "WSP003"]
    assert len(wsp003) == 1
    assert "a" in wsp003[0].message and "b" in wsp003[0].message


def test_cross_ref_directory_mismatch_WSP003():
    spec = {"name": "a", "consumes_apis": []}
    manifest = {"name": "a"}
    diags = check_cross_refs(spec, manifest, directory_name="c", config={})
    wsp003 = [d for d in diags if d.rule == "WSP003"]
    assert len(wsp003) == 1


def test_cross_ref_consumes_apis_undeclared_WSP004():
    spec = {"name": "w", "consumes_apis": ["known_api", "unknown_api"]}
    config = {"custom_apis": ["known_api"]}
    diags = check_cross_refs(spec, manifest=None, directory_name=None, config=config)
    wsp004 = [d for d in diags if d.rule == "WSP004"]
    assert len(wsp004) == 1
    assert "unknown_api" in wsp004[0].message


def test_cross_ref_all_match_no_diagnostics():
    spec = {"name": "w", "consumes_apis": ["api1"]}
    manifest = {"name": "w"}
    config = {"custom_apis": ["api1"]}
    diags = check_cross_refs(spec, manifest, directory_name="w", config=config)
    assert diags == []


def test_cross_ref_custom_apis_explicitly_empty_flags_orphans():
    """Review finding P1-1: when custom_apis is present but empty, consumes
    entries must still be flagged as orphans."""
    spec = {"name": "w", "consumes_apis": ["api1", "api2"]}
    config = {"custom_apis": []}
    diags = check_cross_refs(spec, manifest=None, directory_name=None, config=config)
    wsp004 = [d for d in diags if d.rule == "WSP004"]
    assert len(wsp004) == 2


def test_cross_ref_custom_apis_absent_skips_check():
    """Review finding P1-1: when custom_apis is absent from config, the user
    hasn't wired it yet -- don't flag consumes entries."""
    spec = {"name": "w", "consumes_apis": ["api1"]}
    config = {}  # no custom_apis key at all
    diags = check_cross_refs(spec, manifest=None, directory_name=None, config=config)
    assert [d for d in diags if d.rule == "WSP004"] == []
