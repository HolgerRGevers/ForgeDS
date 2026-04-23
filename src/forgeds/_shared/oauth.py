"""Shared OAuth helpers for Zoho Creator tooling.

Factored out of `forgeds.hybrid.upload_to_creator` so that both the
Access-import uploader and the Phase 2C widget deployer
(`forgeds-deploy-widget`) can share a single token-resolution code path
without creating a cycle between `hybrid/` and `widgets/`.

Surface:
- `TokenManager`           — OAuth 2.0 refresh-token client (preserved API).
- `resolve_access_token()` — four-step source-order resolver per spec §7.2.
- `OAuthResolutionError`   — raised when every source fails.
- `parse_flat_yaml()`      — minimal flat `key: value` loader for
                             `config/zoho-api.yaml`.

Stdlib only. Tokens are never printed; only source *names* are surfaced.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Iterable


# ============================================================
# Exceptions
# ============================================================


class OAuthResolutionError(Exception):
    """Raised when no OAuth source can produce an access token.

    Attributes:
        attempted_sources: list of (source_name, reason) tuples. Source
            names match the prefixes in spec §7.2 (`arg:--token`,
            `env:<VAR>`, `config:<file>`, `refresh:<auth_base>`).
    """

    def __init__(self, attempted_sources: list[tuple[str, str]]) -> None:
        self.attempted_sources = attempted_sources
        lines = [f"  - {name}: {reason}" for name, reason in attempted_sources]
        super().__init__(
            "No OAuth source resolved. Attempted sources:\n" + "\n".join(lines)
        )


# ============================================================
# Flat YAML loader (lifted from upload_to_creator.parse_yaml)
# ============================================================


def parse_flat_yaml(path: str) -> dict[str, str]:
    """Parse a flat `key: value` YAML file. No nesting, no lists."""
    result: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value:
                    result[key] = value
    return result


# ============================================================
# OAuth Token Management
# ============================================================


class TokenManager:
    """Manages OAuth 2.0 access-token refresh for Zoho APIs.

    API preserved from the original `hybrid.upload_to_creator.TokenManager`
    so existing callers need no changes beyond the import path.
    """

    def __init__(self, config: dict[str, str]) -> None:
        self.client_id = config.get("client_id", "")
        self.client_secret = config.get("client_secret", "")
        self.refresh_token = config.get("refresh_token", "")
        self.auth_base = config.get("auth_base", "https://accounts.zoho.com")
        self.access_token: str = ""
        self.expires_at: float = 0.0

    def get_access_token(self) -> str:
        """Return a valid access token, refreshing if needed.

        Exits the process with status 1 on a failed refresh (preserves
        legacy behaviour of `upload_to_creator`). Callers that want to
        handle failure should catch OAuthResolutionError from
        `resolve_access_token()` instead.
        """
        if self.access_token and time.time() < self.expires_at:
            return self.access_token

        url = f"{self.auth_base}/oauth/v2/token"
        data = (
            f"grant_type=refresh_token"
            f"&client_id={self.client_id}"
            f"&client_secret={self.client_secret}"
            f"&refresh_token={self.refresh_token}"
        ).encode("utf-8")

        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(req) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                self.access_token = body["access_token"]
                self.expires_at = time.time() + body.get("expires_in", 3600) - 60
                return self.access_token
        except (urllib.error.URLError, KeyError) as e:
            print(f"Error refreshing token: {e}", file=sys.stderr)
            sys.exit(1)

    def validate(self) -> list[str]:
        """Validate config has required fields. Returns list of error messages."""
        errors: list[str] = []
        for field in ("client_id", "client_secret", "refresh_token"):
            val = getattr(self, field, "")
            if not val:
                errors.append(f"Missing required config: {field}")
        return errors


# ============================================================
# Source-order token resolver (spec §7.2)
# ============================================================


def _refresh_via_env_or_config(
    config: dict[str, str] | None,
    attempted: list[tuple[str, str]],
) -> tuple[str, str] | None:
    """Try the full OAuth refresh flow using env vars then config.

    Returns (token, source_name) on success, None on failure.
    Appends a (name, reason) to `attempted` for every skipped path.
    """
    env_client_id = os.environ.get("ZOHO_CLIENT_ID", "")
    env_client_secret = os.environ.get("ZOHO_CLIENT_SECRET", "")
    env_refresh = os.environ.get("ZOHO_REFRESH_TOKEN", "")
    env_auth_base = os.environ.get("ZOHO_AUTH_BASE", "")

    cfg_client_id = (config or {}).get("client_id", "")
    cfg_client_secret = (config or {}).get("client_secret", "")
    cfg_refresh = (config or {}).get("refresh_token", "")
    cfg_auth_base = (config or {}).get("auth_base", "")

    client_id = env_client_id or cfg_client_id
    client_secret = env_client_secret or cfg_client_secret
    refresh = env_refresh or cfg_refresh
    auth_base = env_auth_base or cfg_auth_base or "https://accounts.zoho.com"

    if not (client_id and client_secret and refresh):
        missing = []
        if not client_id:
            missing.append("client_id")
        if not client_secret:
            missing.append("client_secret")
        if not refresh:
            missing.append("refresh_token")
        attempted.append((f"refresh:{auth_base}", f"missing {', '.join(missing)}"))
        return None

    tm = TokenManager({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh,
        "auth_base": auth_base,
    })
    try:
        # Avoid TokenManager.get_access_token's sys.exit(1) contract by
        # calling the refresh request directly and wrapping failures.
        url = f"{auth_base}/oauth/v2/token"
        data = (
            f"grant_type=refresh_token"
            f"&client_id={client_id}"
            f"&client_secret={client_secret}"
            f"&refresh_token={refresh}"
        ).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            tm.access_token = body["access_token"]
            tm.expires_at = time.time() + body.get("expires_in", 3600) - 60
            return (tm.access_token, f"refresh:{auth_base}")
    except (urllib.error.URLError, KeyError, ValueError) as exc:
        attempted.append((f"refresh:{auth_base}", f"request failed: {exc}"))
        return None


def resolve_access_token(
    *,
    explicit_token: str | None,
    config_path: str | None,
) -> tuple[str, str]:
    """Resolve an OAuth access token via the four-step order (spec §7.2).

    Order:
      1. `explicit_token` arg (source name: `arg:--token`)
      2. `ZOHO_ACCESS_TOKEN` env var (`env:ZOHO_ACCESS_TOKEN`)
      3. `config_path` file `access_token:` field (`config:<basename>`)
      4. Full OAuth refresh flow using env or config
         (`refresh:<auth_base>`)

    Returns `(token, source_name)`. The token value is never logged;
    only the source name is safe to surface.

    Raises `OAuthResolutionError` if every source fails. The exception
    carries `attempted_sources: list[(name, reason)]` for diagnostics.
    """
    attempted: list[tuple[str, str]] = []

    # 1. explicit arg
    if explicit_token:
        return (explicit_token, "arg:--token")
    attempted.append(("arg:--token", "not provided"))

    # 2. env var
    env_tok = os.environ.get("ZOHO_ACCESS_TOKEN", "")
    if env_tok:
        return (env_tok, "env:ZOHO_ACCESS_TOKEN")
    attempted.append(("env:ZOHO_ACCESS_TOKEN", "not set"))

    # 3. config file access_token
    config: dict[str, str] | None = None
    config_basename = "zoho-api.yaml"
    if config_path:
        if os.path.exists(config_path):
            config_basename = os.path.basename(config_path) or config_basename
            try:
                config = parse_flat_yaml(config_path)
            except OSError as exc:
                attempted.append((f"config:{config_basename}", f"read error: {exc}"))
                config = None
            else:
                cfg_tok = (config or {}).get("access_token", "")
                if cfg_tok:
                    return (cfg_tok, f"config:{config_basename}")
                attempted.append((f"config:{config_basename}", "access_token missing"))
        else:
            attempted.append((f"config:{config_basename}", "file not found"))
    else:
        attempted.append((f"config:{config_basename}", "no config_path supplied"))

    # 4. refresh flow
    result = _refresh_via_env_or_config(config, attempted)
    if result is not None:
        return result

    raise OAuthResolutionError(attempted)
