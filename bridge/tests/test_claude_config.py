import os
from pathlib import Path

import pytest

from bridge.claude_config import (
    resolve_api_key,
    EFFORT_LEVELS,
    DEFAULT_IDE_EFFORT,
    DEFAULT_APP_CREATION_EFFORT,
    get_effort_config,
    build_anthropic_client,
)


def test_resolve_api_key_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-from-env")
    assert resolve_api_key() == "sk-ant-from-env"


def test_resolve_api_key_from_yaml(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    fake_home = tmp_path / "home"
    (fake_home / ".forgeds").mkdir(parents=True)
    (fake_home / ".forgeds" / "anthropic.yaml").write_text(
        "api_key: sk-ant-from-yaml\n", encoding="utf-8"
    )
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    assert resolve_api_key() == "sk-ant-from-yaml"


def test_resolve_api_key_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert resolve_api_key() is None


def test_resolve_api_key_env_wins_over_yaml(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env-wins")
    fake_home = tmp_path / "home"
    (fake_home / ".forgeds").mkdir(parents=True)
    (fake_home / ".forgeds" / "anthropic.yaml").write_text(
        "api_key: sk-ant-yaml-loser\n", encoding="utf-8"
    )
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    assert resolve_api_key() == "sk-ant-env-wins"


def test_effort_levels_has_all_four_tiers():
    assert set(EFFORT_LEVELS.keys()) == {"low", "medium", "high", "max"}
    for tier, cfg in EFFORT_LEVELS.items():
        assert "model" in cfg
        assert "max_tokens" in cfg
        assert "thinking" in cfg


def test_default_efforts():
    assert DEFAULT_IDE_EFFORT == "high"
    assert DEFAULT_APP_CREATION_EFFORT == "max"


def test_get_effort_config_unknown_falls_back_to_high():
    cfg = get_effort_config("bogus")
    assert cfg == EFFORT_LEVELS["high"]


def test_get_effort_config_none_uses_default_ide():
    cfg = get_effort_config(None)
    assert cfg == EFFORT_LEVELS[DEFAULT_IDE_EFFORT]


def test_build_anthropic_client_returns_none_when_no_key(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert build_anthropic_client() is None


def test_build_anthropic_client_returns_client_when_key_present(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    client = build_anthropic_client()
    assert client is not None
    assert client.__class__.__name__ == "AsyncAnthropic"
