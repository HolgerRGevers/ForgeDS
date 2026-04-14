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
# Security: path validation to prevent traversal attacks
# ---------------------------------------------------------------------------
_PROJECT_ROOT: Path | None = None


def _get_project_root() -> Path:
    """Return the project root, caching on first call."""
    global _PROJECT_ROOT
    if _PROJECT_ROOT is None:
        try:
            from forgeds._shared.config import find_project_root
            _PROJECT_ROOT = find_project_root().resolve()
        except Exception:
            _PROJECT_ROOT = Path.cwd().resolve()
    return _PROJECT_ROOT


def _is_safe_path(file_path: str) -> bool:
    """Return True if *file_path* resolves inside the project root."""
    if not file_path:
        return False
    try:
        resolved = Path(file_path).resolve()
        root = _get_project_root()
        # Path.is_relative_to added in 3.9
        return resolved == root or str(resolved).startswith(str(root) + os.sep)
    except (OSError, ValueError):
        return False


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

    # Security: validate all paths resolve within the project root
    targets: list[str] = []
    if directory:
        if not _is_safe_path(directory):
            return {"error": "Directory path is outside the project root."}
        targets = [directory]
    else:
        for f in files:
            if not _is_safe_path(f):
                return {"error": f"File path is outside the project root: {Path(f).name}"}
            targets.append(f)

    if not targets:
        return {"error": "No files or directory specified for lint check."}

    # Determine how to call the linter — pass each target as a separate arg
    lint_cmd = shutil.which("forgeds-lint")
    if lint_cmd:
        cmd = [lint_cmd] + targets
    else:
        cmd = [sys.executable, "-m", "forgeds.core.lint_deluge"] + targets

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

    # Security: reject paths outside the project root
    if file_path and not _is_safe_path(file_path):
        return {"error": "File path is outside the project root.", "content": "", "language": language}

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


# ---------------------------------------------------------------------------
# get_schema -- return Access tables and Zoho forms (mock)
# ---------------------------------------------------------------------------

_ACCESS_TABLES = [
    {
        "name": "tblExpenseClaims",
        "columns": [
            {"name": "ClaimID", "type": "AUTONUMBER", "primaryKey": True},
            {"name": "EmployeeName", "type": "TEXT", "length": 100},
            {"name": "AmountZAR", "type": "CURRENCY"},
            {"name": "DepartmentID", "type": "LONG", "foreignKey": "tblDepartments.DeptID"},
            {"name": "GLAccountID", "type": "LONG", "foreignKey": "tblGLAccounts.GLID"},
            {"name": "ClaimDate", "type": "DATETIME"},
            {"name": "Status", "type": "TEXT", "length": 20},
            {"name": "IsApproved", "type": "BOOLEAN"},
        ],
    },
    {
        "name": "tblDepartments",
        "columns": [
            {"name": "DeptID", "type": "AUTONUMBER", "primaryKey": True},
            {"name": "DeptName", "type": "TEXT", "length": 50},
            {"name": "ApprovingManager", "type": "TEXT", "length": 100},
        ],
    },
    {
        "name": "tblGLAccounts",
        "columns": [
            {"name": "GLID", "type": "AUTONUMBER", "primaryKey": True},
            {"name": "GLCode", "type": "TEXT", "length": 10},
            {"name": "AccountName", "type": "TEXT", "length": 100},
            {"name": "ESGCategory", "type": "TEXT", "length": 50},
            {"name": "CarbonFactor", "type": "DOUBLE"},
        ],
    },
    {
        "name": "tblClients",
        "columns": [
            {"name": "ClientID", "type": "AUTONUMBER", "primaryKey": True},
            {"name": "ClientName", "type": "TEXT", "length": 100},
            {"name": "ContactEmail", "type": "TEXT", "length": 100},
            {"name": "IsActive", "type": "BOOLEAN"},
        ],
    },
    {
        "name": "tblApprovalHistory",
        "columns": [
            {"name": "HistoryID", "type": "AUTONUMBER", "primaryKey": True},
            {"name": "ClaimID", "type": "LONG", "foreignKey": "tblExpenseClaims.ClaimID"},
            {"name": "ActionType", "type": "TEXT", "length": 20},
            {"name": "Actor", "type": "TEXT", "length": 100},
            {"name": "ActionDate", "type": "DATETIME"},
            {"name": "Comments", "type": "TEXT", "length": 255},
        ],
    },
]

