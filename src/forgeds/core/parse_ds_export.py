#!/usr/bin/env python3
"""
Parse a Zoho Creator .ds export and extract structured data.

Extracts:
  - Form definitions (fields, types, display names)
  - Workflow scripts (embedded Deluge code)
  - Scheduled task scripts
  - Approval process scripts

Generates:
  - docs/build-guide/field-link-names.md (auto-generated)
  - Stdout summary of all extracted data
  - Optional: JSON field data for build_deluge_db.py integration

Usage:
    python -m forgeds.core.parse_ds_export exports/App.ds
    python -m forgeds.core.parse_ds_export exports/*.ds --extract-scripts src/deluge/
    python -m forgeds.core.parse_ds_export exports/*.ds --generate-field-docs docs/build-guide/
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from forgeds._shared.config import load_config, get_db_dir


# ============================================================
# Data structures
# ============================================================

@dataclass
class FormField:
    link_name: str
    display_name: str
    field_type: str
    notes: str = ""


@dataclass
class FormDef:
    name: str
    display_name: str
    fields: list[FormField] = field(default_factory=list)


@dataclass
class ScriptDef:
    name: str
    display_name: str
    form: str
    event: str          # "on success", "on validate", "on load", "on edit", "on approve", "on reject"
    trigger: str        # "on add", "on edit", "on add or edit", "scheduled", "approval"
    code: str
    context: str        # "form-workflow", "scheduled", "approval"


# ============================================================
# Parser
# ============================================================

class DSParser:
    """Parse a .ds export file into structured data."""

    def __init__(self, content: str) -> None:
        self.lines = content.splitlines()
        self.forms: list[FormDef] = []
        self.scripts: list[ScriptDef] = []
        self.pos = 0

    def parse(self) -> None:
        """Run all parsing passes."""
        self._parse_forms()
        self._parse_workflows()
        self._parse_schedules()
        self._parse_approvals()

    def _parse_forms(self) -> None:
        """Extract form definitions from the forms { ... } block."""
        i = 0
        while i < len(self.lines):
            line = self.lines[i].strip()

            # Match: form <name> at top level (indented by 2-3 tabs)
            m = re.match(r"^\t{2,3}form\s+(\w+)\s*$", self.lines[i])
            if m and i + 1 < len(self.lines) and self.lines[i + 1].strip() == "{":
                form_name = m.group(1)
                form = self._parse_single_form(form_name, i)
                if form and form.fields:
                    self.forms.append(form)
            i += 1

    def _parse_single_form(self, form_name: str, start: int) -> FormDef | None:
        """Parse a single form definition block."""
        display_name = form_name
        fields: list[FormField] = []

        brace_depth = 0
        in_form = False
        got_display_name = False
        i = start

        while i < len(self.lines):
            line = self.lines[i]
            stripped = line.strip()

            if "{" in stripped:
                brace_depth += stripped.count("{")
                if not in_form:
                    in_form = True
            if "}" in stripped:
                brace_depth -= stripped.count("}")
                if in_form and brace_depth <= 0:
                    break

            # Extract form-level displayname (first one at brace depth 1)
            dm = re.match(r'\s*displayname\s*=\s*"([^"]*)"', stripped)
            if dm and brace_depth == 1 and not got_display_name:
                display_name = dm.group(1)
                got_display_name = True

            # Extract field: look for field definition patterns
            # Fields have format: field_name ( type = xxx ... )
            # They can also be: must have field_name ( type = xxx ... )
            fm = re.match(
                r"^\s*(?:must have\s+)?(\w+)\s*$", stripped
            )
            if fm and brace_depth == 1 and i + 1 < len(self.lines):
                next_line = self.lines[i + 1].strip()
                if next_line == "(":
                    field_link = fm.group(1)
                    # Skip section headers and action blocks
                    if field_link in ("Section", "actions", "submit", "reset",
                                      "update", "cancel"):
                        i += 1
                        continue
                    f = self._parse_field(field_link, i + 1)
                    if f:
                        fields.append(f)

            i += 1

        if not fields:
            return None
        return FormDef(name=form_name, display_name=display_name, fields=fields)

    def _parse_field(self, link_name: str, paren_start: int) -> FormField | None:
        """Parse a field's parenthesized definition block."""
        field_type = ""
        display_name = link_name
        notes_parts: list[str] = []

        paren_depth = 0
        i = paren_start
        while i < len(self.lines):
            stripped = self.lines[i].strip()
            paren_depth += stripped.count("(") - stripped.count(")")

            tm = re.match(r"type\s*=\s*(\w[\w\s]*)", stripped)
            if tm:
                field_type = tm.group(1).strip()

            dnm = re.match(r'displayname\s*=\s*"([^"]*)"', stripped)
            if dnm:
                display_name = dnm.group(1)

            if "personal data = true" in stripped:
                notes_parts.append("personal data")
            if "private = true" in stripped:
                notes_parts.append("private/hidden")
            if re.search(r"initial value\s*=", stripped):
                m = re.search(r"initial value\s*=\s*(\S+)", stripped)
                if m:
                    notes_parts.append(f"default: {m.group(1)}")

            if paren_depth <= 0 and i > paren_start:
                break
            i += 1

        if not field_type:
            return None
        return FormField(
            link_name=link_name,
            display_name=display_name,
            field_type=field_type,
            notes=", ".join(notes_parts),
        )

    def _parse_workflows(self) -> None:
        """Extract workflow scripts from the workflow { form { ... } } block.

        Only searches inside {} brace-scoped blocks — never inside ()
        paren blocks (report columns, quickview fields, etc.).  This
        follows the design rule: action attributes [] live inside {}
        control flow; bare [] / () blocks are not workflow containers.
        """
        # Step 1: locate the workflow { form { ... } } section
        wf_start = None
        i = 0
        while i < len(self.lines):
            stripped = self.lines[i].strip()
            if stripped == "workflow" and i + 1 < len(self.lines):
                if self.lines[i + 1].strip() == "{":
                    wf_start = i + 2
                    break
            i += 1

        if wf_start is None:
            return

        # Step 2: find the brace-scope boundary of the workflow block
        brace_depth = 1  # already inside the opening {
        wf_end = wf_start
        while wf_end < len(self.lines):
            line = self.lines[wf_end].strip()
            brace_depth += line.count("{") - line.count("}")
            if brace_depth <= 0:
                break
            wf_end += 1

        # Step 3: scan only within the workflow block for named entries,
        #         skipping anything inside () paren blocks
        i = wf_start
        paren_depth = 0
        while i < wf_end:
            stripped = self.lines[i].strip()

            # Track paren depth — skip content inside () blocks
            paren_depth += stripped.count("(") - stripped.count(")")
            if paren_depth > 0:
                i += 1
                continue

            # Match workflow names like: Name_Here as "Display Name"
            wm = re.match(
                r'\s*(\w+)\s+as\s+"([^"]*)"', stripped
            )
            if wm:
                name = wm.group(1)
                display = wm.group(2)

                # Look for form = X, record event, and script code
                form_name = ""
                record_event = ""
                event_type = ""
                code = ""

                j = i + 1
                inner_brace = 0
                in_block = False
                while j < wf_end:
                    line = self.lines[j].strip()
                    if "{" in line:
                        inner_brace += line.count("{")
                        in_block = True
                    if "}" in line:
                        inner_brace -= line.count("}")
                        if in_block and inner_brace <= 0:
                            break

                    fm = re.match(r"form\s*=\s*(\w+)", line)
                    if fm:
                        form_name = fm.group(1)

                    rem = re.match(r"record event\s*=\s*(.+)", line)
                    if rem:
                        record_event = rem.group(1).strip()

                    for evt in ["on success", "on validate", "on load",
                                "on update of"]:
                        if line.startswith(evt):
                            event_type = evt

                    # Extract script code from custom deluge script ( ... )
                    if line == "custom deluge script":
                        code = self._extract_script_code(j + 1)

                    j += 1

                if code and form_name:
                    self.scripts.append(ScriptDef(
                        name=name,
                        display_name=display,
                        form=form_name,
                        event=event_type or "on success",
                        trigger=record_event or "on add",
                        code=code,
                        context="form-workflow",
                    ))
            i += 1

    def _parse_schedules(self) -> None:
        """Extract scheduled task scripts."""
        i = 0
        while i < len(self.lines):
            stripped = self.lines[i].strip()
            if stripped.startswith("schedule") and i + 1 < len(self.lines):
                if self.lines[i + 1].strip() == "{":
                    self._parse_schedule_block(i + 2)
            i += 1

    def _parse_schedule_block(self, start: int) -> None:
        """Parse inside a schedule { ... } block."""
        i = start
        while i < len(self.lines):
            stripped = self.lines[i].strip()
            sm = re.match(r'(\w+)\s+as\s+"([^"]*)"', stripped)
            if sm:
                name = sm.group(1)
                display = sm.group(2)
                form_name = ""
                code = ""

                j = i + 1
                brace_depth = 0
                while j < len(self.lines):
                    line = self.lines[j].strip()
                    brace_depth += line.count("{") - line.count("}")

                    fm = re.match(r"form\s*=\s*(\w+)", line)
                    if fm:
                        form_name = fm.group(1)

                    if line == "on load":
                        # Next line should be (
                        if j + 1 < len(self.lines) and "(" in self.lines[j + 1]:
                            code = self._extract_script_code(j + 1)

                    if brace_depth < 0:
                        break
                    j += 1

                if code:
                    self.scripts.append(ScriptDef(
                        name=name,
                        display_name=display,
                        form=form_name,
                        event="on load",
                        trigger="scheduled",
                        code=code,
                        context="scheduled",
                    ))
            i += 1

    def _parse_approvals(self) -> None:
        """Extract approval process scripts (on approve / on reject)."""
        i = 0
        while i < len(self.lines):
            stripped = self.lines[i].strip()
            if stripped.startswith("approval") and i + 1 < len(self.lines):
                if self.lines[i + 1].strip() == "{":
                    self._parse_approval_block(i + 2)
                    break
            i += 1

    def _parse_approval_block(self, start: int) -> None:
        """Parse inside an approval { ... } block."""
        i = start
        current_approval = ""
        current_display = ""

        while i < len(self.lines):
            stripped = self.lines[i].strip()

            # Match approval process name
            am = re.match(r'(\w+)\s+as\s+"([^"]*)"', stripped)
            if am:
                current_approval = am.group(1)
                current_display = am.group(2)

            # Match on approve or on reject
            for event in ["on approve", "on reject"]:
                if stripped.startswith(event):
                    # Find the on load ( ... ) script inside
                    j = i + 1
                    while j < len(self.lines):
                        line_j = self.lines[j].strip()
                        if line_j == "on load":
                            if j + 1 < len(self.lines) and "(" in self.lines[j + 1]:
                                code = self._extract_script_code(j + 1)
                                if code:
                                    self.scripts.append(ScriptDef(
                                        name=f"{current_approval}_{event.replace(' ', '_')}",
                                        display_name=f"{current_display} - {event.title()}",
                                        form="expense_claims",
                                        event=event,
                                        trigger="approval",
                                        code=code,
                                        context="approval",
                                    ))
                            break
                        if "}" in line_j and "{" not in line_j:
                            break
                        j += 1

            i += 1

    def _extract_script_code(self, paren_line: int) -> str:
        """Extract code between ( ... ) delimiters for a custom deluge script."""
        code_lines: list[str] = []
        paren_depth = 0
        started = False
        i = paren_line

        while i < len(self.lines):
            line = self.lines[i]
            stripped = line.strip()

            paren_depth += stripped.count("(") - stripped.count(")")

            if not started and "(" in stripped:
                started = True
                # If there's code after the opening (, grab it
                after_paren = stripped.split("(", 1)[1].strip()
                if after_paren:
                    code_lines.append(after_paren)
                i += 1
                continue

            if started:
                if paren_depth <= 0:
                    # Last line - get content before closing )
                    before_paren = stripped.rsplit(")", 1)[0].strip()
                    if before_paren:
                        code_lines.append(before_paren)
                    break
                code_lines.append(line.rstrip())

            i += 1

        # De-indent: find minimum leading whitespace and strip it
        if not code_lines:
            return ""

        non_empty = [l for l in code_lines if l.strip()]
        if not non_empty:
            return ""

        min_indent = min(len(l) - len(l.lstrip()) for l in non_empty)
        dedented = [l[min_indent:] if len(l) > min_indent else l.lstrip()
                    for l in code_lines]

        return "\n".join(dedented).strip()


