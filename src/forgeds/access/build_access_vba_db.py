#!/usr/bin/env python3
"""
Build the Access/VBA language SQLite database.

Populates access_vba_lang.db with Access SQL and VBA syntax data
for use by lint_access.py, lint_hybrid.py, and validate_import_data.py.

Usage:
    python -m forgeds.access.build_access_vba_db          # creates access_vba_lang.db
    python -m forgeds.access.build_access_vba_db --force   # recreate from scratch
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from forgeds._shared.config import load_config, get_db_dir, find_project_root

DB_PATH = str(get_db_dir() / "access_vba_lang.db")

_config = load_config()
SEED_DIR = Path(find_project_root()) / _config.get("seed_data_dir", "config/seed-data")


def create_schema(cur: sqlite3.Cursor) -> None:
    """Create all tables."""
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS access_data_types (
            name            TEXT PRIMARY KEY,
            jet_sql_name    TEXT NOT NULL,
            vba_type        TEXT,
            zoho_equivalent TEXT,
            size_limit      TEXT,
            notes           TEXT
        );

        CREATE TABLE IF NOT EXISTS access_reserved_words (
            word TEXT PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS access_operators (
            symbol          TEXT NOT NULL,
            name            TEXT NOT NULL,
            category        TEXT NOT NULL,
            access_context  TEXT,
            notes           TEXT,
            PRIMARY KEY (symbol, category)
        );

        CREATE TABLE IF NOT EXISTS vba_functions (
            name            TEXT NOT NULL,
            category        TEXT NOT NULL,
            subcategory     TEXT,
            returns_type    TEXT,
            description     TEXT,
            PRIMARY KEY (name, category)
        );

        CREATE TABLE IF NOT EXISTS access_sql_functions (
            name            TEXT NOT NULL,
            category        TEXT NOT NULL,
            syntax          TEXT,
            description     TEXT,
            PRIMARY KEY (name, category)
        );

        CREATE TABLE IF NOT EXISTS vba_keywords (
            keyword         TEXT PRIMARY KEY,
            category        TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS access_table_fields (
            table_name      TEXT NOT NULL,
            field_name      TEXT NOT NULL,
            access_type     TEXT NOT NULL,
            zoho_form       TEXT,
            zoho_field      TEXT,
            notes           TEXT,
            PRIMARY KEY (table_name, field_name)
        );

        CREATE TABLE IF NOT EXISTS type_mappings (
            access_type     TEXT NOT NULL,
            zoho_type       TEXT NOT NULL,
            conversion_notes TEXT,
            data_loss_risk  TEXT,
            PRIMARY KEY (access_type, zoho_type)
        );

        CREATE TABLE IF NOT EXISTS field_name_mappings (
            access_table    TEXT NOT NULL,
            access_field    TEXT NOT NULL,
            zoho_form       TEXT NOT NULL,
            zoho_field      TEXT NOT NULL,
            transform_notes TEXT,
            PRIMARY KEY (access_table, access_field)
        );

        CREATE TABLE IF NOT EXISTS banned_patterns_access (
            pattern         TEXT PRIMARY KEY,
            pattern_type    TEXT NOT NULL,
            message         TEXT NOT NULL,
            severity        TEXT NOT NULL DEFAULT 'ERROR'
        );

        CREATE TABLE IF NOT EXISTS vba_error_patterns (
            pattern         TEXT PRIMARY KEY,
            category        TEXT NOT NULL,
            cause           TEXT NOT NULL,
            fix             TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS access_constraints (
            table_name      TEXT NOT NULL,
            constraint_type TEXT NOT NULL,
            field_name      TEXT NOT NULL,
            reference_table TEXT,
            reference_field TEXT,
            notes           TEXT,
            PRIMARY KEY (table_name, field_name, constraint_type)
        );
    """)


