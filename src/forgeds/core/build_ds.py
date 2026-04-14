#!/usr/bin/env python3
"""
Generate a Zoho Creator .ds import file from project configuration.

Reads form/field definitions from config/forms.yaml, wires in Deluge
scripts from config/deluge-manifest.yaml + src/deluge/*.dg files, and
emits a .ds file that Zoho Creator can import via Settings > Import.

Usage:
    forgeds-build-ds
    forgeds-build-ds -o myapp.ds
    forgeds-build-ds --no-scripts -o schema-only.ds
    forgeds-build-ds --validate existing.ds
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from forgeds._shared.config import load_config, find_project_root
from forgeds._shared.diagnostics import Diagnostic, Severity


# ============================================================
# Data structures
# ============================================================

# forms.yaml type names -> Zoho .ds export type names
TYPE_MAP = {
    "SingleLine": "text",
    "MultiLine": "textarea",
    "Dropdown": "picklist",
    "Number": "number",
    "Decimal": "decimal",
    "Date": "date",
    "DateTime": "datetime",
    "Email": "email",
    "Checkbox": "checkbox",
    "URL": "url",
    "Phone": "phone",
    "Currency": "currency",
    "Percent": "percent",
    "RichText": "richtext",
    "File": "upload file",
    "Image": "image",
    "Audio": "audio",
    "Video": "video",
    "Signature": "signature",
}

VALID_FIELD_TYPES = set(TYPE_MAP.keys())


@dataclass
class FieldSpec:
    name: str
    display_name: str
    field_type: str
    required: bool = False
    choices: str = ""
    row: int = 0


@dataclass
class FormSpec:
    link_name: str
    display_name: str
    fields: list[FieldSpec] = field(default_factory=list)


@dataclass
class ReportSpec:
    link_name: str
    report_type: str  # "list" or "kanban"
    form: str
    columns: str
    filter_expr: str = ""


@dataclass
class WorkflowSpec:
    link_name: str
    display_name: str
    form: str
    record_event: str  # "on add", "on edit", "on add or edit"
    event_type: str    # "on success", "on validate"
    code: str


@dataclass
class ScheduleSpec:
    link_name: str
    display_name: str
    form: str
    code: str


@dataclass
class BlueprintStage:
    name: str
    display_name: str


@dataclass
class BlueprintTransition:
    link_name: str
    display_name: str
    from_stage: str
    to_stage: str


@dataclass
class BlueprintSpec:
    link_name: str
    display_name: str
    form: str  # form link_name this blueprint is on
    status_field: str  # field that holds the state (usually "Status")
    stages: list[BlueprintStage] = field(default_factory=list)
    transitions: list[BlueprintTransition] = field(default_factory=list)


@dataclass
class PageSpec:
    link_name: str
    display_name: str
    components: list[str] = field(default_factory=list)  # report link_names


# ============================================================
# YAML parser for forms.yaml
# ============================================================

def _parse_forms_yaml(path: Path) -> tuple[list[FormSpec], list[ReportSpec]]:
    """Parse config/forms.yaml into FormSpec and ReportSpec lists.

    Uses a dedicated mini-parser (following the ds_editor.py pattern)
    rather than the shared config loader, because forms.yaml needs
    multi-key dict items in lists (name, type, displayname, etc.).
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    forms: list[FormSpec] = []
    reports: list[ReportSpec] = []

    # State machine
    section = None        # "forms" or "reports"
    current_form = None   # form link name
    current_display = ""
    current_fields: list[FieldSpec] = []
    in_fields = False
    current_field: dict = {}
    current_report = None
    report_data: dict = {}
    row_counter = 0

    def _flush_field():
        nonlocal current_field, row_counter
        if current_field and "name" in current_field:
            row_counter += 1
            current_fields.append(FieldSpec(
                name=current_field["name"],
                display_name=current_field.get("displayname", current_field["name"]),
                field_type=current_field.get("type", "SingleLine"),
                required=current_field.get("required", False),
                choices=current_field.get("choices", ""),
                row=row_counter,
            ))
        current_field = {}

    def _flush_form():
        nonlocal current_form, current_display, current_fields, row_counter, in_fields
        if current_form and current_fields:
            forms.append(FormSpec(
                link_name=current_form,
                display_name=current_display or current_form,
                fields=list(current_fields),
            ))
        current_form = None
        current_display = ""
        current_fields = []
        row_counter = 0
        in_fields = False

    def _flush_report():
        nonlocal current_report, report_data
        if current_report and report_data:
            reports.append(ReportSpec(
                link_name=current_report,
                report_type=report_data.get("type", "list"),
                form=report_data.get("form", ""),
                columns=report_data.get("columns", ""),
                filter_expr=report_data.get("filter", ""),
            ))
        current_report = None
        report_data = {}

    def _parse_val(s: str):
        s = s.strip()
        if s.startswith('"') and s.endswith('"'):
            return s[1:-1]
        if s.startswith("'") and s.endswith("'"):
            return s[1:-1]
        if s.lower() == "true":
            return True
        if s.lower() == "false":
            return False
        return s

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if not stripped or stripped.startswith("#"):
            continue

        # Top-level sections
        if indent == 0 and stripped.startswith("forms:"):
            _flush_field()
            _flush_form()
            _flush_report()
            section = "forms"
            continue
        if indent == 0 and stripped.startswith("reports:"):
            _flush_field()
            _flush_form()
            _flush_report()
            section = "reports"
            continue

        if section == "forms":
            # Form name (indent 2)
            if indent == 2 and ":" in stripped and not stripped.startswith("-"):
                _flush_field()
                _flush_form()
                key = stripped.split(":")[0].strip()
                current_form = key
                in_fields = False
                continue

            # Form-level properties (indent 4)
            if indent == 4 and current_form and not stripped.startswith("-"):
                if ":" in stripped:
                    k, v = stripped.split(":", 1)
                    k = k.strip()
                    v = _parse_val(v)
                    if k == "displayname":
                        current_display = v
                    elif k == "fields":
                        in_fields = True
                continue

            # Field list items (indent 6, starts with "- ")
            if indent == 6 and stripped.startswith("- ") and in_fields:
                _flush_field()
                rest = stripped[2:].strip()
                if ":" in rest:
                    k, v = rest.split(":", 1)
                    current_field = {k.strip(): _parse_val(v)}
                continue

            # Field properties (indent 8)
            if indent == 8 and current_field and ":" in stripped:
                k, v = stripped.split(":", 1)
                current_field[k.strip()] = _parse_val(v)
                continue

        if section == "reports":
            # Report name (indent 2)
            if indent == 2 and ":" in stripped and not stripped.startswith("-"):
                _flush_report()
                current_report = stripped.split(":")[0].strip()
                report_data = {}
                continue

            # Report properties (indent 4)
            if indent == 4 and current_report and ":" in stripped:
                k, v = stripped.split(":", 1)
                report_data[k.strip()] = _parse_val(v)
                continue

    # Final flush
    _flush_field()
    _flush_form()
    _flush_report()

    return forms, reports