# ============================================================
# Output generators
# ============================================================

def generate_field_link_docs(forms: list[FormDef]) -> str:
    """Generate field-link-names.md content."""
    lines = [
        "# Field Link Names",
        "",
        "Auto-generated from `.ds` export by `parse_ds_export.py`.",
        "",
        "## Overview",
        "",
        "Verified field link name mapping extracted from the `.ds` export. "
        "These are the actual Deluge-accessible field identifiers used in scripts.",
        "",
    ]

    for form in forms:
        lines.append(f"## {form.display_name} (`{form.name}`)")
        lines.append("")
        lines.append("| Link Name | Display Name | Type | Notes |")
        lines.append("|-----------|-------------|------|-------|")
        for f in form.fields:
            notes = f.notes or ""
            lines.append(f"| {f.link_name} | {f.display_name} | {f.field_type} | {notes} |")
        lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append("- Field link names are case-sensitive in Deluge")
    lines.append("- `action_1` (not `action`) is the link name for the Action field in Approval_History")
    lines.append("- `Employee_Name1` is the composite name field "
                 "(access subfields via `.first_name`, `.last_name`)")
    lines.append("- Private fields (Department_Shadow, Client_Shadow, Parent_Claim_ID) "
                 "are hidden from end users")
    lines.append("")

    return "\n".join(lines)