def populate_access_data_types(cur: sqlite3.Cursor) -> None:
    cur.executemany("INSERT OR REPLACE INTO access_data_types VALUES (?, ?, ?, ?, ?, ?)", [
        ("AUTOINCREMENT", "AUTOINCREMENT", "Long", "Autonumber", "4 bytes", "Auto-incrementing PK"),
        ("TEXT", "TEXT(n)", "String", "Text", "up to 255 chars", "Default n=255"),
        ("MEMO", "MEMO", "String", "Textarea", "~1GB", "Multi-line text, no size limit in Access"),
        ("LONG", "LONG", "Long", "Number", "4 bytes (-2B to 2B)", "32-bit signed integer"),
        ("INTEGER", "INTEGER", "Integer", "Number", "2 bytes (-32768 to 32767)", "16-bit signed"),
        ("SINGLE", "SINGLE", "Single", "Decimal", "4 bytes", "Single-precision float"),
        ("DOUBLE", "DOUBLE", "Double", "Decimal", "8 bytes", "Double-precision float"),
        ("CURRENCY", "CURRENCY", "Currency", "Currency", "8 bytes, 4 decimal places", "Fixed-point, no rounding errors"),
        ("BIT", "BIT", "Boolean", "Checkbox", "1 bit", "Access: -1=True/0=False, Zoho: true/false"),
        ("DATETIME", "DATETIME", "Date", "DateTime", "8 bytes", "Jan 1 100 to Dec 31 9999"),
        ("BYTE", "BYTE", "Byte", "Number", "1 byte (0-255)", None),
        ("GUID", "GUID", "String", "Text", "16 bytes", "Replication ID"),
        ("BINARY", "BINARY(n)", "Byte()", None, "up to 510 bytes", "No Zoho equivalent"),
        ("IMAGE", "IMAGE", "Byte()", "File", "~1GB", "OLE Object / attachment"),
    ])


def populate_access_reserved_words(cur: sqlite3.Cursor) -> None:
    words = [
        "SELECT", "FROM", "WHERE", "INSERT", "INTO", "UPDATE", "DELETE",
        "CREATE", "DROP", "ALTER", "TABLE", "INDEX", "VIEW", "CONSTRAINT",
        "PRIMARY", "KEY", "FOREIGN", "REFERENCES", "NOT", "NULL", "DEFAULT",
        "UNIQUE", "CHECK", "AND", "OR", "IN", "BETWEEN", "LIKE", "IS",
        "EXISTS", "ALL", "ANY", "SOME", "AS", "ON", "JOIN", "INNER", "LEFT",
        "RIGHT", "OUTER", "CROSS", "UNION", "INTERSECT", "EXCEPT", "ORDER",
        "BY", "ASC", "DESC", "GROUP", "HAVING", "DISTINCT", "TOP", "SET",
        "VALUES", "ADD", "COLUMN", "CASCADE", "RESTRICT", "GRANT", "REVOKE",
        "BEGIN", "COMMIT", "ROLLBACK", "TRANSACTION", "PROCEDURE", "FUNCTION",
        "EXEC", "EXECUTE", "DECLARE", "CASE", "WHEN", "THEN", "ELSE", "END",
        "IF", "WHILE", "FOR", "RETURN", "TRUE", "FALSE", "COUNT", "SUM",
        "AVG", "MIN", "MAX",
    ]
    for w in words:
        cur.execute("INSERT OR REPLACE INTO access_reserved_words VALUES (?)", (w,))


def populate_access_operators(cur: sqlite3.Cursor) -> None:
    rows = [
        ("+", "Addition", "arithmetic", "both", "Also string concatenation in VBA"),
        ("-", "Subtraction", "arithmetic", "both", None),
        ("*", "Multiplication", "arithmetic", "both", None),
        ("/", "Division", "arithmetic", "both", "Returns Double"),
        ("\\", "Integer Division", "arithmetic", "both", "Returns truncated integer"),
        ("Mod", "Modulus", "arithmetic", "both", None),
        ("^", "Exponentiation", "arithmetic", "both", None),
        ("=", "Equals", "comparison", "sql", "Note: = not == in Access SQL"),
        ("<>", "Not Equals", "comparison", "sql", "Not != like other languages"),
        ("<", "Less Than", "comparison", "both", None),
        (">", "Greater Than", "comparison", "both", None),
        ("<=", "Less or Equal", "comparison", "both", None),
        (">=", "Greater or Equal", "comparison", "both", None),
        ("AND", "Logical AND", "logical", "both", None),
        ("OR", "Logical OR", "logical", "both", None),
        ("NOT", "Logical NOT", "logical", "both", None),
        ("&", "String Concatenation", "string", "both", "Preferred over + for strings"),
        ("Like", "Pattern Match", "string", "both", "Uses * and ? wildcards in Access"),
        ("=", "Assignment", "assignment", "vba", "Same symbol as comparison"),
        ("Eqv", "Equivalence", "bitwise", "vba", None),
        ("Imp", "Implication", "bitwise", "vba", None),
        ("Xor", "Exclusive Or", "bitwise", "vba", None),
    ]
    cur.executemany("INSERT OR REPLACE INTO access_operators VALUES (?, ?, ?, ?, ?)", rows)


