"""Tests for the shared OAuth helper (Phase 2C Task 2)."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from forgeds._shared.oauth import (
    OAuthResolutionError,
    TokenManager,
    parse_flat_yaml,
    resolve_access_token,
)


# ---------------------------------------------------------------------------
# resolve_access_token precedence
# ---------------------------------------------------------------------------

def test_token_resolver_arg_wins_over_all(monkeypatch):
    """Explicit --token arg beats env and config."""
    monkeypatch.setenv("ZOHO_ACCESS_TOKEN", "from-env")
    with tempfile.TemporaryDirectory() as tmp:
        cfg = Path(tmp) / "zoho-api.yaml"
        cfg.write_text("access_token: from-config\n", encoding="utf-8")
        token, source = resolve_access_token(
            explicit_token="explicit",
            config_path=str(cfg),
        )
    assert token == "explicit"
    assert source == "arg:--token"


def test_token_resolver_env_wins_over_config(monkeypatch):
    """ZOHO_ACCESS_TOKEN env var beats config-file access_token."""
    monkeypatch.setenv("ZOHO_ACCESS_TOKEN", "from-env")
    with tempfile.TemporaryDirectory() as tmp:
        cfg = Path(tmp) / "zoho-api.yaml"
        cfg.write_text("access_token: from-config\n", encoding="utf-8")
        token, source = resolve_access_token(
            explicit_token=None,
            config_path=str(cfg),
        )
    assert token == "from-env"
    assert source == "env:ZOHO_ACCESS_TOKEN"


def test_token_resolver_config_fallback(monkeypatch):
    """Config-file access_token is used when no env is set."""
    monkeypatch.delenv("ZOHO_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("ZOHO_REFRESH_TOKEN", raising=False)
    with tempfile.TemporaryDirectory() as tmp:
        cfg = Path(tmp) / "zoho-api.yaml"
        cfg.write_text("access_token: from-config\n", encoding="utf-8")
        token, source = resolve_access_token(
            explicit_token=None,
            config_path=str(cfg),
        )
    assert token == "from-config"
    assert source == "config:zoho-api.yaml"


def test_token_resolver_refresh_flow_invoked(monkeypatch):
    """Full OAuth refresh when no access_token is directly available."""
    monkeypatch.delenv("ZOHO_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("ZOHO_CLIENT_ID", "cid")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "csec")
    monkeypatch.setenv("ZOHO_REFRESH_TOKEN", "rtok")

    # Mock urlopen response
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(
        {"access_token": "fresh-token", "expires_in": 3600}
    ).encode()
    mock_resp.__enter__ = lambda self: mock_resp
    mock_resp.__exit__ = lambda *a: None

    with patch("forgeds._shared.oauth.urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        token, source = resolve_access_token(
            explicit_token=None,
            config_path=None,
        )
    assert token == "fresh-token"
    assert source.startswith("refresh:")
    assert mock_urlopen.called


def test_token_resolver_all_sources_fail(monkeypatch):
    """When nothing resolves, raises OAuthResolutionError with attempted-source details."""
    monkeypatch.delenv("ZOHO_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("ZOHO_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("ZOHO_CLIENT_ID", raising=False)
    monkeypatch.delenv("ZOHO_CLIENT_SECRET", raising=False)

    with pytest.raises(OAuthResolutionError) as exc_info:
        resolve_access_token(explicit_token=None, config_path=None)

    err = exc_info.value
    assert hasattr(err, "attempted_sources")
    source_names = [s[0] for s in err.attempted_sources]
    assert "arg:--token" in source_names
    assert "env:ZOHO_ACCESS_TOKEN" in source_names
    assert "config:zoho-api.yaml" in source_names
    assert any(n.startswith("refresh:") for n in source_names)


def test_token_never_logged(monkeypatch, capsys):
    """Resolver must not print the token value to stdout/stderr."""
    monkeypatch.setenv("ZOHO_ACCESS_TOKEN", "SUPER-SECRET-TOKEN-VALUE")
    token, source = resolve_access_token(explicit_token=None, config_path=None)
    captured = capsys.readouterr()
    assert "SUPER-SECRET-TOKEN-VALUE" not in captured.out
    assert "SUPER-SECRET-TOKEN-VALUE" not in captured.err
    # source name is fine to print
    assert token == "SUPER-SECRET-TOKEN-VALUE"


# ---------------------------------------------------------------------------
# parse_flat_yaml
# ---------------------------------------------------------------------------

def test_parse_flat_yaml_basic():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "cfg.yaml"
        p.write_text(
            "# a comment\n"
            "client_id: abc123\n"
            "client_secret: \"quoted-value\"\n"
            "empty:\n"
            "\n"
            "refresh_token: 'single-quoted'\n",
            encoding="utf-8",
        )
        out = parse_flat_yaml(str(p))
    assert out["client_id"] == "abc123"
    assert out["client_secret"] == "quoted-value"
    assert out["refresh_token"] == "single-quoted"
    # empty value should be skipped (parse_yaml skips empties per its original behavior)
    assert "empty" not in out


# ---------------------------------------------------------------------------
# TokenManager preserved behaviour (smoke)
# ---------------------------------------------------------------------------

def test_token_manager_validate_reports_missing_fields():
    tm = TokenManager({})
    errors = tm.validate()
    assert any("client_id" in e for e in errors)
    assert any("client_secret" in e for e in errors)
    assert any("refresh_token" in e for e in errors)


def test_token_manager_get_access_token_uses_refresh_flow():
    cfg = {
        "client_id": "cid",
        "client_secret": "csec",
        "refresh_token": "rtok",
        "auth_base": "https://accounts.zoho.com",
    }
    tm = TokenManager(cfg)

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(
        {"access_token": "fresh", "expires_in": 3600}
    ).encode()
    mock_resp.__enter__ = lambda self: mock_resp
    mock_resp.__exit__ = lambda *a: None

    with patch("forgeds._shared.oauth.urllib.request.urlopen", return_value=mock_resp):
        token = tm.get_access_token()
    assert token == "fresh"