def generate_field_json(forms: list[FormDef]) -> list[dict[str, str | None]]:
    """Generate field data as JSON-serializable dicts for DB integration."""
    rows: list[dict[str, str | None]] = []
    for form in forms:
        for f in form.fields:
            rows.append({
                "form_name": form.name,
                "field_link": f.link_name,
                "display": f.display_name,
                "field_type": f.field_type,
                "notes": f.notes or None,
            })
    return rows


def write_extracted_script(
    script: ScriptDef, output_dir: str, version: str = "v2.1",
) -> str:
    """Write an extracted script to a .dg file and return the path."""
    # Determine subdirectory
    if script.context == "scheduled":
        subdir = "scheduled"
    elif script.context == "approval":
        subdir = "approval-scripts"
    else:
        subdir = "form-workflows"

    # Build filename
    event_suffix = script.event.replace(" ", "_").replace("on_", "")
    filename = f"{script.form}.{event_suffix}.{script.name}.extracted.dg"
    filepath = os.path.join(output_dir, subdir, filename)

    # Build header
    header = (
        f"// ============================================================\n"
        f"// Script:   {filename}\n"
        f"// Name:     {script.display_name}\n"
        f"// Location: {script.form} > {script.trigger} > {script.event}\n"
        f"// Trigger:  {script.trigger}\n"
        f"// Purpose:  Extracted from .ds export\n"
        f"// Version:  {version} (extracted)\n"
        f"// ============================================================\n"
    )

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n")
        f.write(script.code)
        f.write("\n")

    return filepath


