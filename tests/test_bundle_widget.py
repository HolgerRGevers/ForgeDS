"""Tests for forgeds-bundle-widget (Phase 2C Task 6)."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import json
import shutil
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from forgeds.widgets.bundle_widget import main
from forgeds.widgets.scaffold_widget import main as scaffold_main
from forgeds.widgets.zet_shim import ZetResult


FIXTURES = Path(__file__).parent / "fixtures" / "widgets_phase2c"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_project(tmp_path: Path, *, widget_name: str = "good_bundle_widget",
                   spec_name: str = "spec_minimal",
                   override_name: str | None = None) -> Path:
    """Build a project root containing:
      - forgeds.yaml declaring one widget
      - src/widgets/<widget_name>/... (scaffolded from spec)
    Returns project root.
    """
    # Write forgeds.yaml
    declared_name = override_name or widget_name
    (tmp_path / "forgeds.yaml").write_text(
        f"project:\n"
        f"  name: test\n"
        f"  version: 0.0.1\n"
        f"custom_apis:\n"
        f"  - get_pending_claims\n"
        f"  - approve_claim\n"
        f"widgets:\n"
        f"  {declared_name}:\n"
        f"    root: src/widgets/{widget_name}\n"
        f"    consumes_apis:\n"
        f"      - get_pending_claims\n"
        f"      - approve_claim\n",
        encoding="utf-8",
    )

    # Prepare a spec file that renames the default
    spec_src = (FIXTURES / spec_name / "widget-spec.yaml").read_text(encoding="utf-8")
    # Rename to match requested widget_name
    lines = spec_src.splitlines()
    lines[0] = f"name: {widget_name}"
    spec_text = "\n".join(lines) + "\n"
    spec_path = tmp_path / "widget-spec.yaml"
    spec_path.write_text(spec_text, encoding="utf-8")

    # Scaffold from the spec into src/widgets/
    widgets_parent = tmp_path / "src" / "widgets"
    rc = scaffold_main(["--spec", str(spec_path), "--output", str(widgets_parent)])
    assert rc == 0, f"scaffold setup failed with rc={rc}"
    return tmp_path


# ---------------------------------------------------------------------------
# Happy path with --no-zet
# ---------------------------------------------------------------------------

def test_bundle_happy_path_no_zet(tmp_path, monkeypatch):
    project = _build_project(tmp_path)
    monkeypatch.chdir(project)

    rc = main(["--no-zet", "--skip-lint"])
    # Exit 0 (no warnings) or 1 (if BND005/TODO-tokens fire). Scaffolded index.js
    # has TODO tokens, so BND005 will warn.
    assert rc in (0, 1)

    zip_path = project / "dist" / "widgets" / "good_bundle_widget-0.0.1.zip"
    assert zip_path.is_file(), f"expected {zip_path}, found: {list((project / 'dist' / 'widgets').glob('*'))}"

    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        assert "plugin-manifest.json" in names
        assert "index.js" in names
        assert "index.html" in names
        assert "styles.css" in names
        # widget-spec.yaml must NOT be in the bundle (authoring-only)
        assert "widget-spec.yaml" not in names


# ---------------------------------------------------------------------------
# ZET absent
# ---------------------------------------------------------------------------

def test_bundle_exits_3_when_zet_missing(tmp_path, monkeypatch):
    project = _build_project(tmp_path)
    monkeypatch.chdir(project)

    # Without --no-zet, mock zet_shim to report absent
    with patch("forgeds.widgets.bundle_widget.run_zet_pack",
               return_value=ZetResult(returncode=3, stdout="", stderr="absent")):
        rc = main(["--skip-lint"])
    assert rc == 3


def test_bundle_succeeds_with_no_zet_flag(tmp_path, monkeypatch):
    project = _build_project(tmp_path)
    monkeypatch.chdir(project)

    # Even when zet would be absent, --no-zet must succeed
    with patch("forgeds.widgets.bundle_widget.run_zet_pack",
               return_value=ZetResult(returncode=3, stdout="", stderr="absent")):
        rc = main(["--no-zet", "--skip-lint"])
    assert rc in (0, 1)


# ---------------------------------------------------------------------------
# Spec / manifest mismatch
# ---------------------------------------------------------------------------

def test_bundle_rejects_spec_manifest_mismatch_BND001(tmp_path, monkeypatch, capsys):
    # Build project, then mutate the manifest to have a different name
    project = _build_project(tmp_path)
    manifest_path = project / "src" / "widgets" / "good_bundle_widget" / "plugin-manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["name"] = "mismatched"
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    monkeypatch.chdir(project)
    rc = main(["--no-zet", "--skip-lint"])
    assert rc == 2
    out = capsys.readouterr().out
    assert "WSP003" in out or "BND001" in out


# ---------------------------------------------------------------------------
# Missing manifest
# ---------------------------------------------------------------------------

def test_bundle_missing_manifest_BND001(tmp_path, monkeypatch, capsys):
    project = _build_project(tmp_path)
    (project / "src" / "widgets" / "good_bundle_widget" / "plugin-manifest.json").unlink()
    monkeypatch.chdir(project)

    rc = main(["--no-zet", "--skip-lint"])
    assert rc == 2
    out = capsys.readouterr().out
    assert "WG004" in out or "BND001" in out


# ---------------------------------------------------------------------------
# ZET stderr surfacing
# ---------------------------------------------------------------------------

def test_bundle_surfaces_zet_stderr_as_BND003(tmp_path, monkeypatch, capsys):
    project = _build_project(tmp_path)
    monkeypatch.chdir(project)

    def fake_zet(source_dir, dist_dir, **kwargs):
        # Simulate zet pack writing a zip and emitting a stderr warning
        Path(dist_dir).mkdir(parents=True, exist_ok=True)
        (Path(dist_dir) / "good_bundle_widget-0.0.1.zip").write_bytes(b"PK\x03\x04")
        return ZetResult(returncode=0, stdout="", stderr="warning: foo")

    with patch("forgeds.widgets.bundle_widget.run_zet_pack", side_effect=fake_zet):
        rc = main(["--skip-lint"])
    assert rc == 1  # warnings
    out = capsys.readouterr().out
    assert "BND003" in out


def test_bundle_zet_failure_BND002(tmp_path, monkeypatch, capsys):
    project = _build_project(tmp_path)
    monkeypatch.chdir(project)

    with patch("forgeds.widgets.bundle_widget.run_zet_pack",
               return_value=ZetResult(returncode=1, stdout="", stderr="bad")):
        rc = main(["--skip-lint"])
    assert rc == 2
    out = capsys.readouterr().out
    assert "BND002" in out


# ---------------------------------------------------------------------------
# BND005 — TODO tokens
# ---------------------------------------------------------------------------

def test_bundle_todo_tokens_BND005(tmp_path, monkeypatch, capsys):
    project = _build_project(tmp_path)
    monkeypatch.chdir(project)

    # Scaffolded index.js has TODO tokens (TODO(phase-2a), TODO(zoho-lifecycle))
    rc = main(["--no-zet", "--skip-lint"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "BND005" in out


# ---------------------------------------------------------------------------
# BND006 — output collision
# ---------------------------------------------------------------------------

def test_bundle_output_collision_BND006(tmp_path, monkeypatch, capsys):
    project = _build_project(tmp_path)
    monkeypatch.chdir(project)

    # Pre-create the output zip
    out_dir = project / "dist" / "widgets"
    out_dir.mkdir(parents=True)
    (out_dir / "good_bundle_widget-0.0.1.zip").write_bytes(b"prior")

    rc = main(["--no-zet", "--skip-lint"])
    assert rc == 2
    out = capsys.readouterr().out
    assert "BND006" in out
    # Prior content unchanged
    assert (out_dir / "good_bundle_widget-0.0.1.zip").read_bytes() == b"prior"


def test_bundle_force_overwrites_existing(tmp_path, monkeypatch):
    project = _build_project(tmp_path)
    monkeypatch.chdir(project)
    out_dir = project / "dist" / "widgets"
    out_dir.mkdir(parents=True)
    zp = out_dir / "good_bundle_widget-0.0.1.zip"
    zp.write_bytes(b"prior")

    rc = main(["--no-zet", "--skip-lint", "--force"])
    assert rc in (0, 1)
    assert zp.read_bytes() != b"prior"


# ---------------------------------------------------------------------------
# Widget selection flags
# ---------------------------------------------------------------------------

def test_bundle_widget_selection_single_auto(tmp_path, monkeypatch):
    """Single-widget project works without --widget flag."""
    project = _build_project(tmp_path)
    monkeypatch.chdir(project)
    rc = main(["--no-zet", "--skip-lint"])
    assert rc in (0, 1)


def test_bundle_widget_selection_multiple_requires_flag(tmp_path, monkeypatch, capsys):
    # Two widgets declared, no --widget flag -> BND001
    (tmp_path / "forgeds.yaml").write_text(
        "project:\n  name: t\n  version: 0.0.1\n"
        "custom_apis:\n  - a\n  - b\n"
        "widgets:\n"
        "  one:\n    root: src/widgets/one\n    consumes_apis:\n      - a\n"
        "  two:\n    root: src/widgets/two\n    consumes_apis:\n      - b\n",
        encoding="utf-8",
    )
    # No actual widget dirs; we never reach that code -- should fail on resolve
    monkeypatch.chdir(tmp_path)
    rc = main(["--no-zet", "--skip-lint"])
    assert rc == 2
    out = capsys.readouterr().out
    assert "BND001" in out
    assert "multiple widgets" in out or "pass --widget" in out
