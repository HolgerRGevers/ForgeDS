"""Thin wrapper around `npx zet pack` — Phase 2C Task 5.

Mirrors the Phase 1 ESLint pattern (runtime-optional Node tool):
- `shutil.which("npx")` is None   -> returncode=3 with install hint
- subprocess TimeoutExpired       -> returncode=2 with timeout message
- `zet pack` non-zero exit        -> pass-through returncode + stderr
- success                         -> returncode=0 + captured stdout/stderr
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class ZetResult:
    """Outcome of a single `zet pack` invocation.

    returncode:
      0  — success
      1  — zet pack emitted warnings / stderr but returncode 0 (remapped by caller)
      2  — subprocess failure (non-zero exit or timeout)
      3  — `npx` not on PATH (Node/ZET not installed)
    """
    returncode: int
    stdout: str
    stderr: str


_INSTALL_HINT = (
    "npx not found on PATH. Install Node >= 18, then run:\n"
    "  npm install -g zoho-extension-toolkit\n"
    "Or use `forgeds-bundle-widget --no-zet` for the pure-Python fallback."
)


def run_zet_pack(
    source_dir: str,
    dist_dir: str,
    *,
    verbose: bool = False,
    timeout_s: int = 120,
) -> ZetResult:
    """Run `npx zet pack --source <source_dir> --dist <dist_dir>`.

    Returns a `ZetResult`. Never raises -- all error paths map to a
    returncode + message so callers can surface them as Phase 2A
    diagnostics uniformly.
    """
    if shutil.which("npx") is None:
        return ZetResult(returncode=3, stdout="", stderr=_INSTALL_HINT)

    argv = ["npx", "zet", "pack", "--source", source_dir, "--dist", dist_dir]
    if verbose:
        argv.append("-v")

    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return ZetResult(
            returncode=2,
            stdout="",
            stderr=f"zet pack timed out after {timeout_s}s",
        )
    except OSError as exc:
        return ZetResult(
            returncode=2,
            stdout="",
            stderr=f"failed to invoke npx: {exc}",
        )

    return ZetResult(
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