# ============================================================
# Main
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse Zoho Creator .ds export files",
    )
    parser.add_argument("ds_file", help="Path to the .ds export file")
    parser.add_argument(
        "--extract-scripts", metavar="DIR",
        help="Extract embedded scripts to .dg files in DIR",
    )
    parser.add_argument(
        "--generate-field-docs", metavar="DIR",
        help="Generate field-link-names.md in DIR",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output field data as JSON to stdout",
    )
    args = parser.parse_args()

    # Read .ds file
    try:
        with open(args.ds_file, encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError) as e:
        print(f"Error reading {args.ds_file}: {e}", file=sys.stderr)
        sys.exit(1)

    # Parse
    ds = DSParser(content)
    ds.parse()

    # Summary
    print(f"Parsed: {args.ds_file}")
    print(f"  Forms: {len(ds.forms)}")
    for form in ds.forms:
        print(f"    {form.name} ({form.display_name}): {len(form.fields)} fields")
    print(f"  Scripts: {len(ds.scripts)}")
    for script in ds.scripts:
        print(f"    [{script.context}] {script.display_name} "
              f"({script.form} > {script.event}): {len(script.code)} chars")

    # Generate field docs
    if args.generate_field_docs:
        doc_path = os.path.join(args.generate_field_docs, "field-link-names.md")
        doc_content = generate_field_link_docs(ds.forms)
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(doc_content)
        print(f"\nGenerated: {doc_path}")

    # Extract scripts
    if args.extract_scripts:
        print(f"\nExtracting scripts to {args.extract_scripts}:")
        for script in ds.scripts:
            path = write_extracted_script(script, args.extract_scripts)
            print(f"  {path}")

    # JSON output
    if args.json:
        field_data = generate_field_json(ds.forms)
        print(json.dumps(field_data, indent=2))

    # Total field count
    total_fields = sum(len(f.fields) for f in ds.forms)
    print(f"\nTotal: {len(ds.forms)} forms, {total_fields} fields, {len(ds.scripts)} scripts")


if __name__ == "__main__":
    main()
