"""Tests for the optional `deploy:` block in forgeds.yaml (Phase 2C)."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import tempfile
from pathlib import Path

from forgeds._shared.config import load_config


def test_load_config_without_deploy_block_ok():
    """Defaults dict should include an empty deploy dict when no config exists."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = load_config(start=tmp)
        assert "deploy" in cfg
        assert cfg["deploy"] == {}


def test_load_config_with_deploy_block_parsed():
    """A forgeds.yaml with a nested deploy block is parsed as a dict."""
    yaml = (
        "project:\n"
        "  name: test\n"
        "  version: 0.0.1\n"
        "deploy:\n"
        "  oauth_env_prefix: ZOHO\n"
        "  auth_base: https://accounts.zoho.com\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "forgeds.yaml").write_text(yaml, encoding="utf-8")
        cfg = load_config(start=tmp)
        assert cfg["deploy"]["oauth_env_prefix"] == "ZOHO"
        assert cfg["deploy"]["auth_base"] == "https://accounts.zoho.com"


def test_load_config_deploy_block_unknown_keys_preserved():
    """Unknown keys under deploy: pass through (no schema enforcement in v1)."""
    yaml = (
        "project:\n"
        "  name: test\n"
        "  version: 0.0.1\n"
        "deploy:\n"
        "  future_field: surprise\n"
        "  nested:\n"
        "    inner: value\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "forgeds.yaml").write_text(yaml, encoding="utf-8")
        cfg = load_config(start=tmp)
        assert cfg["deploy"]["future_field"] == "surprise"
        assert cfg["deploy"]["nested"]["inner"] == "value"
