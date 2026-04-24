"""HTTP client for the (UNVERIFIED) Zoho Creator widget-upload endpoint.

Phase 2C Task 7.

The publish endpoint shape is speculative -- the spec §7.5 research
spike must confirm before `forgeds-deploy-widget --confirm` is
ungated. This module ships so the deploy CLI has a client to dry-run
against; every request/response field is annotated UNVERIFIED.

Surface:
- `compose_url(target)` — build the target URL from a `creator:app-id=<id>`
  string (parsing is defensive).
- `upload_widget_zip(...)` — send the multipart POST and return a
  PublishResult with any DPY005 diagnostics.

Stdlib only (`urllib.request`). Tokens never appear in logs, repr, or
diagnostics — only the target URL and the source name are safe to
print.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from forgeds._shared.diagnostics import Diagnostic, Severity


@dataclass
class PublishResult:
    ok: bool
    response: dict = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    url: str = ""  # safe to print; never the token


def _diag(file: str, sev: Severity, code: str, message: str) -> Diagnostic:
    return Diagnostic(file=file, line=1, rule=code, severity=sev, message=message)


# UNVERIFIED — spec §7.3 speculative endpoint shape. Confirm in spike.
_BASE_URL = "https://creator.zoho.com/api/v2.1/applications"


def compose_url(target: str) -> str:
    """Build a target upload URL from a `creator:app-id=<id>` string.

    Accepts shapes:
      - creator:app-id=abc123
      - creator:app_id=abc123
      - app-id=abc123
      - abc123   (fallback: treat bare value as app_id)
    """
    # Strip scheme prefix
    if target.startswith("creator:"):
        target = target[len("creator:"):]
    # Pull the value after `=` if present
    if "=" in target:
        _, _, app_id = target.partition("=")
        app_id = app_id.strip()
    else:
        app_id = target.strip()
    # UNVERIFIED (§7.5)
    return f"{_BASE_URL}/{app_id}/plugins/upload"


def _build_multipart_body(
    zip_bytes: bytes,
    metadata: dict,
    boundary: str,
) -> bytes:
    """Compose a multipart/form-data body with the ZIP file + metadata JSON.

    UNVERIFIED shape per spec §7.3. Fields: `file` (binary, the zip);
    `metadata` (JSON string with name + version).
    """
    crlf = b"\r\n"
    parts = []
    # metadata
    parts.append(f"--{boundary}".encode())
    parts.append(b'Content-Disposition: form-data; name="metadata"')
    parts.append(b"Content-Type: application/json")
    parts.append(b"")
    parts.append(json.dumps(metadata).encode())
    # file
    parts.append(f"--{boundary}".encode())
    parts.append(
        b'Content-Disposition: form-data; name="file"; filename="widget.zip"'
    )
    parts.append(b"Content-Type: application/zip")
    parts.append(b"")
    parts.append(zip_bytes)
    # closing
    parts.append(f"--{boundary}--".encode())
    parts.append(b"")
    return crlf.join(parts)


def upload_widget_zip(
    *,
    zip_path: str,
    widget_name: str,
    version: str,
    access_token: str,
    target: str,
    timeout_s: int = 60,
) -> PublishResult:
    """POST a widget ZIP to the (UNVERIFIED) Creator plugin-upload endpoint.

    Returns a PublishResult. Never raises; HTTP / network errors are
    mapped to DPY005 diagnostics. The `access_token` argument is never
    included in the result -- only the target URL is safe to surface.
    """
    url = compose_url(target)

    try:
        zip_bytes = Path(zip_path).read_bytes()
    except OSError as exc:
        return PublishResult(
            ok=False,
            diagnostics=[_diag(zip_path, Severity.ERROR, "DPY005",
                               f"could not read ZIP: {exc}")],
            url=url,
        )

    # Cryptographically irrelevant boundary; pick a stable one
    boundary = "----ForgeDSBoundary" + os.urandom(8).hex()
    body = _build_multipart_body(
        zip_bytes,
        {"name": widget_name, "version": version},
        boundary,
    )

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            detail = "<unreadable>"
        return PublishResult(
            ok=False,
            diagnostics=[_diag(url, Severity.ERROR, "DPY005",
                               f"HTTP {exc.code}: {detail}")],
            url=url,
        )
    except (urllib.error.URLError, OSError) as exc:
        return PublishResult(
            ok=False,
            diagnostics=[_diag(url, Severity.ERROR, "DPY005",
                               f"network error: {exc}")],
            url=url,
        )

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return PublishResult(
            ok=False,
            response={"raw": raw[:500]},
            diagnostics=[_diag(url, Severity.ERROR, "DPY005",
                               "non-JSON response from publish endpoint (UNVERIFIED)")],
            url=url,
        )

    # UNVERIFIED success code per spec §7.3 — Zoho uses 3000 historically
    code = parsed.get("code")
    if code == 3000:
        return PublishResult(ok=True, response=parsed, url=url)
    return PublishResult(
        ok=False,
        response=parsed,
        diagnostics=[_diag(url, Severity.ERROR, "DPY005",
                           f"publish endpoint returned code={code} "
                           f"message={parsed.get('message', '<none>')} (UNVERIFIED)")],
        url=url,
    )
