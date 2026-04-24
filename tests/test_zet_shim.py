"""Tests for zet_shim (Phase 2C Task 5)."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import shutil
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from forgeds.widgets.zet_shim import ZetResult, run_zet_pack


# ---------------------------------------------------------------------------
# Absent toolchain
# ---------------------------------------------------------------------------

def test_zet_shim_absent_returns_exit3_sentinel():
    with patch("forgeds.widgets.zet_shim.shutil.which", return_value=None):
        result = run_zet_pack("src", "dist")
    assert result.returncode == 3
    assert "npm install" in result.stderr


# ---------------------------------------------------------------------------
# Success
# ---------------------------------------------------------------------------

def test_zet_shim_success_returns_stdout_stderr():
    mock_completed = MagicMock(returncode=0, stdout="ok", stderr="")
    with patch("forgeds.widgets.zet_shim.shutil.which", return_value="/path/to/npx"), \
         patch("forgeds.widgets.zet_shim.subprocess.run", return_value=mock_completed):
        result = run_zet_pack("src", "dist")
    assert result.returncode == 0
    assert result.stdout == "ok"
    assert result.stderr == ""


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------

def test_zet_shim_timeout():
    with patch("forgeds.widgets.zet_shim.shutil.which", return_value="/path/to/npx"), \
         patch("forgeds.widgets.zet_shim.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd="zet pack", timeout=5)):
        result = run_zet_pack("src", "dist", timeout_s=5)
    assert result.returncode == 2
    assert "timed out" in result.stderr


# ---------------------------------------------------------------------------
# Non-zero exit
# ---------------------------------------------------------------------------

def test_zet_shim_nonzero_exit():
    mock_completed = MagicMock(returncode=1, stdout="", stderr="bad manifest")
    with patch("forgeds.widgets.zet_shim.shutil.which", return_value="/path/to/npx"), \
         patch("forgeds.widgets.zet_shim.subprocess.run", return_value=mock_completed):
        result = run_zet_pack("src", "dist")
    assert result.returncode == 1
    assert result.stderr == "bad manifest"


# ---------------------------------------------------------------------------
# Argv shape
# ---------------------------------------------------------------------------

def test_zet_shim_argv_shape():
    mock_completed = MagicMock(returncode=0, stdout="", stderr="")
    with patch("forgeds.widgets.zet_shim.shutil.which", return_value="/path/to/npx"), \
         patch("forgeds.widgets.zet_shim.subprocess.run", return_value=mock_completed) as mock_run:
        run_zet_pack("/abs/source", "/abs/dist", verbose=True, timeout_s=60)

    args, kwargs = mock_run.call_args
    argv = args[0]
    assert argv[:3] == ["npx", "zet", "pack"]
    assert argv[3:5] == ["--source", "/abs/source"]
    assert argv[5:7] == ["--dist", "/abs/dist"]
    assert "-v" in argv
    assert kwargs.get("timeout") == 60
    assert kwargs.get("capture_output") is True
    assert kwargs.get("text") is True


# ---------------------------------------------------------------------------
# Integration skip-marker
# ---------------------------------------------------------------------------

@pytest.mark.skipif(shutil.which("npx") is None, reason="npx not on PATH")
def test_zet_shim_npx_version_reachable():
    """Integration: if npx is available, `npx zet --version` should at
    least return *some* exit code (even if ZET itself isn't installed)."""
    try:
        subprocess.run(
            ["npx", "zet", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        pytest.skip("npx zet --version failed to execute")
