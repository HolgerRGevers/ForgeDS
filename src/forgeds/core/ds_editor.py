#!/usr/bin/env python3
"""
Zoho Creator .ds Export Editor.

Programmatic modifications to .ds export files for deployment via import.
Reads configuration from config/ YAML files and applies changes to the .ds.

Subcommands:
    add-descriptions     Add field help text from config/field-descriptions.yaml
    remove-reports       Remove named reports and all their references
    restrict-menus       Strip Edit/Duplicate/Delete from report menus
    rebuild-dashboard    Replace a page's ZML content with native components
    audit                Show current state: descriptions, reports, menu permissions

Usage:
    python -m forgeds.core.ds_editor add-descriptions exports/FILE.ds
    python -m forgeds.core.ds_editor remove-reports exports/FILE.ds --reports name1,name2
    python -m forgeds.core.ds_editor restrict-menus exports/FILE.ds --reports name1,name2
    python -m forgeds.core.ds_editor rebuild-dashboard exports/FILE.ds --page My_Dashboard
    python -m forgeds.core.ds_editor audit exports/FILE.ds
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from forgeds._shared.config import load_config, get_db_dir


# ============================================================
# Simple YAML loader (stdlib only)
# ============================================================

def load_field_descriptions(yaml_path: Path) -> dict[str, dict[str, str]]:
    """Load field-descriptions.yaml into {form: {field: description}}."""
    result: dict[str, dict[str, str]] = {}
    current_form = ""

    with open(yaml_path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Top-level form key (no indent, ends with :)
            if not line.startswith(" ") and stripped.endswith(":"):
                current_form = stripped.rstrip(":")
                result[current_form] = {}
                continue

            # Field entry (indented, key: "value")
            m = re.match(r'^\s+(\w+):\s*"(.+)"\s*$', line)
            if m and current_form:
                result[current_form][m.group(1)] = m.group(2)

    return result


# ============================================================
# Add descriptions
# ============================================================

def add_descriptions(ds_path: Path, descriptions: dict[str, dict[str, str]]) -> int:
    """Add help_text description blocks to fields in a .ds file.

    Returns the number of descriptions added.
    """
    with open(ds_path, encoding="utf-8") as f:
        lines = f.read().split("\n")

    # Flatten descriptions for lookup: {field_name: {form_name: desc}}
    field_to_forms: dict[str, dict[str, str]] = {}
    for form, fields in descriptions.items():
        for field, desc in fields.items():
            if field not in field_to_forms:
                field_to_forms[field] = {}
            field_to_forms[field][form] = desc

    current_form = ""
    added = 0
    i = 0

    while i < len(lines):
        # Track current form
        form_match = re.match(r"^\t{2,3}form\s+(\w+)\s*$", lines[i])
        if form_match:
            current_form = form_match.group(1)

        # Find field definitions: field_name followed by (
        field_match = re.match(r"^\t{3,4}(?:must have\s+)?(\w+)\s*$", lines[i])
        if field_match and i + 1 < len(lines) and lines[i + 1].strip() == "(":
            field_name = field_match.group(1)

            # Skip non-field entries
            if field_name in (
                "Section", "actions", "submit", "reset", "update", "cancel",
                "prefix", "first_name", "last_name", "suffix",
            ):
                i += 1
                continue

            # Check if already has description
            has_desc = False
            j = i + 2
            paren_depth = 1
            while j < len(lines) and paren_depth > 0:
                paren_depth += lines[j].count("(") - lines[j].count(")")
                if "type = help_text" in lines[j]:
                    has_desc = True
                    break
                j += 1

            if has_desc:
                i += 1
                continue

            # Find description text
            desc = None
            if field_name in field_to_forms:
                if current_form in field_to_forms[field_name]:
                    desc = field_to_forms[field_name][current_form]
                elif len(field_to_forms[field_name]) == 1:
                    # Only one form has this field -- use it
                    desc = next(iter(field_to_forms[field_name].values()))

            if desc:
                # Find the row = 1 line to insert before
                j = i + 2
                paren_depth = 1
                insert_at = None
                while j < len(lines) and paren_depth > 0:
                    paren_depth += lines[j].count("(") - lines[j].count(")")
                    if "row = 1" in lines[j] and paren_depth == 1:
                        insert_at = j
                        break
                    j += 1

                if insert_at:
                    indent = "\t\t\t\t"
                    desc_block = [
                        f"{indent}description",
                        f"{indent}[",
                        f"{indent}\ttype = help_text",
                        f'{indent}\tmessage = "{desc}"',
                        f"{indent}]",
                    ]
                    for k, desc_line in enumerate(desc_block):
                        lines.insert(insert_at + k, desc_line)
                    added += 1
                    i = insert_at + len(desc_block)
                    continue

        i += 1

    with open(ds_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return added


# ============================================================
# Remove reports
# ============================================================

def remove_reports(ds_path: Path, report_names: list[str]) -> int:
    """Remove named reports and ALL references from a .ds file.

    Handles the full 5-point dependency chain:
      1. Report definition (kanban/list block in reports section)
      2. Permission entries (ReportPermissions in share_settings)
      3. Quickview/detailview config (web > reports > report block)
      4. Navigation menu entry (web > menu > space > section > report block)
      5. Page Content ZML references (warn only, don't auto-remove)

    Returns the number of report blocks removed.
    """
    with open(ds_path, encoding="utf-8") as f:
        lines = f.readlines()

    removed = 0
    warnings: list[str] = []

    for name in report_names:
        escaped = re.escape(name)

        # --- Pass 1: Remove brace-delimited blocks ---
        # Matches: kanban/list definitions, report config blocks, nav entries
        # Pattern: any line containing the report name followed by a { } block
        new_lines: list[str] = []
        skipping = False
        skip_depth = 0
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.rstrip()

            if not skipping:
                # Match report definition: kanban/list report_name
                # Match quickview/detailview config: report report_name
                # Match navigation entry: report report_name
                is_block_start = bool(re.match(
                    rf"^\s+(?:kanban|list|report)\s+{escaped}\s*$", stripped,
                ))

                if is_block_start:
                    # Start skipping this block
                    skipping = True
                    skip_depth = 0
                    removed += 1
                    i += 1
                    continue

                # Match single-line permission entry: report_name={"View",...}
                if re.match(rf"^\s+{escaped}=\{{.*\}}\s*$", stripped):
                    i += 1
                    continue

                new_lines.append(line)
            else:
                # Track brace depth to find block end
                skip_depth += line.count("{") - line.count("}")
                if skip_depth <= 0:
                    skipping = False
                # Don't append — we're inside a skipped block

            i += 1

        lines = new_lines

        # --- Pass 2: Check ZML content for references (warn only) ---
        for j, line in enumerate(lines):
            if f"linkName = '{name}'" in line or f"linkName='{name}'" in line:
                warnings.append(
                    f"WARNING: Page Content ZML references '{name}' at line {j + 1}. "
                    f"This page needs manual redesign in Creator UI."
                )

    # --- Pass 3: Post-removal validation ---
    content = "".join(lines)

    # Check for orphaned references
    for name in report_names:
        remaining = content.count(name)
        if remaining > 0:
            warnings.append(
                f"WARNING: {remaining} reference(s) to '{name}' still remain after removal. "
                f"Manual cleanup may be needed."
            )

    # Check structural balance
    braces = content.count("{") - content.count("}")
    parens = content.count("(") - content.count(")")
    if braces != 0:
        warnings.append(f"WARNING: Brace imbalance after removal: {braces}")
    if parens != 0:
        warnings.append(f"WARNING: Paren imbalance after removal: {parens}")

    # Print warnings
    for w in warnings:
        print(f"  {w}")

    with open(ds_path, "w", encoding="utf-8") as f:
        f.write(content)

    return removed


# ============================================================
# Restrict menus
# ============================================================

MENU_ITEMS_TO_REMOVE = {"Edit", "Duplicate", "Delete", "Print", "Add", "Import", "Export"}


def restrict_menus(ds_path: Path, report_names: list[str]) -> int:
    """Remove Edit/Duplicate/Delete/etc from report menus.

    Returns the number of reports modified.
    """
    with open(ds_path, encoding="utf-8") as f:
        lines = f.read().split("\n")

    modified = 0
    in_target = False
    current_report = ""
    i = 0
    new_lines: list[str] = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Track report context
        report_match = re.match(r"\t+report\s+(\w+)\s*$", line)
        if report_match:
            current_report = report_match.group(1)
            in_target = current_report in report_names

        if in_target:
            # Remove menu items from header blocks
            if stripped == "header":
                new_lines.append(line)
                i += 1
                if i < len(lines) and lines[i].strip() == "(":
                    new_lines.append(lines[i])
                    depth = 1
                    i += 1
                    while i < len(lines) and depth > 0:
                        s = lines[i].strip()
                        depth += s.count("(") - s.count(")")
                        if depth <= 0:
                            new_lines.append(lines[i])
                            break
                        if s in MENU_ITEMS_TO_REMOVE:
                            i += 1
                            continue
                        new_lines.append(lines[i])
                        i += 1
                    modified += 1
                    i += 1
                    continue

            # Remove entire record block (keyword + parens + content)
            if stripped == "record":
                # Skip "record" line
                i += 1
                if i < len(lines) and lines[i].strip() == "(":
                    # Skip everything until matching )
                    depth = 1
                    i += 1
                    while i < len(lines) and depth > 0:
                        depth += lines[i].strip().count("(") - lines[i].strip().count(")")
                        i += 1
                    continue
                continue

            # Remove entire right-click blocks
            if stripped == "on right click":
                i += 1
                if i < len(lines) and lines[i].strip() == "(":
                    depth = 1
                    i += 1
                    while i < len(lines) and depth > 0:
                        depth += lines[i].strip().count("(") - lines[i].strip().count(")")
                        i += 1
                    continue

        new_lines.append(line)
        i += 1

    with open(ds_path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))

    return modified


# ============================================================
# Rebuild dashboard
# ============================================================

# Registry of dashboard builders keyed by page name.
# Each builder is a callable that returns a ZML string with native components.
# Consumers populate this dict with their own project-specific builders.
DASHBOARD_BUILDERS: dict[str, callable] = {}


def _build_kpi_tile(bg: str, icon_bg: str, icon: str, value: str,
                    label: str, label_color: str, criteria: str = "") -> str:
    """Build a single KPI tile using native panel/text/image components."""
    crit = f"\n\tcriteria = '{criteria}'" if criteria else ""
    return (
        f"<pc\n\tpadding = '20px'\n\tbgColor = '{bg}'\n\twidth = '25%'\n"
        f"\thAlign = 'left'\n\tvAlign = 'middle'\n>\n"
        f"<pr width='auto' height='auto'>\n<pc>\n"
        f"<image\n\tcolor = '#FFFFFF'\n\tbgColor = '{icon_bg}'\n"
        f"\twidth = '48px'\n\theight = '48px'\n\ttype = 'icon'\n"
        f"\tvalue = '{icon}'\n\tsize = '20px'\n\tcornerRadius = '10px'\n"
        f"\ticonType = 'outline'\n/>\n</pc>\n<pc hAlign='left'>\n"
        f"<pr><pc>\n<text\n\tmarginLeft = '16px'\n\tcolor = '#FFFFFF'\n"
        f"\tsize = '22px'\n\tbold = 'true'\n\ttype = 'Form Data'\n"
        f"\tdisplayType = 'actual'\n\tthousandsSeperator = 'LOCALE'\n"
        f"\tdecimalSeperator = 'DOT'\n\tnumberScale = 'none'\n"
        f"\tvalue = '{value}'{crit}\n/>\n</pc></pr>\n<pr><pc>\n"
        f"<text\n\tmarginLeft = '16px'\n\tmarginTop = '3px'\n"
        f"\tcolor = '{label_color}'\n\tsize = '13px'\n\ttype = 'Text'\n"
        f"\tvalue = '{label}'\n/>\n</pc></pr>\n</pc>\n</pr>\n</pc>\n"
    )


def replace_page_content(ds_path: Path, page_name: str, new_zml: str) -> None:
    """Replace the Content attribute of a named page in a .ds file."""
    with open(ds_path, encoding="utf-8") as f:
        content = f.read()

    marker = f"page {page_name}"
    start = content.find(marker)
    if start == -1:
        print(f"ERROR: Page '{page_name}' not found in {ds_path}", file=sys.stderr)
        sys.exit(1)

    attr_start = content.find('Content="', start)
    if attr_start == -1 or attr_start > start + 5000:
        print(f"ERROR: No Content attribute found for page '{page_name}'", file=sys.stderr)
        sys.exit(1)

    value_start = attr_start + len('Content="')
    end_marker = '</zml>"'
    end = content.find(end_marker, value_start)
    if end == -1:
        print(f'ERROR: No closing </zml>" found for page {page_name}', file=sys.stderr)
        sys.exit(1)

    value_end = end + len("</zml>")
    escaped = new_zml.replace("\n", "\\n").replace("\t", "\\t")
    result = content[:value_start] + escaped + content[value_end:]

    with open(ds_path, "w", encoding="utf-8") as f:
        f.write(result)

    old_len = value_end - value_start
    print(f"Replaced {page_name} Content ({old_len} -> {len(escaped)} chars)")


# ============================================================
# Audit
# ============================================================

def audit_ds(ds_path: Path) -> None:
    """Print audit summary of descriptions, reports, and menu permissions."""
    with open(ds_path, encoding="utf-8") as f:
        content = f.read()

    # Count descriptions
    desc_count = content.count("type = help_text")
    print(f"Field descriptions (help_text): {desc_count}")

    # Count fields (approximate)
    field_defs = len(re.findall(r"^\t{3,4}(?:must have\s+)?\w+\s*$", content, re.MULTILINE))
    print(f"Field definitions (approximate): {field_defs}")
    print(f"Description coverage: {desc_count}/{field_defs} ({100*desc_count//max(field_defs,1)}%)")

    # List reports
    print("\nReports:")
    for m in re.finditer(r"^\t+(?:list|kanban)\s+(\w+)\s*$", content, re.MULTILINE):
        report_type = "list" if "list" in m.group(0) else "kanban"
        print(f"  [{report_type}] {m.group(1)}")

    # Check menu permissions per report
    print("\nReport menu audit:")
    for m in re.finditer(r"^\t+report\s+(\w+)\s*$", content, re.MULTILINE):
        name = m.group(1)
        # Find the next ~500 chars to check for Edit/Delete
        start = m.start()
        block = content[start:start + 2000]
        has_edit = "Edit" in block.split("report", 1)[-1][:500] if "report" in block else False
        has_delete = "Delete" in block.split("report", 1)[-1][:500] if "report" in block else False
        status = "FULL" if has_edit else "RESTRICTED"
        print(f"  {name}: {status}")


# ============================================================
# Main
# ============================================================

def main() -> None:
    config = load_config()

    parser = argparse.ArgumentParser(
        description="Zoho Creator .ds export editor",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add-descriptions
    p_desc = sub.add_parser("add-descriptions", help="Add field help text from YAML config")
    p_desc.add_argument("ds_file", help="Path to .ds file")
    p_desc.add_argument(
        "--config",
        default=str(Path(config.get("config_dir", "config")) / "field-descriptions.yaml"),
        help="Path to field-descriptions.yaml",
    )

    # remove-reports
    p_rm = sub.add_parser("remove-reports", help="Remove named reports and references")
    p_rm.add_argument("ds_file", help="Path to .ds file")
    p_rm.add_argument("--reports", required=True, help="Comma-separated report names to remove")

    # restrict-menus
    p_menu = sub.add_parser("restrict-menus", help="Strip Edit/Delete from report menus")
    p_menu.add_argument("ds_file", help="Path to .ds file")
    p_menu.add_argument("--reports", required=True, help="Comma-separated report names to restrict")

    # rebuild-dashboard
    p_dash = sub.add_parser("rebuild-dashboard", help="Replace page ZML with native components")
    p_dash.add_argument("ds_file", help="Path to .ds file")
    p_dash.add_argument("--page", required=True,
                        help=f"Page name to rebuild. Available: {', '.join(DASHBOARD_BUILDERS) or '(none registered)'}")
    p_dash.add_argument("--dry-run", action="store_true", help="Print ZML without modifying file")

    # audit
    p_audit = sub.add_parser("audit", help="Audit descriptions, reports, menus")
    p_audit.add_argument("ds_file", help="Path to .ds file")

    # Global KB flag (applies to add-descriptions and audit)
    parser.add_argument(
        "--kb", action="store_true",
        help="Use KB for missing descriptions and post-edit residual reporting.",
    )

    args = parser.parse_args()
    ds_path = Path(args.ds_file)

    if not ds_path.exists():
        print(f"Error: {ds_path} not found", file=sys.stderr)
        sys.exit(1)

    # KB accessor (optional)
    kb = None
    if getattr(args, "kb", False):
        from forgeds._shared.kb_accessor import get_kb
        kb = get_kb()
        if not kb.available():
            print("WARNING: knowledge.db not found. KB features disabled.", file=sys.stderr)
            kb = None

    if args.command == "add-descriptions":
        config_path = Path(args.config)
        if not config_path.exists() and kb is None:
            print(f"Error: {config_path} not found", file=sys.stderr)
            sys.exit(1)
        descriptions: dict[str, dict[str, str]] = {}
        if config_path.exists():
            descriptions = load_field_descriptions(config_path)

        # KB enrichment: fill missing descriptions from KB documentation
        if kb is not None:
            content = ds_path.read_text(encoding="utf-8")
            # Extract form names from .ds
            form_names = re.findall(r"^\t+form\s+(\w+)\s*$", content, re.MULTILINE)
            kb_added = 0
            for form in form_names:
                if form not in descriptions:
                    descriptions[form] = {}
                # Find fields in this form that lack descriptions
                fields_in_form = re.findall(
                    rf"(?<=form {form}).*?(?=form \w|$)",
                    content, re.DOTALL,
                )
                if fields_in_form:
                    for fm in re.finditer(r"field\s+(\w+)", fields_in_form[0]):
                        field_name = fm.group(1)
                        if field_name not in descriptions.get(form, {}):
                            ctx = kb.query(f"{form} {field_name} field description", max_words=100)
                            if ctx:
                                # Extract first sentence as description
                                first_line = ctx.split("\n")[0].strip("# *").strip()[:200]
                                if first_line:
                                    descriptions.setdefault(form, {})[field_name] = first_line
                                    kb_added += 1
            if kb_added:
                print(f"KB: enriched {kb_added} field description(s) from knowledge base.", file=sys.stderr)

        total_fields = sum(len(f) for f in descriptions.values())
        print(f"Loaded {total_fields} field descriptions")
        added = add_descriptions(ds_path, descriptions)
        print(f"Added {added} descriptions to {ds_path}")

    elif args.command == "remove-reports":
        names = [n.strip() for n in args.reports.split(",")]
        removed = remove_reports(ds_path, names)
        print(f"Removed {removed} report(s) from {ds_path}")

    elif args.command == "restrict-menus":
        names = [n.strip() for n in args.reports.split(",")]
        modified = restrict_menus(ds_path, names)
        print(f"Restricted menus on {modified} block(s) in {ds_path}")

    elif args.command == "rebuild-dashboard":
        page = args.page
        if page not in DASHBOARD_BUILDERS:
            print(f"Error: No builder for page '{page}'. "
                  f"Available: {', '.join(DASHBOARD_BUILDERS) or '(none registered)'}", file=sys.stderr)
            sys.exit(1)
        zml = DASHBOARD_BUILDERS[page]()
        if args.dry_run:
            print(zml)
        else:
            replace_page_content(ds_path, page, zml)

    elif args.command == "audit":
        audit_ds(ds_path)

        # KB: run projection on the audited .ds for residual reporting
        if kb is not None:
            try:
                from forgeds.knowledge.app_ingest import ingest_ds_app
                module = f"app:{ds_path.stem}"
                ingest_ds_app(str(ds_path), str(kb.db_path), module_name=module)
                report = kb.project(module)
                if report:
                    print(f"\nKB Projection: R({ds_path.stem}) = {report.residual:.1f}")
                    print(f"  Gaps: {len(report.gaps)}")
                    for g in sorted(report.gaps, key=lambda x: -x.severity)[:5]:
                        sev = {2.0: "CRIT", 1.5: "HIGH", 1.0: "MED", 0.5: "LOW"}.get(g.severity, "INFO")
                        print(f"    [{sev}] {g.entity}: {g.message[:70]}")
            except Exception as e:
                print(f"  KB audit error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