_ZOHO_FORMS = [
    {
        "name": "Expense_Claims",
        "fields": [
            {"name": "Claim_ID", "type": "Auto Number"},
            {"name": "Employee_Name", "type": "Text"},
            {"name": "Amount_ZAR", "type": "Decimal"},
            {"name": "Department", "type": "Lookup"},
            {"name": "GL_Account", "type": "Lookup"},
            {"name": "Claim_Date", "type": "DateTime"},
            {"name": "Status", "type": "Picklist"},
            {"name": "Is_Approved", "type": "Checkbox"},
        ],
    },
    {
        "name": "Departments",
        "fields": [
            {"name": "Dept_Name", "type": "Text"},
            {"name": "Approving_Manager", "type": "Text"},
            {"name": "ID", "type": "Auto Number"},
        ],
    },
    {
        "name": "GL_Accounts",
        "fields": [
            {"name": "GL_Code", "type": "Text"},
            {"name": "Account_Name", "type": "Text"},
            {"name": "ESG_Category", "type": "Text"},
            {"name": "Carbon_Factor", "type": "Decimal"},
            {"name": "ID", "type": "Auto Number"},
        ],
    },
    {
        "name": "Clients",
        "fields": [
            {"name": "Client_Name", "type": "Text"},
            {"name": "Contact_Email", "type": "Text"},
            {"name": "Is_Active", "type": "Checkbox"},
            {"name": "ID", "type": "Auto Number"},
        ],
    },
    {
        "name": "Approval_History",
        "fields": [
            {"name": "Claim", "type": "Lookup"},
            {"name": "action_1", "type": "Picklist"},
            {"name": "Actor", "type": "Text"},
            {"name": "Action_Date", "type": "DateTime"},
            {"name": "Comments", "type": "Text"},
            {"name": "Added_User", "type": "Text"},
        ],
    },
]

# Pre-computed table name mapping (Access -> Zoho)
_TABLE_NAME_MAP = {
    "tblExpenseClaims": "Expense_Claims",
    "tblDepartments": "Departments",
    "tblGLAccounts": "GL_Accounts",
    "tblClients": "Clients",
    "tblApprovalHistory": "Approval_History",
}

# Type mismatches worth flagging
_TYPE_MISMATCHES = {
    ("CURRENCY", "Decimal"): "CURRENCY (4dp fixed-point) -> Decimal (2dp) — precision loss possible",
    ("BOOLEAN", "Checkbox"): "Access BOOLEAN (-1/0) -> Zoho Checkbox (true/false) — value mapping required",
    ("DATETIME", "DateTime"): "Access DATETIME (no timezone) -> Zoho DateTime (UTC) — timezone awareness gap",
}


def _build_table_mappings() -> list[dict]:
    """Generate field-level mappings between Access tables and Zoho forms."""
    mappings = []
    for access_tbl in _ACCESS_TABLES:
        zoho_name = _TABLE_NAME_MAP.get(access_tbl["name"])
        if not zoho_name:
            continue
        zoho_form = next((f for f in _ZOHO_FORMS if f["name"] == zoho_name), None)
        if not zoho_form:
            continue

        field_maps = []
        zoho_fields = {f["name"]: f for f in zoho_form["fields"]}
        for col in access_tbl["columns"]:
            # Simple heuristic: match by similar name
            best_match = None
            for zf_name in zoho_fields:
                if col["name"].replace("ID", "").replace("_", "").lower() in zf_name.replace("_", "").lower():
                    best_match = zf_name
                    break
            mismatch = None
            if best_match:
                zoho_type = zoho_fields[best_match]["type"]
                key = (col["type"], zoho_type)
                mismatch = _TYPE_MISMATCHES.get(key)
            field_maps.append({
                "accessColumn": col["name"],
                "zohoField": best_match,
                "accessType": col["type"],
                "zohoType": zoho_fields[best_match]["type"] if best_match else None,
                "mismatch": mismatch,
            })

        mappings.append({
            "accessTable": access_tbl["name"],
            "zohoForm": zoho_name,
            "status": "mapped",
            "fieldMappings": field_maps,
        })
    return mappings


async def handle_get_schema(data: dict) -> dict:
    """Return Access tables, Zoho forms, and auto-generated mappings.

    Mock implementation returning realistic ERM schema data.
    """
    await asyncio.sleep(0.2)
    return {
        "accessTables": _ACCESS_TABLES,
        "zohoForms": _ZOHO_FORMS,
        "tableMappings": _build_table_mappings(),
    }


