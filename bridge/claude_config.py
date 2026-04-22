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
