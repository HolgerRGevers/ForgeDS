"""Anthropic credentials, effort-level mapping, client factory, error helpers."""
from __future__ import annotations

import os
from pathlib import Path

import yaml


def resolve_api_key() -> str | None:
    """Return the Anthropic API key, preferring env over ~/.forgeds/anthropic.yaml."""
    env = os.environ.get("ANTHROPIC_API_KEY")
    if env and env.strip():
        return env.strip()
    yaml_path = Path.home() / ".forgeds" / "anthropic.yaml"
    if yaml_path.exists():
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            key = data.get("api_key")
            if isinstance(key, str) and key.strip() and key.strip() != "YOUR_ANTHROPIC_API_KEY_HERE":
                return key.strip()
        except yaml.YAMLError:
            return None
    return None


# ---------------------------------------------------------------------------
# Effort-level mapping - single source of truth
# ---------------------------------------------------------------------------
EFFORT_LEVELS: dict[str, dict] = {
    "low":    {"model": "claude-haiku-4-5-20251001", "thinking": None,  "max_tokens": 2048},
    "medium": {"model": "claude-haiku-4-5-20251001", "thinking": 4096,  "max_tokens": 4096},
    "high":   {"model": "claude-sonnet-4-6",         "thinking": None,  "max_tokens": 4096},
    "max":    {"model": "claude-opus-4-7",           "thinking": 16384, "max_tokens": 8192},
}
DEFAULT_IDE_EFFORT = "high"
DEFAULT_APP_CREATION_EFFORT = "max"


def get_effort_config(effort: str | None) -> dict:
    """Return the effort config for *effort*, falling back to DEFAULT_IDE_EFFORT."""
    if effort is None:
        return EFFORT_LEVELS[DEFAULT_IDE_EFFORT]
    return EFFORT_LEVELS.get(effort, EFFORT_LEVELS[DEFAULT_IDE_EFFORT])


def build_anthropic_client():
    """Return an AsyncAnthropic client, or None if no API key is configured."""
    key = resolve_api_key()
    if not key:
        return None
    from anthropic import AsyncAnthropic  # deferred import so tests without SDK still parse
    return AsyncAnthropic(api_key=key)