def populate_vba_functions(cur: sqlite3.Cursor) -> None:
    """Populate VBA built-in functions by category."""
    funcs = []

    # Text functions
    for fn in ["Left", "Right", "Mid", "Len", "LenB", "Trim", "LTrim", "RTrim",
               "UCase", "LCase", "StrConv", "Space", "String", "Replace",
               "InStr", "InStrRev", "StrComp", "StrReverse", "Format"]:
        funcs.append((fn, "text", "manipulation", "String", None))
    for fn in ["Chr", "ChrW", "Asc", "AscW"]:
        funcs.append((fn, "text", "character", "String/Integer", None))
    for fn in ["Split", "Join"]:
        funcs.append((fn, "text", "array", "Array/String", None))
    for fn in ["Hex", "Oct"]:
        funcs.append((fn, "text", "encoding", "String", None))

    # Math functions
    for fn in ["Abs", "Int", "Fix", "Sgn", "Sqr", "Exp", "Log", "Rnd",
               "Randomize", "Round"]:
        funcs.append((fn, "math", "general", "Number", None))

    # Trig functions
    for fn in ["Sin", "Cos", "Tan", "Atn"]:
        funcs.append((fn, "math", "trig", "Double", None))

    # DateTime functions
    for fn in ["Now", "Date", "Time", "Timer"]:
        funcs.append((fn, "datetime", "current", "Date/Single", None))
    for fn in ["DateAdd", "DateDiff", "DatePart", "DateSerial", "TimeSerial",
               "DateValue", "TimeValue"]:
        funcs.append((fn, "datetime", "calculation", "Date/Long", None))
    for fn in ["Year", "Month", "Day", "Hour", "Minute", "Second", "Weekday",
               "WeekdayName", "MonthName"]:
        funcs.append((fn, "datetime", "extract", "Integer/String", None))
    funcs.append(("IsDate", "datetime", "check", "Boolean", None))
    funcs.append(("CDate", "datetime", "convert", "Date", None))
    funcs.append(("Format", "datetime", "format", "String", "Overloaded with text Format"))

    # Conversion functions
    for fn, ret in [("CStr", "String"), ("CInt", "Integer"), ("CLng", "Long"),
                    ("CDbl", "Double"), ("CSng", "Single"), ("CCur", "Currency"),
                    ("CBool", "Boolean"), ("CByte", "Byte"), ("CVar", "Variant"),
                    ("CDec", "Decimal"), ("Val", "Double"), ("Str", "String")]:
        funcs.append((fn, "conversion", None, ret, None))

    # Type check functions
    for fn in ["IsNull", "IsEmpty", "IsNumeric", "IsDate", "IsArray",
               "IsObject", "IsError", "IsMissing"]:
        funcs.append((fn, "type_check", None, "Boolean", None))
    funcs.append(("TypeName", "type_check", None, "String", None))
    funcs.append(("VarType", "type_check", None, "Integer", None))

    # File functions
    for fn in ["Dir", "FileLen", "FileDateTime", "FreeFile", "EOF", "LOF",
               "Loc", "Seek", "FileCopy", "Kill", "MkDir", "RmDir", "ChDir",
               "CurDir"]:
        funcs.append((fn, "file", None, "Varies", None))

    # Interaction functions
    funcs.append(("MsgBox", "interaction", None, "Integer", "Returns button clicked"))
    funcs.append(("InputBox", "interaction", None, "String", "Returns user input"))
    for fn in ["DoCmd.OpenForm", "DoCmd.Close", "DoCmd.GoToRecord",
               "DoCmd.RunSQL", "DoCmd.SetWarnings", "DoCmd.TransferSpreadsheet",
               "DoCmd.TransferDatabase", "DoCmd.OutputTo"]:
        funcs.append((fn, "interaction", "docmd", None, "Access-specific action"))

    # Error handling
    for fn in ["Err.Number", "Err.Description", "Err.Clear", "Err.Raise"]:
        funcs.append((fn, "error_handling", None, "Varies", None))
    funcs.append(("Error", "error_handling", None, "String", "Returns error message for number"))
    funcs.append(("CVErr", "error_handling", None, "Variant", "Creates error value"))

    cur.executemany("INSERT OR REPLACE INTO vba_functions VALUES (?, ?, ?, ?, ?)", funcs)


