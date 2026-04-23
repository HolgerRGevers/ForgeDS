"""Tests for harness.js (Phase 2B Task 3).

Each test invokes the Node harness directly against a throwaway widget
authored in `tmp_path`. Exit code and stdout JSON shape are asserted.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = REPO_ROOT / "src" / "forgeds" / "widgets" / "runtime"
HARNESS = RUNTIME_DIR / "harness.js"


def _node_available() -> bool:
    return shutil.which("node") is not None


pytestmark = pytest.mark.skipif(not _node_available(), reason="Node not on PATH")


def _ensure_mock_built():
    if not (RUNTIME_DIR / "sdk_mock.js").exists():
        subprocess.run(
            [sys.executable, "-m", "forgeds.widgets.build_widget_sdk_db"],
            cwd=str(REPO_ROOT), check=True, capture_output=True,
        )
        subprocess.run(
            [sys.executable, "-m", "forgeds.widgets.gen_sdk_mock"],
            cwd=str(REPO_ROOT), check=True, capture_output=True,
        )


def _run_harness(entry: Path, *, widget_name: str = "test_widget",
                 timeout_ms: int = 10000) -> subprocess.CompletedProcess:
    _ensure_mock_built()
    return subprocess.run(
        [
            "node", str(HARNESS),
            "--widget-root", str(entry.parent),
            "--entry-point", str(entry),
            "--widget-name", widget_name,
            "--timeout-ms", str(timeout_ms),
        ],
        capture_output=True, text=True,
    )


def _write_widget(tmp_path: Path, body: str) -> Path:
    entry = tmp_path / "index.js"
    entry.write_text(body, encoding="utf-8")
    return entry


def test_harness_prints_callog_json_to_stdout_on_success(tmp_path):
    entry = _write_widget(tmp_path, """
'use strict';
module.exports = {
  init: function() {
    return ZOHO.CREATOR.API.getRecords('r', '', 1, 10);
  }
};
""")
    r = _run_harness(entry)
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout.strip())
    assert payload["status"] == "ok"
    assert payload["widget"] == "test_widget"
    assert len(payload["callLog"]) == 1
    assert payload["callLog"][0]["method"] == "ZOHO.CREATOR.API.getRecords"


def test_harness_exit_0_on_success(tmp_path):
    entry = _write_widget(tmp_path, "module.exports = {};")
    r = _run_harness(entry)
    assert r.returncode == 0, r.stderr


def test_harness_exit_4_on_missing_entry_point(tmp_path):
    missing = tmp_path / "does-not-exist.js"
    r = _run_harness(missing)
    assert r.returncode == 4
    assert "FORGEDS-RUNTIME-ERROR" in r.stderr


def test_harness_exit_5_on_sync_throw(tmp_path):
    entry = _write_widget(tmp_path, "throw new Error('boom');")
    r = _run_harness(entry)
    assert r.returncode == 5


def test_harness_exit_5_on_init_rejects(tmp_path):
    entry = _write_widget(tmp_path, """
module.exports = { init: function() { return Promise.reject(new Error('async boom')); } };
""")
    r = _run_harness(entry)
    assert r.returncode == 5
    payload = json.loads(r.stdout.strip())
    assert payload["status"] == "throw"
    assert "async boom" in payload["error"]["message"]


def test_harness_exit_6_on_timeout(tmp_path):
    entry = _write_widget(tmp_path, """
module.exports = {
  init: function() { return new Promise(function() { /* never resolve */ }); }
};
""")
    r = _run_harness(entry, timeout_ms=200)
    assert r.returncode == 6
    payload = json.loads(r.stdout.strip())
    assert payload["status"] == "timeout"


def test_harness_records_declared_permissions_from_mock(tmp_path):
    entry = _write_widget(tmp_path, """
module.exports = {
  init: async function() {
    await ZOHO.CREATOR.API.addRecords('form', { foo: 1 });
  }
};
""")
    r = _run_harness(entry)
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout.strip())
    assert "ZOHO.CREATOR.API.write" in payload["permissionsObserved"]


def test_harness_callog_timestamp_is_numeric(tmp_path):
    entry = _write_widget(tmp_path, """
module.exports = {
  init: async function() {
    await ZOHO.CREATOR.API.getRecords('r', '', 1, 10);
  }
};
""")
    r = _run_harness(entry)
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout.strip())
    ts = payload["callLog"][0]["timestamp"]
    assert isinstance(ts, (int, float))
    assert ts >= 0


def test_harness_captures_non_serialisable_args_as_placeholder(tmp_path):
    entry = _write_widget(tmp_path, """
module.exports = {
  init: function() {
    const fn = function() {};
    return ZOHO.CREATOR.API.invokeCustomApi('approve_claim', fn);
  }
};
""")
    r = _run_harness(entry)
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout.strip())
    assert payload["status"] == "ok"
    # JSON.stringify of a function yields undefined; Array.from then JSON.stringify gives [null]
    # either [null, ...] or ['__nonserialisable__', ...] is acceptable per spec §4.4
    args = payload["callLog"][0]["args"]
    assert args[0] == "approve_claim"


def test_harness_requires_entry_point_flag(tmp_path):
    """No --entry-point arg → exit 4 with FORGEDS-RUNTIME-ERROR."""
    r = subprocess.run(
        ["node", str(HARNESS)],
        capture_output=True, text=True,
    )
    assert r.returncode == 4
    assert "FORGEDS-RUNTIME-ERROR" in r.stderr
