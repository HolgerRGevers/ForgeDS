"""Handler functions for each WebSocket message type."""

from __future__ import annotations

import asyncio
import json
import os
import re
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
# parse_ds -- parse a .ds export or project directory to return app structure
# ---------------------------------------------------------------------------


def _slugify(name: str) -> str:
    """Convert a name to a lowercase slug suitable for element IDs."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _parse_ds_file(ds_path: str) -> dict | None:
    """Parse a .ds export file and extract the application tree structure.

    Returns a dict with ``name``, ``displayName``, and ``tree`` or None if
    the file cannot be parsed.
    """
    try:
        content = Path(ds_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    lines = content.split("\n")
    app_name = Path(ds_path).stem

    forms: list[dict] = []
    reports: list[dict] = []
    pages: list[dict] = []

    current_form = ""
    current_fields: list[dict] = []
    # Regex patterns for .ds structure
    form_pat = re.compile(r"^\t{2,3}form\s+(\w+)\s*$")
    field_pat = re.compile(r"^\t{3,4}(?:must have\s+)?(\w+)\s*$")
    field_type_pat = re.compile(r"type\s*=\s*(\w+)")
    report_pat = re.compile(r"^\t+(?:list|kanban)\s+(\w+)\s*$")
    page_pat = re.compile(r"^\t+page\s+(\w+)\s*$")
    schedule_pat = re.compile(r"^\t+schedule\s+(\w+)\s*$")

    skip_fields = {
        "Section", "actions", "submit", "reset", "update", "cancel",
        "prefix", "first_name", "last_name", "suffix",
    }

    schedules: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Detect forms
        m = form_pat.match(line)
        if m:
            if current_form and current_fields:
                forms.append({"name": current_form, "fields": list(current_fields)})
            current_form = m.group(1)
            current_fields = []
            i += 1
            continue

        # Detect fields within a form
        if current_form:
            fm = field_pat.match(line)
            if fm:
                fname = fm.group(1)
                if fname not in skip_fields and i + 1 < len(lines) and lines[i + 1].strip() == "(":
                    # Try to detect field type from the block
                    ftype = "Text"
                    j = i + 2
                    depth = 1
                    while j < len(lines) and depth > 0:
                        depth += lines[j].count("(") - lines[j].count(")")
                        tm = field_type_pat.search(lines[j])
                        if tm and depth == 1:
                            ftype = tm.group(1)
                        j += 1
                    current_fields.append({"name": fname, "type": ftype})

        # Detect reports
        rm = report_pat.match(line)
        if rm:
            reports.append({"name": rm.group(1), "kind": "list" if "list" in line else "kanban"})

        # Detect pages
        pm = page_pat.match(line)
        if pm:
            pages.append({"name": pm.group(1)})

        # Detect schedules
        sm = schedule_pat.match(line)
        if sm:
            schedules.append({"name": sm.group(1)})

        i += 1

    # Flush last form
    if current_form and current_fields:
        forms.append({"name": current_form, "fields": list(current_fields)})

    # Build tree
    display_name = app_name.replace("_", " ").title()
    children = []

    # Forms section
    if forms:
        form_children = []
        for form in forms:
            slug = _slugify(form["name"])
            field_nodes = [
                {
                    "id": f"field-{slug}-{_slugify(f['name'])}",
                    "label": f["name"],
                    "type": "field",
                    "fieldType": f["type"],
                }
                for f in form["fields"]
            ]
            form_children.append({
                "id": f"form-{slug}",
                "label": form["name"].replace("_", " "),
                "type": "form",
                "isExpanded": False,
                "children": [
                    {
                        "id": f"field-section-{slug}",
                        "label": "Fields",
                        "type": "section",
                        "isExpanded": False,
                        "children": field_nodes,
                    },
                ],
            })
        children.append({
            "id": "forms-section",
            "label": "Forms",
            "type": "section",
            "isExpanded": True,
            "children": form_children,
        })

    # Reports section
    if reports:
        children.append({
            "id": "reports-section",
            "label": "Reports",
            "type": "section",
            "isExpanded": False,
            "children": [
                {"id": f"report-{_slugify(r['name'])}", "label": r["name"].replace("_", " "), "type": "report"}
                for r in reports
            ],
        })

    # Pages section
    if pages:
        children.append({
            "id": "pages-section",
            "label": "Pages",
            "type": "section",
            "isExpanded": False,
            "children": [
                {"id": f"page-{_slugify(p['name'])}", "label": p["name"].replace("_", " "), "type": "page"}
                for p in pages
            ],
        })

    # Schedules section
    if schedules:
        children.append({
            "id": "schedules-section",
            "label": "Schedules",
            "type": "section",
            "isExpanded": False,
            "children": [
                {"id": f"schedule-{_slugify(s['name'])}", "label": s["name"].replace("_", " "), "type": "schedule"}
                for s in schedules
            ],
        })

    return {
        "name": app_name,
        "displayName": display_name,
        "tree": [{
            "id": "app-root",
            "label": display_name,
            "type": "application",
            "isExpanded": True,
            "children": children,
        }],
    }


def _build_tree_from_project() -> dict:
    """Build an app tree by scanning the project directory and ForgeDS databases.

    Reads form/field data from deluge_lang.db and scans the filesystem for
    .dg script files to populate workflow, schedule, and API sections.
    """
    import sqlite3

    from forgeds._shared.config import load_config, get_db_dir, find_project_root

    config = load_config()
    project_name = config.get("project", {}).get("name", "Untitled")
    display_name = project_name.replace("_", " ").title()

    children = []

    # --- Forms from deluge_lang.db ---
    db_dir = get_db_dir()
    deluge_db = db_dir / "deluge_lang.db"
    if deluge_db.is_file():
        conn = sqlite3.connect(str(deluge_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        form_fields: dict[str, list[dict]] = {}
        for row in cur.execute(
            "SELECT form_name, field_link, display, field_type "
            "FROM form_fields ORDER BY form_name, field_link"
        ):
            form_fields.setdefault(row["form_name"], []).append({
                "name": row["field_link"],
                "type": row["field_type"],
                "display": row["display"] or row["field_link"],
            })
        conn.close()

        if form_fields:
            form_children = []
            for fname, fields in sorted(form_fields.items()):
                slug = _slugify(fname)
                field_nodes = [
                    {
                        "id": f"field-{slug}-{_slugify(f['name'])}",
                        "label": f["name"],
                        "type": "field",
                        "fieldType": f["type"],
                    }
                    for f in fields
                ]
                form_children.append({
                    "id": f"form-{slug}",
                    "label": fname.replace("_", " "),
                    "type": "form",
                    "isExpanded": False,
                    "children": [{
                        "id": f"field-section-{slug}",
                        "label": "Fields",
                        "type": "section",
                        "isExpanded": False,
                        "children": field_nodes,
                    }],
                })
            children.append({
                "id": "forms-section",
                "label": "Forms",
                "type": "section",
                "isExpanded": True,
                "children": form_children,
            })

    # --- Scan project dir for .dg files ---
    try:
        project_root = find_project_root()
    except Exception:
        project_root = Path.cwd()

    workflow_nodes = []
    schedule_nodes = []
    api_nodes = []

    for dg_file in sorted(project_root.rglob("*.dg")):
        rel = str(dg_file.relative_to(project_root))
        name = dg_file.stem
        slug = _slugify(name)
        parts = rel.replace("\\", "/").lower()

        node = {
            "id": f"script-{slug}",
            "label": name.replace("_", " "),
            "filePath": rel.replace("\\", "/"),
        }

        if "scheduled" in parts or "schedule" in parts:
            node["id"] = f"schedule-{slug}"
            node["type"] = "schedule"
            schedule_nodes.append(node)
        elif "custom-api" in parts or "api" in parts:
            node["id"] = f"api-{slug}"
            node["type"] = "api"
            api_nodes.append(node)
        else:
            node["id"] = f"wf-{slug}"
            node["type"] = "workflow"
            # Detect trigger from filename convention: form.trigger.dg
            if "." in name:
                trigger = name.rsplit(".", 1)[-1]
                node["trigger"] = trigger
            workflow_nodes.append(node)

    # Attach workflows to forms if possible, or add as top-level section
    if workflow_nodes:
        children.append({
            "id": "workflows-section",
            "label": "Workflows",
            "type": "section",
            "isExpanded": False,
            "children": workflow_nodes,
        })

    if schedule_nodes:
        children.append({
            "id": "schedules-section",
            "label": "Schedules",
            "type": "section",
            "isExpanded": False,
            "children": schedule_nodes,
        })

    if api_nodes:
        children.append({
            "id": "apis-section",
            "label": "Custom APIs",
            "type": "section",
            "isExpanded": False,
            "children": api_nodes,
        })

    return {
        "name": project_name,
        "displayName": display_name,
        "tree": [{
            "id": "app-root",
            "label": display_name,
            "type": "application",
            "isExpanded": True,
            "children": children,
        }],
    }


async def handle_parse_ds(data: dict) -> dict:
    """Parse a .ds export or scan the project to return the app tree structure.

    If ``file_path`` points to a real .ds file, parse it directly.
    Otherwise, build the tree from ForgeDS databases and project .dg files.
    """
    file_path = data.get("file_path", "")

    # Try parsing a real .ds file first
    if file_path and os.path.isfile(file_path) and file_path.endswith(".ds"):
        result = _parse_ds_file(file_path)
        if result:
            return result

    # Fall back to project-level tree building
    try:
        return _build_tree_from_project()
    except Exception as exc:
        return {
            "name": "error",
            "displayName": "Error",
            "error": f"Failed to build project tree: {exc}",
            "tree": [],
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

async def handle_read_file(data: dict) -> dict:
    """Read a file from disk and return its content with detected language."""
    file_path = data.get("file_path", "")

    if not file_path:
        return {"error": "No file_path specified.", "content": "", "language": "text"}

    ext = Path(file_path).suffix.lower()
    language = _EXTENSION_LANGUAGE_MAP.get(ext, "text")

    if not os.path.isfile(file_path):
        return {"error": f"File not found: {file_path}", "content": "", "language": language}

    try:
        content = Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {"error": f"Failed to read file: {exc}", "content": "", "language": language}

    return {"content": content, "language": language}


# ---------------------------------------------------------------------------
# write_file -- save content to disk
# ---------------------------------------------------------------------------
async def handle_write_file(data: dict) -> dict:
    """Write content to a file on disk.

    Accepts ``file_path`` and ``content``.  The path is validated to prevent
    directory-traversal attacks (``..`` segments are rejected).

    Returns ``{"success": True, "bytes": <int>}`` on success or an error dict.
    """
    file_path = data.get("file_path", "")
    content = data.get("content")

    if not file_path:
        return {"error": "No file_path specified."}
    if content is None:
        return {"error": "No content specified."}

    resolved = Path(file_path).resolve()

    # Reject path traversal — no ".." allowed in the raw input
    if ".." in Path(file_path).parts:
        return {"error": "Path traversal is not allowed."}

    try:
        # Create parent directories if needed
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return {"success": True, "bytes": len(content.encode("utf-8"))}
    except (OSError, UnicodeEncodeError) as exc:
        return {"error": f"Failed to write file: {exc}"}


# ---------------------------------------------------------------------------
# inspect_element -- real implementation using ForgeDS DB and AST
# ---------------------------------------------------------------------------


def _find_field_usages(field_name: str, project_root: Path) -> list[dict]:
    """Scan .dg files for references to a field name using the Deluge AST.

    Falls back to simple text search if the parser is unavailable.
    """
    usages = []
    for dg_file in sorted(project_root.rglob("*.dg")):
        try:
            source = dg_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        # Use simple grep for field references (input.Field, Form[Field ==], etc.)
        for lineno, line in enumerate(source.splitlines(), 1):
            if field_name in line:
                usages.append({
                    "script": str(dg_file.relative_to(project_root)).replace("\\", "/"),
                    "line": lineno,
                    "context": line.strip(),
                })
    return usages


def _find_form_references_in_script(script_path: str) -> list[dict]:
    """Parse a .dg script and find form/field references using the AST."""
    try:
        from forgeds.lang.parser import parse_source
        from forgeds.lang import ast_nodes as ast

        source = Path(script_path).read_text(encoding="utf-8")
        tree = parse_source(source)

        relationships = []
        seen = set()

        class RefFinder(ast.Visitor):
            def visit_FormQuery(self, node: ast.FormQuery) -> None:
                if node.form not in seen:
                    seen.add(node.form)
                    relationships.append({"target": node.form, "type": "queries"})
                self.generic_visit(node)

            def visit_InsertStmt(self, node: ast.InsertStmt) -> None:
                if node.table not in seen:
                    seen.add(node.table)
                    relationships.append({"target": node.table, "type": "inserts_into"})
                self.generic_visit(node)

            def visit_DeleteStmt(self, node: ast.DeleteStmt) -> None:
                if node.table not in seen:
                    seen.add(node.table)
                    relationships.append({"target": node.table, "type": "deletes_from"})
                self.generic_visit(node)

        RefFinder().visit(tree)
        return relationships
    except Exception:
        return []


async def handle_inspect_element(data: dict) -> dict:
    """Return inspector data for a tree element.

    Uses ForgeDS databases for field/form metadata and the Deluge AST
    for script cross-reference analysis.
    """
    element_id = data.get("element_id", "")
    element_type = data.get("element_type", "")
    # Optional extra data the frontend may pass
    field_name = data.get("label", element_id.split("-")[-1] if "-" in element_id else element_id)
    file_path = data.get("filePath", "")

    try:
        from forgeds._shared.config import get_db_dir, find_project_root
        project_root = find_project_root()
    except Exception:
        project_root = Path.cwd()

    # --- Field inspection ---
    if element_type == "field":
        properties: dict[str, Any] = {
            "displayName": field_name,
            "type": data.get("fieldType", "Text"),
        }
        relationships: list[dict] = []
        usages: list[dict] = []

        # Enrich from deluge_lang.db
        try:
            import sqlite3
            db_path = get_db_dir() / "deluge_lang.db"
            if db_path.is_file():
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT form_name, field_link, display, field_type, notes "
                    "FROM form_fields WHERE field_link = ? LIMIT 1",
                    (field_name,),
                ).fetchone()
                if row:
                    properties["form"] = row["form_name"]
                    properties["type"] = row["field_type"]
                    if row["display"]:
                        properties["displayName"] = row["display"]
                    if row["notes"]:
                        properties["notes"] = row["notes"]
                conn.close()
        except Exception:
            pass

        # Find usages in .dg files
        usages = _find_field_usages(field_name, project_root)

        return {"properties": properties, "relationships": relationships, "usages": usages}

    # --- Workflow / Schedule / API inspection (script-backed) ---
    if element_type in ("workflow", "schedule", "api"):
        properties = {"type": element_type, "displayName": field_name}
        if file_path:
            properties["scriptFile"] = file_path
        if data.get("trigger"):
            properties["trigger"] = data["trigger"]

        # Parse the script for form references
        relationships = []
        if file_path:
            abs_path = project_root / file_path if not os.path.isabs(file_path) else Path(file_path)
            if abs_path.is_file():
                relationships = _find_form_references_in_script(str(abs_path))
                # Get line count
                try:
                    line_count = len(abs_path.read_text(encoding="utf-8").splitlines())
                    properties["lineCount"] = line_count
                except Exception:
                    pass

        return {"properties": properties, "relationships": relationships, "usages": []}

    # --- Form inspection ---
    if element_type == "form":
        properties = {"displayName": field_name.replace("_", " ")}
        relationships = []

        try:
            import sqlite3
            db_path = get_db_dir() / "deluge_lang.db"
            if db_path.is_file():
                conn = sqlite3.connect(str(db_path))
                form_name = field_name.replace(" ", "_")
                rows = conn.execute(
                    "SELECT COUNT(*) FROM form_fields WHERE form_name = ?",
                    (form_name,),
                ).fetchone()
                properties["fieldCount"] = rows[0] if rows else 0

                # Check for workflow scripts
                wf_count = sum(
                    1 for _ in project_root.rglob(f"*{form_name.lower()}*.dg")
                )
                properties["hasWorkflows"] = wf_count > 0
                conn.close()
        except Exception:
            pass

        return {"properties": properties, "relationships": relationships, "usages": []}

    # --- Report / Page / other ---
    if element_type == "report":
        return {
            "properties": {"displayName": field_name.replace("_", " "), "type": "report"},
            "relationships": [],
            "usages": [],
        }

    if element_type == "page":
        return {
            "properties": {"displayName": field_name.replace("_", " "), "type": "page"},
            "relationships": [],
            "usages": [],
        }

    # Fallback
    return {
        "properties": {"displayName": field_name, "type": element_type},
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
# get_schema -- read real schema from ForgeDS SQLite databases
# ---------------------------------------------------------------------------

# Type mismatches worth flagging in the mapping UI
_TYPE_MISMATCHES = {
    ("CURRENCY", "Decimal"): "CURRENCY (4dp fixed-point) -> Decimal (2dp) — precision loss possible",
    ("BOOLEAN", "Checkbox"): "Access BOOLEAN (-1/0) -> Zoho Checkbox (true/false) — value mapping required",
    ("DATETIME", "DateTime"): "Access DATETIME (no timezone) -> Zoho DateTime (UTC) — timezone awareness gap",
    ("MEMO", "Text"): "MEMO (unlimited) -> Text (255 chars) — truncation risk; use Textarea",
}


def _read_schema_from_dbs() -> dict:
    """Read Access tables, Zoho forms, and mappings from the SQLite databases."""
    import sqlite3

    from forgeds._shared.config import get_db_dir

    db_dir = get_db_dir()
    access_db = db_dir / "access_vba_lang.db"
    deluge_db = db_dir / "deluge_lang.db"

    if not access_db.is_file() and not deluge_db.is_file():
        raise FileNotFoundError(
            f"No ForgeDS databases found in {db_dir}. "
            "Run 'forgeds-build-db' and 'forgeds-build-access-db' first."
        )

    access_tables: list[dict] = []
    zoho_forms: list[dict] = []
    field_mappings_raw: list[dict] = []  # from field_name_mappings table
    constraints: list[dict] = []

    # --- Read Access schema ---
    if access_db.is_file():
        conn = sqlite3.connect(str(access_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Group fields by table
        table_fields: dict[str, list[dict]] = {}
        for row in cur.execute(
            "SELECT table_name, field_name, access_type, zoho_form, zoho_field, notes "
            "FROM access_table_fields ORDER BY table_name, field_name"
        ):
            tname = row["table_name"]
            if tname not in table_fields:
                table_fields[tname] = []
            table_fields[tname].append({
                "name": row["field_name"],
                "type": row["access_type"],
            })

        # Read constraints for PK / FK enrichment
        pk_fields: dict[str, set[str]] = {}
        fk_fields: dict[tuple[str, str], str] = {}
        for row in cur.execute(
            "SELECT table_name, constraint_type, field_name, reference_table, reference_field "
            "FROM access_constraints"
        ):
            if row["constraint_type"] == "pk":
                pk_fields.setdefault(row["table_name"], set()).add(row["field_name"])
            elif row["constraint_type"] == "fk":
                fk_fields[(row["table_name"], row["field_name"])] = (
                    f"{row['reference_table']}.{row['reference_field']}"
                )

        for tname, fields in table_fields.items():
            columns = []
            for f in fields:
                col: dict[str, Any] = {"name": f["name"], "type": f["type"]}
                if tname in pk_fields and f["name"] in pk_fields[tname]:
                    col["primaryKey"] = True
                fk_key = (tname, f["name"])
                if fk_key in fk_fields:
                    col["foreignKey"] = fk_fields[fk_key]
                columns.append(col)
            access_tables.append({"name": tname, "columns": columns})

        # Read field_name_mappings for the table mapping view
        for row in cur.execute(
            "SELECT access_table, access_field, zoho_form, zoho_field, transform_notes "
            "FROM field_name_mappings"
        ):
            field_mappings_raw.append(dict(row))

        # Read type_mappings for mismatch detection
        type_map: dict[str, str] = {}
        for row in cur.execute("SELECT access_type, zoho_type FROM type_mappings"):
            type_map[row["access_type"]] = row["zoho_type"]

        conn.close()

    # --- Read Zoho form schema ---
    if deluge_db.is_file():
        conn = sqlite3.connect(str(deluge_db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        form_fields: dict[str, list[dict]] = {}
        for row in cur.execute(
            "SELECT form_name, field_link, display, field_type, notes "
            "FROM form_fields ORDER BY form_name, field_link"
        ):
            fname = row["form_name"]
            if fname not in form_fields:
                form_fields[fname] = []
            form_fields[fname].append({
                "name": row["field_link"],
                "type": row["field_type"],
                "display": row["display"] or row["field_link"],
            })

        for fname, fields in form_fields.items():
            zoho_forms.append({"name": fname, "fields": fields})

        conn.close()

    # --- Build table mappings ---
    # Group field_name_mappings by (access_table, zoho_form)
    mapping_groups: dict[tuple[str, str], list[dict]] = {}
    for fm in field_mappings_raw:
        key = (fm["access_table"], fm["zoho_form"])
        mapping_groups.setdefault(key, []).append(fm)

    # Build a quick lookup of zoho field types
    zoho_field_types: dict[tuple[str, str], str] = {}
    for form in zoho_forms:
        for f in form["fields"]:
            zoho_field_types[(form["name"], f["name"])] = f["type"]

    # Build a quick lookup of access field types
    access_field_types: dict[tuple[str, str], str] = {}
    for tbl in access_tables:
        for c in tbl["columns"]:
            access_field_types[(tbl["name"], c["name"])] = c["type"]

    table_mappings = []
    for (atbl, zform), fmaps in mapping_groups.items():
        field_maps = []
        for fm in fmaps:
            access_type = access_field_types.get((atbl, fm["access_field"]), "")
            zoho_type = zoho_field_types.get((zform, fm["zoho_field"]), "")
            mismatch = _TYPE_MISMATCHES.get((access_type, zoho_type))
            field_maps.append({
                "accessColumn": fm["access_field"],
                "zohoField": fm["zoho_field"],
                "accessType": access_type,
                "zohoType": zoho_type,
                "mismatch": mismatch,
            })
        table_mappings.append({
            "accessTable": atbl,
            "zohoForm": zform,
            "status": "mapped",
            "fieldMappings": field_maps,
        })

    return {
        "accessTables": access_tables,
        "zohoForms": zoho_forms,
        "tableMappings": table_mappings,
    }


async def handle_get_schema(data: dict) -> dict:
    """Return Access tables, Zoho forms, and mappings from ForgeDS databases."""
    try:
        return _read_schema_from_dbs()
    except Exception as exc:
        return {
            "error": f"Failed to read schema: {exc}",
            "accessTables": [],
            "zohoForms": [],
            "tableMappings": [],
        }


# ---------------------------------------------------------------------------
# run_validation -- real implementation using ForgeDS linters
# ---------------------------------------------------------------------------


def _diagnostics_to_details(diagnostics: list) -> list[dict]:
    """Convert a list of Diagnostic objects to the JSON shape the frontend expects."""
    details = []
    for d in diagnostics:
        details.append({
            "severity": d.severity.value.lower(),
            "rule": d.rule,
            "message": d.message,
            "file": d.file,
            "line": d.line,
        })
    return details


def _validation_response(tool: str, details: list[dict]) -> dict:
    """Build the standard validation response envelope."""
    import datetime
    import uuid

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
    summary = ", ".join(parts) if parts else "No issues found"

    return {
        "id": f"val-{uuid.uuid4().hex[:8]}",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "tool": tool,
        "status": status,
        "summary": summary,
        "details": details,
    }


async def handle_run_validation(data: dict) -> dict:
    """Run validation checks using the real ForgeDS linters.

    Args:
        data: Dict with ``tool`` ("lint-hybrid" or "validate"),
              optional ``csv_dir``, ``scripts_dir``, and ``data`` flag.
    """
    tool = data.get("tool", "lint-hybrid")

    try:
        if tool == "lint-hybrid":
            from forgeds.hybrid.lint_hybrid import (
                HybridDB,
                run_schema_rules,
                run_data_rules,
                run_script_rules,
            )

            db = HybridDB()
            diagnostics = run_schema_rules(db)

            csv_dir = data.get("csv_dir", "")
            if csv_dir:
                diagnostics.extend(run_data_rules(db, csv_dir))

            scripts_dir = data.get("scripts_dir", "")
            if scripts_dir:
                diagnostics.extend(run_script_rules(db, scripts_dir))

            details = _diagnostics_to_details(diagnostics)
            return _validation_response(tool, details)

        else:
            # "validate" tool — pre-flight data validation
            from forgeds.hybrid.validate_import import (
                ValidatorDB,
                validate_csv_file,
                load_parent_pk_values,
            )

            csv_dir = data.get("csv_dir", "")
            if not csv_dir:
                return _validation_response(tool, [{
                    "severity": "error",
                    "rule": "VD000",
                    "message": "No csv_dir specified for validate tool.",
                    "file": "",
                    "line": 0,
                }])

            vdb = ValidatorDB()
            check_picklists = data.get("check_picklists", False)
            check_refs = data.get("check_refs", False)
            parent_data = load_parent_pk_values(csv_dir) if check_refs else None

            all_diags = []
            for fname in sorted(os.listdir(csv_dir)):
                if fname.lower().endswith(".csv"):
                    filepath = os.path.join(csv_dir, fname)
                    all_diags.extend(validate_csv_file(
                        filepath, vdb,
                        check_picklists=check_picklists,
                        check_refs=check_refs,
                        parent_data=parent_data,
                    ))

            details = _diagnostics_to_details(all_diags)
            return _validation_response(tool, details)

    except ImportError as exc:
        return _validation_response(tool, [{
            "severity": "error",
            "rule": "BRIDGE",
            "message": f"ForgeDS tools not available: {exc}",
            "file": "",
            "line": 0,
        }])
    except Exception as exc:
        return _validation_response(tool, [{
            "severity": "error",
            "rule": "BRIDGE",
            "message": f"Validation failed: {exc}",
            "file": "",
            "line": 0,
        }])


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
    tables = data.get("tables", [])
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


_DELUGE_SYSTEM_PROMPT = """\
You are a Zoho Creator Deluge scripting expert. Generate a Deluge custom API \
function based on the user's requirements.

