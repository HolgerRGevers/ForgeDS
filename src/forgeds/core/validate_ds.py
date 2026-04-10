#!/usr/bin/env python3
"""
Zoho Creator .ds file structural validator.

Recursive descent parser that catches structural placement errors,
reference integrity violations, and Deluge field name mismatches
before Zoho Creator import.

Rules:
    DS101  Element outside its parent block
    DS102  Missing required section (forms, pages, web)
    DS103  Unmatched brace/paren within a block
    DS104  Missing required form attribute (displayname, actions)
    DS105  Missing required field attribute (type)
    DS106  Unknown field type
    DS107  Unexpected section keyword
    DS201  Report references undefined form
    DS202  Workflow/schedule references undefined form
    DS203  Web reports references undefined report
    DS204  Web/device forms references undefined form
    DS301  input.field not in workflow target form
    DS302  form[field] uses field not in that form
    DS303  insert into form [field] uses field not in that form
    DS304  Field reference case mismatch

Usage:
    forgeds-validate-ds app.ds
    forgeds-validate-ds app.ds --errors-only
    forgeds-validate-ds app.ds -q
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field

from forgeds._shared.diagnostics import Diagnostic, Severity


# ============================================================
# Valid .ds field types
# ============================================================

VALID_FIELD_TYPES = {
    "text", "textarea", "picklist", "number", "decimal",
    "date", "datetime", "email", "checkbox", "url", "phone",
    "currency", "percent", "richtext", "upload file", "image",
    "audio", "video", "signature", "autonumber", "list",
    "USD", "percentage",
}

NON_FIELD_KEYWORDS = {
    "Section", "actions", "submit", "reset", "update", "cancel",
    "blueprint", "on", "must",
}

TOP_LEVEL_SECTIONS = {
    "forms", "reports", "pages", "workflow", "web",
    "phone", "tablet", "share_settings", "translation",
}

REQUIRED_SECTIONS = {"forms", "pages", "web"}

SYSTEM_FIELDS = {"ID", "Added_User", "Added_Time", "Modified_User", "Modified_Time"}


# ============================================================
# Layer 1: Line Reader
# ============================================================

class DsReader:
    """Cursor over .ds file lines with peek/advance helpers."""

    def __init__(self, lines: list[str], filename: str) -> None:
        self._lines = lines
        self._pos = 0
        self.filename = filename

    def peek(self) -> str:
        if self._pos >= len(self._lines):
            return ""
        return self._lines[self._pos].strip()

    def peek_raw(self) -> str:
        if self._pos >= len(self._lines):
            return ""
        return self._lines[self._pos]

    def line_no(self) -> int:
        return self._pos + 1

    def advance(self) -> str:
        line = self.peek()
        self._pos += 1
        return line

    def advance_raw(self) -> str:
        line = self.peek_raw()
        self._pos += 1
        return line

    def skip_blank(self) -> None:
        while not self.at_end():
            s = self.peek()
            if s == "" or s.startswith("//"):
                self._pos += 1
            else:
                break

    def at_end(self) -> bool:
        return self._pos >= len(self._lines)


# ============================================================
# Layer 2: Recursive Descent Validator
# ============================================================

@dataclass
class DsSchema:
    form_fields: dict[str, set[str]] = field(default_factory=dict)
    form_names: set[str] = field(default_factory=set)
    report_names: set[str] = field(default_factory=set)
    deluge_blocks: list[tuple[str, str, int, str]] = field(default_factory=list)


def skip_block(reader: DsReader) -> None:
    depth = 0
    while not reader.at_end():
        line = reader.advance()
        depth += line.count("{") - line.count("}")
        if depth <= 0:
            return


def skip_paren_block(reader: DsReader) -> None:
    depth = 0
    while not reader.at_end():
        line = reader.advance()
        depth += line.count("(") - line.count(")")
        if depth <= 0:
            return


def validate_form(reader: DsReader, diags: list[Diagnostic], schema: DsSchema) -> None:
    m = re.match(r"form\s+(\w+)", reader.peek())
    if not m:
        return
    form_name = m.group(1)
    form_line = reader.line_no()
    reader.advance()
    schema.form_names.add(form_name)

    reader.skip_blank()
    if reader.peek() != "{":
        diags.append(Diagnostic(reader.filename, reader.line_no(), "DS103",
                                Severity.ERROR, f"Expected '{{' after 'form {form_name}'"))
        return
    reader.advance()

    fields: set[str] = set()
    has_displayname = False
    has_actions = False
    depth = 1

    while not reader.at_end() and depth > 0:
        reader.skip_blank()
        line = reader.peek()

        if line == "}":
            depth -= 1
            reader.advance()
            if depth == 0:
                break
            continue

        if line.startswith("displayname"):
            has_displayname = True
            reader.advance()
            continue

        if line.startswith("success message"):
            reader.advance()
            continue

        if line == "Section":
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "(":
                skip_paren_block(reader)
            continue

        if line == "actions":
            has_actions = True
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                skip_block(reader)
            continue

        if line.startswith("blueprint"):
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                skip_block(reader)
            continue

        fm = re.match(r"^(must\s+have\s+)?(\w+)$", line)
        if fm:
            field_name = fm.group(2)
            if field_name in NON_FIELD_KEYWORDS:
                reader.advance()
                continue
            field_line = reader.line_no()
            reader.advance()
            reader.skip_blank()

            if reader.peek() == "(":
                fields.add(field_name)
                has_type = False
                field_type = ""
                paren_depth = 0
                while not reader.at_end():
                    attr_line = reader.advance()
                    paren_depth += attr_line.count("(") - attr_line.count(")")
                    tm = re.match(r"type\s*=\s*(.+)", attr_line.strip())
                    if tm:
                        has_type = True
                        field_type = tm.group(1).strip()
                    if paren_depth <= 0:
                        break

                if not has_type:
                    diags.append(Diagnostic(reader.filename, field_line, "DS105",
                                            Severity.ERROR,
                                            f"Field '{field_name}' in form '{form_name}' has no 'type' attribute"))
                if has_type and field_type and field_type not in VALID_FIELD_TYPES:
                    diags.append(Diagnostic(reader.filename, field_line, "DS106",
                                            Severity.ERROR,
                                            f"Field '{field_name}' has unknown type '{field_type}'"))
            continue

        reader.advance()

    if not has_displayname:
        diags.append(Diagnostic(reader.filename, form_line, "DS104",
                                Severity.WARNING, f"Form '{form_name}' missing 'displayname' attribute"))
    if not has_actions:
        diags.append(Diagnostic(reader.filename, form_line, "DS104",
                                Severity.WARNING, f"Form '{form_name}' missing 'actions' block"))

    schema.form_fields[form_name] = fields


def validate_forms(reader: DsReader, diags: list[Diagnostic], schema: DsSchema) -> None:
    reader.advance()
    reader.skip_blank()
    if reader.peek() != "{":
        diags.append(Diagnostic(reader.filename, reader.line_no(), "DS103",
                                Severity.ERROR, "Expected '{' after 'forms'"))
        return
    reader.advance()

    while not reader.at_end():
        reader.skip_blank()
        line = reader.peek()
        if line == "}":
            reader.advance()
            return
        if line.startswith("form "):
            validate_form(reader, diags, schema)
        else:
            reader.advance()


def validate_reports(reader: DsReader, diags: list[Diagnostic], schema: DsSchema) -> None:
    reader.advance()
    reader.skip_blank()
    if reader.peek() != "{":
        diags.append(Diagnostic(reader.filename, reader.line_no(), "DS103",
                                Severity.ERROR, "Expected '{' after 'reports'"))
        return
    reader.advance()

    while not reader.at_end():
        reader.skip_blank()
        line = reader.peek()
        if line == "}":
            reader.advance()
            return

        rm = re.match(r"(list|kanban)\s+(\w+)", line)
        if rm:
            report_name = rm.group(2)
            schema.report_names.add(report_name)
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                depth = 0
                while not reader.at_end():
                    rline = reader.advance()
                    depth += rline.count("{") - rline.count("}")
                    fm = re.search(r"show all rows from\s+(\w+)", rline)
                    if fm:
                        ref_form = fm.group(1)
                        if ref_form not in schema.form_names:
                            diags.append(Diagnostic(reader.filename, reader.line_no() - 1,
                                                    "DS201", Severity.ERROR,
                                                    f"Report '{report_name}' references undefined form '{ref_form}'"))
                    if depth <= 0:
                        break
            continue
        reader.advance()


def validate_workflow(reader: DsReader, diags: list[Diagnostic], schema: DsSchema) -> None:
    reader.advance()
    reader.skip_blank()
    if reader.peek() != "{":
        diags.append(Diagnostic(reader.filename, reader.line_no(), "DS103",
                                Severity.ERROR, "Expected '{' after 'workflow'"))
        return
    reader.advance()

    depth = 1
    while not reader.at_end() and depth > 0:
        reader.skip_blank()
        line = reader.peek()

        if line == "}":
            depth -= 1
            reader.advance()
            if depth == 0:
                return
            continue
        if line == "{":
            depth += 1
            reader.advance()
            continue

        if line == "form":
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                _parse_wf_form_block(reader, diags, schema)
            continue
        if line == "schedule":
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                _parse_wf_schedule_block(reader, diags, schema)
            continue
        if line == "blueprint":
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                skip_block(reader)
            continue

        reader.advance()


def _parse_wf_form_block(reader: DsReader, diags: list[Diagnostic], schema: DsSchema) -> None:
    reader.advance()
    while not reader.at_end():
        reader.skip_blank()
        line = reader.peek()
        if line == "}":
            reader.advance()
            return
        wm = re.match(r'(\w+)\s+as\s+"(.+)"', line)
        if wm:
            wf_name = wm.group(1)
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                _parse_wf_item(reader, diags, schema, wf_name, "workflow")
            continue
        reader.advance()


def _parse_wf_schedule_block(reader: DsReader, diags: list[Diagnostic], schema: DsSchema) -> None:
    reader.advance()
    while not reader.at_end():
        reader.skip_blank()
        line = reader.peek()
        if line == "}":
            reader.advance()
            return
        sm = re.match(r'(\w+)\s+as\s+"(.+)"', line)
        if sm:
            sched_name = sm.group(1)
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                _parse_wf_item(reader, diags, schema, sched_name, "schedule")
            continue
        reader.advance()


def _parse_wf_item(reader: DsReader, diags: list[Diagnostic], schema: DsSchema,
                   item_name: str, item_type: str) -> None:
    reader.advance()
    target_form = ""
    depth = 1

    while not reader.at_end() and depth > 0:
        line = reader.peek()

        fm = re.match(r"form\s*=\s*(\w+)", line)
        if fm:
            target_form = fm.group(1)
            if target_form not in schema.form_names:
                diags.append(Diagnostic(reader.filename, reader.line_no(), "DS202",
                                        Severity.ERROR,
                                        f"{item_type.title()} '{item_name}' references undefined form '{target_form}'"))

        if line in ("custom deluge script", "on load"):
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "(":
                code_start = reader.line_no()
                code_lines = []
                paren_depth = 0
                while not reader.at_end():
                    cl = reader.advance_raw()
                    paren_depth += cl.count("(") - cl.count(")")
                    code_lines.append(cl)
                    if paren_depth <= 0:
                        break
                code_text = "\n".join(code_lines[1:-1]) if len(code_lines) > 2 else ""
                schema.deluge_blocks.append((target_form, code_text, code_start, item_name))
            continue

        depth += line.count("{") - line.count("}")
        reader.advance()


def validate_web(reader: DsReader, diags: list[Diagnostic], schema: DsSchema) -> None:
    reader.advance()
    reader.skip_blank()
    if reader.peek() != "{":
        return
    reader.advance()

    depth = 1
    while not reader.at_end() and depth > 0:
        reader.skip_blank()
        line = reader.peek()

        if line == "}":
            depth -= 1
            reader.advance()
            continue
        if line == "{":
            depth += 1
            reader.advance()
            continue

        fm = re.match(r"form\s+(\w+)", line)
        if fm:
            ref = fm.group(1)
            if ref not in schema.form_names:
                diags.append(Diagnostic(reader.filename, reader.line_no(), "DS204",
                                        Severity.WARNING,
                                        f"Web section references undefined form '{ref}'"))

        rm = re.match(r"report\s+(\w+)", line)
        if rm:
            ref = rm.group(1)
            if ref not in schema.report_names:
                diags.append(Diagnostic(reader.filename, reader.line_no(), "DS203",
                                        Severity.WARNING,
                                        f"Web section references undefined report '{ref}'"))

        reader.advance()


def validate_device(reader: DsReader, diags: list[Diagnostic], schema: DsSchema,
                    device: str) -> None:
    reader.advance()
    reader.skip_blank()
    if reader.peek() != "{":
        return
    reader.advance()

    depth = 1
    while not reader.at_end() and depth > 0:
        line = reader.peek()
        if line == "}":
            depth -= 1
        elif line == "{":
            depth += 1

        fm = re.match(r"form\s+(\w+)", line)
        if fm:
            ref = fm.group(1)
            if ref not in schema.form_names:
                diags.append(Diagnostic(reader.filename, reader.line_no(), "DS204",
                                        Severity.WARNING,
                                        f"{device.title()} section references undefined form '{ref}'"))
        reader.advance()


def validate_pages(reader: DsReader, diags: list[Diagnostic]) -> None:
    reader.advance()
    reader.skip_blank()
    if reader.peek() != "{":
        return
    skip_block(reader)


def validate_application(reader: DsReader, diags: list[Diagnostic], schema: DsSchema) -> None:
    # Skip header comment
    while not reader.at_end():
        line = reader.peek()
        if line.startswith("/*"):
            while not reader.at_end():
                if "*/" in reader.advance():
                    break
            continue
        if line == "":
            reader.advance()
            continue
        break

    # Expect application declaration
    line = reader.peek()
    if not re.match(r'application\s+".*"', line):
        diags.append(Diagnostic(reader.filename, reader.line_no(), "DS107",
                                Severity.ERROR,
                                f"Expected 'application \"Name\"', found: {line[:50]}"))
        return
    reader.advance()

    reader.skip_blank()
    if reader.peek() != "{":
        diags.append(Diagnostic(reader.filename, reader.line_no(), "DS103",
                                Severity.ERROR, "Expected '{' after application declaration"))
        return
    reader.advance()

    # Skip metadata
    while not reader.at_end():
        reader.skip_blank()
        line = reader.peek()
        if line.startswith(("date format", "time zone", "time format")):
            reader.advance()
            continue
        break

    seen_sections: set[str] = set()

    while not reader.at_end():
        reader.skip_blank()
        line = reader.peek()

        if line == "}":
            reader.advance()
            break

        # Orphan detection
        if re.match(r"form\s+\w+", line) and "forms" in seen_sections:
            diags.append(Diagnostic(reader.filename, reader.line_no(), "DS101",
                                    Severity.ERROR,
                                    f"'{line}' found at application level — must be inside 'forms {{ }}' block"))
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                skip_block(reader)
            continue

        if re.match(r"(list|kanban)\s+\w+", line) and "reports" in seen_sections:
            diags.append(Diagnostic(reader.filename, reader.line_no(), "DS101",
                                    Severity.ERROR,
                                    f"'{line}' found at application level — must be inside 'reports {{ }}' block"))
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                skip_block(reader)
            continue

        keyword = line.split()[0] if line.split() else ""

        if keyword == "forms":
            seen_sections.add("forms")
            validate_forms(reader, diags, schema)
        elif keyword == "reports":
            seen_sections.add("reports")
            validate_reports(reader, diags, schema)
        elif keyword == "workflow":
            seen_sections.add("workflow")
            validate_workflow(reader, diags, schema)
        elif keyword == "pages":
            seen_sections.add("pages")
            validate_pages(reader, diags)
        elif keyword == "web":
            seen_sections.add("web")
            validate_web(reader, diags, schema)
        elif keyword in ("phone", "tablet"):
            seen_sections.add(keyword)
            validate_device(reader, diags, schema, keyword)
        elif keyword in ("share_settings", "translation"):
            seen_sections.add(keyword)
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                skip_block(reader)
        else:
            diags.append(Diagnostic(reader.filename, reader.line_no(), "DS107",
                                    Severity.WARNING,
                                    f"Unexpected keyword at application level: '{line[:40]}'"))
            reader.advance()

    for required in REQUIRED_SECTIONS:
        if required not in seen_sections:
            diags.append(Diagnostic(reader.filename, reader.line_no(), "DS102",
                                    Severity.ERROR, f"Missing required section: '{required}'"))


# ============================================================
# Layer 3: Deluge Field Reference Checker
# ============================================================

def check_deluge_refs(diags: list[Diagnostic], schema: DsSchema) -> None:
    for target_form, code, line_offset, script_name in schema.deluge_blocks:
        code_lines = code.splitlines()

        for i, code_line in enumerate(code_lines):
            abs_line = line_offset + i

            for m in re.finditer(r"input\.(\w+)", code_line):
                _check_field_ref(diags, schema, m.group(1), target_form,
                                 abs_line, script_name, "DS301",
                                 f"input.{m.group(1)}")

            for m in re.finditer(r"(\w+)\[(\w+)\s*[=!<>]", code_line):
                form_ref = m.group(1)
                field_ref = m.group(2)
                if form_ref in schema.form_fields:
                    _check_field_ref(diags, schema, field_ref, form_ref,
                                     abs_line, script_name, "DS302",
                                     f"{form_ref}[{field_ref}]")

            insert_m = re.search(r"insert\s+into\s+(\w+)", code_line)
            if insert_m:
                insert_form = insert_m.group(1)
                for j in range(i, min(i + 20, len(code_lines))):
                    il = code_lines[j].strip()
                    if il == "]" or il.endswith("];"):
                        break
                    ifm = re.match(r"(\w+)\s*=\s*", il)
                    if ifm and ifm.group(1) not in ("insert", "into", "row"):
                        _check_field_ref(diags, schema, ifm.group(1), insert_form,
                                         line_offset + j, script_name, "DS303",
                                         f"insert into {insert_form} [{ifm.group(1)}]")


def _check_field_ref(diags: list[Diagnostic], schema: DsSchema,
                     field_name: str, form_name: str, line: int,
                     script_name: str, rule: str, context: str) -> None:
    if field_name in SYSTEM_FIELDS:
        return

    fields = schema.form_fields.get(form_name, set())
    if not fields:
        return

    if field_name in fields:
        return

    lower_map = {f.lower(): f for f in fields}
    if field_name.lower() in lower_map:
        actual = lower_map[field_name.lower()]
        diags.append(Diagnostic("", line, "DS304", Severity.WARNING,
                                f"Case mismatch in {context}: '{field_name}' should be '{actual}' "
                                f"(in script '{script_name}')"))
    else:
        diags.append(Diagnostic("", line, rule, Severity.WARNING,
                                f"{context} references undefined field in form '{form_name}' "
                                f"(in script '{script_name}')"))


# ============================================================
# Public API + CLI
# ============================================================

def validate_ds_file(path: str) -> list[Diagnostic]:
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    reader = DsReader(lines, path)
    diags: list[Diagnostic] = []
    schema = DsSchema()

    validate_application(reader, diags, schema)
    check_deluge_refs(diags, schema)

    return diags


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Zoho Creator .ds file structural validator",
        epilog="Exit codes: 0=clean, 1=warnings, 2=errors",
    )
    parser.add_argument("paths", nargs="+", help=".ds files to validate")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Only show errors and warnings, suppress info")
    parser.add_argument("--errors-only", action="store_true",
                        help="Only show ERROR severity")
    parser.add_argument("--summary", action="store_true",
                        help="Show only summary counts")
    args = parser.parse_args()

    all_diags: list[Diagnostic] = []
    file_count = 0

    for path in args.paths:
        file_count += 1
        diags = validate_ds_file(path)
        for d in diags:
            if not d.file:
                d.file = path
        all_diags.extend(diags)

    if args.errors_only:
        all_diags = [d for d in all_diags if d.severity == Severity.ERROR]
    elif args.quiet:
        all_diags = [d for d in all_diags if d.severity != Severity.INFO]

    severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
    all_diags.sort(key=lambda d: (d.file, d.line, severity_order[d.severity]))

    if not args.summary:
        for diag in all_diags:
            print(diag)

    errors = sum(1 for d in all_diags if d.severity == Severity.ERROR)
    warnings = sum(1 for d in all_diags if d.severity == Severity.WARNING)
    infos = sum(1 for d in all_diags if d.severity == Severity.INFO)

    print(
        f"\n--- Validated {file_count} file(s): "
        f"{errors} error(s), {warnings} warning(s), {infos} info(s) ---"
    )

    sys.exit(2 if errors > 0 else 1 if warnings > 0 else 0)


if __name__ == "__main__":
    main()
