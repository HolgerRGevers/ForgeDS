"""Handler functions for each WebSocket message type."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
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

        diagnostics = _parse_lint_diagnostics(stdout)
        return {
            "exit_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "summary": _parse_lint_output(stdout, proc.returncode),
            "diagnostics": diagnostics,
        }
    except FileNotFoundError:
        # Linter not available — return mock diagnostics for demo purposes
        return {
            "exit_code": 1,
            "error": "forgeds-lint not found. Returning mock diagnostics.",
            "diagnostics": _MOCK_DIAGNOSTICS,
        }
    except asyncio.TimeoutError:
        return {
            "exit_code": -1,
            "error": "Lint check timed out after 30 seconds.",
            "diagnostics": [],
        }


def _parse_lint_diagnostics(stdout: str) -> list[dict]:
    """Parse lint output lines into structured diagnostics.

    Expected line format: ``E: file:line -- message`` or ``W: file:line -- message``.
    """
    import re

    diagnostics: list[dict] = []
    pattern = re.compile(r"^(E|W|I):\s*(.+?):(\d+)\s*--\s*(.+)$")

    for line in stdout.strip().splitlines():
        m = pattern.match(line.strip())
        if m:
            severity_char, filepath, lineno, message = m.groups()
            severity = {"E": "error", "W": "warning", "I": "info"}.get(severity_char, "info")
            diagnostics.append({
                "file": filepath.strip(),
                "line": int(lineno),
                "rule": f"deluge-lint-{severity_char.lower()}",
                "severity": severity,
                "message": message.strip(),
            })

    return diagnostics


# Mock diagnostics for demo when real linter is unavailable
_MOCK_DIAGNOSTICS = [
    {
        "file": "src/deluge/form-workflows/expense_claim.on_validate.dg",
        "line": 14,
        "rule": "deluge-lint-w",
        "severity": "warning",
        "message": "consider adding GL null guard",
    },
    {
        "file": "src/deluge/form-workflows/expense_claim.on_success.dg",
        "line": 8,
        "rule": "deluge-lint-w",
        "severity": "warning",
        "message": "Added_User should use zoho.loginuser",
    },
]


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


# ---------------------------------------------------------------------------
# parse_ds -- parse a .ds export and return app structure (mock)
# ---------------------------------------------------------------------------
async def handle_parse_ds(data: dict) -> dict:
    """Parse a .ds export and return app structure. Mock implementation."""
    file_path = data.get("file_path", "")
    await asyncio.sleep(0.2)

    return {
        "name": "expense_reimbursement",
        "displayName": "Expense Reimbursement Management",
        "tree": [
            {
                "id": "app-root",
                "label": "Expense Reimbursement Management",
                "type": "application",
                "isExpanded": True,
                "children": [
                    {
                        "id": "forms-section",
                        "label": "Forms",
                        "type": "section",
                        "isExpanded": True,
                        "children": [
                            {
                                "id": "form-expense-claims",
                                "label": "Expense Claims",
                                "type": "form",
                                "isExpanded": False,
                                "children": [
                                    {"id": "field-section", "label": "Fields", "type": "section", "isExpanded": False, "children": [
                                        {"id": "field-claim-id", "label": "Claim_ID", "type": "field", "fieldType": "Auto Number"},
                                        {"id": "field-employee", "label": "Employee_Name", "type": "field", "fieldType": "Text"},
                                        {"id": "field-amount", "label": "Amount_ZAR", "type": "field", "fieldType": "Decimal"},
                                        {"id": "field-department", "label": "Department", "type": "field", "fieldType": "Lookup"},
                                        {"id": "field-gl-account", "label": "GL_Account", "type": "field", "fieldType": "Lookup"},
                                        {"id": "field-status", "label": "Status", "type": "field", "fieldType": "Picklist"},
                                        {"id": "field-esg-category", "label": "ESG_Category", "type": "field", "fieldType": "Text"},
                                        {"id": "field-carbon-kg", "label": "Estimated_Carbon_KG", "type": "field", "fieldType": "Decimal"},
                                    ]},
                                    {"id": "wf-section-ec", "label": "Workflows", "type": "section", "isExpanded": False, "children": [
                                        {"id": "wf-on-validate", "label": "On Validate (hard stops)", "type": "workflow", "trigger": "on_validate", "filePath": "src/deluge/form-workflows/expense_claim.on_validate.dg"},
                                        {"id": "wf-on-success", "label": "Self-approval prevention + routing", "type": "workflow", "trigger": "on_success", "filePath": "src/deluge/form-workflows/expense_claim.on_success.dg"},
                                        {"id": "wf-on-load", "label": "Employee Name auto-populate", "type": "workflow", "trigger": "on_load", "filePath": "src/deluge/form-workflows/expense_claim.on_load.auto_populate.dg"},
                                    ]},
                                ],
                            },
                            {
                                "id": "form-approval-history",
                                "label": "Approval History",
                                "type": "form",
                                "isExpanded": False,
                                "children": [
                                    {"id": "field-section-ah", "label": "Fields", "type": "section", "children": [
                                        {"id": "field-ah-claim", "label": "Claim", "type": "field", "fieldType": "Lookup"},
                                        {"id": "field-ah-action", "label": "action_1", "type": "field", "fieldType": "Picklist"},
                                        {"id": "field-ah-actor", "label": "Actor", "type": "field", "fieldType": "Text"},
                                        {"id": "field-ah-added-user", "label": "Added_User", "type": "field", "fieldType": "Text"},
                                    ]},
                                ],
                            },
                            {
                                "id": "form-gl-accounts",
                                "label": "GL Accounts",
                                "type": "form",
                                "isExpanded": False,
                                "children": [
                                    {"id": "field-section-gl", "label": "Fields", "type": "section", "children": [
                                        {"id": "field-gl-code", "label": "GL_Code", "type": "field", "fieldType": "Text"},
                                        {"id": "field-gl-name", "label": "Account_Name", "type": "field", "fieldType": "Text"},
                                        {"id": "field-gl-esg", "label": "ESG_Category", "type": "field", "fieldType": "Text"},
                                        {"id": "field-gl-carbon", "label": "Carbon_Factor", "type": "field", "fieldType": "Decimal"},
                                    ]},
                                ],
                            },
                        ],
                    },
                    {
                        "id": "reports-section",
                        "label": "Reports",
                        "type": "section",
                        "isExpanded": False,
                        "children": [
                            {"id": "report-all-claims", "label": "All Expense Claims", "type": "report"},
                            {"id": "report-my-claims", "label": "My Claims", "type": "report"},
                            {"id": "report-pending", "label": "Pending Approvals Manager", "type": "report"},
                            {"id": "report-audit", "label": "AuditTrail", "type": "report"},
                        ],
                    },
                    {
                        "id": "pages-section",
                        "label": "Pages",
                        "type": "section",
                        "isExpanded": False,
                        "children": [
                            {"id": "page-mgmt-dash", "label": "Management Dashboard", "type": "page"},
                            {"id": "page-emp-dash", "label": "Employee Dashboard", "type": "page"},
                        ],
                    },
                    {
                        "id": "schedules-section",
                        "label": "Schedules",
                        "type": "section",
                        "isExpanded": False,
                        "children": [
                            {"id": "schedule-sla", "label": "SLA Enforcement Daily", "type": "schedule", "trigger": "daily", "filePath": "src/deluge/scheduled/sla_enforcement_daily.dg"},
                        ],
                    },
                    {
                        "id": "apis-section",
                        "label": "Custom APIs",
                        "type": "section",
                        "isExpanded": False,
                        "children": [
                            {"id": "api-dashboard", "label": "Get_Dashboard_Summary", "type": "api", "filePath": "src/deluge/custom-api/get_dashboard_summary.dg"},
                            {"id": "api-claim-status", "label": "Get_Claim_Status", "type": "api", "filePath": "src/deluge/custom-api/get_claim_status.dg"},
                        ],
                    },
                ],
            },
        ],
    }


# ---------------------------------------------------------------------------
# read_file -- read a file and return its content
# ---------------------------------------------------------------------------
_EXTENSION_LANGUAGE_MAP = {
    ".dg": "deluge",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".py": "python",
    ".ds": "deluge",
    ".md": "markdown",
    ".sql": "sql",
    ".txt": "text",
}

_MOCK_CONTENT = {
    "deluge": (
        "// Deluge workflow script\n"
        "claimAmt = input.Amount_ZAR;\n"
        "threshold = ifnull(Compliance_Config[Config_Key == \"CLAIM_THRESHOLD\" && Active == true].Threshold_Value, 999.99);\n"
        "if (claimAmt > threshold)\n"
        "{\n"
        "    alert \"Amount exceeds approval threshold\";\n"
        "    cancel submit;\n"
        "}\n"
    ),
    "json": '{\n  "project": "expense_reimbursement",\n  "version": "0.1"\n}\n',
    "yaml": "project:\n  name: expense_reimbursement\n  platform: zoho-creator\n",
}


async def handle_read_file(data: dict) -> dict:
    """Read a file from disk and return its content with detected language.

    If the file does not exist, returns mock content for demo purposes.
    """
    file_path = data.get("file_path", "")

    ext = Path(file_path).suffix.lower() if file_path else ""
    language = _EXTENSION_LANGUAGE_MAP.get(ext, "text")

    if file_path and os.path.isfile(file_path):
        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return {"error": f"Failed to read file: {exc}", "content": "", "language": language}
    else:
        # Return mock content for demo purposes
        content = _MOCK_CONTENT.get(language, "// File not found — mock content\n")

    return {"content": content, "language": language}


# ---------------------------------------------------------------------------
# inspect_element -- return inspector data for an element (mock)
# ---------------------------------------------------------------------------
_FIELD_INSPECTOR_DEFAULTS = {
    "field-claim-id": {
        "properties": {"type": "Auto Number", "form": "Expense Claims", "displayName": "Claim ID", "required": True, "unique": True},
        "relationships": [{"target": "Approval History.Claim", "type": "lookup_target"}],
        "usages": [{"script": "expense_claim.on_success.dg", "line": 3, "context": "claimId = input.Claim_ID;"}],
    },
    "field-amount": {
        "properties": {"type": "Decimal", "form": "Expense Claims", "displayName": "Amount (ZAR)", "required": True, "unique": False},
        "relationships": [{"target": "GL_Accounts.Carbon_Factor", "type": "calculation_input"}],
        "usages": [
            {"script": "expense_claim.on_validate.dg", "line": 2, "context": "claimAmt = input.Amount_ZAR;"},
            {"script": "expense_claim.on_success.dg", "line": 12, "context": "input.Estimated_Carbon_KG = input.Amount_ZAR * carbonFactor;"},
        ],
    },
    "field-status": {
        "properties": {"type": "Picklist", "form": "Expense Claims", "displayName": "Status", "required": True, "unique": False,
                        "values": ["Draft", "Submitted", "Approved", "Rejected", "Paid"]},
        "relationships": [],
        "usages": [{"script": "expense_claim.on_success.dg", "line": 5, "context": "input.Status = \"Submitted\";"}],
    },
}


async def handle_inspect_element(data: dict) -> dict:
    """Return inspector data for a tree element. Mock implementation.

    Returns properties, relationships, and code usages appropriate for
    the element type.
    """
    element_id = data.get("element_id", "")
    element_type = data.get("element_type", "")

    # Field-level inspection
    if element_type == "field" and element_id in _FIELD_INSPECTOR_DEFAULTS:
        return _FIELD_INSPECTOR_DEFAULTS[element_id]

    if element_type == "field":
        return {
            "properties": {"type": "Text", "form": "Unknown", "displayName": element_id, "required": False, "unique": False},
            "relationships": [],
            "usages": [],
        }

    if element_type == "workflow":
        return {
            "properties": {"trigger": "on_success", "form": "Expense Claims", "scriptFile": f"src/deluge/form-workflows/{element_id}.dg"},
            "relationships": [
                {"target": "Expense Claims", "type": "form_event"},
                {"target": "Approval History", "type": "inserts_into"},
            ],
            "usages": [],
        }

    if element_type == "form":
        return {
            "properties": {"fieldCount": 8, "hasWorkflows": True, "displayName": element_id},
            "relationships": [
                {"target": "GL Accounts", "type": "lookup_source"},
                {"target": "Approval History", "type": "lookup_target"},
            ],
            "usages": [],
        }

    if element_type == "report":
        return {
            "properties": {"sourceForm": "Expense Claims", "displayName": element_id},
            "relationships": [{"target": "Expense Claims", "type": "data_source"}],
            "usages": [],
        }

    if element_type == "schedule":
        return {
            "properties": {"trigger": "daily", "scriptFile": "src/deluge/scheduled/sla_enforcement_daily.dg"},
            "relationships": [{"target": "Expense Claims", "type": "queries"}],
            "usages": [],
        }

    if element_type == "api":
        return {
            "properties": {"method": "GET", "scriptFile": f"src/deluge/custom-api/{element_id}.dg"},
            "relationships": [{"target": "Expense Claims", "type": "queries"}],
            "usages": [],
        }

    # Fallback
    return {
        "properties": {"displayName": element_id, "type": element_type},
        "relationships": [],
        "usages": [],
    }


# ---------------------------------------------------------------------------
# ai_chat -- process AI chat message (mock)
# ---------------------------------------------------------------------------
async def handle_ai_chat(data: dict) -> dict:
    """Process an AI chat message and return a mock response.

    A future version will route to Claude Code CLI with ForgeDS context.
    """
    message = data.get("message", "")
    await asyncio.sleep(0.3)

    # Generate a contextual mock response based on keywords
    lower = message.lower()

    if "validate" in lower or "validation" in lower:
        response = (
            "For form validation in Deluge, use the `on_validate` trigger. "
            "This runs before the record is saved, allowing you to enforce "
            "hard stops with `cancel submit`. Example:\n\n"
            "```\nclaimAmt = input.Amount_ZAR;\n"
            "threshold = ifnull(Compliance_Config[Config_Key == \"CLAIM_THRESHOLD\" "
            "&& Active == true].Threshold_Value, 999.99);\n"
            "if (claimAmt > threshold)\n{\n"
            "    alert \"Amount exceeds threshold\";\n"
            "    cancel submit;\n}\n```"
        )
    elif "approval" in lower:
        response = (
            "The approval workflow uses segregation of duties: a submitter "
            "cannot approve their own claim. The `on_success` trigger checks "
            "`zoho.loginuser` against the submitter and routes to the "
            "appropriate approver based on the department's `Approving_Manager` field. "
            "Every approval action is logged into the `Approval_History` form with "
            "`Added_User = zoho.loginuser`."
        )
    elif "esg" in lower or "carbon" in lower:
        response = (
            "ESG tracking is integrated at the GL Account level. Each GL Account "
            "has an `ESG_Category` and `Carbon_Factor`. When a claim is approved, "
            "the system calculates `Estimated_Carbon_KG = Amount_ZAR * Carbon_Factor` "
            "using `ifnull(glRec.Carbon_Factor, 0)` for safety. This aligns with "
            "ISSB (IFRS S1/S2) and GRI Standards."
        )
    else:
        response = (
            "I can help with Deluge scripting for your Zoho Creator app. "
            "Ask me about form validation, approval workflows, ESG tracking, "
            "GL account lookups, or any other aspect of the expense reimbursement system. "
            "I follow the project conventions including null guards, "
            "Added_User requirements, and South African compliance rules."
        )

    return {"response": response, "model": "mock"}
