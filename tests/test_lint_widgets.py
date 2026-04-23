"""Tests for forgeds.widgets.lint_widgets — ESLint orchestrator."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import forgeds.widgets.lint_widgets as lw


def test_eslint_missing_returns_exit_3(capsys):
    """When `npx eslint --version` fails, main() must exit 3 with an install hint."""
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("npx not found")

    with patch.object(lw.subprocess, "run", side_effect=fake_run):
        rc = lw.main(["--no-args-discover"])
    assert rc == 3
    captured = capsys.readouterr()
    assert "eslint" in captured.err.lower()
    assert "install" in captured.err.lower()


def test_emit_text_format_matches_shared_diag(capsys):
    """Text mode prints Diagnostic.__str__ output, one per line."""
    diags = [
        lw._mk_diag("src/widgets/x/index.js", 1, "JS:no-unused-vars", "WARNING", "unused variable"),
    ]
    lw._emit(diags, fmt="text")
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1
    assert "src/widgets/x/index.js:1:" in out[0]
    assert "[JS:no-unused-vars]" in out[0]
    assert "WARNING" in out[0]


def test_emit_json_envelope_shape(capsys):
    """JSON mode emits the v1 envelope with tool/version/diagnostics keys."""
    diags = [
        lw._mk_diag("a.js", 2, "JS:semi", "ERROR", "missing semicolon"),
    ]
    lw._emit(diags, fmt="json-v1")
    payload = json.loads(capsys.readouterr().out)
    assert payload["tool"] == "forgeds-lint-widgets"
    assert payload["version"] == "1"
    assert len(payload["diagnostics"]) == 1
    d = payload["diagnostics"][0]
    assert d["file"] == "a.js"
    assert d["line"] == 2
    assert d["rule"] == "JS:semi"
    assert d["severity"] == "error"
    assert d["message"] == "missing semicolon"


def test_translate_eslint_result_maps_severity():
    """ESLint severity 2 -> ERROR, 1 -> WARNING; severity 0 is dropped."""
    eslint_json = [
        {
            "filePath": "/abs/a.js",
            "messages": [
                {"line": 1, "ruleId": "no-unused-vars", "severity": 1, "message": "unused"},
                {"line": 2, "ruleId": "no-undef",       "severity": 2, "message": "undef"},
                {"line": 3, "ruleId": "off-rule",       "severity": 0, "message": "ignored"},
            ],
        }
    ]
    diags = lw._translate_eslint(eslint_json)
    assert len(diags) == 2
    by_rule = {d.rule: d for d in diags}
    assert by_rule["JS:no-unused-vars"].severity.value == "WARNING"
    assert by_rule["JS:no-undef"].severity.value == "ERROR"