Rules:
- Output ONLY the Deluge function code, no markdown fences or explanation.
- Use ifnull() guards for all field lookups to prevent null pointer errors.
- Use zoho.loginuser for audit trails (Added_User fields).
- Return a Map with "status" key and relevant data.
- Form queries use bracket syntax: FormName[criteria].
- Use proper Deluge types: Map(), List(), insert into Form [...].
- Follow Zoho Creator conventions for field naming (underscores, Title_Case).
"""


async def _generate_code_with_claude(prompt: str, api_config: dict) -> str | None:
    """Try to generate code using Claude API. Returns None if unavailable."""
    try:
        import anthropic
    except ImportError:
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None

    func_name = api_config.get("functionName", "custom_api_function")
    method = api_config.get("method", "GET").upper()
    params = api_config.get("parameters", [])
    param_desc = ", ".join(
        f"{p.get('name', 'param')} ({p.get('type', 'string')})"
        for p in params
    ) if params else "none"

    user_msg = (
        f"Generate a Deluge custom API function.\n"
        f"Function name: {func_name}\n"
        f"HTTP method: {method}\n"
        f"Parameters: {param_desc}\n"
        f"Requirements: {prompt}"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=_DELUGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        return response.content[0].text
    except Exception:
        return None


async def handle_generate_api_code(data: dict) -> dict:
    """Generate Deluge function code based on prompt and API config.

    Tries Claude API first (if anthropic package and ANTHROPIC_API_KEY are
    available), falls back to template-based generation.
    """
    prompt = data.get("prompt", "")
    api_config = data.get("apiConfig", {})

    # Try Claude API
    code = await _generate_code_with_claude(prompt, api_config)
    source = "claude"

    # Fall back to template generator
    if code is None:
        code = _generate_deluge_code(prompt, api_config)
        source = "template"

    return {"code": code, "source": source}


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
