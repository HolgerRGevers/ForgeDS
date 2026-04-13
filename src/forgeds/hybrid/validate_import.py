#!/usr/bin/env python3
"""
Pre-flight data validator for Access-to-Zoho Creator import.

Validates CSV or JSON data against Zoho Creator constraints before upload.
Checks field lengths, type compatibility, required fields, referential
integrity, and picklist values. Uses the shared Diagnostic format.

Platform: Cross-platform (stdlib only)

Usage:
    forgeds-validate-import exports/csv/
    forgeds-validate-import exports/csv/ --check-picklists
    forgeds-validate-import exports/csv/ --check-refs
    forgeds-validate-import exports/csv/ --check-picklists --check-refs
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import sys
from pathlib import Path

from forgeds._shared.config import get_db_dir
from forgeds._shared.diagnostics import Severity, Diagnostic
from forgeds.schema.registry import get_registry


# ============================================================
# Constants
# ============================================================

ACCESS_DB_PATH = get_db_dir() / "access_vba_lang.db"
DELUGE_DB_PATH = get_db_dir() / "deluge_lang.db"

# Zoho Creator field size limits
ZOHO_TEXT_MAX = 255
ZOHO_TEXTAREA_MAX = 50000


# ============================================================
# Helpers
# ============================================================

def _diag(filename: str, line: int, severity: Severity, code: str, message: str) -> Diagnostic:
    """Build a Diagnostic using the shared dataclass layout."""
    return Diagnostic(file=filename, line=line, rule=code, severity=severity, message=message)


# ============================================================
# Database Access
# ============================================================

class ValidatorDB:
    """Cached lookups from both language databases."""

    def __init__(self) -> None:
        self.type_mappings: dict[str, dict] = {}
        self.field_mappings: dict[tuple[str, str], dict] = {}
        self.valid_statuses: set[str] = set()
        self.valid_actions: set[str] = set()
        self.zoho_fields: dict[tuple[str, str], str] = {}  # (form, field) -> type
        self.access_fields: dict[tuple[str, str], str] = {}  # (table, field) -> type
        self.table_to_form: dict[str, str] = {}
        self.fk_relationships: dict[tuple[str, str], tuple[str, str]] = {}

        self._load_access_db()
        self._load_deluge_db()

    def _load_access_db(self) -> None:
        if not ACCESS_DB_PATH.exists():
            return
        conn = sqlite3.connect(str(ACCESS_DB_PATH))
        cur = conn.cursor()

        # Type mappings
        try:
            for row in cur.execute("SELECT access_type, zoho_type, conversion_notes, data_loss_risk FROM type_mappings"):
                self.type_mappings[row[0]] = {
                    "zoho_type": row[1],
                    "notes": row[2],
                    "risk": row[3],
                }
        except sqlite3.OperationalError:
            pass

        # Field name mappings
        try:
            for row in cur.execute("SELECT access_table, access_field, zoho_form, zoho_field FROM field_name_mappings"):
                self.field_mappings[(row[0], row[1])] = {
                    "zoho_form": row[2],
                    "zoho_field": row[3],
                }
        except sqlite3.OperationalError:
            pass

        # Access table fields
        try:
            for row in cur.execute("SELECT table_name, field_name, access_type FROM access_table_fields"):
                self.access_fields[(row[0], row[1])] = row[2]
        except sqlite3.OperationalError:
            pass

        conn.close()

    def _load_deluge_db(self) -> None:
        # Schema data — delegated to SchemaRegistry (single source of truth)
        reg = get_registry()
        self.valid_statuses = set(reg.valid_statuses())
        self.valid_actions = set(reg.valid_actions())
        self.zoho_fields = {
            (name, f.link_name): f.field_type_raw
            for name, schema in reg.all_forms().items()
            for f in schema.fields.values()
        }

        # Table-to-form mapping
        t2f = reg.table_to_form()
        self.table_to_form = t2f if t2f else {
            "Departments": "departments",
            "Clients": "clients",
            "GL_Accounts": "gl_accounts",
            "Approval_Thresholds": "approval_thresholds",
            "Expense_Claims": "expense_claims",
            "Approval_History": "approval_history",
        }

        # FK relationships
        edges = reg.get_relations().all_edges()
        if edges:
            self.fk_relationships = {
                (fk.child_form, fk.child_field): (fk.parent_form, fk.parent_field)
                for fk in edges
            }
        else:
            self.fk_relationships = {
                ("Expense_Claims", "Department_ID"): ("Departments", "ID"),
                ("Expense_Claims", "Client_ID"): ("Clients", "ID"),
                ("Expense_Claims", "GL_Code_ID"): ("GL_Accounts", "ID"),
                ("Approval_History", "Claim_ID"): ("Expense_Claims", "ID"),
            }


# ============================================================
# Validators
# ============================================================

def validate_csv_file(
    filepath: str,
    db: ValidatorDB,
    check_picklists: bool = False,
    check_refs: bool = False,
    parent_data: dict[str, set[str]] | None = None,
) -> list[Diagnostic]:
    """Validate a single CSV file against Zoho constraints."""
    diagnostics: list[Diagnostic] = []
    filename = os.path.basename(filepath)
    table_name = Path(filename).stem  # e.g., "Departments" from "Departments.csv"

    if table_name not in db.table_to_form:
        diagnostics.append(_diag(
            filename, 0, Severity.INFO, "VD001",
            f"Table '{table_name}' not in known tables -- skipping validation",
        ))
        return diagnostics

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            diagnostics.append(_diag(
                filename, 1, Severity.ERROR, "VD002",
                "CSV file has no header row",
            ))
            return diagnostics

        for row_num, row in enumerate(reader, start=2):  # line 1 = header
            for col_name, value in row.items():
                if col_name is None:
                    continue

                # VD010: Check field length for TEXT fields
                access_type = db.access_fields.get((table_name, col_name), "")
                if "TEXT" in access_type and value and len(value) > ZOHO_TEXT_MAX:
                    diagnostics.append(_diag(
                        filename, row_num, Severity.ERROR, "VD010",
                        f"Field '{col_name}' value length {len(value)} exceeds "
                        f"Zoho Text max {ZOHO_TEXT_MAX} chars",
                    ))

                # VD011: Check MEMO field length
                if access_type == "MEMO" and value and len(value) > ZOHO_TEXTAREA_MAX:
                    diagnostics.append(_diag(
                        filename, row_num, Severity.WARNING, "VD011",
                        f"Field '{col_name}' value length {len(value)} exceeds "
                        f"Zoho Textarea max {ZOHO_TEXTAREA_MAX} chars",
                    ))

                # VD012: Check Boolean values
                if access_type == "BIT" and value:
                    if value.lower() not in ("true", "false", "0", "1", "-1", ""):
                        diagnostics.append(_diag(
                            filename, row_num, Severity.ERROR, "VD012",
                            f"Field '{col_name}' has invalid boolean value: '{value}' "
                            f"(expected true/false)",
                        ))
                    elif value in ("-1", "0", "1"):
                        diagnostics.append(_diag(
                            filename, row_num, Severity.WARNING, "VD013",
                            f"Field '{col_name}' uses Access boolean format "
                            f"('{value}') -- convert to true/false for Zoho",
                        ))

                # VD014: Check CURRENCY format
                if access_type == "CURRENCY" and value:
                    cleaned = value.replace(",", "").strip()
                    # Should not have currency symbols
                    if any(c in cleaned for c in "R$"):
                        diagnostics.append(_diag(
                            filename, row_num, Severity.WARNING, "VD014",
                            f"Field '{col_name}' contains currency symbol in "
                            f"'{value}' -- use plain decimal for Zoho",
                        ))
                    else:
                        try:
                            float(cleaned)
                        except ValueError:
                            diagnostics.append(_diag(
                                filename, row_num, Severity.ERROR, "VD015",
                                f"Field '{col_name}' has non-numeric currency "
                                f"value: '{value}'",
                            ))

            # VD020: Check picklist values
            if check_picklists:
                # Status field
                status_val = row.get("Status", "")
                if status_val and db.valid_statuses and status_val not in db.valid_statuses:
                    diagnostics.append(_diag(
                        filename, row_num, Severity.WARNING, "VD020",
                        f"Status value '{status_val}' not in valid set: "
                        f"{sorted(db.valid_statuses)}",
                    ))

                # Action field
                action_val = row.get("Action_Type", "")
                if action_val and db.valid_actions and action_val not in db.valid_actions:
                    diagnostics.append(_diag(
                        filename, row_num, Severity.WARNING, "VD021",
                        f"Action value '{action_val}' not in valid set: "
                        f"{sorted(db.valid_actions)}",
                    ))

            # VD030: Check referential integrity
            if check_refs and parent_data:
                for (child_table, child_field), (parent_table, parent_pk) in db.fk_relationships.items():
                    if table_name != child_table:
                        continue
                    fk_val = row.get(child_field, "")
                    if fk_val and parent_table in parent_data:
                        if fk_val not in parent_data[parent_table]:
                            diagnostics.append(_diag(
                                filename, row_num, Severity.ERROR, "VD030",
                                f"FK '{child_field}' value '{fk_val}' not found "
                                f"in {parent_table}.{parent_pk}",
                            ))

    return diagnostics


def load_parent_pk_values(csv_dir: str, table_to_form: dict[str, str]) -> dict[str, set[str]]:
    """Load primary key values from all parent tables for FK validation."""
    pk_values: dict[str, set[str]] = {}
    for table_name in table_to_form:
        csv_path = os.path.join(csv_dir, f"{table_name}.csv")
        if not os.path.exists(csv_path):
            continue
        ids: set[str] = set()
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                id_val = row.get("ID", "")
                if id_val:
                    ids.add(id_val)
        pk_values[table_name] = ids
    return pk_values


# ============================================================
# Main
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate Access data for Zoho Creator import",
    )
    parser.add_argument(
        "csv_dir",
        help="Directory containing CSV files to validate",
    )
    parser.add_argument(
        "--check-picklists", action="store_true",
        help="Validate picklist values against Zoho valid sets",
    )
    parser.add_argument(
        "--check-refs", action="store_true",
        help="Validate FK referential integrity across tables",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.csv_dir):
        print(f"Error: Not a directory: {args.csv_dir}", file=sys.stderr)
        sys.exit(1)

    # Load databases
    db = ValidatorDB()
    if not ACCESS_DB_PATH.exists():
        print(f"WARNING: {ACCESS_DB_PATH} not found -- run build_access_vba_db first",
              file=sys.stderr)
    if not DELUGE_DB_PATH.exists():
        print(f"WARNING: {DELUGE_DB_PATH} not found -- run build_deluge_db first",
              file=sys.stderr)

    # Load parent PKs for FK validation
    parent_data = None
    if args.check_refs:
        parent_data = load_parent_pk_values(args.csv_dir, db.table_to_form)

    # Validate each CSV file
    all_diagnostics: list[Diagnostic] = []
    csv_files = sorted(Path(args.csv_dir).glob("*.csv"))

    if not csv_files:
        print(f"No CSV files found in {args.csv_dir}")
        sys.exit(0)

    for csv_file in csv_files:
        diagnostics = validate_csv_file(
            str(csv_file), db,
            check_picklists=args.check_picklists,
            check_refs=args.check_refs,
            parent_data=parent_data,
        )
        all_diagnostics.extend(diagnostics)

    # Print results
    errors = sum(1 for d in all_diagnostics if d.severity == Severity.ERROR)
    warnings = sum(1 for d in all_diagnostics if d.severity == Severity.WARNING)
    infos = sum(1 for d in all_diagnostics if d.severity == Severity.INFO)

    for d in all_diagnostics:
        print(d)

    print(f"\nValidated {len(csv_files)} files: "
          f"{errors} errors, {warnings} warnings, {infos} info")

    if errors > 0:
        sys.exit(2)
    elif warnings > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