def populate_access_sql_functions(cur: sqlite3.Cursor) -> None:
    """Populate Access SQL functions by category."""
    funcs = []

    # Aggregate functions
    for fn in ["Count", "Sum", "Avg", "Min", "Max", "First", "Last",
               "StDev", "StDevP", "Var", "VarP"]:
        funcs.append((fn, "aggregate", f"{fn}(expr)", f"Aggregate {fn.lower()} of values"))

    # String functions
    for fn in ["Left", "Right", "Mid", "Len", "Trim", "LCase", "UCase",
               "InStr", "Replace", "StrConv", "Format", "Space", "String"]:
        funcs.append((fn, "string", f"{fn}(args)", None))

    # DateTime functions
    for fn in ["Now", "Date", "Time", "DateAdd", "DateDiff", "DatePart",
               "DateSerial", "TimeSerial", "Year", "Month", "Day", "Hour",
               "Minute", "Second", "Weekday", "Format"]:
        funcs.append((fn, "datetime", f"{fn}(args)", None))

    # Math functions
    for fn in ["Abs", "Int", "Fix", "Sgn", "Sqr", "Round", "Rnd"]:
        funcs.append((fn, "math", f"{fn}(number)", None))

    # Conversion and utility
    for fn in ["CStr", "CInt", "CLng", "CDbl", "CSng", "CCur", "CBool",
               "Val", "Str", "Nz", "IIf"]:
        funcs.append((fn, "conversion", f"{fn}(expr)", None))

    # Domain aggregate functions
    for fn in ["DLookup", "DCount", "DSum", "DAvg", "DMin", "DMax",
               "DFirst", "DLast"]:
        funcs.append((fn, "domain", f'{fn}("field", "domain", "criteria")',
                      "Domain aggregate - queries table directly"))

    cur.executemany("INSERT OR REPLACE INTO access_sql_functions VALUES (?, ?, ?, ?)", funcs)


def populate_vba_keywords(cur: sqlite3.Cursor) -> None:
    keywords = {
        "declaration": [
            "Dim", "ReDim", "Static", "Const", "Type", "Enum", "Private",
            "Public", "Friend", "Global", "Option", "Explicit", "Base", "Compare",
        ],
        "control_flow": [
            "If", "Then", "Else", "ElseIf", "Select", "Case", "For", "To",
            "Step", "Next", "Each", "In", "Do", "While", "Until", "Loop",
            "Wend", "With", "GoTo", "GoSub", "Exit", "Stop",
        ],
        "error_handling": ["On", "Error", "Resume", "Err"],
        "scope": [
            "Sub", "Function", "Property", "Get", "Let", "Set", "ByVal",
            "ByRef", "Optional", "ParamArray",
        ],
        "module": [
            "Module", "Class", "Implements", "New", "Me", "Nothing", "Null",
            "Empty", "True", "False", "And", "Or", "Not", "Xor", "Eqv",
            "Imp", "Is", "Like", "Mod", "End", "Return",
        ],
    }
    for cat, words in keywords.items():
        for w in words:
            cur.execute("INSERT OR REPLACE INTO vba_keywords VALUES (?, ?)", (w, cat))


def populate_access_table_fields(cur: sqlite3.Cursor) -> None:
    """Populate ERM table schemas from seed-data/access_table_fields.json."""
    json_path = SEED_DIR / "access_table_fields.json"
    with open(json_path, encoding="utf-8") as f:
        fields_data = json.load(f)
    rows = [
        (r["table_name"], r["field_name"], r["access_type"],
         r.get("zoho_form"), r.get("zoho_field"), r.get("notes"))
        for r in fields_data
    ]
    cur.executemany("INSERT OR REPLACE INTO access_table_fields VALUES (?, ?, ?, ?, ?, ?)", rows)


def populate_type_mappings(cur: sqlite3.Cursor) -> None:
    """Populate from seed-data/type_mappings.json."""
    json_path = SEED_DIR / "type_mappings.json"
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    rows = [
        (r["access_type"], r["zoho_type"], r.get("conversion_notes"), r.get("data_loss_risk"))
        for r in data
    ]
    cur.executemany("INSERT OR REPLACE INTO type_mappings VALUES (?, ?, ?, ?)", rows)


def populate_field_name_mappings(cur: sqlite3.Cursor) -> None:
    """Populate from seed-data/field_name_mappings.json."""
    json_path = SEED_DIR / "field_name_mappings.json"
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    rows = [
        (r["access_table"], r["access_field"], r["zoho_form"],
         r["zoho_field"], r.get("transform_notes"))
        for r in data
    ]
    cur.executemany("INSERT OR REPLACE INTO field_name_mappings VALUES (?, ?, ?, ?, ?)", rows)


