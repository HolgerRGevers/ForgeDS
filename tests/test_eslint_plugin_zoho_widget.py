"""Tests for eslint-plugin-zoho-widget + sidecar emission (Phase 2B Task 5).

Scope:
  * Sidecar is written by lint_widgets.main() at a deterministic location
    before ESLint is invoked.
  * Sidecar JSON shape matches spec §6.3.
  * Each plugin rule module is loadable under Node and exposes the
    expected ESLint-rule interface (meta + create).

Full ESLint-subprocess integration of the plugin (stage → invoke → parse
findings) is Phase 2C; Phase 2B ships the plugin source and sidecar
wiring as the static complement to the runtime harness.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / "src" / "forgeds" / "widgets" / "eslint-plugin-zoho-widget"


def _node_available() -> bool:
    return shutil.which("node") is not None


def test_plugin_package_json_names_plugin_correctly():
    pkg = json.loads((PLUGIN_DIR / "package.json").read_text(encoding="utf-8"))
    assert pkg["name"] == "eslint-plugin-zoho-widget"
    assert pkg["main"] == "index.js"


def test_plugin_index_exports_rules_object():
    index = (PLUGIN_DIR / "index.js").read_text(encoding="utf-8")
    assert "no-undeclared-apis" in index
    assert "no-unused-apis" in index


@pytest.mark.skipif(not _node_available(), reason="Node not on PATH")
def test_plugin_is_requireable_via_node():
    js = (
        "const p = require('./index.js');"
        "process.stdout.write(JSON.stringify(Object.keys(p.rules)));"
    )
    r = subprocess.run(
        ["node", "-e", js], cwd=str(PLUGIN_DIR), capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    rules = json.loads(r.stdout.strip())
    assert set(rules) == {"no-undeclared-apis", "no-unused-apis"}


@pytest.mark.skipif(not _node_available(), reason="Node not on PATH")
def test_no_undeclared_apis_rule_exposes_eslint_interface():
    js = (
        "const r = require('./rules/no-undeclared-apis.js');"
        "const ok = r.meta && r.meta.type === 'problem' && typeof r.create === 'function';"
        "process.stdout.write(ok ? 'yes' : 'no');"
    )
    r = subprocess.run(
        ["node", "-e", js], cwd=str(PLUGIN_DIR), capture_output=True, text=True,
    )
    assert r.stdout.strip() == "yes", r.stderr


@pytest.mark.skipif(not _node_available(), reason="Node not on PATH")
def test_no_unused_apis_rule_exposes_eslint_interface():
    js = (
        "const r = require('./rules/no-unused-apis.js');"
        "const ok = r.meta && typeof r.create === 'function';"
        "process.stdout.write(ok ? 'yes' : 'no');"
    )
    r = subprocess.run(
        ["node", "-e", js], cwd=str(PLUGIN_DIR), capture_output=True, text=True,
    )
    assert r.stdout.strip() == "yes", r.stderr


@pytest.mark.skipif(not _node_available(), reason="Node not on PATH")
def test_no_undeclared_apis_rule_no_ops_without_sidecar(tmp_path):
    """The rule's create() returns {} when FORGEDS_ESLINT_SIDECAR is unset."""
    js = (
        "delete process.env.FORGEDS_ESLINT_SIDECAR;"
        "const r = require('./rules/no-undeclared-apis.js');"
        "const visitors = r.create({ getFilename: () => '/x' });"
        "process.stdout.write(JSON.stringify(Object.keys(visitors)));"
    )
    env = {**os.environ}
    env.pop("FORGEDS_ESLINT_SIDECAR", None)
    r = subprocess.run(
        ["node", "-e", js], cwd=str(PLUGIN_DIR), capture_output=True, text=True, env=env,
    )
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout.strip()) == []


def test_lint_widgets_writes_sidecar_when_widgets_declared(tmp_path, monkeypatch):
    """Invoking lint_widgets against a project with widgets must emit the sidecar."""
    import forgeds.widgets.lint_widgets as lw

    # Stage a minimal project that declares one widget, and copy a tiny JS file
    # so ESLint has something to chew on.
    project = tmp_path / "proj"
    project.mkdir()
    (project / "forgeds.yaml").write_text(
        "custom_apis:\n"
        "  - get_pending_claims\n"
        "widgets:\n"
        "  w1:\n"
        "    root: src/widgets/w1/\n"
        "    consumes_apis: [get_pending_claims]\n",
        encoding="utf-8",
    )
    widget_root = project / "src" / "widgets" / "w1"
    widget_root.mkdir(parents=True)
    (widget_root / "index.js").write_text("ZOHO.CREATOR.API.getRecords('r');\n", encoding="utf-8")

    monkeypatch.chdir(project)
    # Bypass the actual ESLint subprocess so the test does not depend on npx.
    monkeypatch.setattr(lw, "_eslint_available", lambda: True)
    monkeypatch.setattr(lw, "_run_eslint_on", lambda *_args, **_kwargs: [])

    rc = lw.main([])
    assert rc == 0

    sidecar = project / ".forgeds" / "eslint_plugin_manifest.json"
    assert sidecar.exists(), "sidecar was not written"

    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["version"] == "1"
    assert "w1" in payload["widgets"]
    w = payload["widgets"]["w1"]
    assert Path(w["root"]).resolve() == widget_root.resolve()
    assert w["consumesApis"] == ["get_pending_claims"]
    assert isinstance(w.get("knownSdkMethods"), list)
