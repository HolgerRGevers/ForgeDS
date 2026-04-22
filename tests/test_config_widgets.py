"""Tests for widgets-related forgeds.yaml config extensions."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import tempfile
from pathlib import Path

from forgeds._shared.config import load_config


def test_load_config_returns_empty_custom_apis_when_missing():
    """Defaults dict should include an empty custom_apis list."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = load_config(start=tmp)
        assert cfg.get("custom_apis") == []


def test_load_config_returns_empty_widgets_when_missing():
    """Defaults dict should include an empty widgets dict."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = load_config(start=tmp)
        assert cfg.get("widgets") == {}


def test_load_config_parses_custom_apis_list():
    """YAML custom_apis list should parse into config['custom_apis']."""
    yaml = (
        "project:\n"
        "  name: test\n"
        "  version: 0.0.1\n"
        "custom_apis:\n"
        "  - get_pending_claims\n"
        "  - approve_claim\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "forgeds.yaml").write_text(yaml, encoding="utf-8")
        cfg = load_config(start=tmp)
        assert cfg.get("custom_apis") == ["get_pending_claims", "approve_claim"]


def test_load_config_parses_widgets_dict():
    """YAML widgets dict-of-dicts should parse into config['widgets']."""
    yaml = (
        "project:\n"
        "  name: test\n"
        "  version: 0.0.1\n"
        "custom_apis:\n"
        "  - get_pending_claims\n"
        "widgets:\n"
        "  expense_dashboard:\n"
        "    root: src/widgets/expense_dashboard/\n"
        "    consumes_apis:\n"
        "      - get_pending_claims\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "forgeds.yaml").write_text(yaml, encoding="utf-8")
        cfg = load_config(start=tmp)
        widgets = cfg.get("widgets", {})
        assert "expense_dashboard" in widgets
        assert widgets["expense_dashboard"]["root"] == "src/widgets/expense_dashboard/"
        assert widgets["expense_dashboard"]["consumes_apis"] == ["get_pending_claims"]