def populate_banned_patterns(cur: sqlite3.Cursor) -> None:
    rows = [
        ("SELECT *", "syntax", "Avoid SELECT * - use explicit column list for clarity and performance", "WARN"),
        ("EXEC ", "syntax", "EXEC/EXECUTE not supported in Access SQL - use DoCmd.RunSQL in VBA", "ERROR"),
        ("@@IDENTITY", "variable", "@@IDENTITY is unreliable in Access - use DMax or autonumber", "WARN"),
        ("GoTo ", "keyword", "Avoid GoTo outside error handling - use structured control flow", "WARN"),
        ("On Error Resume Next", "syntax", "Blanket error suppression hides bugs - use targeted error handling", "WARN"),
        ("DoCmd.SetWarnings False", "syntax", "Disabling warnings hides errors - use error handling instead", "WARN"),
    ]
    cur.executemany("INSERT OR REPLACE INTO banned_patterns_access VALUES (?, ?, ?, ?)", rows)


def populate_vba_error_patterns(cur: sqlite3.Cursor) -> None:
    rows = [
        ("Type mismatch", "runtime", "Variable type doesn't match expected type", "Check data types, use conversion functions (CStr, CLng, etc.)"),
        ("Object variable not set", "runtime", "Reference to Nothing object", "Use Set keyword and check Is Nothing before access"),
        ("Subscript out of range", "runtime", "Array index beyond bounds", "Check array bounds with LBound/UBound"),
        ("Division by zero", "runtime", "Dividing by zero", "Check divisor before division"),
        ("Overflow", "runtime", "Value exceeds data type range", "Use larger data type (Long instead of Integer)"),
        ("File not found", "runtime", "File path doesn't exist", "Use Dir() to check existence first"),
        ("Permission denied", "runtime", "File is locked or read-only", "Close other handles, check file attributes"),
        ("Object doesn't support this property", "runtime", "Calling non-existent method/property", "Check object type and available members"),
        ("Method or data member not found", "compile", "Typo in property/method name", "Check spelling and object type"),
        ("Variable not defined", "compile", "Using undeclared variable with Option Explicit", "Add Dim statement"),
        ("Expected: end of statement", "compile", "Syntax error in statement", "Check line syntax, missing operators"),
        ("Sub or Function not defined", "compile", "Calling non-existent procedure", "Check procedure name and module scope"),
    ]
    cur.executemany("INSERT OR REPLACE INTO vba_error_patterns VALUES (?, ?, ?, ?)", rows)


def populate_access_constraints(cur: sqlite3.Cursor) -> None:
    rows = [
        # Primary keys
        ("Departments", "pk", "ID", None, None, "AUTOINCREMENT"),
        ("Clients", "pk", "ID", None, None, "AUTOINCREMENT"),
        ("GL_Accounts", "pk", "ID", None, None, "AUTOINCREMENT"),
        ("Approval_Thresholds", "pk", "ID", None, None, "AUTOINCREMENT"),
        ("Expense_Claims", "pk", "ID", None, None, "AUTOINCREMENT"),
        ("Approval_History", "pk", "ID", None, None, "AUTOINCREMENT"),
        # NOT NULL constraints
        ("Departments", "not_null", "Department_Name", None, None, None),
        ("Clients", "not_null", "Client_Name", None, None, None),
        ("GL_Accounts", "not_null", "GL_Code", None, None, None),
        ("GL_Accounts", "not_null", "Account_Name", None, None, None),
        ("Approval_Thresholds", "not_null", "Tier_Name", None, None, None),
        # Foreign keys
        ("Expense_Claims", "fk", "Department_ID", "Departments", "ID", "FK_EC_Dept"),
        ("Expense_Claims", "fk", "Client_ID", "Clients", "ID", "FK_EC_Client"),
        ("Expense_Claims", "fk", "GL_Code_ID", "GL_Accounts", "ID", "FK_EC_GL"),
        ("Approval_History", "fk", "Claim_ID", "Expense_Claims", "ID", "FK_AH_Claim"),
    ]
    cur.executemany("INSERT OR REPLACE INTO access_constraints VALUES (?, ?, ?, ?, ?, ?)", rows)


def build_database(db_path: str) -> None:
    """Build the complete database."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    create_schema(cur)
    populate_access_data_types(cur)
    populate_access_reserved_words(cur)
    populate_access_operators(cur)
    populate_vba_functions(cur)
    populate_access_sql_functions(cur)
    populate_vba_keywords(cur)
    populate_access_table_fields(cur)
    populate_type_mappings(cur)
    populate_field_name_mappings(cur)
    populate_banned_patterns(cur)
    populate_vba_error_patterns(cur)
    populate_access_constraints(cur)

    conn.commit()

    # Print summary
    tables = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print(f"Database built: {db_path}")
    for (table,) in tables:
        count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count} rows")

    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Access/VBA language SQLite database")
    parser.add_argument("--force", action="store_true", help="Recreate database from scratch")
    args = parser.parse_args()

    if args.force and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing {DB_PATH}")

    build_database(DB_PATH)


if __name__ == "__main__":
    main()
