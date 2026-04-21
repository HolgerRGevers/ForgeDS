#!/usr/bin/env python3
"""
Export Microsoft Access tables to CSV for Zoho Creator import.

Exports each table from an .accdb file to a separate CSV file with
proper type conversions (BIT -> true/false, DATETIME -> ISO 8601,
CURRENCY -> decimal string). Exports in dependency order.

Platform: Windows only (requires pyodbc + Access ODBC driver)

Usage:
    python -m forgeds.access.export_access_csv exports/ERM.accdb
    python -m forgeds.access.export_access_csv exports/ERM.accdb --output-dir exports/csv/
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

from forgeds._shared.config import load_config, get_db_dir

try:
    import pyodbc
except ImportError:
    print("Error: pyodbc not installed. Run: pip install pyodbc", file=sys.stderr)
    sys.exit(1)


# Export order: lookup tables first, then transactions, then audit.
# Prefer config-driven order; fall back to hardcoded default.
_HARDCODED_EXPORT_ORDER = [
    "Departments",
    "Clients",
    "GL_Accounts",
    "Approval_Thresholds",
    "Expense_Claims",
    "Approval_History",
]

_config = load_config()
_schema = _config.get("schema", {})
_config_order = [pair[0] for pair in _schema.get("upload_order", [])]
EXPORT_ORDER = _config_order if _config_order else _HARDCODED_EXPORT_ORDER


def get_connection_string(db_path: str) -> str:
    """Build ODBC connection string for Access."""
    return (
        r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
        f"DBQ={os.path.abspath(db_path)};"
    )


def convert_value(value: object, col_type: int) -> str:
    """Convert Access value to CSV-safe string for Zoho import."""
    if value is None:
        return ""

    # BIT/Boolean: Access uses -1/0, Zoho uses true/false
    if isinstance(value, bool):
        return "true" if value else "false"

    # DATETIME: export as ISO 8601
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    # CURRENCY/Decimal: plain decimal string without locale formatting
    if isinstance(value, float):
        # Remove trailing zeros but keep at least one decimal place
        formatted = f"{value:.4f}".rstrip("0").rstrip(".")
        return formatted

    return str(value)


def export_table(
    conn: pyodbc.Connection, table_name: str, output_dir: str
) -> int:
    """Export a single table to CSV. Returns row count."""
    cur = conn.cursor()

    # Get column names
    cur.execute(f"SELECT * FROM [{table_name}] WHERE 1=0")
    columns = [desc[0] for desc in cur.description]

    # Fetch all rows
    cur.execute(f"SELECT * FROM [{table_name}]")
    rows = cur.fetchall()

    # Write CSV (UTF-8, no BOM -- Zoho Creator prefers plain UTF-8)
    csv_path = os.path.join(output_dir, f"{table_name}.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for row in rows:
            converted = [convert_value(val, None) for val in row]
            writer.writerow(converted)

    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export Access tables to CSV for Zoho Creator import",
    )
    parser.add_argument(
        "database",
        help="Path to .accdb file",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="Output directory for CSV files (default: exports/csv/ under project root)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.database):
        print(f"Error: Database not found: {args.database}", file=sys.stderr)
        sys.exit(1)

    # Determine output directory
    output_dir = args.output_dir
    if output_dir is None:
        from forgeds._shared.config import find_project_root
        output_dir = str(find_project_root() / "exports" / "csv")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Connect
    conn_str = get_connection_string(args.database)
    try:
        conn = pyodbc.connect(conn_str)
    except pyodbc.Error as e:
        print(f"Error connecting to database: {e}", file=sys.stderr)
        sys.exit(1)

    # Get available tables
    cur = conn.cursor()
    available_tables = {
        row.table_name
        for row in cur.tables(tableType="TABLE")
    }

    # Export in dependency order
    total_rows = 0
    exported = 0
    for table in EXPORT_ORDER:
        if table not in available_tables:
            print(f"  SKIP: {table} (not found in database)")
            continue
        count = export_table(conn, table, output_dir)
        total_rows += count
        exported += 1
        print(f"  {table}: {count} records -> {table}.csv")

    # Export any remaining tables not in EXPORT_ORDER
    extra_tables = available_tables - set(EXPORT_ORDER)
    for table in sorted(extra_tables):
        if table.startswith("MSys"):
            continue  # Skip Access system tables
        count = export_table(conn, table, output_dir)
        total_rows += count
        exported += 1
        print(f"  {table}: {count} records -> {table}.csv (extra)")

    conn.close()

    print(f"\nExported {exported} tables, {total_rows} total records")
    print(f"Output: {os.path.abspath(output_dir)}")


if __name__ == "__main__":
    main()
