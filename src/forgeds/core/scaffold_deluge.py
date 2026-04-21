#!/usr/bin/env python3
"""
Deluge Script Scaffolder.

Generates .dg file skeletons with boilerplate pre-filled from the
deluge-manifest.yaml and email-templates.yaml configuration files.

Usage:
    python -m forgeds.core.scaffold_deluge --list                     # list all scripts in manifest
    python -m forgeds.core.scaffold_deluge --name lm_approval.on_approve  # scaffold one script
    python -m forgeds.core.scaffold_deluge --name NEW_SCRIPT --location "Form > Workflow" \
        --trigger "On Success" --purpose "Description" --context form-workflow \
        --include audit-trail,sendmail
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from forgeds._shared.config import load_config, get_db_dir

# PyYAML is not stdlib, so we parse YAML manually for simple structures
# to keep the zero-dependency requirement.


# ============================================================
# Simple YAML-subset parser (no external deps)
# ============================================================

def _parse_simple_yaml(text: str) -> dict[str, object]:
    """Parse a simple YAML file (flat keys, lists, nested dicts at 1-2 levels)."""
    result: dict[str, object] = {}
    current_key = ""
    current_list: list[dict[str, str]] | None = None
    current_dict: dict[str, str] | None = None
    current_section: dict[str, object] | None = None
    section_key = ""

    for raw_line in text.splitlines():
        # Skip comments and blanks
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip())

        # Top-level key (no indent or 0 indent)
        if indent == 0 and ":" in stripped:
            # Flush previous
            if current_list is not None and current_key:
                result[current_key] = current_list
            if current_section is not None and section_key:
                result[section_key] = current_section

            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            if val:
                result[key] = val.strip("'\"")
                current_key = ""
                current_list = None
                current_section = None
                section_key = ""
            else:
                current_key = key
                current_list = None
                current_dict = None
                current_section = None
                section_key = ""
            continue

        # List item (starts with -)
        if stripped.startswith("- ") and indent == 2:
            if current_list is None:
                current_list = []
            # New list item dict
            current_dict = {}
            current_list.append(current_dict)
            # Parse inline key: value
            rest = stripped[2:].strip()
            if ":" in rest:
                k, _, v = rest.partition(":")
                current_dict[k.strip()] = v.strip().strip("'\"")
            continue

        # Dict continuation (indented key: value)
        if ":" in stripped and indent >= 2:
            k, _, v = stripped.partition(":")
            k = k.strip()
            v = v.strip().strip("'\"")

            # Determine if we're in a list item dict or a section dict
            if indent == 4 and current_dict is not None:
                current_dict[k] = v
            elif indent == 2 and current_key:
                # This is a section with named sub-dicts
                if current_section is None:
                    current_section = {}
                    section_key = current_key
                current_section[k] = {}
                current_dict = current_section[k]  # type: ignore[assignment]
            elif indent == 4 and current_dict is not None:
                current_dict[k] = v

        # Handle includes as list
        if "includes:" in stripped and "[" in stripped:
            val = stripped.split("[")[1].rstrip("]").strip()
            if current_dict is not None:
                current_dict["includes"] = val

    # Flush
    if current_list is not None and current_key:
        result[current_key] = current_list
    if current_section is not None and section_key:
        result[section_key] = current_section

    return result


def load_yaml(path: Path) -> dict[str, object]:
    """Load a YAML file."""
    with open(path, encoding="utf-8") as f:
        return _parse_simple_yaml(f.read())


# ============================================================
# Boilerplate generators
# ============================================================

VERSION = "v2.1 (Fix-Forward Remediation Plan)"


def generate_header(
    name: str, location: str, trigger: str, purpose: str,
) -> str:
    """Generate the standard .dg header comment block."""
    return (
        f"// ============================================================\n"
        f"// Script:   {name}.dg\n"
        f"// Location: {location}\n"
        f"// Trigger:  {trigger}\n"
        f"// Purpose:  {purpose}\n"
        f"// Version:  {VERSION}\n"
        f"// ============================================================\n"
    )


def generate_audit_trail(
    action: str = '"ACTION"',
    comments: str = '"Description of action"',
    actor: str = "zoho.loginuser",
    claim_ref: str = "input.ID",
) -> str:
    """Generate an insert into approval_history block."""
    return (
        f"row = insert into approval_history\n"
        f"[\n"
        f"    claim = {claim_ref}\n"
        f"    action_1 = {action}\n"
        f"    actor = {actor}\n"
        f"    timestamp = zoho.currenttime\n"
        f"    comments = {comments}\n"
        f"    Added_User = zoho.loginuser\n"
        f"];\n"
    )


def generate_sendmail(
    to: str = '"recipient@domain.com"',
    subject: str = '"Subject"',
    message: str = '"Message body"',
    cc: str | None = None,
) -> str:
    """Generate a sendmail block."""
    lines = [
        "sendmail",
        "[",
        "    from : zoho.adminuserid",
        f"    to : {to}",
    ]
    if cc:
        lines.append(f"    cc : {cc}")
    lines.extend([
        f"    subject : {subject}",
        f"    message : {message}",
        "];",
    ])
    return "\n".join(lines) + "\n"


def generate_self_approval_check(
    hod_email: str = '"hod.demo@yourdomain.com"',
) -> str:
    """Generate the self-approval prevention pattern."""
    return (
        "// Self-Approval Prevention (King IV Principle 1)\n"
        'if (thisapp.permissions.isUserInRole("Line Manager"))\n'
        "{\n"
        '    input.status = "Pending HoD Approval";\n'
        "\n"
        f"    {generate_audit_trail(action='\"Submitted (Self-approval bypass)\"', comments='\"Submitter holds Line Manager role. Routed directly to HoD.\"')}\n"
        f"    {generate_sendmail(to=hod_email, subject='\"Expense Claim \" + input.claim_id + \" - Direct HoD Review\"', message='\"Submitted by a Line Manager. Self-approval prevention engaged.\"')}\n"
        "    return;\n"
        "}\n"
    )


def generate_gl_lookup() -> str:
    """Generate the GL code auto-population pattern."""
    return (
        "// GL code auto-population\n"
        'glCode = "";\n'
        "glRec = gl_accounts[expense_category == input.category && Active == true];\n"
        "if (glRec != null && glRec.count() > 0)\n"
        "{\n"
        "    glCode = glRec.gl_code;\n"
        "    input.gl_code = glCode;\n"
        "}\n"
    )


def generate_threshold_check() -> str:
    """Generate the threshold lookup + fallback pattern."""
    return (
        "// Query threshold config table\n"
        'thresholdRec = approval_thresholds[tier_name == "Tier 1 - Line Manager" && Active == true];\n'
        "\n"
        "// Null guard: if config record missing, use fallback matching seed data\n"
        "if (thresholdRec != null)\n"
        "{\n"
        "    thresholdAmount = ifnull(thresholdRec.max_amount_zar, 999.99);\n"
        "}\n"
        "else\n"
        "{\n"
        "    thresholdAmount = 999.99;\n"
        f"    {generate_audit_trail(action='\"Warning\"', comments='\"Approval threshold config record not found. Using fallback R999.99.\"')}"
        "}\n"
    )


# ============================================================
# Custom API template
# ============================================================

def generate_custom_api_boilerplate(name: str) -> str:
    """Generate Custom API-specific boilerplate (request extraction, response map)."""
    return (
        "// --- Request Parameters ---\n"
        "// Parameters are defined in the Custom API Builder wizard (Step 2: Request).\n"
        "// Access them using the parameter names defined in the wizard.\n"
        "// UNCERTAIN: Exact parameter access syntax needs Creator verification.\n"
        "// Possible patterns:\n"
        "//   paramValue = param.get(\"param_name\");\n"
        "//   paramValue = crmAPIRequest.get(\"params\").get(\"param_name\");\n"
        "\n"
        "// --- Business Logic ---\n"
        "// Query forms, compute values, call external services.\n"
        "// No input.FieldName here -- this is API context, not form context.\n"
        "// No alert or cancel submit -- use response map for error reporting.\n"
        "\n"
        "// TODO: Add business logic here\n"
        "\n"
        "// --- Build Response ---\n"
        "// Response keys MUST match the Custom API Builder wizard (Step 3: Response).\n"
        "// UNCERTAIN: Exact response construction syntax needs Creator verification.\n"
        "// Possible pattern:\n"
        "//   response = Map();\n"
        "//   response.put(\"key_name\", value);\n"
    )


# ============================================================
# Scaffold assembly
# ============================================================

def _kb_snippets_for_context(kb, context: str, includes: list[str]) -> list[str]:
    """Query KB for code patterns matching the scaffold context.

    Returns a list of comment-annotated code blocks suitable for
    insertion into a scaffolded .dg file.
    """
    snippets: list[str] = []
    queries: list[str] = []

    if context == "form-workflow":
        queries.append("on_validate cancel submit")
        queries.append("form workflow validation pattern")
    elif context == "approval-script":
        queries.append("approval workflow before transition")
        queries.append("self-approval prevention segregation")
    elif context == "scheduled":
        queries.append("scheduled task cron pattern")
    elif context == "custom-api":
        queries.append("custom API response map")

    # Include-specific queries
    if "audit-trail" in includes:
        queries.append("insert into approval_history audit trail")
    if "sendmail" in includes:
        queries.append("sendmail zoho.adminuserid notification")
    if "threshold-check" in includes:
        queries.append("approval threshold lookup fallback")

    for q in queries:
        patterns = kb.get_patterns(q)
        if patterns:
            # Take the first (most relevant) pattern
            code = patterns[0].strip()
            # Wrap as a KB-sourced comment block
            lines = code.split("\n")
            block = ["// --- KB Pattern: " + q + " ---"]
            for line in lines[:30]:  # Cap at 30 lines per snippet
                block.append("// " + line if not line.startswith("//") else line)
            block.append("// --- End KB Pattern ---")
            snippets.append("\n".join(block))

    return snippets


def scaffold_script(
    name: str,
    location: str,
    trigger: str,
    purpose: str,
    context: str,
    includes: list[str],
    *,
    kb_snippets: list[str] | None = None,
) -> str:
    """Assemble a complete .dg scaffold from components."""
    parts: list[str] = []

    # Header
    parts.append(generate_header(name, location, trigger, purpose))
    parts.append("")

    # Context-specific notes
    if context == "approval-script":
        parts.append("// Note: Uses thisapp.permissions.isUserInRole() - zoho.loginuserrole does NOT exist")
    elif context == "scheduled":
        parts.append("// Note: Uses daysBetween (not hoursBetween) due to Free Trial daily-only schedule constraint")
    elif context == "custom-api":
        parts.append("// Note: Custom API context -- no input.FieldName, no alert, no cancel submit.")
    parts.append("")

    # Custom API gets its own boilerplate instead of the form-oriented includes
    if context == "custom-api":
        parts.append(generate_custom_api_boilerplate(name))
        parts.append("")
        return "\n".join(parts)

    # Optional boilerplate sections
    if "threshold-check" in includes:
        parts.append(generate_threshold_check())
        parts.append("")

    if "self-approval" in includes:
        parts.append(generate_self_approval_check())
        parts.append("")

    if "gl-lookup" in includes:
        parts.append(generate_gl_lookup())
        parts.append("")

    # KB-sourced pattern snippets (when --kb-patterns is passed)
    if kb_snippets:
        parts.append("// ============================================================")
        parts.append("// KB-sourced patterns (reference — adapt to your form/fields)")
        parts.append("// ============================================================")
        for snippet in kb_snippets:
            parts.append(snippet)
            parts.append("")

    parts.append("// TODO: Add business logic here")
    parts.append("")

    if "audit-trail" in includes:
        parts.append("// Audit trail")
        parts.append(generate_audit_trail())
        parts.append("")

    if "sendmail" in includes:
        parts.append("// Notification")
        parts.append(generate_sendmail())
        parts.append("")

    return "\n".join(parts)


# ============================================================
# Main
# ============================================================

def main() -> None:
    config = load_config()
    config_dir_str = config.get("config_dir", "")

    # Try config_dir from forgeds.yaml, then fall back to sibling config/ dir
    if config_dir_str:
        config_dir = Path(config_dir_str)
    else:
        config_dir = Path.cwd() / "config"

    manifest_path = config_dir / "deluge-manifest.yaml"

    parser = argparse.ArgumentParser(
        description="Generate Deluge script scaffolds from manifest",
    )
    parser.add_argument("--list", action="store_true", help="List all scripts in manifest")
    parser.add_argument("--name", help="Script name to scaffold (from manifest or new)")
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    parser.add_argument("--location", default="", help="Creator UI location (for new scripts)")
    parser.add_argument("--trigger", default="", help="Trigger event (for new scripts)")
    parser.add_argument("--purpose", default="", help="One-line purpose (for new scripts)")
    parser.add_argument("--context", default="form-workflow",
                        choices=["form-workflow", "approval-script", "scheduled", "custom-api"],
                        help="Script context type")
    parser.add_argument("--include", default="",
                        help="Comma-separated boilerplate: audit-trail,sendmail,self-approval,gl-lookup,threshold-check")
    parser.add_argument("--kb-patterns", action="store_true",
                        help="Pull code patterns from the knowledge base into the scaffold.")
    args = parser.parse_args()

    # Load manifest
    manifest: dict[str, object] = {}
    if manifest_path.exists():
        manifest = load_yaml(manifest_path)

    scripts_list: list[dict[str, str]] = manifest.get("scripts", [])  # type: ignore[assignment]

    if args.list:
        print("Scripts in manifest:")
        for s in scripts_list:
            name = s.get("name", "?")
            purpose = s.get("purpose", "")
            ctx = s.get("context", "")
            print(f"  [{ctx}] {name}: {purpose}")
        sys.exit(0)

    if not args.name:
        parser.print_help()
        sys.exit(1)

    # Find in manifest or use CLI args
    found = None
    for s in scripts_list:
        if s.get("name") == args.name:
            found = s
            break

    if found:
        name = found.get("name", args.name)
        location = found.get("location", "")
        trigger = found.get("trigger", "")
        purpose = found.get("purpose", "")
        context = found.get("context", "form-workflow")
        includes_str = found.get("includes", "")
        if isinstance(includes_str, str):
            includes = [i.strip() for i in includes_str.split(",") if i.strip()]
        else:
            includes = list(includes_str) if includes_str else []
    else:
        name = args.name
        location = args.location
        trigger = args.trigger
        purpose = args.purpose
        context = args.context
        includes = [i.strip() for i in args.include.split(",") if i.strip()]

    # KB patterns (optional)
    kb_snips = None
    if args.kb_patterns:
        from forgeds._shared.kb_accessor import get_kb
        kb = get_kb()
        if kb.available():
            kb_snips = _kb_snippets_for_context(kb, context, includes)
            print(f"KB: injecting {len(kb_snips)} pattern(s) into scaffold.", file=sys.stderr)
        else:
            print("WARNING: knowledge.db not found. KB patterns disabled.", file=sys.stderr)

    # Generate
    output = scaffold_script(name, location, trigger, purpose, context, includes, kb_snippets=kb_snips)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Scaffold written to {out_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()
