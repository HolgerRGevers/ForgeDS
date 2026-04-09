"""Handler functions for each WebSocket message type."""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
from typing import Any, Callable, Coroutine

from bridge import __version__
from bridge.enrichment import classify_pattern, log_error


# ---------------------------------------------------------------------------
# Type alias for the streaming send callback
# ---------------------------------------------------------------------------
SendFn = Callable[[dict], Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# refine_prompt -- mock implementation
# ---------------------------------------------------------------------------
async def handle_refine_prompt(data: dict) -> dict:
    """Take raw prompt text and return a structured refinement.

    This is a mock that returns a realistic response shaped like a Zoho
    Creator project specification.  A future version will invoke Claude Code
    CLI with ForgeDS context.
    """
    raw_prompt = data.get("prompt", "")

    # Simulate some processing time
    await asyncio.sleep(0.3)

    return {
        "sections": [
            {
                "id": "forms",
                "title": "Forms",
                "icon": "[F]",
                "content": "The following forms will be created for the expense reimbursement workflow",
                "items": ["Expense_Claims", "GL_Accounts", "Approval_History"],
                "isEditable": True,
            },
            {
                "id": "workflows",
                "title": "Workflows",
                "icon": "[W]",
                "content": "Event-driven scripts for form actions",
                "items": ["on_submit_validate", "on_approval_update", "auto_populate_esg"],
                "isEditable": True,
            },
            {
                "id": "reports",
                "title": "Reports & Dashboards",
                "icon": "[R]",
                "content": "Reporting views for claims and audit trails",
                "items": ["All_Claims", "Pending_Approvals", "Approval_Audit_Trail"],
                "isEditable": True,
            },
            {
                "id": "approvals",
                "title": "Approval Processes",
                "icon": "[A]",
                "content": "Multi-level approval workflow with segregation of duties",
                "items": ["Line Manager Approval", "HoD Approval"],
                "isEditable": True,
            },
            {
                "id": "apis",
                "title": "API Endpoints",
                "icon": "[API]",
                "content": "Custom API endpoints for external integrations",
                "items": ["Get_Dashboard_Summary", "Get_Claim_Status"],
                "isEditable": True,
            },
        ],
    }


# ---------------------------------------------------------------------------
# build_project -- mock streaming implementation
# ---------------------------------------------------------------------------
async def handle_build_project(data: dict, send_fn: SendFn) -> dict:
    """Simulate generating project files with streaming progress.

    Sends incremental stream messages via send_fn, then returns a
    final summary.
    """
    sections = data.get("sections", [])
    # Derive project name from first section title or fallback
    project_name = sections[0].get("title", "Untitled_App") if sections else "Untitled_App"

    steps = [
        {"step": 1, "total": 5, "message": "Creating project scaffold for %s..." % project_name},
        {"step": 2, "total": 5, "message": "Generating form definitions (.ds schema)..."},
        {"step": 3, "total": 5, "message": "Generating Deluge workflows (.dg scripts)..."},
        {"step": 4, "total": 5, "message": "Running forgeds-lint on generated scripts..."},
        {"step": 5, "total": 5, "message": "Build complete."},
    ]

    generated_files: list[dict[str, str]] = []

    for step in steps:
        await send_fn({"chunk": step})
        await asyncio.sleep(0.4)

        # Simulate file generation on step 3
        if step["step"] == 3:
            generated_files = [
                {
                    "name": "on_submit_validate.dg",
                    "path": "src/deluge/form-workflows/on_submit_validate.dg",
                    "content": "// On Submit Validate workflow\nclaimAmt = input.Amount_ZAR;\nthreshold = ifnull(Compliance_Config[Config_Key == \"CLAIM_THRESHOLD\" && Active == true].Threshold_Value, 999.99);",
                    "language": "deluge",
                },
                {
                    "name": "on_approval_update.dg",
                    "path": "src/deluge/approval-scripts/on_approval_update.dg",
                    "content": "// On Approval Update\nglRec = GL_Accounts[ID == input.GL_Account];\nif (glRec != null && glRec.count() > 0)\n{\n    input.ESG_Category = glRec.ESG_Category;\n    carbonFactor = ifnull(glRec.Carbon_Factor, 0);\n    input.Estimated_Carbon_KG = input.Amount_ZAR * carbonFactor;\n}",
                    "language": "deluge",
                },
                {
                    "name": "forgeds.yaml",
                    "path": "forgeds.yaml",
                    "content": "project:\n  name: \"%s\"\n  platform: zoho-creator" % project_name,
                    "language": "yaml",
                },
            ]

    return {
        "status": "success",
        "project_name": project_name,
        "files": generated_files,
        "lint_result": {
            "errors": 0,
            "warnings": 1,
            "details": ["W: on_submit_validate.dg:14 -- consider adding GL null guard"],
        },
    }


# ---------------------------------------------------------------------------
# lint_check -- real implementation (invokes forgeds-lint CLI)
# ---------------------------------------------------------------------------
async def handle_lint_check(data: dict) -> dict:
    """Invoke forgeds-lint on specified files via subprocess.

    Args:
        data: Dict with ``files`` (list of paths) or ``directory`` (single path).

    Returns:
        Dict with exit_code, stdout, stderr, and parsed summary.
    """
    files = data.get("files", [])
    directory = data.get("directory", "")
    target = directory if directory else " ".join(files)

    if not target:
        return {"error": "No files or directory specified for lint check."}

    # Determine how to call the linter
    lint_cmd = shutil.which("forgeds-lint")
    if lint_cmd:
        cmd = [lint_cmd, target]
    else:
        cmd = [sys.executable, "-m", "forgeds.core.lint_deluge", target]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=30)
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        # Log errors into enrichment pipeline
        if proc.returncode and proc.returncode >= 2:
            log_error({
                "source": "lint_check",
                "target": target,
                "exit_code": proc.returncode,
                "message": stderr or stdout,
            })

        return {
            "exit_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "summary": _parse_lint_output(stdout, proc.returncode),
        }
    except FileNotFoundError:
        return {
            "exit_code": -1,
            "error": "forgeds-lint not found. Install with: pip install -e .[dev]",
        }
    except asyncio.TimeoutError:
        return {
            "exit_code": -1,
            "error": "Lint check timed out after 30 seconds.",
        }


def _parse_lint_output(stdout: str, exit_code: int | None) -> dict:
    """Extract a structured summary from linter stdout."""
    lines = stdout.strip().splitlines()
    errors = sum(1 for ln in lines if ln.strip().startswith("E:"))
    warnings = sum(1 for ln in lines if ln.strip().startswith("W:"))
    return {
        "clean": exit_code == 0,
        "errors": errors,
        "warnings": warnings,
        "lines": len(lines),
    }


# ---------------------------------------------------------------------------
# get_status -- bridge health check
# ---------------------------------------------------------------------------
async def handle_get_status() -> dict:
    """Return bridge status information."""
    lint_available = shutil.which("forgeds-lint") is not None

    return {
        "bridge_version": __version__,
        "python_version": sys.version,
        "tools": {
            "forgeds-lint": "available" if lint_available else "not_found",
            "claude-code": "mock",
        },
        "status": "running",
    }
