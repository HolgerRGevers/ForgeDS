"""Tests for forgeds._shared.output_format."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from forgeds._shared.output_format import UnknownFormatError, resolve_format


def test_format_cli_flag_wins(monkeypatch):
    monkeypatch.setenv("FORGEDS_OUTPUT", "json-v1")
    assert resolve_format("text") == "text"


def test_format_env_var_honored(monkeypatch):
    monkeypatch.setenv("FORGEDS_OUTPUT", "json-v1")
    assert resolve_format(None) == "json-v1"


def test_format_default_is_text(monkeypatch):
    monkeypatch.delenv("FORGEDS_OUTPUT", raising=False)
    assert resolve_format(None) == "text"


def test_format_invalid_flag_raises():
    with pytest.raises(UnknownFormatError) as exc_info:
        resolve_format("json")
    assert exc_info.value.value == "json"
    assert "CLI flag" in exc_info.value.source


def test_format_invalid_env_raises(monkeypatch):
    monkeypatch.setenv("FORGEDS_OUTPUT", "bogus")
    with pytest.raises(UnknownFormatError) as exc_info:
        resolve_format(None)
    assert exc_info.value.value == "bogus"
    assert exc_info.value.source == "FORGEDS_OUTPUT"


def test_format_empty_env_falls_through_to_default(monkeypatch):
    monkeypatch.setenv("FORGEDS_OUTPUT", "")
    assert resolve_format(None) == "text"
