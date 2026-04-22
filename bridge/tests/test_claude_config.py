import os
from pathlib import Path

import pytest

from bridge.claude_config import resolve_api_key


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
