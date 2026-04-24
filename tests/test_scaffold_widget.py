"""Tests for forgeds-scaffold-widget (Phase 2C Task 4)."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from forgeds.widgets.scaffold_widget import main, _render_templates
from forgeds.widgets.spec_loader import load_spec
from forgeds.widgets.validate_manifest import validate_manifest_file

FIXTURES = Path(__file__).parent / "fixtures" / "widgets_phase2c"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _run_scaffold(tmp_path: Path, spec_dir: str, extra_args: list[str] | None = None) -> int:
    spec_src = FIXTURES / spec_dir / "widget-spec.yaml"
    out_dir = tmp_path / "src_widgets"
    args = ["--spec", str(spec_src), "--output", str(out_dir)]
    if extra_args:
        args.extend(extra_args)
    return main(args)


# ---------------------------------------------------------------------------
# Happy-path scaffold
# ---------------------------------------------------------------------------

def test_scaffold_emits_full_tree_from_minimal_spec(tmp_path):
    rc = _run_scaffold(tmp_path, "spec_minimal")
    assert rc == 0

    out_dir = tmp_path / "src_widgets" / "expense_dashboard"
    expected = ["widget-spec.yaml", "plugin-manifest.json", "index.js", "index.html", "styles.css"]
    for name in expected:
        assert (out_dir / name).is_file(), f"missing {name}"

    # Manifest passes Phase 1 validator
    manifest_path = out_dir / "plugin-manifest.json"
    diags = validate_manifest_file(str(manifest_path))
    assert diags == [], f"manifest validator found issues: {diags}"

    # index.js mentions the description in a top comment
    idx = (out_dir / "index.js").read_text(encoding="utf-8")
    assert "Displays expense claims" in idx
    # One stub per consumes_api
    assert "async function get_pending_claims" in idx
    assert "async function approve_claim" in idx
    # TODO tags present
    assert "TODO(phase-2a)" in idx
    assert "TODO(zoho-lifecycle)" in idx


def test_scaffold_emits_full_tree_from_full_spec(tmp_path):
    rc = _run_scaffold(tmp_path, "spec_full")
    assert rc == 0

    out_dir = tmp_path / "src_widgets" / "expense_dashboard"
    idx = (out_dir / "index.js").read_text(encoding="utf-8")

    # state model expanded
    assert "selectedClaim: null" in idx
    assert "pendingList: null" in idx
    # events bound expanded
    assert "function onPageLoad" in idx
    assert "function onRecordSave" in idx


# ---------------------------------------------------------------------------
# Malformed spec
# ---------------------------------------------------------------------------

def test_scaffold_emits_diagnostics_for_malformed_spec(tmp_path, capsys):
    rc = _run_scaffold(tmp_path, "spec_missing_name")
    assert rc == 2
    out = capsys.readouterr().out
    assert "WSP002" in out
    # No files written
    target = tmp_path / "src_widgets"
    assert not target.exists() or not any(target.rglob("*.js"))


# ---------------------------------------------------------------------------
# Collision & --force behavior
# ---------------------------------------------------------------------------

def test_scaffold_errors_on_collision_without_force(tmp_path, capsys):
    # Seed a conflicting existing file at the target path
    target = tmp_path / "src_widgets" / "expense_dashboard"
    target.mkdir(parents=True)
    (target / "index.js").write_text("HANDWRITTEN", encoding="utf-8")

    rc = _run_scaffold(tmp_path, "spec_minimal")
    assert rc == 2
    out = capsys.readouterr().out
    assert "SCF001" in out
    # existing file preserved
    assert (target / "index.js").read_text(encoding="utf-8") == "HANDWRITTEN"


def test_scaffold_overwrites_with_force_and_warns(tmp_path, capsys):
    target = tmp_path / "src_widgets" / "expense_dashboard"
    target.mkdir(parents=True)
    (target / "index.js").write_text("HANDWRITTEN", encoding="utf-8")

    rc = _run_scaffold(tmp_path, "spec_minimal", ["--force"])
    assert rc == 1  # warnings
    out = capsys.readouterr().out
    assert "SCF002" in out
    # file overwritten
    content = (target / "index.js").read_text(encoding="utf-8")
    assert "HANDWRITTEN" not in content
    assert "get_pending_claims" in content


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def test_scaffold_dry_run_touches_no_files(tmp_path, capsys):
    rc = _run_scaffold(tmp_path, "spec_minimal", ["--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[dry-run]" in out
    # no files written
    target = tmp_path / "src_widgets"
    assert not target.exists()


def test_scaffold_dry_run_ignores_existing_for_exit_code(tmp_path, capsys):
    """Dry-run is observation-only; even with pre-existing files, exit 0."""
    target = tmp_path / "src_widgets" / "expense_dashboard"
    target.mkdir(parents=True)
    (target / "index.js").write_text("HAND", encoding="utf-8")

    rc = _run_scaffold(tmp_path, "spec_minimal", ["--dry-run"])
    # dry-run doesn't emit SCF001; file is preserved
    assert rc == 0
    assert (target / "index.js").read_text(encoding="utf-8") == "HAND"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_scaffold_is_idempotent_on_unchanged_spec(tmp_path, capsys):
    rc1 = _run_scaffold(tmp_path, "spec_minimal")
    assert rc1 == 0

    target = tmp_path / "src_widgets" / "expense_dashboard"
    first_bytes = {f.name: f.read_bytes() for f in target.iterdir()}

    # Second run without --force should be a no-op
    rc2 = _run_scaffold(tmp_path, "spec_minimal")
    assert rc2 == 0
    out = capsys.readouterr().out
    assert "SCF001" not in out

    # File bytes unchanged
    for name, b in first_bytes.items():
        assert (target / name).read_bytes() == b


def test_scaffold_idempotency_drift_SCF004(tmp_path, capsys):
    """After first successful scaffold, hand-edit one file; second run
    without --force should report drift as SCF004 + SCF001 and halt."""
    _run_scaffold(tmp_path, "spec_minimal")
    target = tmp_path / "src_widgets" / "expense_dashboard"
    idx = target / "index.js"
    idx.write_text("HAND-EDITED\n", encoding="utf-8")

    rc = _run_scaffold(tmp_path, "spec_minimal")
    # Drift + collision → exit 2
    assert rc == 2
    out = capsys.readouterr().out
    assert "SCF004" in out
    assert "SCF001" in out
    # hand-edit preserved
    assert idx.read_text(encoding="utf-8") == "HAND-EDITED\n"


# ---------------------------------------------------------------------------
# JSON-v1 envelope
# ---------------------------------------------------------------------------

def test_scaffold_output_json_envelope(tmp_path, capsys):
    rc = _run_scaffold(tmp_path, "spec_minimal", ["--format", "json-v1"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["tool"] == "scaffold_widget"
    assert payload["version"] == "1"
    assert isinstance(payload["diagnostics"], list)


# ---------------------------------------------------------------------------
# _render_templates direct (no filesystem)
# ---------------------------------------------------------------------------

def test_render_templates_no_events_produces_placeholder():
    spec = {
        "name": "w",
        "location": "form_view",
        "description": "d",
        "consumes_apis": [],
    }
    out = _render_templates(spec)
    assert "(no consumes_apis declared)" in out["index.js"]
    assert "(no state_model declared)" in out["index.js"]
    assert "(no events_bound declared)" in out["index.js"]
