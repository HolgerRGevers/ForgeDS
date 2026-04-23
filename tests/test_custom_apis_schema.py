"""Tests for the extended custom_apis schema loader and CFG diagnostics."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from forgeds._shared.config import (
    load_config,
    load_config_with_diagnostics,
    normalize_custom_apis,
    validate_custom_apis,
)
from forgeds._shared.diagnostics import Severity

FIXTURES = Path(__file__).parent / "fixtures" / "custom_apis"


def _rules(diags):
    return {d.rule for d in diags}


def test_config_loader_accepts_form_a_custom_apis():
    cfg = load_config(start=str(FIXTURES / "form_a_bare_list"))
    assert cfg["custom_apis"] == ["get_pending_claims", "approve_claim"]


def test_config_loader_accepts_form_b_custom_apis():
    cfg = load_config(start=str(FIXTURES / "form_b_extended"))
    apis = cfg["custom_apis"]
    assert "get_pending_claims" in apis
    gpc = apis["get_pending_claims"]
    assert gpc["returns"] == "PendingClaim[]"
    assert gpc["params"][0]["name"] == "status"
    assert gpc["params"][1]["default"] == 50
    assert gpc["permissions"] == ["api.read"]


def test_normalize_form_a_to_dict():
    cfg = {"custom_apis": ["a", "b"]}
    out = normalize_custom_apis(cfg)
    assert out["custom_apis"] == {"a": {}, "b": {}}
    assert out["_custom_apis_form"] == "A"


def test_normalize_form_b_unchanged():
    cfg = {"custom_apis": {"a": {"returns": "string"}}}
    out = normalize_custom_apis(cfg)
    assert out["custom_apis"] == {"a": {"returns": "string"}}
    assert out["_custom_apis_form"] == "B"


def test_cfg010_mixed_forms():
    cfg, diags = load_config_with_diagnostics(start=str(FIXTURES / "mixed_forms"))
    assert "CFG010" in _rules(diags)
    assert any(d.severity == Severity.ERROR for d in diags if d.rule == "CFG010")


def test_cfg011_info_on_form_a():
    cfg, diags = load_config_with_diagnostics(start=str(FIXTURES / "form_a_bare_list"))
    cfg011 = [d for d in diags if d.rule == "CFG011"]
    assert len(cfg011) == 1
    assert cfg011[0].severity == Severity.INFO


def test_cfg011_not_emitted_on_form_b():
    cfg, diags = load_config_with_diagnostics(start=str(FIXTURES / "form_b_extended"))
    assert "CFG011" not in _rules(diags)


def test_cfg013_warn_on_unknown_named_type():
    cfg, diags = load_config_with_diagnostics(start=str(FIXTURES / "unknown_named_type"))
    warns = [d for d in diags if d.rule == "CFG013"]
    assert len(warns) >= 2  # params[0].type and returns
    for d in warns:
        assert d.severity == Severity.WARNING


def test_cfg014_error_on_missing_param_keys():
    cfg, diags = load_config_with_diagnostics(start=str(FIXTURES / "missing_param_keys"))
    err = [d for d in diags if d.rule == "CFG014"]
    assert len(err) == 1
    assert err[0].severity == Severity.ERROR
    assert "name" in err[0].message and "type" in err[0].message


def test_cfg015_error_on_non_list_permissions():
    diags = validate_custom_apis({
        "custom_apis": {"api1": {"permissions": "api.read"}},
    })
    cfg015 = [d for d in diags if d.rule == "CFG015"]
    assert len(cfg015) == 1
    assert cfg015[0].severity == Severity.ERROR


def test_cfg012_widget_consumes_undeclared_api():
    diags = validate_custom_apis({
        "custom_apis": ["a", "b"],
        "widgets": {
            "dash": {
                "root": "src/widgets/dash/",
                "consumes_apis": ["a", "c"],
            },
        },
    })
    cfg012 = [d for d in diags if d.rule == "CFG012"]
    assert len(cfg012) == 1
    assert "dash" in cfg012[0].message and "'c'" in cfg012[0].message


def test_no_diagnostics_on_clean_form_b():
    diags = validate_custom_apis({
        "custom_apis": {
            "api1": {
                "params": [{"name": "x", "type": "string"}],
                "returns": "boolean",
                "permissions": ["api.read"],
            },
        },
        "widgets": {},
    })
    assert diags == []


def test_cross_reference_form_a_clean():
    diags = validate_custom_apis({
        "custom_apis": ["a", "b"],
        "widgets": {"w": {"root": "x/", "consumes_apis": ["a"]}},
    })
    rules = _rules(diags)
    # CFG011 is info-level but still present for Form-A; CFG012 must not fire
    assert "CFG012" not in rules
    assert "CFG011" in rules