# ============================================================
# Manifest + script loader
# ============================================================

def _parse_manifest_yaml(path: Path) -> list[dict]:
    """Parse deluge-manifest.yaml into a list of script metadata dicts."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    scripts = []
    current: dict = {}

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.lstrip()

        if not stripped or stripped.startswith("#"):
            continue

        # Top-level key
        if not line[0].isspace() and ":" in stripped:
            continue

        # List item start
        if stripped.startswith("- "):
            if current:
                scripts.append(current)
            rest = stripped[2:].strip()
            current = {}
            if ":" in rest:
                k, v = rest.split(":", 1)
                v = v.strip().strip('"').strip("'")
                current[k.strip()] = v
            continue

        # Continuation of current dict item
        if current and ":" in stripped:
            k, v = stripped.split(":", 1)
            v = v.strip().strip('"').strip("'")
            k = k.strip()
            if v.startswith("[") and v.endswith("]"):
                inner = v[1:-1]
                v = [p.strip().strip('"').strip("'") for p in inner.split(",") if p.strip()]
            current[k] = v
            continue

    if current:
        scripts.append(current)

    return scripts


def _read_script_code(dg_path: Path) -> str:
    """Read a .dg file and strip the header comment block."""
    text = dg_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Strip leading header block (// ===... and // lines at the top)
    start = 0
    in_header = True
    for i, line in enumerate(lines):
        stripped = line.strip()
        if in_header:
            if stripped.startswith("//") or stripped == "":
                continue
            else:
                start = i
                in_header = False
                break

    code_lines = lines[start:]
    # Strip trailing empty lines
    while code_lines and not code_lines[-1].strip():
        code_lines.pop()

    return "\n".join(code_lines)


def _derive_link_name(manifest_name: str) -> str:
    """Convert manifest name like 'chargeback_incident.on_success' to 'Chargeback_On_Success'."""
    # Remove the .on_success / .on_validate suffix for the link name
    parts = manifest_name.replace(".", "_").split("_")
    return "_".join(p.capitalize() for p in parts)


def _derive_display_name(manifest_name: str) -> str:
    """Convert manifest name to a display name like 'Chargeback Incident On Success'."""
    parts = manifest_name.replace(".", " ").replace("_", " ").split()
    return " ".join(p.capitalize() for p in parts)


def load_manifest_scripts(
    manifest_path: Path,
    deluge_dir: Path,
) -> tuple[list[WorkflowSpec], list[ScheduleSpec]]:
    """Load scripts from the deluge manifest and .dg files."""
    entries = _parse_manifest_yaml(manifest_path)
    workflows: list[WorkflowSpec] = []
    schedules: list[ScheduleSpec] = []

    for entry in entries:
        name = entry.get("name", "")
        context = entry.get("context", "")
        form = entry.get("form", "")
        event = entry.get("event", "on_success")
        record_event = entry.get("record_event", "on add")

        if context == "custom-api":
            continue  # Custom APIs are not part of .ds files

        # Locate the .dg file
        if context == "form-workflow":
            dg_path = deluge_dir / "form-workflows" / f"{name}.dg"
        elif context == "scheduled":
            dg_path = deluge_dir / "scheduled" / f"{name}.dg"
        else:
            continue

        if not dg_path.exists():
            print(f"WARNING: Script file not found: {dg_path}", file=sys.stderr)
            continue

        code = _read_script_code(dg_path)
        link_name = _derive_link_name(name)
        display_name = _derive_display_name(name)

        if context == "form-workflow":
            # Map event field to .ds event type
            if event == "on_success":
                event_type = "on success"
            elif event == "on_validate":
                event_type = "on validate"
            else:
                event_type = "on success"

            workflows.append(WorkflowSpec(
                link_name=link_name,
                display_name=display_name,
                form=form if form else "",
                record_event=record_event,
                event_type=event_type,
                code=code,
            ))
        elif context == "scheduled":
            schedules.append(ScheduleSpec(
                link_name=link_name,
                display_name=display_name,
                form=form if form else "",
                code=code,
            ))

    return workflows, schedules


# ============================================================
# DS emitters
# ============================================================

T = "\t"  # Single tab for readability


def _indent_code(code: str, depth: int) -> str:
    """Re-indent Deluge code to the given tab depth."""
    lines = code.splitlines()
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append("")
        else:
            # Preserve relative indentation from the original
            original_indent = len(line) - len(line.lstrip())
            # Convert spaces to tabs (4 spaces = 1 tab)
            extra_tabs = original_indent // 4
            result.append(T * (depth + extra_tabs) + stripped)
    return "\n".join(result)


def _zoho_type(field_type: str) -> str:
    """Map forms.yaml type to Zoho .ds type name."""
    return TYPE_MAP.get(field_type, field_type.lower())


def _format_choices(choices_str: str) -> str:
    """Convert comma-separated choices to Zoho format: {"A","B","C"}."""
    items = [c.strip() for c in choices_str.split(",") if c.strip()]
    return "{" + ",".join(f'"{i}"' for i in items) + "}"


def emit_forms(forms: list[FormSpec]) -> list[str]:
    """Generate the forms { ... } block matching real Zoho .ds export format."""
    lines = []
    lines.append(f" {T}forms")
    lines.append(f"\t{{")

    for form in forms:
        lines.append(f"\t\tform {form.link_name}")
        lines.append(f"\t\t{{")
        lines.append(f'\t\t\tdisplayname = "{form.display_name}"')
        lines.append(f'\t\t\tsuccess message = "{form.display_name} Added Successfully"')

        # Section block (required by Zoho)
        lines.append(f"\t\t\tSection")
        lines.append(f"\t\t\t(")
        lines.append(f"\t\t\t\ttype = section")
        lines.append(f"\t\t\t\trow = 1")
        lines.append(f"\t\t\t\tcolumn = 0   ")
        lines.append(f"\t\t\t\twidth = medium")
        lines.append(f"\t\t\t)")

        for fld in form.fields:
            prefix = "must have " if fld.required else ""
            zoho_t = _zoho_type(fld.field_type)
            lines.append(f"\t\t\t{prefix}{fld.name}")
            lines.append(f"\t\t\t(")
            if fld.field_type == "Dropdown":
                lines.append(f"\t\t\t\ttype = picklist")
                lines.append(f'\t\t\t\tdisplayname = "{fld.display_name}"')
                if fld.choices:
                    lines.append(f"\t\t\t\tvalues = {_format_choices(fld.choices)}")
            else:
                lines.append(f"\t\t\t\ttype = {zoho_t}")
                lines.append(f'\t\t\t\tdisplayname = "{fld.display_name}"')
                if fld.field_type == "DateTime":
                    lines.append(f'\t\t\t\ttimedisplayoptions = "hh:mm:ss"')
                    lines.append(f"\t\t\t\talloweddays = 0,1,2,3,4,5,6")
                elif fld.field_type == "Date":
                    lines.append(f"\t\t\t\talloweddays = 0,1,2,3,4,5,6")
                elif fld.field_type == "Checkbox":
                    lines.append(f"\t\t\t\tinitial value = false")
                elif fld.field_type == "MultiLine":
                    lines.append(f"\t\t\t\theight = 100px")
            lines.append(f"\t\t\t\trow = 1")
            lines.append(f"\t\t\t\tcolumn = 1   ")
            lines.append(f"\t\t\t\twidth = medium")
            lines.append(f"\t\t\t)")

        # Actions block (required by Zoho)
        lines.append(f"\t")
        lines.append(f"\t\t\tactions")
        lines.append(f"\t\t\t{{")
        lines.append(f"\t\t\t\ton add")
        lines.append(f"\t\t\t\t{{")
        lines.append(f"\t\t\t\t\tsubmit")
        lines.append(f"\t\t\t\t\t(")
        lines.append(f'\t\t\t\t\t\ttype = submit')
        lines.append(f'\t\t\t\t\t\tdisplayname = "Submit"')
        lines.append(f"\t\t\t\t\t)")
        lines.append(f"\t\t\t\t\treset")
        lines.append(f"\t\t\t\t\t(")
        lines.append(f'\t\t\t\t\t\ttype = reset')
        lines.append(f'\t\t\t\t\t\tdisplayname = "Reset"')
        lines.append(f"\t\t\t\t\t)")
        lines.append(f"\t\t\t\t}}")
        lines.append(f"\t\t\t\ton edit")
        lines.append(f"\t\t\t\t{{")
        lines.append(f"\t\t\t\t\tupdate")
        lines.append(f"\t\t\t\t\t(")
        lines.append(f'\t\t\t\t\t\ttype = submit')
        lines.append(f'\t\t\t\t\t\tdisplayname = "Update"')
        lines.append(f"\t\t\t\t\t)")
        lines.append(f"\t\t\t\t\tcancel")
        lines.append(f"\t\t\t\t\t(")
        lines.append(f'\t\t\t\t\t\ttype = cancel')
        lines.append(f'\t\t\t\t\t\tdisplayname = "Cancel"')
        lines.append(f"\t\t\t\t\t)")
        lines.append(f"\t\t\t\t}}")
        lines.append(f"\t\t\t}}")

        lines.append(f"\t\t}}")

    lines.append(f"\t}}")
    return lines


def emit_blueprints(blueprints: list[BlueprintSpec]) -> list[str]:
    """Generate blueprint blocks in .ds format.

    Blueprints define state machines on forms — stages (states) and
    transitions (edges).  The KB requires every form with a Status field
    to have a blueprint; the builder now generates them from config.
    """
    if not blueprints:
        return []

    lines: list[str] = []
    lines.append(f"\tblueprints")
    lines.append(f"\t{{")

    for bp in blueprints:
        lines.append(f'\t\tblueprint {bp.link_name} as "{bp.display_name}"')
        lines.append(f"\t\t{{")
        lines.append(f"\t\t\tform = {bp.form}")
        lines.append(f"\t\t\tstatus field = {bp.status_field}")
        lines.append(f"")

        # Stages
        lines.append(f"\t\t\tstages")
        lines.append(f"\t\t\t{{")
        for stage in bp.stages:
            lines.append(f'\t\t\t\tstage {stage.name} as "{stage.display_name}"')
            lines.append(f"\t\t\t\t{{")
            lines.append(f"\t\t\t\t}}")
        lines.append(f"\t\t\t}}")
        lines.append(f"")

        # Transitions
        lines.append(f"\t\t\ttransitions")
        lines.append(f"\t\t\t{{")
        for t in bp.transitions:
            lines.append(f'\t\t\t\ttransition {t.link_name} as "{t.display_name}"')
            lines.append(f"\t\t\t\t{{")
            lines.append(f"\t\t\t\t\tfrom = {t.from_stage}")
            lines.append(f"\t\t\t\t\tto = {t.to_stage}")
            lines.append(f"\t\t\t\t}}")
        lines.append(f"\t\t\t}}")

        lines.append(f"\t\t}}")
    lines.append(f"\t}}")
    return lines


def emit_pages(pages: list[PageSpec]) -> list[str]:
    """Generate page/dashboard blocks in .ds format.

    The KB documents that Creator apps require at least one page with a
    dashboard for the app to load in the browser.  Without pages, the
    import succeeds but the app shows a blank screen.
    """
    if not pages:
        return []

    lines: list[str] = []
    lines.append(f"\tpages")
    lines.append(f"\t{{")

    for page in pages:
        lines.append(f'\t\tpage {page.link_name} as "{page.display_name}"')
        lines.append(f"\t\t{{")
        lines.append(f'\t\t\ttype = "dashboard"')
        for comp in page.components:
            lines.append(f"\t\t\tcomponent {comp}")
            lines.append(f"\t\t\t{{")
            lines.append(f'\t\t\t\ttype = "report"')
            lines.append(f'\t\t\t\treport = {comp}')
            lines.append(f"\t\t\t}}")
        lines.append(f"\t\t}}")

    lines.append(f"\t}}")
    return lines


def emit_reports(reports: list[ReportSpec]) -> list[str]:
    """Generate reports block matching real Zoho .ds export format."""
    if not reports:
        return []

    lines = []
    lines.append(f"\treports")
    lines.append(f"\t{{")

    for rpt in reports:
        # Build column display list
        cols = [c.strip() for c in rpt.columns.split(",") if c.strip()]
        col_entries = "\n".join(
            f'\t\t\t\t{c} as "{c}"' for c in cols
        )

        lines.append(f"\t\t{rpt.report_type} {rpt.link_name}")
        lines.append(f"\t\t{{")
        lines.append(f'\t\t\tdisplayName = "{rpt.link_name}"')
        if rpt.filter_expr:
            lines.append(f'\t\t\tshow all rows from {rpt.form}  [{rpt.filter_expr}]  ')
        else:
            lines.append(f"\t\t\tshow all rows from {rpt.form}    ")
        lines.append(f"\t\t\t(")
        for c in cols:
            lines.append(f'\t\t\t\t{c} as "{c}"')
        lines.append(f"\t\t\t)")
        lines.append(f"\t\t}}")

    lines.append(f"\t}}")
    return lines


def emit_application(
    app_name: str,
    display_name: str,
    forms: list[FormSpec],
    reports: list[ReportSpec],
    workflows: list[WorkflowSpec],
    schedules: list[ScheduleSpec],
    *,
    blueprints: list[BlueprintSpec] | None = None,
    pages: list[PageSpec] | None = None,
) -> str:
    """Generate the complete .ds file content matching real Zoho export format."""
    from datetime import datetime
    now = datetime.now().strftime("%d-%b-%Y %H:%M:%S")

    lines = []
    # Header comment (matching Zoho export style)
    lines.append("/*")
    lines.append(f" * Generated by : ForgeDS build-ds")
    lines.append(f" * Generated on : {now}")
    lines.append(f" * Version      : 1.0")
    lines.append(" */")

    # Application declaration (quoted name, like real exports)
    lines.append(f' application "{display_name}"')
    lines.append(" {")
    lines.append(f' \tdate format = "dd-MMM-yyyy"')
    lines.append(f' \ttime zone = "Africa/Johannesburg"')
    lines.append(f' \ttime format = "24-hr"')

    # Forms
    lines.append("")
    lines.extend(emit_forms(forms))

    # Reports
    if reports:
        lines.append("")
        lines.extend(emit_reports(reports))

    # Blueprints (KB-adherent: generated for any form with a Status field)
    if blueprints:
        lines.append("")
        lines.extend(emit_blueprints(blueprints))

    # Pages / Dashboards (KB-adherent: required for app to load in Creator)
    if pages:
        lines.append("")
        lines.extend(emit_pages(pages))

    # Workflows + Schedules (nested inside workflow block, like real exports)
    if workflows or schedules:
        lines.append("")
        lines.append("")
        lines.append(f"\t\tworkflow")
        lines.append(f"\t\t{{")
        lines.append(f"\t\tform")
        lines.append(f"\t\t{{")

        for wf in workflows:
            lines.append(f'\t\t\t{wf.link_name} as "{wf.display_name}"')
            lines.append(f"\t\t\t{{")
            lines.append(f"\t\t\t\ttype =  form")
            lines.append(f"\t\t\t\tform = {wf.form}")
            lines.append(f"")
            lines.append(f"\t\t\t\trecord event = {wf.record_event}")
            lines.append(f"")
            lines.append(f"\t\t\t\t{wf.event_type}")
            lines.append(f"\t\t\t\t{{")
            lines.append(f"\t\t\t\t\tactions ")
            lines.append(f"\t\t\t\t\t{{")
            lines.append(f"\t\t\t\t\t\tcustom deluge script")
            lines.append(f"\t\t\t\t\t\t(")
            lines.append(_indent_code(wf.code, 7))
            lines.append(f"\t\t\t\t\t\t)")
            lines.append(f"\t\t\t\t\t}}")
            lines.append(f"\t\t\t\t}}")
            lines.append(f"")
            lines.append(f"\t\t\t}}")

        lines.append(f"\t\t}}")

        # Schedules nested inside workflow block (only emit if present)
        if schedules:
            lines.append(f"")
            lines.append(f"\t\tschedule")
            lines.append(f"\t\t{{")

            for sched in schedules:
                lines.append(f'\t\t\t{sched.link_name} as "{sched.display_name}"')
                lines.append(f"\t\t\t{{")
                lines.append(f"\t\t\t\ttype =  schedule")
                lines.append(f"\t\t\t\tform = {sched.form}")
                lines.append(f'\t\t\t\ttime zone = "Africa/Johannesburg"')
                lines.append(f"\t\t\t\ton start")
                lines.append(f"\t\t\t\t{{")
                lines.append(f"\t\t\t\t\tactions ")
                lines.append(f"\t\t\t\t\t{{")
                lines.append(f"\t\t\t\t\ton load")
                lines.append(f"\t\t\t\t\t(")
                lines.append(_indent_code(sched.code, 6))
                lines.append(f"\t\t\t\t\t)")
                lines.append(f"\t\t\t\t\t}}")
                lines.append(f"\t\t\t\t}}")
                lines.append(f"\t\t\t}}")

            lines.append(f"\t\t}}")

        lines.append(f"")
        lines.append(f"")
        lines.append(f"")
        lines.append(f"\t}}")

    # Web section — forms, reports, and menu (required for import)
    lines.append(f"\tweb")
    lines.append(f"\t{{")

    # Web > forms
    lines.append(f"\t\tforms")
    lines.append(f"\t\t{{")
    for form in forms:
        lines.append(f"\t\t\tform {form.link_name}")
        lines.append(f"\t\t\t{{")
        lines.append(f"\t\t\t\tlabel placement = left")
        lines.append(f"\t\t\t}}")
    lines.append(f"\t\t}}")

    # Web > reports (quickview + detailview + menu for each report)
    if reports:
        lines.append(f"\t\treports")
        lines.append(f"\t\t{{")
        for rpt in reports:
            cols = [c.strip() for c in rpt.columns.split(",") if c.strip()]
            lines.append(f"\t\t\treport {rpt.link_name}")
            lines.append(f"\t\t\t{{")

            # Quickview
            lines.append(f"\t\t\t\tquickview")
            lines.append(f"\t\t\t\t(")
            lines.append(f"\t\t\t\t\tlayout")
            lines.append(f"\t\t\t\t\t(")
            lines.append(f"\t\t\t\t\t\ttype = -1")
            lines.append(f"\t\t\t\t\t\tdatablock1")
            lines.append(f"\t\t\t\t\t\t(")
            lines.append(f"\t\t\t\t\t\t\tlayout type = -1")
            lines.append(f"\t\t\t\t\t\t\tfields")
            lines.append(f"\t\t\t\t\t\t\t(")
            for c in cols:
                lines.append(f'\t\t\t\t\t\t\t\t{c} as "{c}"')
            lines.append(f"\t\t\t\t\t\t\t)")
            lines.append(f"\t\t\t\t\t\t)")
            lines.append(f"\t\t\t\t\t)")
            lines.append(f"\t\t\t\t\tmenu")
            lines.append(f"\t\t\t\t\t(")
            lines.append(f"\t\t\t\t\t\theader")
            lines.append(f"\t\t\t\t\t\t(")
            lines.append(f"\t\t\t\t\t\t\tEdit ")
            lines.append(f"\t\t\t\t\t\t\tDuplicate ")
            lines.append(f"\t\t\t\t\t\t\tDelete ")
            lines.append(f"\t\t\t\t\t\t\tPrint ")
            lines.append(f"\t\t\t\t\t\t\tAdd ")
            lines.append(f"\t\t\t\t\t\t\tImport ")
            lines.append(f"\t\t\t\t\t\t\tExport ")
            lines.append(f"\t\t\t\t\t\t)")
            lines.append(f"\t\t\t\t\t\trecord")
            lines.append(f"\t\t\t\t\t\t(")
            lines.append(f"\t\t\t\t\t\t\tEdit   \t   ")
            lines.append(f"\t\t\t\t\t\t\tDuplicate   \t   ")
            lines.append(f"\t\t\t\t\t\t\tDelete   \t   ")
            lines.append(f"\t\t\t\t\t\t\tPrint   \t   ")
            lines.append(f"\t\t\t\t\t\t)")
            lines.append(f"\t\t\t\t\t)")
            lines.append(f"\t\t\t\t\taction")
            lines.append(f"\t\t\t\t\t(")
            lines.append(f"\t\t\t\t\t\ton click")
            lines.append(f"\t\t\t\t\t\t(")
            lines.append(f"\t\t\t\t\t\t\tView Record   \t   ")
            lines.append(f"\t\t\t\t\t\t)")
            lines.append(f"\t\t\t\t\t\ton right click")
            lines.append(f"\t\t\t\t\t\t(")
            lines.append(f"\t\t\t\t\t\t\tEdit   \t   ")
            lines.append(f"\t\t\t\t\t\t\tDuplicate   \t   ")
            lines.append(f"\t\t\t\t\t\t\tDelete   \t   ")
            lines.append(f"\t\t\t\t\t\t\tPrint   \t   ")
            lines.append(f"\t\t\t\t\t\t\tView Record   \t   ")
            lines.append(f"\t\t\t\t\t\t)")
            lines.append(f"\t\t\t\t\t)")
            lines.append(f"\t\t\t\t)")
            lines.append(f"")

            # Detailview
            lines.append(f"\t\t\t\tdetailview")
            lines.append(f"\t\t\t\t(")
            lines.append(f"\t\t\t\t\tlayout")
            lines.append(f"\t\t\t\t\t(")
            lines.append(f"\t\t\t\t\t\ttype = 1")
            lines.append(f"\t\t\t\t\t\tdatablock1")
            lines.append(f"\t\t\t\t\t\t(")
            lines.append(f"\t\t\t\t\t\t\tlayout type = -2")
            lines.append(f'\t\t\t\t\t\t\ttitle = "Overview"')
            lines.append(f"\t\t\t\t\t\t\tfields")
            lines.append(f"\t\t\t\t\t\t\t(")
            for c in cols:
                lines.append(f'\t\t\t\t\t\t\t\t{c} as "{c}"')
            lines.append(f"\t\t\t\t\t\t\t)")
            lines.append(f"\t\t\t\t\t\t)")
            lines.append(f"\t\t\t\t\t)")
            lines.append(f"\t\t\t\t\tmenu")
            lines.append(f"\t\t\t\t\t(")
            lines.append(f"\t\t\t\t\t\theader")
            lines.append(f"\t\t\t\t\t\t(")
            lines.append(f"\t\t\t\t\t\t\tEdit ")
            lines.append(f"\t\t\t\t\t\t\tDuplicate ")
            lines.append(f"\t\t\t\t\t\t\tDelete ")
            lines.append(f"\t\t\t\t\t\t\tPrint ")
            lines.append(f"\t\t\t\t\t\t)")
            lines.append(f"\t\t\t\t\t)")
            lines.append(f"\t\t\t\t)")

            lines.append(f"\t\t\t}}")
        lines.append(f"\t\t}}")

    # Web > menu (navigation structure)
    lines.append(f"\t\tmenu")
    lines.append(f"\t\t{{")
    lines.append(f"\t\t\tspace Space")
    lines.append(f"\t\t\t{{")
    lines.append(f'\t\t\t\tdisplayname = "Space"')
    lines.append(f'\t\t\t\ticon = "objects-spaceship"')

    # Build menu sections — one per form with its reports
    form_reports: dict[str, list[ReportSpec]] = {}
    for rpt in reports:
        form_reports.setdefault(rpt.form, []).append(rpt)

    section_num = 0
    for form in forms:
        section_num += 1
        lines.append(f"")
        lines.append(f"\t\t\t\tsection Section_{section_num}")
        lines.append(f"\t\t\t\t{{")
        lines.append(f'\t\t\t\t\tdisplayname = "{form.display_name}"')
        lines.append(f'\t\t\t\t\ticon = "travel-world"')
        lines.append(f"\t\t\t\t\tform  {form.link_name}")
        lines.append(f"\t\t\t\t\t{{")
        lines.append(f'\t\t\t\t\t\ticon = "ui-1-bold-add"')
        lines.append(f"\t\t\t\t\t}}")
        for rpt in form_reports.get(form.link_name, []):
            lines.append(f"\t\t\t\t\treport {rpt.link_name}")
            lines.append(f"\t\t\t\t\t{{")
            lines.append(f'\t\t\t\t\t\ticon = "travel-world"')
            lines.append(f"\t\t\t\t\t}}")
        lines.append(f"\t\t\t\t}}")

    lines.append(f"\t\t\t}}")
    # menu > preference
    lines.append(f"\t\t\tpreference")
    lines.append(f"\t\t\t{{")
    lines.append(f"\t\t\t\ticon")
    lines.append(f"\t\t\t\t{{")
    lines.append(f"\t\t\t\t\tstyle = solid")
    lines.append(f"\t\t\t\t\tshow = {{space,section,component}}")
    lines.append(f"\t\t\t\t}}")
    lines.append(f"\t\t\t}}")
    lines.append(f"\t\t}}")
    # web > customize
    lines.append(f"\t\tcustomize")
    lines.append(f"\t\t{{")
    lines.append(f"\t\t\tnew theme = 11")
    lines.append(f'\t\t\tfont = "poppins"')
    lines.append(f"\t\t\tcolor options")
    lines.append(f"\t\t\t{{")
    lines.append(f'\t\t\t\tcolor = "5"')
    lines.append(f"\t\t\t}}")
    lines.append(f"\t\t\tlogo")
    lines.append(f"\t\t\t{{")
    lines.append(f'\t\t\t\tpreference = "none"')
    lines.append(f'\t\t\t\tplacement = "left"')
    lines.append(f"\t\t\t}}")
    lines.append(f"\t\t}}")
    lines.append(f"\t}}")  # close web

    # share_settings — default profiles
    lines.append(f"\tshare_settings")
    lines.append(f"\t{{")
    for profile_name, profile_type, desc in [
        ("Read", "Users_Permissions", "This profile will have read permission for all components\\n"),
        ("Write", "Users_Permissions", "This profile will have write permission for all components\\n"),
        ("Administrator", "Users_Permissions", "This profile will have all the permissions.\\n"),
        ("Developer", "Developer", "Developer Profile\\n"),
        ("Customer", "Customer_Portal", "This is the default profile having only add and view permission.\\n"),
    ]:
        lines.append(f'\t\t\t"{profile_name}"')
        lines.append(f"\t\t\t{{")
        lines.append(f'\t\t\t\tname = "{profile_name}"')
        lines.append(f'\t\t\t\ttype = {profile_type}')
        lines.append(f'\t\t\t\tpermissions = {{Chat:true, Predefined:true, ApiAccess:true, PIIAccess:true, ePHIAccess:true}}')
        lines.append(f'\t\t\t\tdescription = "{desc}"')
        lines.append(f"\t\t\t}}")
    # roles
    lines.append(f"\t\t\troles")
    lines.append(f"\t\t\t{{")
    lines.append(f'\t\t\t\t"CEO"')
    lines.append(f"\t\t\t\t{{")
    lines.append(f'\t\t\t\t\tdescription = "User belonging to this role can access data of all other users."')
    lines.append(f"\t\t\t\t}}")
    lines.append(f"\t\t\t}}")
    lines.append(f"\t}}")

    # phone section
    def _emit_device_section(device_name: str) -> list[str]:
        dl = []
        dl.append(f"\t{device_name}")
        dl.append(f"\t{{")
        dl.append(f"\t\tforms")
        dl.append(f"\t\t{{")
        for form in forms:
            dl.append(f"\t\t\tform {form.link_name}")
            dl.append(f"\t\t\t{{")
            dl.append(f"\t\t\t\tlabel placement = auto")
            dl.append(f"\t\t\t}}")
        dl.append(f"\t\t}}")
        dl.append(f"\t\tcustomize")
        dl.append(f"\t\t{{")
        dl.append(f"\t\t\tlayout = slidingpane")
        dl.append(f'\t\t\tfont = "default"')
        dl.append(f'\t\t\tstyle = "3"')
        dl.append(f"\t\t\tcolor options")
        dl.append(f"\t\t\t{{")
        dl.append(f"\t\t\t\tcolor = green")
        dl.append(f"\t\t\t}}")
        dl.append(f"\t\t\tlogo")
        dl.append(f"\t\t\t{{")
        dl.append(f'\t\t\t\tpreference = "none"')
        dl.append(f"\t\t\t}}")
        dl.append(f"\t\t}}")
        dl.append(f"\t}}")
        return dl

    lines.extend(_emit_device_section("phone"))
    lines.extend(_emit_device_section("tablet"))

    # translation
    lines.append(f"\ttranslation")
    lines.append("{")
    lines.append('{"Language_Settings":{"LANGAGUE_WITH_LOGIN":"browser"}}')
    lines.append("}")

    # Note: reports configuration block omitted — it contains an
    # app-specific Version/Key that Zoho generates internally.
    # Including fake values crashes the app on open.

    lines.append("}")
    return "\n".join(lines) + "\n"


# ============================================================
# Validator
# ============================================================

def validate_ds(content: str, source: str = "<generated>") -> list[Diagnostic]:
    """Validate a .ds file for structural correctness.

    Two validation passes:
      Pass 1 — Delimiter balance, form/report references, field checks
      Pass 2 — Section-aware context validation (constructs in wrong section)
    """
    diagnostics: list[Diagnostic] = []
    lines = content.splitlines()

    # --- Pass 1: Balance + references ---
    brace_count = 0
    paren_count = 0
    form_names: set[str] = set()
    form_refs: list[tuple[int, str]] = []

    for i, line in enumerate(lines, 1):
        brace_count += line.count("{") - line.count("}")
        paren_count += line.count("(") - line.count(")")

        # Collect form definitions
        fm = re.match(r"\s*form\s+(\w+)\s*$", line.strip())
        if fm:
            form_names.add(fm.group(1))

        # Collect form references in reports/workflows/schedules
        ref = re.match(r"\s*form\s*=\s*(\w+)", line.strip())
        if ref:
            form_refs.append((i, ref.group(1)))

        # Check for dropdown/picklist without choices/values
        if re.match(r"\s*type\s*=\s*(Dropdown|picklist)", line.strip()):
            # Look ahead for choices in the same field block
            has_choices = False
            for j in range(i, min(i + 10, len(lines))):
                if "choices" in lines[j] or "values" in lines[j]:
                    has_choices = True
                    break
                if lines[j].strip() == ")":
                    break
            if not has_choices:
                diagnostics.append(Diagnostic(
                    file=source, line=i, rule="DS005",
                    severity=Severity.WARNING,
                    message="Dropdown field without choices attribute",
                ))

    if brace_count != 0:
        diagnostics.append(Diagnostic(
            file=source, line=len(lines), rule="DS001",
            severity=Severity.ERROR,
            message=f"Brace imbalance: {brace_count:+d} unclosed braces",
        ))

    if paren_count != 0:
        diagnostics.append(Diagnostic(
            file=source, line=len(lines), rule="DS002",
            severity=Severity.ERROR,
            message=f"Parenthesis imbalance: {paren_count:+d} unclosed parens",
        ))

    for line_num, ref_name in form_refs:
        if ref_name not in form_names:
            diagnostics.append(Diagnostic(
                file=source, line=line_num, rule="DS003",
                severity=Severity.WARNING,
                message=f"Form reference '{ref_name}' not found in form definitions",
            ))

    # --- Pass 2: Section-aware context validation ---
    diagnostics.extend(_validate_sections(lines, source))

    return diagnostics


# Top-level .ds section keywords that define structural blocks
_SECTION_KEYWORDS = frozenset({
    "forms", "workflow", "schedule", "approval",
    "web", "share_settings", "phone", "tablet",
})


def _validate_sections(
    lines: list[str], source: str,
) -> list[Diagnostic]:
    """Validate that .ds constructs appear in the correct section context.

    Tracks a section stack using brace-depth matching to determine the
    current context (forms, workflow, approval, etc.) and flags constructs
    that appear in the wrong section.

    Rules:
      DS006 — 'on level N' found outside the approval section
      DS007 — 'on approve' / 'on reject' found outside the approval section
    """
    diagnostics: list[Diagnostic] = []

    # Section stack: (section_name, brace_depth_at_opening_brace)
    # When brace_depth drops below this value, the section is closed.
    section_stack: list[tuple[str, int]] = []
    brace_depth = 0
    paren_depth = 0

    # Pending section: keyword detected, waiting for { to confirm
    pending: str | None = None

    # Block-comment tracking
    in_block_comment = False

    for i in range(len(lines)):
        line_num = i + 1
        stripped = lines[i].strip()

        # Track block comments
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("/*"):
            if "*/" not in stripped:
                in_block_comment = True
            continue

        # Skip single-line comments
        if stripped.startswith("//"):
            continue

        if not stripped:
            continue

        # --- 1. Detect section-opening keywords BEFORE brace processing ---
        # Extract the keyword portion (everything before { or ()
        first_word = stripped.split("{")[0].split("(")[0].strip()

        if paren_depth == 0:
            if first_word in _SECTION_KEYWORDS:
                pending = first_word
            elif first_word == "actions":
                if any(s[0].startswith("form:") for s in section_stack):
                    pending = "form_actions"
            else:
                fm = re.match(r"^form\s+(\w+)$", first_word)
                if fm and any(s[0] == "forms" for s in section_stack):
                    pending = f"form:{fm.group(1)}"

        # --- 2. Process delimiters character by character ---
        for ch in stripped:
            if ch == '(':
                paren_depth += 1
            elif ch == ')':
                paren_depth = max(0, paren_depth - 1)
            elif ch == '{' and paren_depth == 0:
                brace_depth += 1
                if pending:
                    section_stack.append((pending, brace_depth))
                    pending = None
            elif ch == '}' and paren_depth == 0:
                while section_stack and brace_depth == section_stack[-1][1]:
                    section_stack.pop()
                brace_depth -= 1

        # --- 3. Validation rules ---
        # Only validate outside of paren blocks (Deluge script code)
        if paren_depth > 0:
            continue

        section_names = {s[0] for s in section_stack}
        in_approval = "approval" in section_names
        in_form_actions = "form_actions" in section_names

        # DS006: "on level N" outside approval section
        if re.match(r"on level \d+", stripped):
            if not in_approval:
                ctx = "form actions block" if in_form_actions else "non-approval context"
                diagnostics.append(Diagnostic(
                    file=source, line=line_num, rule="DS006",
                    severity=Severity.ERROR,
                    message=(
                        f"'{stripped}' found in {ctx} — "
                        f"approval levels must be inside the approval {{}} section"
                    ),
                ))

        # DS007: "on approve" / "on reject" outside approval section
        for kw in ("on approve", "on reject"):
            if stripped == kw or stripped.startswith(kw + " "):
                if not in_approval:
                    diagnostics.append(Diagnostic(
                        file=source, line=line_num, rule="DS007",
                        severity=Severity.ERROR,
                        message=f"'{kw}' found outside approval section",
                    ))
                break

    return diagnostics


def validate_input(
    forms: list[FormSpec],
    reports: list[ReportSpec],
    source: str = "forms.yaml",
) -> list[Diagnostic]:
    """Validate input data before generation."""
    diagnostics: list[Diagnostic] = []
    form_names = {f.link_name for f in forms}

    for form in forms:
        seen_fields: set[str] = set()
        for fld in form.fields:
            if fld.name in seen_fields:
                diagnostics.append(Diagnostic(
                    file=source, line=0, rule="DS004",
                    severity=Severity.ERROR,
                    message=f"Duplicate field '{fld.name}' in form '{form.link_name}'",
                ))
            seen_fields.add(fld.name)

            if fld.field_type not in VALID_FIELD_TYPES:
                diagnostics.append(Diagnostic(
                    file=source, line=0, rule="DS004",
                    severity=Severity.WARNING,
                    message=f"Unknown field type '{fld.field_type}' for "
                            f"'{form.link_name}.{fld.name}' — may not import correctly",
                ))

            if fld.field_type == "Dropdown" and not fld.choices:
                diagnostics.append(Diagnostic(
                    file=source, line=0, rule="DS005",
                    severity=Severity.WARNING,
                    message=f"Dropdown '{form.link_name}.{fld.name}' has no choices",
                ))

    for rpt in reports:
        if rpt.form not in form_names:
            diagnostics.append(Diagnostic(
                file=source, line=0, rule="DS003",
                severity=Severity.ERROR,
                message=f"Report '{rpt.link_name}' references undefined form '{rpt.form}'",
            ))

    return diagnostics


# ============================================================
# CLI
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="forgeds-build-ds",
        description="Generate a Zoho Creator .ds import file from project configuration.",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output .ds file path (default: stdout)",
    )
    parser.add_argument(
        "--forms",
        help="Path to forms.yaml (default: config/forms.yaml)",
    )
    parser.add_argument(
        "--no-scripts",
        action="store_true",
        help="Generate forms and reports only, skip workflows and schedules",
    )
    parser.add_argument(
        "--validate",
        metavar="PATH",
        help="Validate an existing .ds file instead of generating",
    )
    parser.add_argument(
        "--kb-validate",
        action="store_true",
        help="After generating, ingest into KB and run projections to compute residual.",
    )
    args = parser.parse_args()

    # Validate-only mode
    if args.validate:
        ds_path = Path(args.validate)
        if not ds_path.exists():
            print(f"ERROR: File not found: {ds_path}", file=sys.stderr)
            sys.exit(2)
        content = ds_path.read_text(encoding="utf-8")
        diagnostics = validate_ds(content, str(ds_path))
        if diagnostics:
            for d in diagnostics:
                print(d, file=sys.stderr)
            errors = sum(1 for d in diagnostics if d.severity == Severity.ERROR)
            sys.exit(2 if errors else 1)
        else:
            print(f"OK: {ds_path} — no issues found")
            sys.exit(0)

    # Find project root
    root = find_project_root()
    config = load_config()

    # Resolve forms.yaml path
    forms_path = Path(args.forms) if args.forms else root / "config" / "forms.yaml"
    if not forms_path.exists():
        print(f"ERROR: Forms config not found: {forms_path}", file=sys.stderr)
        print("Create config/forms.yaml with form and field definitions.", file=sys.stderr)
        sys.exit(2)

    # Load forms and reports
    forms, reports = _parse_forms_yaml(forms_path)
    if not forms:
        print(f"ERROR: No forms found in {forms_path}", file=sys.stderr)
        sys.exit(2)

    # Validate input
    input_diags = validate_input(forms, reports, str(forms_path))
    input_errors = [d for d in input_diags if d.severity == Severity.ERROR]
    if input_errors:
        for d in input_diags:
            print(d, file=sys.stderr)
        sys.exit(2)
    for d in input_diags:
        print(d, file=sys.stderr)

    # Load scripts from manifest
    workflows: list[WorkflowSpec] = []
    schedules: list[ScheduleSpec] = []

    if not args.no_scripts:
        manifest_path = root / "config" / "deluge-manifest.yaml"
        deluge_dir = root / "src" / "deluge"
        if manifest_path.exists() and deluge_dir.exists():
            workflows, schedules = load_manifest_scripts(manifest_path, deluge_dir)
        elif manifest_path.exists():
            print(f"WARNING: Deluge dir not found: {deluge_dir}", file=sys.stderr)
        # If no manifest, just skip scripts silently

    # Get app name from config (handle both nested and flat parsing)
    project = config.get("project", {})
    app_name = project.get("name", "") or config.get("name", "My_App")
    display_name = app_name

    # KB-adherent: auto-generate blueprints for forms with a Status field
    blueprints: list[BlueprintSpec] = []
    for form in forms:
        status_fields = [f for f in form.fields if f.name.lower() == "status"]
        if status_fields:
            sf = status_fields[0]
            # Build stages from picklist choices if available
            stages: list[BlueprintStage] = []
            if sf.choices:
                for choice in [c.strip() for c in sf.choices.split(",") if c.strip()]:
                    stage_link = choice.replace(" ", "_").replace("-", "_")
                    stages.append(BlueprintStage(name=stage_link, display_name=choice))

            # Auto-generate sequential transitions between stages
            transitions: list[BlueprintTransition] = []
            for i in range(len(stages) - 1):
                t_name = f"{stages[i].name}_to_{stages[i+1].name}".lower()
                t_display = f"{stages[i].display_name} to {stages[i+1].display_name}"
                transitions.append(BlueprintTransition(
                    link_name=t_name,
                    display_name=t_display,
                    from_stage=stages[i].name,
                    to_stage=stages[i+1].name,
                ))

            if stages:
                bp = BlueprintSpec(
                    link_name=f"{form.link_name}_workflow",
                    display_name=f"{form.display_name} Workflow",
                    form=form.link_name,
                    status_field="Status",
                    stages=stages,
                    transitions=transitions,
                )
                blueprints.append(bp)
                print(f"  Blueprint: {bp.display_name} ({len(stages)} stages, "
                      f"{len(transitions)} transitions)", file=sys.stderr)

    # KB-adherent: auto-generate default dashboard page
    pages: list[PageSpec] = []
    if reports:
        page_components = [r.link_name for r in reports[:6]]  # max 6 per dashboard
        pages.append(PageSpec(
            link_name="Dashboard",
            display_name="Dashboard",
            components=page_components,
        ))
        print(f"  Page: Dashboard ({len(page_components)} components)", file=sys.stderr)

    # Generate .ds content
    content = emit_application(
        app_name, display_name, forms, reports, workflows, schedules,
        blueprints=blueprints, pages=pages,
    )

    # Validate output
    output_diags = validate_ds(content, args.output or "<stdout>")
    for d in output_diags:
        print(d, file=sys.stderr)
    output_errors = [d for d in output_diags if d.severity == Severity.ERROR]

    if output_errors:
        print("ERROR: Generated .ds has structural errors — not writing output.", file=sys.stderr)
        sys.exit(2)

    # Write output
    if args.output:
        out_path = Path(args.output)
        out_path.write_text(content, encoding="utf-8")
        print(f"Generated: {out_path}")
        print(f"  Forms: {len(forms)}")
        print(f"  Reports: {len(reports)}")
        print(f"  Blueprints: {len(blueprints)}")
        print(f"  Pages: {len(pages)}")
        print(f"  Workflows: {len(workflows)}")
        print(f"  Schedules: {len(schedules)}")
    else:
        sys.stdout.write(content)

    # KB post-build validation (optional)
    if args.kb_validate:
        from forgeds._shared.kb_accessor import get_kb
        kb = get_kb()
        if kb.available():
            import tempfile
            # Write .ds to a temp file if output was stdout
            if args.output:
                ds_for_ingest = Path(args.output)
            else:
                tmp = tempfile.NamedTemporaryFile(suffix=".ds", delete=False, mode="w", encoding="utf-8")
                tmp.write(content)
                tmp.close()
                ds_for_ingest = Path(tmp.name)

            try:
                from forgeds.knowledge.app_ingest import ingest_ds_app
                module = f"app:{app_name.replace(' ', '_')}"
                ingest_ds_app(str(ds_for_ingest), str(kb.db_path), module_name=module)
                report = kb.project(module)
                if report:
                    print(f"\n  KB Projection: R({app_name}) = {report.residual:.1f}", file=sys.stderr)
                    print(f"  Gaps: {len(report.gaps)}", file=sys.stderr)
                    for g in sorted(report.gaps, key=lambda x: -x.severity)[:10]:
                        sev = {2.0: "CRITICAL", 1.5: "HIGH", 1.0: "MEDIUM", 0.5: "LOW"}.get(g.severity, "INFO")
                        print(f"    [{sev}] {g.entity}: {g.message[:80]}", file=sys.stderr)
                    if len(report.gaps) > 10:
                        print(f"    ... and {len(report.gaps) - 10} more gap(s)", file=sys.stderr)
            except Exception as e:
                print(f"  KB validation error: {e}", file=sys.stderr)
            finally:
                if not args.output:
                    ds_for_ingest.unlink(missing_ok=True)
        else:
            print("WARNING: knowledge.db not found. KB validation disabled.", file=sys.stderr)

    # Exit code
    warnings = len(input_diags) + len(output_diags) - len(input_errors) - len(output_errors)
    sys.exit(1 if warnings else 0)


if __name__ == "__main__":
    main()
