"""Integration tests for --format json-v1 across all four linters."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures"

# Integration tests shell out to the real linters, which require the language DBs
# to be built. Skip with a clear message when DBs are missing (CI or fresh clone).
DELUGE_DB = REPO_ROOT / "deluge_lang.db"
requires_deluge_db = pytest.mark.skipif(
    not DELUGE_DB.exists(),
    reason="deluge_lang.db not built; run `python -m forgeds.core.build_deluge_db`",
)


def _run_python(module: str, *args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    """Invoke a linter via `python -m <module>` with configurable env."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
    )


def _assert_v1_envelope(payload: dict, tool: str) -> None:
    assert payload["tool"] == tool, f"expected tool={tool!r}, got {payload['tool']!r}"
    assert payload["version"] == "1"
    assert isinstance(payload["diagnostics"], list)


@requires_deluge_db
def test_lint_deluge_json_v1_shape():
    """forgeds-lint --format json-v1 on a bad fixture emits valid envelope."""
    res = _run_python(
        "forgeds.core.lint_deluge",
        "--format", "json-v1",
        str(FIXTURES / "lint_test_bad.dg"),
    )
    assert res.returncode in (0, 1, 2), f"unexpected exit {res.returncode}: {res.stderr}"
    payload = json.loads(res.stdout.strip())
    _assert_v1_envelope(payload, "forgeds-lint")
    for d in payload["diagnostics"]:
        assert set(d.keys()) == {"file", "line", "rule", "severity", "message"}
        assert d["severity"] in ("error", "warning", "info")


def test_lint_access_json_v1_shape():
    res = _run_python(
        "forgeds.access.lint_access",
        "--format", "json-v1",
        str(FIXTURES / "lint_test_access_bad.sql"),
    )
    assert res.returncode in (0, 1, 2), f"unexpected exit {res.returncode}: {res.stderr}"
    payload = json.loads(res.stdout.strip())
    _assert_v1_envelope(payload, "forgeds-lint-access")


def test_lint_hybrid_json_v1_shape():
    """forgeds-lint-hybrid --format json-v1 runs without crashing."""
    res = _run_python("forgeds.hybrid.lint_hybrid", "--format", "json-v1")
    assert res.returncode in (0, 1, 2), f"unexpected exit {res.returncode}: {res.stderr}"
    payload = json.loads(res.stdout.strip())
    _assert_v1_envelope(payload, "forgeds-lint-hybrid")


@requires_deluge_db
def test_lint_env_var_honored():
    """FORGEDS_OUTPUT=json-v1 triggers JSON output without --format flag."""
    res = _run_python(
        "forgeds.core.lint_deluge",
        str(FIXTURES / "lint_test_bad.dg"),
        env_extra={"FORGEDS_OUTPUT": "json-v1"},
    )
    payload = json.loads(res.stdout.strip())
    _assert_v1_envelope(payload, "forgeds-lint")


@requires_deluge_db
def test_lint_cli_flag_overrides_env():
    """--format text beats FORGEDS_OUTPUT=json-v1."""
    res = _run_python(
        "forgeds.core.lint_deluge",
        "--format", "text",
        str(FIXTURES / "lint_test_bad.dg"),
        env_extra={"FORGEDS_OUTPUT": "json-v1"},
    )
    stdout = res.stdout.strip()
    # Text mode includes the "--- Linted N file(s):" summary and is NOT JSON.
    assert "Linted" in stdout, f"expected text summary, got: {stdout[:200]!r}"
    with pytest.raises(json.JSONDecodeError):
        json.loads(stdout)


@requires_deluge_db
def test_lint_invalid_format_exits_2():
    """Unknown --format value exits 2 with a stderr message and no stdout."""
    res = _run_python(
        "forgeds.core.lint_deluge",
        "--format", "sarif",
        str(FIXTURES / "lint_test_bad.dg"),
    )
    # argparse itself rejects choices values with exit 2 before our resolver runs
    assert res.returncode == 2
    assert res.stdout == ""
    assert "sarif" in res.stderr.lower() or "invalid choice" in res.stderr.lower()


@requires_deluge_db
def test_lint_invalid_env_value_exits_2():
    """FORGEDS_OUTPUT with an unknown value exits 2 via the format resolver."""
    res = _run_python(
        "forgeds.core.lint_deluge",
        str(FIXTURES / "lint_test_bad.dg"),
        env_extra={"FORGEDS_OUTPUT": "sarif"},
    )
    assert res.returncode == 2
    assert "sarif" in res.stderr.lower()
    assert res.stdout == ""


def test_lint_widgets_json_v1_routes_through_shared_envelope(monkeypatch):
    """lint_widgets._emit delegates JSON-v1 to shared envelope serializer."""
    import forgeds.widgets.lint_widgets as lw

    called = {"n": 0, "last_tool": None}

    def spy(tool, diagnostics):
        called["n"] += 1
        called["last_tool"] = tool
        return '{"tool":"' + tool + '","version":"1","diagnostics":[]}'

    monkeypatch.setattr(lw, "to_json_v1", spy)
    lw._emit([lw._mk_diag("a.js", 1, "JS:semi", "ERROR", "x")], fmt="json-v1")
    assert called["n"] == 1
    assert called["last_tool"] == "forgeds-lint-widgets"
