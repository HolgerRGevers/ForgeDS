"""Tests for forgeds-deploy-widget (Phase 2C Task 8)."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import json
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from forgeds.widgets.deploy_widget import main as deploy_main
from forgeds.widgets.publish_client import PublishResult


FIXTURES = Path(__file__).parent / "fixtures" / "widgets_phase2c"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project_with_bundle(tmp_path: Path, name: str = "expense_dashboard",
                              version: str = "0.0.1") -> tuple[Path, Path]:
    """Create a project with a pre-bundled widget ZIP + widget tree.

    Returns (project_root, zip_path).
    """
    # forgeds.yaml
    (tmp_path / "forgeds.yaml").write_text(
        f"project:\n  name: t\n  version: 0.0.1\n"
        f"custom_apis:\n  - get_pending_claims\n  - approve_claim\n"
        f"widgets:\n"
        f"  {name}:\n    root: src/widgets/{name}\n"
        f"    consumes_apis:\n      - get_pending_claims\n      - approve_claim\n",
        encoding="utf-8",
    )
    # widget tree
    widget_dir = tmp_path / "src" / "widgets" / name
    widget_dir.mkdir(parents=True)
    src_spec = (FIXTURES / "spec_minimal" / "widget-spec.yaml").read_text(encoding="utf-8")
    lines = src_spec.splitlines()
    lines[0] = f"name: {name}"
    (widget_dir / "widget-spec.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Manifest matching the name and version
    (widget_dir / "plugin-manifest.json").write_text(json.dumps({
        "name": name,
        "version": version,
        "config": {"widgets": [{"location": "form_view", "url": "index.html"}]},
        "permissions": [],
    }, indent=2), encoding="utf-8")
    (widget_dir / "index.html").write_text("<!doctype html><html></html>", encoding="utf-8")
    (widget_dir / "index.js").write_text("// code", encoding="utf-8")

    # Bundle ZIP
    dist = tmp_path / "dist" / "widgets"
    dist.mkdir(parents=True)
    zp = dist / f"{name}-{version}.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr("plugin-manifest.json", (widget_dir / "plugin-manifest.json").read_text())
        zf.writestr("index.html", "<!doctype html>")
        zf.writestr("index.js", "// code")
    return (tmp_path, zp)


# ---------------------------------------------------------------------------
# Flag conflicts
# ---------------------------------------------------------------------------

def test_deploy_confirm_and_dry_run_DPY002(capsys, tmp_path, monkeypatch):
    project, _ = _make_project_with_bundle(tmp_path)
    monkeypatch.chdir(project)
    rc = deploy_main(["--dry-run", "--confirm", "--target", "creator:app-id=a"])
    assert rc == 2
    assert "DPY002" in capsys.readouterr().out


def test_deploy_confirm_without_target_DPY001(capsys, tmp_path, monkeypatch):
    project, _ = _make_project_with_bundle(tmp_path)
    monkeypatch.chdir(project)
    rc = deploy_main(["--confirm"])
    assert rc == 2
    assert "DPY001" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Spike gate
# ---------------------------------------------------------------------------

def test_deploy_confirm_returns_exit3_until_spike(
    capsys, tmp_path, monkeypatch,
):
    """Without both the override env AND pytest ctx, --confirm exits 3."""
    project, _ = _make_project_with_bundle(tmp_path)
    monkeypatch.chdir(project)
    # Explicitly UNSET the override env so the gate stays closed even
    # though PYTEST_CURRENT_TEST is set automatically by pytest.
    monkeypatch.delenv("FORGEDS_DEPLOY_SPIKE_OVERRIDE_TESTONLY", raising=False)

    rc = deploy_main(["--confirm", "--target", "creator:app-id=a", "--non-interactive"])
    out = capsys.readouterr().out
    assert rc == 3
    assert "§7.5" in out or "7.5" in out
    assert "DPY001" in out


def test_deploy_spike_gate_env_alone_not_sufficient(
    capsys, tmp_path, monkeypatch,
):
    """Setting the override env but simulating no pytest ctx still exits 3."""
    project, _ = _make_project_with_bundle(tmp_path)
    monkeypatch.chdir(project)
    monkeypatch.setenv("FORGEDS_DEPLOY_SPIKE_OVERRIDE_TESTONLY", "1")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    rc = deploy_main(["--confirm", "--target", "creator:app-id=a", "--non-interactive"])
    assert rc == 3
    assert "DPY001" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Dry-run default + OAuth resolution
# ---------------------------------------------------------------------------

def test_deploy_dry_run_is_default_DPY004(capsys, tmp_path, monkeypatch):
    project, _ = _make_project_with_bundle(tmp_path)
    monkeypatch.chdir(project)
    monkeypatch.setenv("ZOHO_ACCESS_TOKEN", "abc")

    with patch("forgeds.widgets.deploy_widget.upload_widget_zip") as mock_upload:
        rc = deploy_main(["--target", "creator:app-id=abc123"])
    assert rc == 0
    mock_upload.assert_not_called()
    out = capsys.readouterr().out
    assert "DPY004" in out
    assert "abc123" in out


def test_deploy_resolves_env_token_DPY004(capsys, tmp_path, monkeypatch):
    project, _ = _make_project_with_bundle(tmp_path)
    monkeypatch.chdir(project)
    monkeypatch.setenv("ZOHO_ACCESS_TOKEN", "from-env")

    rc = deploy_main(["--target", "creator:app-id=a"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "env:ZOHO_ACCESS_TOKEN" in out
    # token value never in output
    assert "from-env" not in out


def test_deploy_resolves_config_token_DPY004(capsys, tmp_path, monkeypatch):
    project, _ = _make_project_with_bundle(tmp_path)
    monkeypatch.chdir(project)
    monkeypatch.delenv("ZOHO_ACCESS_TOKEN", raising=False)

    cfg = project / "config" / "zoho-api.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("access_token: from-config\n", encoding="utf-8")

    rc = deploy_main(["--target", "creator:app-id=a"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "config:zoho-api.yaml" in out
    assert "from-config" not in out


def test_deploy_no_oauth_source_DPY003(capsys, tmp_path, monkeypatch):
    project, _ = _make_project_with_bundle(tmp_path)
    monkeypatch.chdir(project)
    monkeypatch.delenv("ZOHO_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("ZOHO_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("ZOHO_CLIENT_ID", raising=False)
    monkeypatch.delenv("ZOHO_CLIENT_SECRET", raising=False)

    rc = deploy_main(["--target", "creator:app-id=a"])
    assert rc == 2
    out = capsys.readouterr().out
    assert "DPY003" in out


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

def test_deploy_redacts_token_in_all_logs(capsys, tmp_path, monkeypatch):
    project, _ = _make_project_with_bundle(tmp_path)
    monkeypatch.chdir(project)
    secret = "PROD-TOKEN-VALUE-9999"
    monkeypatch.setenv("ZOHO_ACCESS_TOKEN", secret)

    rc = deploy_main(["--verbose", "--target", "creator:app-id=a"])
    captured = capsys.readouterr()
    assert rc == 0
    assert secret not in captured.out
    assert secret not in captured.err


# ---------------------------------------------------------------------------
# Spike-bypassed success path (writes deployment block)
# ---------------------------------------------------------------------------

def test_deploy_writes_deployment_block_on_mocked_success(
    capsys, tmp_path, monkeypatch,
):
    project, zp = _make_project_with_bundle(tmp_path)
    monkeypatch.chdir(project)
    monkeypatch.setenv("ZOHO_ACCESS_TOKEN", "abc")
    monkeypatch.setenv("FORGEDS_DEPLOY_SPIKE_OVERRIDE_TESTONLY", "1")
    # PYTEST_CURRENT_TEST is set automatically by pytest -> spike gate opens

    with patch("forgeds.widgets.deploy_widget.upload_widget_zip",
               return_value=PublishResult(ok=True, response={"code": 3000}, url="u")):
        rc = deploy_main([
            "--confirm", "--non-interactive",
            "--target", "creator:app-id=xyz",
        ])
    assert rc == 0

    # widget-spec.yaml should now have a deployment block
    spec_path = project / "src" / "widgets" / "expense_dashboard" / "widget-spec.yaml"
    text = spec_path.read_text(encoding="utf-8")
    assert "deployment:" in text
    assert "last_uploaded_target:" in text
    assert "creator:app-id=xyz" in text
    assert "last_uploaded_version:" in text


# ---------------------------------------------------------------------------
# JSON-v1 envelope
# ---------------------------------------------------------------------------

def test_deploy_json_envelope(capsys, tmp_path, monkeypatch):
    project, _ = _make_project_with_bundle(tmp_path)
    monkeypatch.chdir(project)
    monkeypatch.setenv("ZOHO_ACCESS_TOKEN", "abc")

    rc = deploy_main(["--target", "creator:app-id=a", "--format", "json-v1"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["tool"] == "deploy_widget"
    assert payload["version"] == "1"
