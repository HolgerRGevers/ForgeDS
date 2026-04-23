"""End-to-end tests for the forgeds-status CLI entry point."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from forgeds.status import cli
from forgeds.status.checks import StatusCheck

FIXTURES = Path(__file__).parent / "fixtures" / "status"


def _stub_checks(*groups):
    """Make a predictable checks list from (category, id, status, rule) tuples."""
    return [StatusCheck(category=c, id=i, status=s, message="msg", rule=r) for c, i, s, r in groups]


def test_status_json_envelope_shape(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_run_all_checks", lambda args: _stub_checks(
        ("config_sanity", "forgeds.yaml", "ok", None),
        ("db_freshness", "deluge_lang.db", "ok", None),
        ("toolchain", "python", "ok", None),
        ("lint_summary", "forgeds-lint", "ok", None),
    ))
    rc = cli.main(["--format", "json-v1"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["tool"] == "forgeds-status"
    assert payload["version"] == "1"
    assert payload["overall"] == "ok"
    assert {c["category"] for c in payload["checks"]} == {
        "config_sanity", "db_freshness", "toolchain", "lint_summary"
    }
    assert rc == 0


def test_status_exit_code_matrix(monkeypatch, capsys):
    # all ok → 0
    monkeypatch.setattr(cli, "_run_all_checks", lambda args: _stub_checks(
        ("config_sanity", "x", "ok", None),
    ))
    assert cli.main(["--format", "json-v1"]) == 0

    # warn present → 1
    monkeypatch.setattr(cli, "_run_all_checks", lambda args: _stub_checks(
        ("config_sanity", "x", "warn", "CFG013"),
    ))
    assert cli.main(["--format", "json-v1"]) == 1

    # miss present → 2
    monkeypatch.setattr(cli, "_run_all_checks", lambda args: _stub_checks(
        ("db_freshness", "x", "miss", "STA002"),
    ))
    assert cli.main(["--format", "json-v1"]) == 2

    # fail present → 2
    monkeypatch.setattr(cli, "_run_all_checks", lambda args: _stub_checks(
        ("config_sanity", "x", "fail", "STA001"),
    ))
    assert cli.main(["--format", "json-v1"]) == 2


def test_status_text_report_section_order(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_run_all_checks", lambda args: _stub_checks(
        ("toolchain", "python", "ok", None),
        ("db_freshness", "deluge_lang.db", "ok", None),
        ("config_sanity", "forgeds.yaml", "ok", None),
        ("lint_summary", "forgeds-lint", "ok", None),
    ))
    cli.main(["--format", "text"])
    out = capsys.readouterr().out
    # spec §5.2 order: Database Freshness, Config Sanity, Lint Summary, Toolchain
    db_pos = out.index("Database Freshness:")
    cfg_pos = out.index("Config Sanity:")
    lint_pos = out.index("Lint Summary:")
    tool_pos = out.index("Toolchain:")
    assert db_pos < cfg_pos < lint_pos < tool_pos


def test_status_broken_yaml_in_text_mode_aborts_early(monkeypatch, capsys):
    """Text mode: fatal STA001 aborts before running db_freshness/toolchain/lint."""
    # Point at fixture with a forgeds.yaml file that is clearly broken AT PARSE TIME.
    # Since _load_yaml_simple is permissive, we simulate via missing file instead.
    from forgeds.status.checks import config_sanity as cs

    def fake_run(start=None):
        return [StatusCheck(category="config_sanity", id="forgeds.yaml",
                            status="fail", message="missing", rule="STA001")]

    monkeypatch.setattr(cs, "run", fake_run)
    # If the rest ran, we'd see more lines — the run-all path will short-circuit
    rc = cli.main(["--format", "text"])
    out = capsys.readouterr().out
    assert "STA001" in out
    assert "Database Freshness:" not in out  # proves early abort
    assert rc == 2


def test_status_json_mode_runs_all_despite_sta001(monkeypatch, capsys):
    """JSON mode: STA001 still fires but other checks also run."""
    from forgeds.status.checks import config_sanity as cs, db_freshness as dbf, toolchain as tc, lint_summary as ls

    monkeypatch.setattr(cs, "run", lambda start=None: [StatusCheck(
        category="config_sanity", id="forgeds.yaml", status="fail",
        message="missing", rule="STA001")])
    monkeypatch.setattr(dbf, "run", lambda: [StatusCheck(
        category="db_freshness", id="deluge_lang.db", status="ok", message="", rule=None)])
    monkeypatch.setattr(tc, "run", lambda start=None: [StatusCheck(
        category="toolchain", id="python", status="ok", message="x", rule=None)])
    monkeypatch.setattr(ls, "run", lambda start=None: [StatusCheck(
        category="lint_summary", id="forgeds-lint", status="ok", message="", rule=None)])

    rc = cli.main(["--format", "json-v1"])
    payload = json.loads(capsys.readouterr().out)
    categories = {c["category"] for c in payload["checks"]}
    assert categories == {"config_sanity", "db_freshness", "toolchain", "lint_summary"}
    assert rc == 2


def test_status_skip_flags(monkeypatch, capsys):
    from forgeds.status.checks import config_sanity as cs, db_freshness as dbf, toolchain as tc, lint_summary as ls

    called = {"toolchain": 0, "lint": 0}

    monkeypatch.setattr(cs, "run", lambda start=None: [StatusCheck(
        category="config_sanity", id="forgeds.yaml", status="ok", message="", rule=None)])
    monkeypatch.setattr(dbf, "run", lambda: [StatusCheck(
        category="db_freshness", id="deluge_lang.db", status="ok", message="", rule=None)])

    def fake_toolchain(start=None):
        called["toolchain"] += 1
        return []

    def fake_lint(start=None):
        called["lint"] += 1
        return []

    monkeypatch.setattr(tc, "run", fake_toolchain)
    monkeypatch.setattr(ls, "run", fake_lint)

    cli.main(["--format", "json-v1", "--skip-lint", "--skip-toolchain"])
    assert called["toolchain"] == 0
    assert called["lint"] == 0


def test_status_rejects_invalid_format(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--format", "xml"])
    assert exc_info.value.code == 2  # argparse exits 2 on invalid choice
