"""Tests for the shared JSON-v1 envelope serializer."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from forgeds._shared.diagnostics import Diagnostic, Severity
from forgeds._shared.envelope import (
    ENVELOPE_VERSION,
    derive_overall,
    status_envelope_v1,
    to_json_v1,
)


def _diag(file="a.dg", line=1, rule="DG001", severity=Severity.ERROR, message="x"):
    return Diagnostic(file=file, line=line, rule=rule, severity=severity, message=message)


def test_envelope_emits_empty_diagnostics_array():
    out = json.loads(to_json_v1("forgeds-lint", []))
    assert out["diagnostics"] == []
    assert "diagnostics" in out


def test_envelope_version_is_string():
    out = json.loads(to_json_v1("forgeds-lint", []))
    assert out["version"] == "1"
    assert isinstance(out["version"], str)
    assert ENVELOPE_VERSION == "1"


def test_envelope_tool_field_exact_name():
    out = json.loads(to_json_v1("forgeds-lint-access", []))
    assert out["tool"] == "forgeds-lint-access"


def test_envelope_severity_is_lowercase():
    out = json.loads(to_json_v1("forgeds-lint", [
        _diag(severity=Severity.ERROR),
        _diag(severity=Severity.WARNING, rule="DG002"),
        _diag(severity=Severity.INFO, rule="DG003"),
    ]))
    sevs = {d["severity"] for d in out["diagnostics"]}
    assert sevs == {"error", "warning", "info"}


def test_envelope_all_base_fields_required():
    out = json.loads(to_json_v1("forgeds-lint", [_diag()]))
    d = out["diagnostics"][0]
    assert set(d.keys()) == {"file", "line", "rule", "severity", "message"}


def test_status_envelope_shape():
    checks = [
        {"category": "db_freshness", "id": "deluge_lang.db", "status": "ok",
         "message": "", "rule": None},
    ]
    out = json.loads(status_envelope_v1("forgeds-status", "ok", checks))
    assert out["tool"] == "forgeds-status"
    assert out["version"] == "1"
    assert out["overall"] == "ok"
    assert out["checks"] == checks


def test_status_overall_derivation_ok():
    assert derive_overall(["ok", "ok", "skip"]) == "ok"


def test_status_overall_derivation_warn():
    assert derive_overall(["ok", "warn"]) == "warn"


def test_status_overall_derivation_miss_is_fail():
    assert derive_overall(["ok", "miss", "warn"]) == "fail"


def test_status_overall_derivation_fail_beats_warn():
    assert derive_overall(["warn", "fail"]) == "fail"