# ---------------------------------------------------------------------------
# run_validation -- run validation checks (mock)
# ---------------------------------------------------------------------------

_LINT_HYBRID_DETAILS = [
    {"severity": "info", "rule": "HY001", "message": "Schema alignment: tblExpenseClaims -> Expense_Claims OK"},
    {"severity": "info", "rule": "HY001", "message": "Schema alignment: tblDepartments -> Departments OK"},
    {"severity": "info", "rule": "HY001", "message": "Schema alignment: tblGLAccounts -> GL_Accounts OK"},
    {"severity": "warning", "rule": "HY003", "message": "Type mismatch: CURRENCY (4dp) -> Decimal (2dp) for Amount field in tblExpenseClaims"},
    {"severity": "warning", "rule": "HY004", "message": "Access BOOLEAN (-1/0) requires value mapping to Zoho Checkbox (true/false) in tblClients.IsActive"},
]

_VALIDATE_DETAILS = [
    {"severity": "info", "rule": "DV001", "message": "Picklist values for Status match seed data: Draft, Submitted, Approved, Rejected, Paid"},
    {"severity": "info", "rule": "DV002", "message": "Foreign key integrity: tblExpenseClaims.DepartmentID -> tblDepartments.DeptID OK (10/10 valid)"},
    {"severity": "warning", "rule": "DV003", "message": "3 records in tblExpenseClaims have NULL GLAccountID — will import as empty Lookup"},
    {"severity": "info", "rule": "DV004", "message": "Date range check: ClaimDate values span 2024-01-15 to 2026-03-28 — all valid"},
    {"severity": "error", "rule": "DV005", "message": "Duplicate EmployeeName+ClaimDate found in 2 records — possible duplicate claims"},
]


async def handle_run_validation(data: dict) -> dict:
    """Run validation checks. Mock implementation.

    Args:
        data: Dict with ``tool`` ("lint-hybrid" or "validate") and
              ``tables`` (list of table names to validate).
    """
    import datetime
    import uuid

    tool = data.get("tool", "lint-hybrid")
    tables = data.get("tables", [])

    await asyncio.sleep(0.4)

    if tool == "lint-hybrid":
        details = _LINT_HYBRID_DETAILS
    else:
        details = _VALIDATE_DETAILS

    # Filter details to requested tables if specified
    if tables:
        filtered = []
        for d in details:
            if any(t in d["message"] for t in tables) or not any(
                tbl in d["message"] for tbl in _TABLE_NAME_MAP
            ):
                filtered.append(d)
        if filtered:
            details = filtered

    info_count = sum(1 for d in details if d["severity"] == "info")
    warn_count = sum(1 for d in details if d["severity"] == "warning")
    err_count = sum(1 for d in details if d["severity"] == "error")

    if err_count > 0:
        status = "error"
    elif warn_count > 0:
        status = "warning"
    else:
        status = "pass"

    parts = []
    if info_count:
        parts.append(f"{info_count} checks passed")
    if warn_count:
        parts.append(f"{warn_count} warnings")
    if err_count:
        parts.append(f"{err_count} errors")
    summary = ", ".join(parts) if parts else "No checks run"

    return {
        "id": f"val-{uuid.uuid4().hex[:8]}",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "tool": tool,
        "status": status,
        "summary": summary,
        "details": details,
    }


# ---------------------------------------------------------------------------
# mock_upload -- simulate data upload with streaming progress
# ---------------------------------------------------------------------------

# Realistic record counts per table
_TABLE_RECORD_COUNTS = {
    "tblExpenseClaims": 85,
    "tblDepartments": 10,
    "tblGLAccounts": 25,
    "tblClients": 18,
    "tblApprovalHistory": 120,
    "Expense_Claims": 85,
    "Departments": 10,
    "GL_Accounts": 25,
    "Clients": 18,
    "Approval_History": 120,
}


