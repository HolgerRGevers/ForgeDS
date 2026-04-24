"""Tests for publish_client (Phase 2C Task 7). UNVERIFIED endpoint shape."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import io
import json
import urllib.error
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from forgeds._shared.diagnostics import Severity
from forgeds.widgets.publish_client import (
    compose_url,
    upload_widget_zip,
)


# ---------------------------------------------------------------------------
# compose_url
# ---------------------------------------------------------------------------

def test_compose_url_creator_app_id():
    url = compose_url("creator:app-id=abc123")
    assert url.endswith("/applications/abc123/plugins/upload")


def test_compose_url_bare_id():
    url = compose_url("abc123")
    assert url.endswith("/applications/abc123/plugins/upload")


def test_compose_url_underscore_variant():
    url = compose_url("creator:app_id=xyz9")
    assert url.endswith("/applications/xyz9/plugins/upload")


# ---------------------------------------------------------------------------
# upload_widget_zip — request shape & success
# ---------------------------------------------------------------------------

def _mk_zip(tmp_path):
    p = tmp_path / "w.zip"
    p.write_bytes(b"PK\x03\x04fake-zip-content")
    return p


def test_publish_client_request_shape_UNVERIFIED(tmp_path):
    zp = _mk_zip(tmp_path)

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(
        {"code": 3000, "plugin": {"id": "p1", "name": "w", "version": "0.0.1"}}
    ).encode()
    mock_resp.__enter__ = lambda self: mock_resp
    mock_resp.__exit__ = lambda *a: None

    with patch("forgeds.widgets.publish_client.urllib.request.urlopen",
               return_value=mock_resp) as mock_urlopen:
        result = upload_widget_zip(
            zip_path=str(zp),
            widget_name="w",
            version="0.0.1",
            access_token="T",
            target="creator:app-id=abc",
        )

    assert result.ok is True
    assert result.response["code"] == 3000

    # Inspect the Request that was sent
    req = mock_urlopen.call_args[0][0]
    assert req.full_url.endswith("/applications/abc/plugins/upload")
    assert req.headers["Authorization"] == "Zoho-oauthtoken T"
    assert req.headers["Content-type"].startswith("multipart/form-data; boundary=")
    # Body contains the ZIP bytes + a metadata JSON
    body = req.data
    assert b"PK\x03\x04fake-zip-content" in body
    assert b'"name": "w"' in body or b'"name":"w"' in body
    assert b'"version": "0.0.1"' in body or b'"version":"0.0.1"' in body


def test_publish_client_response_error(tmp_path):
    zp = _mk_zip(tmp_path)

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(
        {"code": 4099, "message": "bad request"}
    ).encode()
    mock_resp.__enter__ = lambda self: mock_resp
    mock_resp.__exit__ = lambda *a: None

    with patch("forgeds.widgets.publish_client.urllib.request.urlopen",
               return_value=mock_resp):
        result = upload_widget_zip(
            zip_path=str(zp),
            widget_name="w",
            version="0.0.1",
            access_token="T",
            target="creator:app-id=abc",
        )

    assert result.ok is False
    assert any(d.rule == "DPY005" for d in result.diagnostics)


def test_publish_client_network_error(tmp_path):
    zp = _mk_zip(tmp_path)

    with patch("forgeds.widgets.publish_client.urllib.request.urlopen",
               side_effect=urllib.error.URLError("conn refused")):
        result = upload_widget_zip(
            zip_path=str(zp),
            widget_name="w",
            version="0.0.1",
            access_token="T",
            target="creator:app-id=abc",
        )

    assert result.ok is False
    assert any(d.rule == "DPY005" and "network error" in d.message for d in result.diagnostics)


def test_publish_client_http_error(tmp_path):
    zp = _mk_zip(tmp_path)
    http_err = urllib.error.HTTPError(
        "url", 500, "server error", {}, io.BytesIO(b"server exploded")
    )
    with patch("forgeds.widgets.publish_client.urllib.request.urlopen",
               side_effect=http_err):
        result = upload_widget_zip(
            zip_path=str(zp),
            widget_name="w",
            version="0.0.1",
            access_token="T",
            target="creator:app-id=abc",
        )

    assert result.ok is False
    assert any("HTTP 500" in d.message for d in result.diagnostics)


def test_publish_client_missing_zip(tmp_path):
    result = upload_widget_zip(
        zip_path=str(tmp_path / "missing.zip"),
        widget_name="w",
        version="0.0.1",
        access_token="T",
        target="creator:app-id=abc",
    )
    assert result.ok is False
    assert any(d.rule == "DPY005" and "could not read" in d.message for d in result.diagnostics)


# ---------------------------------------------------------------------------
# Token never in logs / result
# ---------------------------------------------------------------------------

def test_publish_client_token_never_in_repr_or_result(tmp_path, capsys):
    zp = _mk_zip(tmp_path)
    secret = "SUPER-SECRET-TOKEN-VALUE"

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"code": 3000}).encode()
    mock_resp.__enter__ = lambda self: mock_resp
    mock_resp.__exit__ = lambda *a: None

    with patch("forgeds.widgets.publish_client.urllib.request.urlopen",
               return_value=mock_resp):
        result = upload_widget_zip(
            zip_path=str(zp),
            widget_name="w",
            version="0.0.1",
            access_token=secret,
            target="creator:app-id=abc",
        )

    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err
    # Result never stores the token
    assert secret not in repr(result)
    assert secret not in str(result.response)
    assert secret not in result.url
