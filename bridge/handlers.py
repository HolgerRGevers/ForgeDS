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
        "original_prompt": raw_prompt,
        "refined": {
            "project_name": "Expense_Reimbursement_Manager",
            "description": "Employee expense claim submission and approval workflow with ESG tracking",
            "forms": [
                {
                    "name": "Expense_Claims",
                    "fields": [
                        {"name": "Claim_Reference", "type": "Auto Number", "prefix": "EXP-"},
                        {"name": "Employee_Name", "type": "Name"},
                        {"name": "Department", "type": "Dropdown", "values": ["Finance", "Operations", "IT", "HR"]},
                        {"name": "Claim_Date", "type": "Date"},
                        {"name": "Amount_ZAR", "type": "Currency"},
                        {"name": "GL_Account", "type": "Lookup", "target": "GL_Accounts"},
                        {"name": "Description", "type": "Multi Line"},
                        {"name": "Receipt", "type": "File Upload"},
                        {"name": "Status", "type": "Dropdown", "values": ["Draft", "Submitted", "Approved", "Rejected"]},
                        {"name": "ESG_Category", "type": "Single Line"},
                        {"name": "Estimated_Carbon_KG", "type": "Decimal"},
                    ],
                },
                {
                    "name": "GL_Accounts",
                    "fields": [
                        {"name": "Account_Code", "type": "Single Line"},
                        {"name": "Account_Name", "type": "Single Line"},
                        {"name": "ESG_Category", "type": "Dropdown", "values": ["Travel", "Energy", "Procurement", "Other"]},
                        {"name": "Carbon_Factor", "type": "Decimal"},
                    ],
                },
                {
                    "name": "Approval_History",
                    "fields": [
                        {"name": "Claim_Reference", "type": "Lookup", "target": "Expense_Claims"},
                        {"name": "Action", "type": "Dropdown", "values": ["Approved", "Rejected", "Escalated"]},
                        {"name": "Approver", "type": "Name"},
                        {"name": "Comments", "type": "Multi Line"},
                        {"name": "Added_User", "type": "Added User"},
                    ],
                },
            ],
            "workflows": [
                {
                    "name": "on_submit_validate",
                    "trigger": "Form submission -- Expense_Claims",
                    "description": "Validates amount thresholds, prevents self-approval, writes audit trail",
                },
                {
                    "name": "on_approval_update",
                    "trigger": "Approval -- Expense_Claims",
                    "description": "Populates ESG fields, writes to Approval_History, sends notification",
                },
            ],
            "reports": [
                {"name": "All_Claims", "form": "Expense_Claims", "type": "List"},
                {"name": "Pending_Approvals", "form": "Expense_Claims", "type": "List", "filter": "Status == Submitted"},
                {"name": "Approval_Audit_Trail", "form": "Approval_History", "type": "List"},
            ],
        },
        "warnings": [
            "Free Trial does not support hoursBetween -- using daysBetween instead",
            "Self-approval prevention requires thisapp.permissions.isUserInRole()",
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
    project = data.get("project", {})
    project_name = project.get("project_name", "Untitled_App")

    steps = [
        {"step": 1, "total": 5, "message": "Creating project scaffold for %s..." % project_name},
        {"step": 2, "total": 5, "message": "Generating form definitions (.ds schema)..."},
        {"step": 3, "total": 5, "message": "Generating Deluge workflows (.dg scripts)..."},
        {"step": 4, "total": 5, "message": "Running forgeds-lint on generated scripts..."},
        {"step": 5, "total": 5, "message": "Build complete."},
    ]

    generated_files: list[str] = []

    for step in steps:
        await send_fn({"chunk": step})
        await asyncio.sleep(0.4)

        # Simulate file generation on step 3
        if step["step"] == 3:
            generated_files = [
                "src/deluge/form-workflows/%s/on_submit_validate.dg" % project_name,
                "src/deluge/approval-scripts/%s/on_approval_update.dg" % project_name,
                "src/deluge/scheduled/%s/daily_compliance_check.dg" % project_name,
            ]

    return {
        "status": "success",
        "project_name": project_name,
        "files_generated": generated_files,
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
