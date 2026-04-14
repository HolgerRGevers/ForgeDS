#!/usr/bin/env python3
"""
Cross-environment linter: validates Access-to-Zoho Creator integration.

Checks schema alignment, type mappings, field coverage, and optionally
validates seed data and Deluge script cross-references against both
the Access and Zoho schemas.

Reads from two SQLite databases:
  - deluge_lang.db    (Zoho Creator / Deluge language data)
  - access_vba_lang.db (Access table schemas and type mappings)

Usage:
    forgeds-lint-hybrid                                    # schema only
    forgeds-lint-hybrid --data exports/csv/                # schema + data
    forgeds-lint-hybrid --data exports/csv/ --scripts src/deluge/  # all
    forgeds-lint-hybrid --verbose                          # include INFO

Exit codes:
    0 = clean (no issues)
    1 = warnings only
    2 = errors found
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sqlite3
import sys
from pathlib import Path

from forgeds._shared.config import load_config, get_db_dir
from forgeds._shared.diagnostics import Severity, Diagnostic


# ============================================================
# Constants
# ============================================================

DELUGE_DB_PATH = get_db_dir() / "deluge_lang.db"
ACCESS_DB_PATH = get_db_dir() / "access_vba_lang.db"

_config = load_config()
_schema = _config.get("schema", {})
MANDATORY_ZOHO_FIELDS = [tuple(pair) for pair in _schema.get("mandatory_zoho_fields", [
    ["expense_claims", "POPIA_Consent"],
    ["approval_history", "Added_User"],
    ["approval_history", "claim"],
])]

# System-generated ID fields to skip in mapping checks
SKIP_ID_FIELDS = {"ID", "id"}


# ============================================================
# Helpers
# ============================================================

def _diag(filename: str, line: int, severity: Severity, code: str, message: str) -> Diagnostic:
    """Build a Diagnostic using the shared dataclass layout."""
    return Diagnostic(file=filename, line=line, rule=code, severity=severity, message=message)


# ============================================================
# Database loader
# ============================================================

class HybridDB:
    """Read-only cache of schema data from both SQLite databases."""

    def __init__(
        self,
        deluge_db_path: Path = DELUGE_DB_PATH,
        access_db_path: Path = ACCESS_DB_PATH,
    ) -> None:
        # Access DB data
        self.access_table_fields: dict[tuple[str, str], str] = {}  # (table, field) -> access_type
        self.type_mappings: dict[str, dict[str, str]] = {}  # access_type -> {zoho_type, notes, risk}
        self.field_name_mappings: dict[tuple[str, str], dict[str, str]] = {}  # (access_table, access_field) -> {zoho_form, zoho_field}
        self.access_constraints: list[dict[str, str]] = []  # list of FK constraint dicts

        # Deluge DB data
        self.form_fields: dict[str, set[str]] = {}  # form_name -> {field_link, ...}
        self.form_field_types: dict[tuple[str, str], str] = {}  # (form_name, field_link) -> field_type
        self.valid_statuses: set[str] = set()
        self.valid_actions: set[str] = set()

        self._load_access_db(access_db_path)
        self._load_deluge_db(deluge_db_path)

    def _load_access_db(self, db_path: Path) -> None:
        if not db_path.exists():
            return
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # access_table_fields
        try:
            for row in conn.execute("SELECT table_name, field_name, access_type FROM access_table_fields"):
                self.access_table_fields[(row["table_name"], row["field_name"])] = row["access_type"]
        except sqlite3.OperationalError:
            pass

        # type_mappings
        try:
            for row in conn.execute("SELECT access_type, zoho_type, conversion_notes, data_loss_risk FROM type_mappings"):
                self.type_mappings[row["access_type"]] = {
                    "zoho_type": row["zoho_type"] or "",
                    "notes": row["conversion_notes"] or "",
                    "risk": row["data_loss_risk"] or "",
                }
        except sqlite3.OperationalError:
            pass

        # field_name_mappings
        try:
            for row in conn.execute("SELECT access_table, access_field, zoho_form, zoho_field FROM field_name_mappings"):
                self.field_name_mappings[(row["access_table"], row["access_field"])] = {
                    "zoho_form": row["zoho_form"],
                    "zoho_field": row["zoho_field"],
                }
        except sqlite3.OperationalError:
            pass

        # access_constraints
        try:
            for row in conn.execute(
                "SELECT constraint_name, constraint_type, table_name, field_name, "
                "ref_table, ref_field FROM access_constraints"
            ):
                self.access_constraints.append({
                    "constraint_name": row["constraint_name"],
                    "constraint_type": row["constraint_type"],
                    "table_name": row["table_name"],
                    "field_name": row["field_name"],
                    "ref_table": row["ref_table"] or "",
                    "ref_field": row["ref_field"] or "",
                })
        except sqlite3.OperationalError:
            pass

        conn.close()

    def _load_deluge_db(self, db_path: Path) -> None:
        if not db_path.exists():
            return
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # form_fields
        try:
            for row in conn.execute("SELECT form_name, field_link, field_type FROM form_fields"):
                form = row["form_name"]
                field = row["field_link"]
                ftype = row["field_type"]
                if form not in self.form_fields:
                    self.form_fields[form] = set()
                self.form_fields[form].add(field)
                self.form_field_types[(form, field)] = ftype
        except sqlite3.OperationalError:
            pass

        # valid_statuses
        try:
            for row in conn.execute("SELECT value FROM valid_statuses"):
                self.valid_statuses.add(row["value"])
        except sqlite3.OperationalError:
            pass

        # valid_actions
        try:
            for row in conn.execute("SELECT value FROM valid_actions"):
                self.valid_actions.add(row["value"])
        except sqlite3.OperationalError:
            pass

        conn.close()

    def get_access_tables(self) -> set[str]:
        """Return set of distinct Access table names."""
        return {table for table, _ in self.access_table_fields}

    def get_access_fields_for_table(self, table: str) -> dict[str, str]:
        """Return {field_name: access_type} for a given Access table."""
        result: dict[str, str] = {}
        for (t, f), atype in self.access_table_fields.items():
            if t == table:
                result[f] = atype
        return result

    def get_zoho_forms(self) -> set[str]:
        """Return set of distinct Zoho form names."""
        return set(self.form_fields.keys())

    def get_mapped_access_tables(self) -> set[str]:
        """Return Access tables that have at least one field_name_mapping."""
        return {table for table, _ in self.field_name_mappings}

    def get_mapped_zoho_forms(self) -> set[str]:
        """Return Zoho forms that have at least one field_name_mapping target."""
        return {m["zoho_form"] for m in self.field_name_mappings.values()}

    def get_fk_constraints(self) -> list[dict[str, str]]:
        """Return FK constraints only."""
        return [c for c in self.access_constraints if c["constraint_type"] == "fk"]


# ============================================================
# Schema Rules (always run)
# ============================================================

def check_hy001(db: HybridDB) -> list[Diagnostic]:
    """HY001 (ERROR): Access field type has no valid Zoho equivalent."""
    diags: list[Diagnostic] = []
    seen_types: set[str] = set()
    for (table, field), access_type in sorted(db.access_table_fields.items()):
        # Normalise: strip length specifiers for lookup (e.g. TEXT(100) -> TEXT)
        base_type = re.sub(r"\(.*\)", "", access_type).strip().upper()
        if base_type in seen_types:
            continue
        mapping = db.type_mappings.get(base_type) or db.type_mappings.get(access_type)
        if mapping is None or not mapping.get("zoho_type"):
            diags.append(_diag(
                "schema", 0, Severity.ERROR, "HY001",
                f"Access type '{access_type}' (used by {table}.{field}) "
                f"has no valid Zoho equivalent in type_mappings.",
            ))
            seen_types.add(base_type)
        else:
            seen_types.add(base_type)
    return diags


def check_hy002(db: HybridDB) -> list[Diagnostic]:
    """HY002 (WARNING): CURRENCY -> Decimal precision verification."""
    diags: list[Diagnostic] = []
    for (table, field), access_type in sorted(db.access_table_fields.items()):
        if access_type.upper() == "CURRENCY":
            diags.append(_diag(
                "schema", 0, Severity.WARNING, "HY002",
                f"{table}.{field} is CURRENCY. Verify Zoho Decimal "
                f"field precision matches Access 4-decimal-place default.",
            ))
    return diags


def check_hy003(db: HybridDB) -> list[Diagnostic]:
    """HY003 (WARNING): MEMO -> Textarea max length."""
    diags: list[Diagnostic] = []
    for (table, field), access_type in sorted(db.access_table_fields.items()):
        if access_type.upper() == "MEMO":
            diags.append(_diag(
                "schema", 0, Severity.WARNING, "HY003",
                f"{table}.{field} is MEMO. Zoho Textarea limit is "
                f"50,000 characters -- verify data fits.",
            ))
    return diags


def check_hy004(db: HybridDB) -> list[Diagnostic]:
    """HY004 (ERROR): Access field has no corresponding Zoho form field."""
    diags: list[Diagnostic] = []
    for (table, field), access_type in sorted(db.access_table_fields.items()):
        if field in SKIP_ID_FIELDS:
            continue
        mapping = db.field_name_mappings.get((table, field))
        if mapping is None:
            diags.append(_diag(
                "schema", 0, Severity.ERROR, "HY004",
                f"Access field {table}.{field} has no entry in "
                f"field_name_mappings -- no Zoho target defined.",
            ))
            continue
        zoho_form = mapping["zoho_form"]
        zoho_field = mapping["zoho_field"]
        form_fields = db.form_fields.get(zoho_form, set())
        if zoho_field not in form_fields:
            diags.append(_diag(
                "schema", 0, Severity.ERROR, "HY004",
                f"Access field {table}.{field} maps to "
                f"{zoho_form}.{zoho_field} but that Zoho field "
                f"does not exist in form_fields.",
            ))
    return diags


def check_hy005(db: HybridDB) -> list[Diagnostic]:
    """HY005 (WARNING): Field name case/format mismatch."""
    diags: list[Diagnostic] = []
    for (table, field), mapping in sorted(db.field_name_mappings.items()):
        zoho_field = mapping["zoho_field"]
        # Normalise both to lowercase with underscores stripped for comparison
        access_norm = field.lower().replace("_", "")
        zoho_norm = zoho_field.lower().replace("_", "")
        if access_norm != zoho_norm:
            diags.append(_diag(
                "schema", 0, Severity.WARNING, "HY005",
                f"Name mismatch: Access {table}.{field} -> "
                f"Zoho {mapping['zoho_form']}.{zoho_field}. "
                f"Verify mapping is intentional.",
            ))
    return diags


def check_hy006(db: HybridDB) -> list[Diagnostic]:
    """HY006 (ERROR): Access FK has no corresponding Zoho lookup field."""
    diags: list[Diagnostic] = []
    fk_constraints = db.get_fk_constraints()
    for fk in fk_constraints:
        child_table = fk["table_name"]
        child_field = fk["field_name"]
        mapping = db.field_name_mappings.get((child_table, child_field))
        if mapping is None:
            diags.append(_diag(
                "schema", 0, Severity.ERROR, "HY006",
                f"Access FK {child_table}.{child_field} -> "
                f"{fk['ref_table']}.{fk['ref_field']} has no "
                f"field_name_mapping -- Zoho lookup field missing.",
            ))
            continue
        zoho_form = mapping["zoho_form"]
        zoho_field = mapping["zoho_field"]
        field_type = db.form_field_types.get((zoho_form, zoho_field), "")
        if field_type and field_type != "list":
            diags.append(_diag(
                "schema", 0, Severity.ERROR, "HY006",
                f"Access FK {child_table}.{child_field} maps to "
                f"{zoho_form}.{zoho_field} (type: {field_type}) "
                f"but expected a lookup (list) field.",
            ))
    return diags


def check_hy007(db: HybridDB) -> list[Diagnostic]:
    """HY007 (WARNING): Text truncation risk for TEXT(n) where n > 255."""
    diags: list[Diagnostic] = []
    for (table, field), access_type in sorted(db.access_table_fields.items()):
        match = re.match(r"TEXT\((\d+)\)", access_type, re.IGNORECASE)
        if match:
            length = int(match.group(1))
            if length > 255:
                diags.append(_diag(
                    "schema", 0, Severity.WARNING, "HY007",
                    f"{table}.{field} is TEXT({length}). "
                    f"Zoho single-line Text max is 255 chars -- "
                    f"data may be truncated on import.",
                ))
    return diags


def check_hy008(db: HybridDB) -> list[Diagnostic]:
    """HY008 (ERROR): Zoho mandatory field has no Access source."""
    diags: list[Diagnostic] = []
    # Build reverse mapping: (zoho_form, zoho_field) -> (access_table, access_field)
    reverse_map: dict[tuple[str, str], tuple[str, str]] = {}
    for (a_table, a_field), mapping in db.field_name_mappings.items():
        reverse_map[(mapping["zoho_form"], mapping["zoho_field"])] = (a_table, a_field)

    for zoho_form, zoho_field in MANDATORY_ZOHO_FIELDS:
        if (zoho_form, zoho_field) not in reverse_map:
            diags.append(_diag(
                "schema", 0, Severity.ERROR, "HY008",
                f"Zoho mandatory field {zoho_form}.{zoho_field} "
                f"has no Access source in field_name_mappings.",
            ))
    return diags


def check_hy009(db: HybridDB) -> list[Diagnostic]:
    """HY009 (INFO): Orphan Access table (no Zoho form mapping)."""
    diags: list[Diagnostic] = []
    mapped_tables = db.get_mapped_access_tables()
    for table in sorted(db.get_access_tables()):
        if table not in mapped_tables:
            diags.append(_diag(
                "schema", 0, Severity.INFO, "HY009",
                f"Access table '{table}' has no field_name_mappings "
                f"entries -- no Zoho form target.",
            ))
    return diags


def check_hy010(db: HybridDB) -> list[Diagnostic]:
    """HY010 (INFO): Zoho-only form (no Access table mapped)."""
    diags: list[Diagnostic] = []
    mapped_forms = db.get_mapped_zoho_forms()
    for form in sorted(db.get_zoho_forms()):
        if form not in mapped_forms:
            diags.append(_diag(
                "schema", 0, Severity.INFO, "HY010",
                f"Zoho form '{form}' has no Access table mapped to it.",
            ))
    return diags


def check_hy013(db: HybridDB) -> list[Diagnostic]:
    """HY013 (WARNING): BIT/Boolean transformation needed."""
    diags: list[Diagnostic] = []
    for (table, field), access_type in sorted(db.access_table_fields.items()):
        if access_type.upper() == "BIT":
            diags.append(_diag(
                "schema", 0, Severity.WARNING, "HY013",
                f"{table}.{field} is BIT. Access uses -1/0 "
                f"but Zoho requires true/false -- transform on import.",
            ))
    return diags


def run_schema_rules(db: HybridDB) -> list[Diagnostic]:
    """Run all schema validation rules."""
    diags: list[Diagnostic] = []
    diags.extend(check_hy001(db))
    diags.extend(check_hy002(db))
    diags.extend(check_hy003(db))
    diags.extend(check_hy004(db))
    diags.extend(check_hy005(db))
    diags.extend(check_hy006(db))
    diags.extend(check_hy007(db))
    diags.extend(check_hy008(db))
    diags.extend(check_hy009(db))
    diags.extend(check_hy010(db))
    diags.extend(check_hy013(db))
    return diags


# ============================================================
# Data Rules (when --data is specified)
# ============================================================

def check_hy011(
    db: HybridDB,
    csv_dir: str,
) -> list[Diagnostic]:
    """HY011 (WARNING): Seed data values not in picklist."""
    diags: list[Diagnostic] = []
    csv_path = Path(csv_dir)
    if not csv_path.is_dir():
        return diags

    for csv_file in sorted(csv_path.glob("*.csv")):
        filename = csv_file.name
        try:
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    continue
                for row_num, row in enumerate(reader, start=2):
                    # Check Status column
                    status_val = row.get("Status", "")
                    if status_val and db.valid_statuses and status_val not in db.valid_statuses:
                        diags.append(_diag(
                            filename, row_num, Severity.WARNING, "HY011",
                            f"Status value \"{status_val}\" not in valid set: "
                            f"{sorted(db.valid_statuses)}",
                        ))
                    # Check Action_Type column
                    action_val = row.get("Action_Type", "")
                    if action_val and db.valid_actions and action_val not in db.valid_actions:
                        diags.append(_diag(
                            filename, row_num, Severity.WARNING, "HY011",
                            f"Action_Type value \"{action_val}\" not in valid set: "
                            f"{sorted(db.valid_actions)}",
                        ))
        except (OSError, UnicodeDecodeError):
            diags.append(_diag(
                filename, 0, Severity.ERROR, "HY000",
                f"Cannot read CSV file: {csv_file}",
            ))
    return diags


def check_hy016(
    db: HybridDB,
    csv_dir: str,
) -> list[Diagnostic]:
    """HY016 (WARNING): CSV value not in valid set (general picklist check)."""
    diags: list[Diagnostic] = []
    csv_path = Path(csv_dir)
    if not csv_path.is_dir():
        return diags

    # Build a map of Zoho picklist field names to their valid values
    picklist_fields: dict[str, set[str]] = {}
    if db.valid_statuses:
        picklist_fields["Status"] = db.valid_statuses
    if db.valid_actions:
        picklist_fields["Action_Type"] = db.valid_actions

    for csv_file in sorted(csv_path.glob("*.csv")):
        filename = csv_file.name
        try:
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    continue
                for row_num, row in enumerate(reader, start=2):
                    for col_name, valid_set in picklist_fields.items():
                        val = row.get(col_name, "")
                        # Skip if already covered by HY011 (Status and Action_Type)
                        if col_name in ("Status", "Action_Type"):
                            continue
                        if val and val not in valid_set:
                            diags.append(_diag(
                                filename, row_num, Severity.WARNING, "HY016",
                                f"Column '{col_name}' value \"{val}\" not in "
                                f"valid set: {sorted(valid_set)}",
                            ))
        except (OSError, UnicodeDecodeError):
            pass  # Already reported by HY011
    return diags


def run_data_rules(db: HybridDB, csv_dir: str) -> list[Diagnostic]:
    """Run all data validation rules."""
    diags: list[Diagnostic] = []
    diags.extend(check_hy011(db, csv_dir))
    diags.extend(check_hy016(db, csv_dir))
    return diags


# ============================================================
# Script Rules (when --scripts is specified)
# ============================================================

INPUT_FIELD_PATTERN = re.compile(r"\binput\.(\w+)")


def _collect_dg_files(scripts_dir: str) -> list[str]:
    """Collect all .dg files from a directory tree."""
    files: list[str] = []
    for root, _dirs, filenames in os.walk(scripts_dir):
        for fn in sorted(filenames):
            if fn.endswith(".dg"):
                files.append(os.path.join(root, fn))
    return files


def _extract_input_fields(filepath: str) -> set[str]:
    """Extract all input.FIELDNAME references from a .dg file."""
    fields: set[str] = set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("//") or stripped.startswith("/*"):
                    continue
                for match in INPUT_FIELD_PATTERN.finditer(line):
                    fields.add(match.group(1))
    except (OSError, UnicodeDecodeError):
        pass
    return fields


def check_hy014(db: HybridDB, scripts_dir: str) -> list[Diagnostic]:
    """HY014 (WARNING): Deluge script references input.Field with no Access source."""
    diags: list[Diagnostic] = []
    dg_files = _collect_dg_files(scripts_dir)

    # Build reverse mapping: zoho_field -> set of Access sources
    zoho_to_access: dict[str, list[str]] = {}
    for (a_table, a_field), mapping in db.field_name_mappings.items():
        zf = mapping["zoho_field"]
        if zf not in zoho_to_access:
            zoho_to_access[zf] = []
        zoho_to_access[zf].append(f"{a_table}.{a_field}")

    for filepath in dg_files:
        filename = os.path.basename(filepath)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except (OSError, UnicodeDecodeError):
            continue

        for lineno_idx, raw_line in enumerate(lines):
            lineno = lineno_idx + 1
            stripped = raw_line.strip()
            if stripped.startswith("//") or stripped.startswith("/*"):
                continue
            for match in INPUT_FIELD_PATTERN.finditer(raw_line):
                field_name = match.group(1)
                # Check if this field exists in any Zoho form
                in_zoho = False
                for form, fields in db.form_fields.items():
                    if field_name in fields:
                        in_zoho = True
                        break
                if not in_zoho:
                    continue  # Not a known Zoho field -- DG004 handles this
                # Check if it has an Access source
                if field_name not in zoho_to_access:
                    diags.append(_diag(
                        filename, lineno, Severity.WARNING, "HY014",
                        f"input.{field_name} has no Access source "
                        f"in field_name_mappings -- Zoho-only computed field.",
                    ))
    return diags


def check_hy015(db: HybridDB, scripts_dir: str) -> list[Diagnostic]:
    """HY015 (INFO): Access field never referenced in any Deluge script."""
    diags: list[Diagnostic] = []
    dg_files = _collect_dg_files(scripts_dir)

    # Collect all input.FIELD references across all scripts
    all_referenced_fields: set[str] = set()
    for filepath in dg_files:
        all_referenced_fields.update(_extract_input_fields(filepath))

    # For each Access field, check if its mapped Zoho field is referenced
    for (a_table, a_field), mapping in sorted(db.field_name_mappings.items()):
        zoho_field = mapping["zoho_field"]
        if zoho_field not in all_referenced_fields:
            diags.append(_diag(
                "scripts", 0, Severity.INFO, "HY015",
                f"Access field {a_table}.{a_field} (-> {mapping['zoho_form']}"
                f".{zoho_field}) is never referenced via input.{zoho_field} "
                f"in any Deluge script.",
            ))
    return diags


def run_script_rules(db: HybridDB, scripts_dir: str) -> list[Diagnostic]:
    """Run all script cross-reference rules."""
    diags: list[Diagnostic] = []
    diags.extend(check_hy014(db, scripts_dir))
    diags.extend(check_hy015(db, scripts_dir))
    return diags


# ============================================================
# Main pipeline
# ============================================================

def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Cross-environment linter: Access-to-Zoho Creator integration",
        epilog="Exit codes: 0=clean, 1=warnings, 2=errors",
    )
    parser.add_argument(
        "--data",
        metavar="CSV_DIR",
        help="Directory of CSV exports to validate (enables data rules)",
    )
    parser.add_argument(
        "--scripts",
        metavar="DELUGE_DIR",
        help="Directory of .dg scripts to cross-reference (enables script rules)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show INFO-level diagnostics (default: only ERROR and WARNING)",
    )
    args = parser.parse_args()

    # Validate paths
    if args.data and not os.path.isdir(args.data):
        print(f"Error: Not a directory: {args.data}", file=sys.stderr)
        sys.exit(1)
    if args.scripts and not os.path.isdir(args.scripts):
        print(f"Error: Not a directory: {args.scripts}", file=sys.stderr)
        sys.exit(1)

    # Check DB availability
    missing_dbs: list[str] = []
    if not DELUGE_DB_PATH.exists():
        missing_dbs.append(f"  {DELUGE_DB_PATH} -- run: forgeds-build-deluge-db")
    if not ACCESS_DB_PATH.exists():
        missing_dbs.append(f"  {ACCESS_DB_PATH} -- rebuild required")
    if missing_dbs:
        print("WARNING: Missing database(s):", file=sys.stderr)
        for msg in missing_dbs:
            print(msg, file=sys.stderr)
        print("Continuing with available data...\n", file=sys.stderr)

    # Load databases
    db = HybridDB()

    # Run rules
    schema_diags = run_schema_rules(db)
    data_diags: list[Diagnostic] = []
    script_diags: list[Diagnostic] = []

    if args.data:
        data_diags = run_data_rules(db, args.data)

    if args.scripts:
        script_diags = run_script_rules(db, args.scripts)

    all_diags = schema_diags + data_diags + script_diags

    # Filter by verbosity
    if not args.verbose:
        all_diags = [d for d in all_diags if d.severity != Severity.INFO]

    # Sort: severity (ERROR first), then filename, then line
    severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
    all_diags.sort(key=lambda d: (severity_order[d.severity], d.file, d.line))

    # Print diagnostics
    for diag in all_diags:
        print(diag)

    # Summary
    schema_count = len(schema_diags)
    data_count = len(data_diags)
    script_count = len(script_diags)

    errors = sum(1 for d in all_diags if d.severity == Severity.ERROR)
    warnings = sum(1 for d in all_diags if d.severity == Severity.WARNING)
    infos = sum(1 for d in all_diags if d.severity == Severity.INFO)

    print(
        f"\n--- Hybrid lint: "
        f"{schema_count} schema checks, "
        f"{data_count} data checks, "
        f"{script_count} script checks ---"
    )
    print(
        f"--- Results: "
        f"{errors} error(s), {warnings} warning(s), {infos} info(s) ---"
    )

    sys.exit(2 if errors > 0 else 1 if warnings > 0 else 0)


if __name__ == "__main__":
    main()