async def handle_mock_upload(data: dict, send_fn: SendFn) -> dict:
    """Simulate data upload with streaming progress.

    Sends incremental progress messages via send_fn for each table,
    simulating batch upload (50 records at a time), then returns a
    final summary.
    """
    tables = data.get("tables", list(_TABLE_NAME_MAP.values()))
    batch_size = 50
    total_records = 0
    errors: list[str] = []

    for table in tables:
        record_count = _TABLE_RECORD_COUNTS.get(table, 30)
        uploaded = 0

        while uploaded < record_count:
            batch = min(batch_size, record_count - uploaded)
            uploaded += batch
            progress = int((uploaded / record_count) * 100)

            await send_fn({
                "chunk": {
                    "table": table,
                    "progress": progress,
                    "uploaded": uploaded,
                    "total": record_count,
                    "status": "uploading" if uploaded < record_count else "complete",
                },
            })
            await asyncio.sleep(0.2)

        total_records += record_count

    return {
        "status": "success",
        "tables_uploaded": len(tables),
        "total_records": total_records,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# generate_api_code -- AI-generate Deluge function code (mock)
# ---------------------------------------------------------------------------

def _generate_deluge_code(prompt: str, api_config: dict) -> str:
    """Generate realistic Deluge function code based on prompt keywords and API config."""
    func_name = api_config.get("functionName", "custom_api_function")
    method = api_config.get("method", "GET").upper()
    params = api_config.get("parameters", [])

    # Build parameter list for function signature
    param_names = [p.get("name", "param") for p in params] if params else []
    param_str = ", ".join(param_names) if param_names else ""
    sig = f"map {func_name}({param_str})"

    lower_prompt = prompt.lower()

    if "pending claims" in lower_prompt or "pending" in lower_prompt:
        body = (
            '    response = Map();\n'
            '    pendingClaims = Expense_Claims[Status == "Pending"];\n'
            '    if (pendingClaims != null && pendingClaims.count() > 0)\n'
            '    {\n'
            '        totalCount = pendingClaims.count();\n'
            '        totalAmount = 0;\n'
            '        for each claim in pendingClaims\n'
            '        {\n'
            '            totalAmount = totalAmount + ifnull(claim.Amount_ZAR, 0);\n'
            '        }\n'
            '        response.put("count", totalCount);\n'
            '        response.put("total_amount", totalAmount);\n'
            '        response.put("status", "success");\n'
            '    }\n'
            '    else\n'
            '    {\n'
            '        response.put("count", 0);\n'
            '        response.put("total_amount", 0);\n'
            '        response.put("status", "success");\n'
            '    }\n'
            '    return response;'
        )
    elif "claim status" in lower_prompt or "by id" in lower_prompt:
        id_param = param_names[0] if param_names else "claim_id"
        body = (
            '    response = Map();\n'
            f'    claimRec = Expense_Claims[ID == {id_param}];\n'
            '    if (claimRec != null && claimRec.count() > 0)\n'
            '    {\n'
            '        rec = claimRec.first();\n'
            '        response.put("claim_id", rec.Claim_ID);\n'
            '        response.put("employee", ifnull(rec.Employee_Name, ""));\n'
            '        response.put("amount_zar", ifnull(rec.Amount_ZAR, 0));\n'
            '        response.put("status", ifnull(rec.Status, "Unknown"));\n'
            '        response.put("esg_category", ifnull(rec.ESG_Category, ""));\n'
            '        response.put("carbon_kg", ifnull(rec.Estimated_Carbon_KG, 0));\n'
            '        response.put("result", "found");\n'
            '    }\n'
            '    else\n'
            '    {\n'
            '        response.put("result", "not_found");\n'
            f'        response.put("message", "No claim found with ID: " + {id_param});\n'
            '    }\n'
            '    return response;'
        )
    elif "esg" in lower_prompt or "carbon" in lower_prompt or "sustainability" in lower_prompt:
        body = (
            '    response = Map();\n'
            '    approvedClaims = Expense_Claims[Status == "Approved"];\n'
            '    totalCarbon = 0;\n'
            '    esgBreakdown = Map();\n'
            '    if (approvedClaims != null && approvedClaims.count() > 0)\n'
            '    {\n'
            '        for each claim in approvedClaims\n'
            '        {\n'
            '            carbonKg = ifnull(claim.Estimated_Carbon_KG, 0);\n'
            '            totalCarbon = totalCarbon + carbonKg;\n'
            '            category = ifnull(claim.ESG_Category, "Uncategorised");\n'
            '            existing = ifnull(esgBreakdown.get(category), 0);\n'
            '            esgBreakdown.put(category, existing + carbonKg);\n'
            '        }\n'
            '    }\n'
            '    response.put("total_carbon_kg", totalCarbon);\n'
            '    response.put("claim_count", ifnull(approvedClaims.count(), 0));\n'
            '    response.put("esg_breakdown", esgBreakdown);\n'
            '    response.put("status", "success");\n'
            '    return response;'
        )
    elif "journal entry" in lower_prompt or "accounting" in lower_prompt:
        id_param = param_names[0] if param_names else "claim_id"
        body = (
            '    response = Map();\n'
            f'    claimRec = Expense_Claims[ID == {id_param}];\n'
            '    if (claimRec != null && claimRec.count() > 0)\n'
            '    {\n'
            '        rec = claimRec.first();\n'
            '        glRec = GL_Accounts[ID == rec.GL_Account];\n'
            '        if (glRec != null && glRec.count() > 0)\n'
            '        {\n'
            '            glCode = glRec.GL_Code;\n'
            '            amount = ifnull(rec.Amount_ZAR, 0);\n'
            '            journalEntry = Map();\n'
            '            journalEntry.put("gl_code", glCode);\n'
            '            journalEntry.put("debit", amount);\n'
            '            journalEntry.put("credit", 0);\n'
            '            journalEntry.put("description", "Expense claim: " + rec.Claim_ID);\n'
            '            journalEntry.put("date", zoho.currentdate);\n'
            '            response.put("journal_entry", journalEntry);\n'
            '            response.put("status", "success");\n'
            '        }\n'
            '        else\n'
            '        {\n'
            '            response.put("status", "error");\n'
            '            response.put("message", "GL Account not found for claim");\n'
            '        }\n'
            '    }\n'
            '    else\n'
            '    {\n'
            '        response.put("status", "error");\n'
            f'        response.put("message", "Claim not found: " + {id_param});\n'
            '    }\n'
            '    return response;'
        )
    else:
        # Default: generic CRUD template based on method
        if method == "POST":
            body = (
                '    response = Map();\n'
                '    // Insert new record from API parameters\n'
                '    row = insert into Expense_Claims\n'
                '    [\n'
                '        Employee_Name = ifnull(employee_name, "")\n'
                '        Amount_ZAR = ifnull(amount, 0)\n'
                '        Status = "Draft"\n'
                '        Added_User = zoho.loginuser\n'
                '    ];\n'
                '    response.put("record_id", row.ID);\n'
                '    response.put("status", "created");\n'
                '    return response;'
            )
        elif method == "PUT":
            id_param = param_names[0] if param_names else "record_id"
            body = (
                '    response = Map();\n'
                f'    rec = Expense_Claims[ID == {id_param}];\n'
                '    if (rec != null && rec.count() > 0)\n'
                '    {\n'
                '        target = rec.first();\n'
                '        // Update fields as needed\n'
                '        response.put("status", "updated");\n'
                f'        response.put("record_id", {id_param});\n'
                '    }\n'
                '    else\n'
                '    {\n'
                '        response.put("status", "not_found");\n'
                '    }\n'
                '    return response;'
            )
        elif method == "DELETE":
            id_param = param_names[0] if param_names else "record_id"
            body = (
                '    response = Map();\n'
                f'    rec = Expense_Claims[ID == {id_param}];\n'
                '    if (rec != null && rec.count() > 0)\n'
                '    {\n'
                '        // Remove record\n'
                f'        delete from Expense_Claims[ID == {id_param}];\n'
                '        response.put("status", "deleted");\n'
                f'        response.put("record_id", {id_param});\n'
                '    }\n'
                '    else\n'
                '    {\n'
                '        response.put("status", "not_found");\n'
                '    }\n'
                '    return response;'
            )
        else:
            # GET (default)
            body = (
                '    response = Map();\n'
                '    records = Expense_Claims[Status != null];\n'
                '    resultList = List();\n'
                '    if (records != null && records.count() > 0)\n'
                '    {\n'
                '        for each rec in records\n'
                '        {\n'
                '            item = Map();\n'
                '            item.put("id", rec.ID);\n'
                '            item.put("employee", ifnull(rec.Employee_Name, ""));\n'
                '            item.put("amount", ifnull(rec.Amount_ZAR, 0));\n'
                '            item.put("status", ifnull(rec.Status, ""));\n'
                '            resultList.add(item);\n'
                '        }\n'
                '    }\n'
                '    response.put("records", resultList);\n'
                '    response.put("count", resultList.size());\n'
                '    return response;'
            )

    return f"{sig}\n{{\n{body}\n}}"


async def handle_generate_api_code(data: dict) -> dict:
    """Generate Deluge function code based on prompt and API config. Mock implementation."""
    prompt = data.get("prompt", "")
    api_config = data.get("apiConfig", {})

    await asyncio.sleep(0.3)

    code = _generate_deluge_code(prompt, api_config)
    return {"code": code}


# ---------------------------------------------------------------------------
# get_api_list -- return saved APIs (mock)
# ---------------------------------------------------------------------------

_SAMPLE_APIS = [
    {
        "id": "api-001",
        "name": "Get_Dashboard_Summary",
        "functionName": "get_dashboard_summary",
        "method": "GET",
        "description": "Returns aggregate dashboard data including claim counts, totals, and ESG metrics",
        "authType": "oauth2",
        "accessScope": "all_users",
        "parameters": [],
        "responseType": "json",
        "status": "active",
    },
    {
        "id": "api-002",
        "name": "Submit_Expense_Claim",
        "functionName": "submit_expense_claim",
        "method": "POST",
        "description": "Submit a new expense claim via API with employee details and amount",
        "authType": "oauth2",
        "accessScope": "selective_users",
        "parameters": [
            {"name": "employee_name", "type": "string", "required": True},
            {"name": "amount", "type": "number", "required": True},
            {"name": "gl_account_id", "type": "number", "required": True},
            {"name": "description", "type": "string", "required": False},
        ],
        "responseType": "json",
        "status": "active",
    },
    {
        "id": "api-003",
        "name": "Get_Claim_Status",
        "functionName": "get_claim_status",
        "method": "GET",
        "description": "Look up the status of a specific expense claim by ID",
        "authType": "oauth2",
        "accessScope": "all_users",
        "parameters": [
            {"name": "claim_id", "type": "number", "required": True},
        ],
        "responseType": "json",
        "status": "active",
    },
]


async def handle_get_api_list(data: dict) -> dict:
    """Return a list of saved/configured APIs. Mock implementation."""
    await asyncio.sleep(0.2)
    return {"apis": _SAMPLE_APIS}


# ---------------------------------------------------------------------------
# export_api -- export API as .dg file + setup instructions (mock)
# ---------------------------------------------------------------------------

async def handle_export_api(data: dict) -> dict:
    """Export an API definition as a .dg file with setup instructions. Mock implementation."""
    api = data.get("api", {})
    func_name = api.get("functionName", "custom_api_function")
    api_name = api.get("name", "Custom_API")
    method = api.get("method", "GET")
    description = api.get("description", "Custom API endpoint")
    auth_type = api.get("authType", "oauth2")
    access_scope = api.get("accessScope", "all_users")
    params = api.get("parameters", [])

    # Generate realistic code for the export
    code = _generate_deluge_code(description, api)

    # Add a file header comment
    param_names = [p.get("name", "param") for p in params] if params else []
    header = (
        f"// Custom API: {api_name}\n"
        f"// Method: {method}\n"
        f"// Auth: {auth_type}\n"
        f"// Description: {description}\n"
    )
    if param_names:
        header += f"// Parameters: {', '.join(param_names)}\n"
    header += "//\n// Generated by ForgeDS IDE\n\n"

    file_content = header + code

    # Build setup instructions
    setup_instructions = [
        "1. Go to Zoho Creator > Microservices > Custom API Builder",
        "2. Click \"Create\"",
        f"3. Set Name to \"{api_name}\"",
        f"4. Set Link Name to \"{func_name}\"",
        f"5. Set Method to \"{method}\"",
    ]

    if params:
        param_list = ", ".join(param_names)
        setup_instructions.append(f"6. Add parameters: {param_list}")
        step = 7
    else:
        step = 6

    setup_instructions.extend([
        f"{step}. Paste the generated Deluge code into the script editor",
        f"{step + 1}. Set Authentication to \"{auth_type}\"",
        f"{step + 2}. Set Access to \"{access_scope}\"",
        f"{step + 3}. Click \"Save\" and test the endpoint",
    ])

    await asyncio.sleep(0.2)

    return {
        "file": {
            "name": f"{func_name}.dg",
            "path": f"src/deluge/custom-api/{func_name}.dg",
            "content": file_content,
        },
        "setupInstructions": setup_instructions,
    }
