#!/usr/bin/env python3
"""
Build the Deluge language SQLite database.

Populates deluge_lang.db with all Deluge syntax data extracted from
official Zoho documentation. This database is consumed by lint_deluge.py
for validation lookups.

Usage:
    python -m forgeds.core.build_deluge_db          # creates deluge_lang.db
    python -m forgeds.core.build_deluge_db --force  # recreate from scratch
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from forgeds._shared.config import load_config, get_db_dir

DB_PATH = str(get_db_dir() / "deluge_lang.db")


def create_schema(cur: sqlite3.Cursor) -> None:
    """Create all tables."""
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS data_types (
            name        TEXT PRIMARY KEY,
            literal     TEXT NOT NULL,
            examples    TEXT,
            notes       TEXT
        );

        CREATE TABLE IF NOT EXISTS reserved_words (
            word TEXT PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS operators (
            symbol      TEXT NOT NULL,
            name        TEXT NOT NULL,
            category    TEXT NOT NULL,  -- arithmetic, assignment, relational, logical
            types       TEXT,           -- comma-separated applicable types
            notes       TEXT,
            PRIMARY KEY (symbol, category)
        );

        CREATE TABLE IF NOT EXISTS zoho_variables (
            name        TEXT PRIMARY KEY,
            returns     TEXT NOT NULL,
            scope       TEXT NOT NULL,  -- "all" or "creator"
            notes       TEXT
        );

        CREATE TABLE IF NOT EXISTS functions (
            name        TEXT NOT NULL,
            category    TEXT NOT NULL,  -- text, number, datetime, list, map, collection, logical, typecheck, conversion, utility
            subcategory TEXT,           -- search, extract, transform, etc.
            returns_bool INTEGER NOT NULL DEFAULT 0,
            description TEXT,
            PRIMARY KEY (name, category)
        );

        CREATE TABLE IF NOT EXISTS builtin_tasks (
            name        TEXT PRIMARY KEY,
            syntax      TEXT,
            required_params TEXT,  -- comma-separated
            optional_params TEXT,  -- comma-separated
            notes       TEXT
        );

        CREATE TABLE IF NOT EXISTS form_fields (
            form_name   TEXT NOT NULL,
            field_link  TEXT NOT NULL,
            display     TEXT,
            field_type  TEXT NOT NULL,
            notes       TEXT,
            PRIMARY KEY (form_name, field_link)
        );

        CREATE TABLE IF NOT EXISTS valid_statuses (
            value TEXT PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS valid_actions (
            value TEXT PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS error_messages (
            error_text  TEXT PRIMARY KEY,
            category    TEXT NOT NULL,  -- save, runtime
            cause       TEXT NOT NULL,
            fix         TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS banned_patterns (
            pattern     TEXT PRIMARY KEY,
            pattern_type TEXT NOT NULL,  -- function, variable, method
            message     TEXT NOT NULL,
            severity    TEXT NOT NULL DEFAULT 'ERROR'
        );
    """)


def populate_data_types(cur: sqlite3.Cursor) -> None:
    cur.executemany("INSERT OR REPLACE INTO data_types VALUES (?, ?, ?, ?)", [
        ("Text", 'double quotes', '"hello", "line1\\nline2"', "MUST use double quotes, never single"),
        ("Number", "integer literal", "42, -7, 0", None),
        ("Decimal", "float literal", "3.14, -0.5", None),
        ("Boolean", "keywords", "true, false", None),
        ("Date", "single quotes", "'2026-04-06'", "Only dates/times use single quotes"),
        ("DateTime", "single quotes", "'2026-04-06 14:30:00'", None),
        ("Time", "single quotes", "'14:30:00'", None),
        ("List", "curly braces", '{"a","b","c"} or List()', "Lists and maps both use {}"),
        ("Map", "curly braces with colons", '{"key":"value","num":42}', None),
        ("File", "from upload or fetch", "(no literal)", None),
        ("Null", "keyword", "null", "Always guard with ifnull()"),
    ])


def populate_reserved_words(cur: sqlite3.Cursor) -> None:
    for word in ["true", "false", "null", "void", "return"]:
        cur.execute("INSERT OR REPLACE INTO reserved_words VALUES (?)", (word,))


def populate_operators(cur: sqlite3.Cursor) -> None:
    rows = [
        # Arithmetic
        ("+", "Addition", "arithmetic", "Number,Decimal,Text", "Text + anything = concatenation"),
        ("-", "Subtraction", "arithmetic", "Number,Decimal,DateTime", "DateTime subtraction supported"),
        ("*", "Multiplication", "arithmetic", "Number,Decimal", None),
        ("/", "Division", "arithmetic", "Number,Decimal", "Division by zero = runtime error"),
        ("%", "Modulus", "arithmetic", "Number,Decimal", None),
        # Assignment
        ("=", "Simple assign", "assignment", "All", None),
        ("+=", "Add-assign", "assignment", "Text,Number,Decimal", None),
        ("-=", "Subtract-assign", "assignment", "Number,Decimal", None),
        ("*=", "Multiply-assign", "assignment", "Number,Decimal", None),
        ("/=", "Divide-assign", "assignment", "Number,Decimal", None),
        ("%=", "Modulus-assign", "assignment", "Number,Decimal", None),
        # Relational
        ("==", "Equals", "relational", "Number,Decimal,DateTime,Text", None),
        ("!=", "Not equals", "relational", "Number,Decimal,DateTime", None),
        ("<", "Less than", "relational", "Number,Decimal,DateTime", "NOT supported for Text"),
        (">", "Greater than", "relational", "Number,Decimal,DateTime", "NOT supported for Text"),
        ("<=", "Less than or equal", "relational", "Number,Decimal,DateTime", None),
        (">=", "Greater than or equal", "relational", "Number,Decimal,DateTime", None),
        # Logical
        ("&&", "AND", "logical", "Boolean", "Both conditions must be true"),
        ("||", "OR", "logical", "Boolean", "At least one must be true"),
        ("!", "NOT", "logical", "Boolean", "Negates single condition"),
    ]
    cur.executemany("INSERT OR REPLACE INTO operators VALUES (?, ?, ?, ?, ?)", rows)


def populate_zoho_variables(cur: sqlite3.Cursor) -> None:
    rows = [
        ("zoho.currentdate", "Current date", "all", None),
        ("zoho.currenttime", "Current datetime", "all", None),
        ("zoho.loginuser", "Username of logged-in user", "all", 'Returns "Public" for public users'),
        ("zoho.loginuser.name", "Full name of logged-in user", "creator", None),
        ("zoho.loginuserid", "Email of logged-in user", "all", "null for unauthenticated"),
        ("zoho.adminuser", "Username of app owner", "all", None),
        ("zoho.adminuserid", "Email of app owner", "all", None),
        ("zoho.appname", "Application link name", "creator", None),
        ("zoho.appuri", "App path", "creator", "Format: /<admin>/<app_link>/"),
        ("zoho.ipaddress", "Public IP of user", "all", "null outside session"),
        ("zoho.device.type", "Device type", "creator", 'Returns "web", "phone", or "tablet"'),
    ]
    cur.executemany("INSERT OR REPLACE INTO zoho_variables VALUES (?, ?, ?, ?)", rows)


def populate_functions(cur: sqlite3.Cursor) -> None:
    """Populate all built-in functions by category."""
    # (name, category, subcategory, returns_bool, description)
    funcs: list[tuple[str, str, str | None, int, str | None]] = []

    # --- Text functions (71) ---
    for fn in ["contains", "notContains", "containsIgnoreCase", "isEmpty",
               "startsWith", "startsWithIgnoreCase", "endsWith", "endsWithIgnoreCase",
               "equalsIgnoreCase", "matches"]:
        funcs.append((fn, "text", "search", 1, None))

    for fn in ["getAlpha", "getAlphaNumeric", "getPrefix", "getPrefixIgnoreCase",
               "getSuffix", "getSuffixIgnoreCase", "getOccurenceCount", "left", "right",
               "mid", "subText", "substring", "find", "indexOf", "lastIndexOf"]:
        funcs.append((fn, "text", "extract", 0, None))

    for fn in ["toUpperCase", "toLowerCase", "proper", "trim", "ltrim", "rtrim",
               "reverse", "leftpad", "rightpad", "concat", "repeat", "text"]:
        funcs.append((fn, "text", "transform", 0, None))

    for fn in ["remove", "removeAllAlpha", "removeAllAlphaNumeric",
               "removeFirstOccurence", "removeLastOccurence"]:
        funcs.append((fn, "text", "remove", 0, None))

    for fn in ["replaceAll", "replaceAllIgnoreCase", "replaceFirst", "replaceFirstIgnoreCase"]:
        funcs.append((fn, "text", "replace", 0, None))

    for fn in ["toList", "toMap", "toLong", "toNumber", "toString", "toText",
               "toJSONList", "toListString", "toDecimal", "toTime", "toDate"]:
        funcs.append((fn, "text", "convert", 0, None))

    for fn in ["len", "length", "isAscii"]:
        funcs.append((fn, "text", "measure", 0, None))

    for fn in ["hexToText", "textToHex"]:
        funcs.append((fn, "text", "encoding", 0, None))

    # --- Number functions (38) ---
    for fn in ["abs", "ceil", "floor", "round", "frac", "sqrt", "power", "exp", "log", "log10"]:
        funcs.append((fn, "number", "math", 0, None))

    for fn in ["sin", "cos", "tan", "asin", "acos", "atan", "atan2",
               "sinh", "cosh", "tanh", "asinh", "acosh", "atanh"]:
        funcs.append((fn, "number", "trig", 0, None))

    for fn in ["average", "median", "max", "min", "largest", "smallest",
               "nthLargest", "nthSmallest"]:
        funcs.append((fn, "number", "statistics", 0, None))

    for fn in ["toHex", "toDecimal", "toLong", "toWords"]:
        funcs.append((fn, "number", "conversion", 0, None))

    funcs.append(("isNumber", "number", "check", 1, None))
    funcs.append(("randomNumber", "number", "check", 0, None))
    funcs.append(("isEven", "number", "check", 1, None))
    funcs.append(("isOdd", "number", "check", 1, None))

    # --- Date-Time functions (51) ---
    for fn in ["addDay", "addBusinessDay", "addWeek", "addMonth", "addYear",
               "addHour", "addMinutes", "addSeconds"]:
        funcs.append((fn, "datetime", "add", 0, None))

    for fn in ["subDay", "subBusinessDay", "subWeek", "subMonth", "subYear",
               "subHour", "subMinutes", "subSeconds"]:
        funcs.append((fn, "datetime", "subtract", 0, None))

    for fn in ["day", "getDay", "getDayOfYear", "getHour", "getMinutes", "getMonth",
               "getSeconds", "getWeekOfYear", "getYear", "hour", "minute", "month",
               "second", "weekday"]:
        funcs.append((fn, "datetime", "extract", 0, None))

    for fn in ["daysBetween", "hoursBetween", "monthsBetween", "yearsBetween",
               "days360", "totalMonth", "totalYear"]:
        funcs.append((fn, "datetime", "calculate", 0, None))

    for fn in ["toStartOfMonth", "toStartOfWeek", "nextWeekDay", "previousWeekDay",
               "edate", "eomonth", "workday"]:
        funcs.append((fn, "datetime", "navigate", 0, None))

    funcs.append(("now", "datetime", "current", 0, None))
    funcs.append(("today", "datetime", "current", 0, None))

    for fn in ["toString", "toTime", "toDate", "toDateTimeString", "unixEpoch"]:
        funcs.append((fn, "datetime", "convert", 0, None))

    funcs.append(("isDate", "datetime", "check", 1, None))

    # --- List functions (25) ---
    for fn in ["add", "addAll", "clear", "remove", "removeAll", "removeElement",
               "insert", "sort", "distinct", "subList"]:
        funcs.append((fn, "list", "modify", 0, None))

    for fn in ["contains", "notContains", "get", "indexOf", "lastIndexOf",
               "isEmpty", "size", "intersect"]:
        funcs.append((fn, "list", "query", 1 if fn in ("contains", "notContains", "isEmpty") else 0, None))

    for fn in ["average", "largest", "smallest", "median", "nthLargest", "nthSmallest"]:
        funcs.append((fn, "list", "stats", 0, None))

    for fn in ["toJSONList", "toList"]:
        funcs.append((fn, "list", "convert", 0, None))

    # --- Map functions (13) ---
    for fn in ["put", "putAll", "remove", "clear"]:
        funcs.append((fn, "map", "modify", 0, None))

    funcs.append(("get", "map", "query", 0, None))
    funcs.append(("containKey", "map", "query", 1, None))
    funcs.append(("containValue", "map", "query", 1, None))
    funcs.append(("notContains", "map", "query", 1, None))
    funcs.append(("isEmpty", "map", "query", 1, None))
    funcs.append(("size", "map", "query", 0, None))
    funcs.append(("keys", "map", "query", 0, None))
    funcs.append(("toMap", "map", "convert", 0, None))
    funcs.append(("toJSONList", "map", "convert", 0, None))

    # --- Collection functions (23) ---
    for fn in ["clear", "containsKey", "containsValue", "delete", "deleteAll",
               "deleteKey", "deleteKeys", "distinct", "duplicate", "get", "getKey",
               "getLastKey", "insert", "insertAll", "intersect", "isEmpty", "keys",
               "size", "sort", "sortKey", "update", "values", "notContains"]:
        funcs.append((fn, "collection", None, 0, None))

    # --- Logical functions (3) ---
    funcs.append(("isBlank", "logical", None, 1, "True if blank (empty string or null)"))
    funcs.append(("isEmpty", "logical", None, 1, "True if empty string"))
    funcs.append(("isNull", "logical", None, 1, "True if null"))

    # --- Type check functions (4) ---
    funcs.append(("isDate", "typecheck", None, 1, "True if valid date"))
    funcs.append(("isFile", "typecheck", None, 1, "True if file"))
    funcs.append(("isNumber", "typecheck", None, 1, "True if numeric"))
    funcs.append(("isText", "typecheck", None, 1, "True if text"))

    # --- Type conversion functions (8) ---
    for fn in ["toDate", "toDecimal", "toJSONList", "toLong",
               "toString", "toTime", "toList", "toMap"]:
        funcs.append((fn, "conversion", None, 0, None))

    # --- Utility functions (2) ---
    funcs.append(("encodeUrl", "utility", None, 0, None))
    funcs.append(("getJSON", "utility", None, 0, None))

    cur.executemany("INSERT OR REPLACE INTO functions VALUES (?, ?, ?, ?, ?)", funcs)


def populate_builtin_tasks(cur: sqlite3.Cursor) -> None:
    rows = [
        ("sendmail", "sendmail [ from: to: subject: message: ]",
         "from,to,subject,message", "cc,bcc,replyto,content_type",
         "from/to must include zoho.adminuserid or zoho.loginuserid"),
        ("sendsms", "sendsms [ to: message: ]",
         "to,message", None, None),
        ("info", "info expression;", None, None, "Debug log, no side effects"),
        ("alert", 'alert "message";', None, None, "User-facing message"),
        ("cancel submit", "cancel submit;", None, None, "Only in On Validate"),
        ("return", "return;", None, None, "Exit current script"),
        ("invokeUrl", "invokeUrl [ url: type: ]",
         "url,type", "headers,parameters,connection,detailed",
         "Custom HTTP requests"),
        ("openUrl", "openUrl(url, target);", "url", "target",
         "Opens URL in browser"),
    ]
    cur.executemany("INSERT OR REPLACE INTO builtin_tasks VALUES (?, ?, ?, ?, ?)", rows)


def populate_form_fields(cur: sqlite3.Cursor) -> None:
    """Populate form fields from seed data or hardcoded defaults.

    When a seed_data_dir is configured and contains form-fields.json,
    loads from that file. Otherwise falls back to built-in defaults
    that cover the standard Zoho Creator expense reimbursement schema.
    """
    # Try loading from seed data config
    config = load_config()
    seed_dir = config.get("seed_data_dir", "")
    if seed_dir:
        seed_path = Path(seed_dir) / "form-fields.json"
        if seed_path.exists():
            try:
                with open(seed_path, encoding="utf-8") as f:
                    rows = json.load(f)
                cur.executemany(
                    "INSERT OR REPLACE INTO form_fields VALUES (?, ?, ?, ?, ?)",
                    [(r["form_name"], r["field_link"], r.get("display"),
                      r["field_type"], r.get("notes")) for r in rows],
                )
                return
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load {seed_path}: {e}. Using defaults.", file=sys.stderr)

    # Hardcoded defaults (standard expense reimbursement schema)
    _populate_default_form_fields(cur)


def _populate_default_form_fields(cur: sqlite3.Cursor) -> None:
    """Populate all form fields from hardcoded defaults."""
    # Expense Claims
    ec_fields = [
        ("expense_claims", "Employee_Name1", "Employee Name", "name", "Composite: .first_name, .last_name"),
        ("expense_claims", "Email", "Email", "picklist", "Users module"),
        ("expense_claims", "Submission_Date", "Submission Date", "datetime", "Auto-set on submit"),
        ("expense_claims", "claim_id", "Claim ID", "autonumber", None),
        ("expense_claims", "department", "Department", "list", "FK -> departments.ID"),
        ("expense_claims", "Claim_Reference", "Claim Reference", "text", "Auto-generated EXP-XXXX"),
        ("expense_claims", "client", "Client", "list", "FK -> clients.ID"),
        ("expense_claims", "Expense_Date", "Expense Date", "date", None),
        ("expense_claims", "Department_Shadow", "Department Shadow", "text", "Private/hidden"),
        ("expense_claims", "category", "Category", "picklist", None),
        ("expense_claims", "Client_Shadow", "Client Shadow", "text", "Private/hidden"),
        ("expense_claims", "amount_zar", "Amount ZAR", "currency", None),
        ("expense_claims", "Supporting_Documents", "Supporting Documents", "file", "Max 10 files"),
        ("expense_claims", "description", "Description", "textarea", None),
        ("expense_claims", "VAT_Invoice_Type", "VAT Invoice Type", "picklist", "None/Abbreviated/Full Tax Invoice"),
        ("expense_claims", "POPIA_Consent", "POPIA Consent", "checkbox", "Mandatory for submission"),
        ("expense_claims", "status", "Status", "picklist", None),
        ("expense_claims", "Rejection_Reason", "Rejection Reason", "textarea", None),
        ("expense_claims", "Version", "Version", "number", "Default: 1"),
        ("expense_claims", "Retention_Expiry_Date", "Retention Expiry Date", "date", "SARS S29: 5yr from submission"),
        ("expense_claims", "Parent_Claim_ID", "Parent Claim ID", "picklist", "Self-ref FK"),
        ("expense_claims", "gl_code", "GL Code", "list", "FK -> gl_accounts.ID"),
        ("expense_claims", "ID", "ID", "autonumber", "System-generated"),
        ("expense_claims", "Requires_Dual_Approval", "Requires Dual Approval", "checkbox", "Two-Key flag, set by HoD approval"),
        ("expense_claims", "Key_1_Approver", "Key 1 Approver", "text", "Stores Key 1 approver username"),
        ("expense_claims", "Key_1_Timestamp", "Key 1 Timestamp", "datetime", "When Key 1 approved"),
        ("expense_claims", "Key_2_Approver", "Key 2 Approver", "text", "Stores Key 2 approver username"),
        ("expense_claims", "Key_2_Timestamp", "Key 2 Timestamp", "datetime", "When Key 2 approved"),
        ("expense_claims", "Estimated_Carbon_KG", "Estimated Carbon KG", "decimal", "Calculated: Amount_ZAR * GL.Carbon_Factor"),
        ("expense_claims", "ESG_Category", "ESG Category", "text", "Denormalized from GL account on approval"),
    ]
    # Approval History
    ah_fields = [
        ("approval_history", "claim", "Claim", "list", "FK -> expense_claims.ID"),
        ("approval_history", "action_1", "Action", "picklist", "NOT action -- must be action_1"),
        ("approval_history", "actor", "Actor", "text", None),
        ("approval_history", "timestamp", "Timestamp", "datetime", None),
        ("approval_history", "comments", "Comments", "textarea", None),
        ("approval_history", "Added_User", "Added User", "system", "MUST be zoho.loginuser"),
    ]
    # Approval Thresholds
    at_fields = [
        ("approval_thresholds", "tier_name", "Tier Name", "text", None),
        ("approval_thresholds", "max_amount_zar", "Max Amount ZAR", "currency", None),
        ("approval_thresholds", "approver_role", "Approver Role", "text", None),
        ("approval_thresholds", "Tier_Order", "Tier Order", "number", "Escalation sequence"),
        ("approval_thresholds", "Active", "Active", "checkbox", "Default: true"),
        ("approval_thresholds", "Requires_Dual_Approval", "Requires Dual Approval", "checkbox", "Two-Key flag"),
        ("approval_thresholds", "Dual_Approval_Role", "Dual Approval Role", "text", "Key 2 approver role"),
        ("approval_thresholds", "Dual_Threshold_ZAR", "Dual Approval Threshold ZAR", "currency", "Amount above which Two-Key applies"),
    ]
    # GL Accounts
    gl_fields = [
        ("gl_accounts", "gl_code", "GL Code", "text", None),
        ("gl_accounts", "account_name", "Account Name", "text", None),
        ("gl_accounts", "expense_category", "Expense Category", "picklist", None),
        ("gl_accounts", "receipt_required", "Receipt Required", "checkbox", None),
        ("gl_accounts", "SARS_Provision", "SARS Provision", "text", None),
        ("gl_accounts", "Risk_Level", "Risk Level", "picklist", "ISO 37001: Standard/Elevated/High"),
        ("gl_accounts", "Active", "Active", "checkbox", "Default: true"),
        ("gl_accounts", "ESG_Category", "ESG Category", "picklist", "ISSB/GRI: Travel Emissions/Energy/Waste/Social/None"),
        ("gl_accounts", "Carbon_Factor", "Carbon Factor", "decimal", "kg CO2e per ZAR spent (DEFRA-adapted)"),
        ("gl_accounts", "GRI_Indicator", "GRI Indicator", "text", "GRI Standards reference (e.g. GRI 305-3)"),
    ]
    # Departments
    dept_fields = [
        ("departments", "department_id", "Department ID", "autonumber", None),
        ("departments", "name", "Name", "text", None),
        ("departments", "is_active", "Active", "checkbox", None),
    ]
    # Clients
    cl_fields = [
        ("clients", "client_id", "Client ID", "autonumber", None),
        ("clients", "name", "Name", "text", None),
        ("clients", "is_active", "Active", "checkbox", None),
    ]
    # Compliance Config
    cc_fields = [
        ("compliance_config", "Config_Key", "Config Key", "text", "Unique setting name"),
        ("compliance_config", "Config_Value", "Config Value", "text", None),
        ("compliance_config", "Description", "Description", "text", None),
        ("compliance_config", "Active", "Active", "checkbox", "Default: true"),
    ]
    all_fields = ec_fields + ah_fields + at_fields + gl_fields + dept_fields + cl_fields + cc_fields
    cur.executemany("INSERT OR REPLACE INTO form_fields VALUES (?, ?, ?, ?, ?)", all_fields)


def populate_valid_values(cur: sqlite3.Cursor) -> None:
    """Populate valid status and action values.

    Loads from seed data JSON files if available, otherwise uses
    hardcoded defaults.
    """
    config = load_config()
    seed_dir = config.get("seed_data_dir", "")

    # Try loading statuses from seed data
    statuses_loaded = False
    if seed_dir:
        statuses_path = Path(seed_dir) / "valid-statuses.json"
        if statuses_path.exists():
            try:
                with open(statuses_path, encoding="utf-8") as f:
                    statuses = json.load(f)
                for s in statuses:
                    cur.execute("INSERT OR REPLACE INTO valid_statuses VALUES (?)", (s,))
                statuses_loaded = True
            except (json.JSONDecodeError, TypeError):
                pass

    if not statuses_loaded:
        for s in ["Draft", "Submitted", "Pending LM Approval", "Pending HoD Approval",
                  "Pending Second Key", "Key 2 Dispute",
                  "Approved", "Rejected", "Resubmitted"]:
            cur.execute("INSERT OR REPLACE INTO valid_statuses VALUES (?)", (s,))

    # Try loading actions from seed data
    actions_loaded = False
    if seed_dir:
        actions_path = Path(seed_dir) / "valid-actions.json"
        if actions_path.exists():
            try:
                with open(actions_path, encoding="utf-8") as f:
                    actions = json.load(f)
                for a in actions:
                    cur.execute("INSERT OR REPLACE INTO valid_actions VALUES (?)", (a,))
                actions_loaded = True
            except (json.JSONDecodeError, TypeError):
                pass

    if not actions_loaded:
        for a in ["Submitted", "Submitted (Self-approval bypass)", "Approved (LM)",
                  "Approved (HoD)", "Approved (Key 1)", "Approved (Key 2)",
                  "Rejected", "Rejected (Key 2)", "Reconsidered (Key 1)",
                  "Escalated (SLA Breach)", "Resubmitted", "Warning"]:
            cur.execute("INSERT OR REPLACE INTO valid_actions VALUES (?)", (a,))


def populate_error_messages(cur: sqlite3.Cursor) -> None:
    rows = [
        # Save errors
        ("Variable is not defined", "save",
         "Using undeclared variable", "Declare before use"),
        ("Expecting } but found EOF", "save",
         "Unclosed brace", "Match all { with }"),
        ("Missing semicolon", "save",
         "Missing ; or unquoted text", "Add ; or wrap in double quotes"),
        ("Number of Arguments mismatches", "save",
         "Wrong param count", "Check function signature"),
        ("From address is not zoho.adminuserid", "save",
         "Invalid sendmail sender", "Use zoho.adminuserid or zoho.loginuserid"),
        ("Not able to find function", "save",
         "Undefined function", "Check function name/spelling"),
        ("Type mismatch in criteria", "save",
         "Comparing incompatible types", "Match operand types"),
        ("Comment not closed properly", "save",
         "Missing closing */", "Add closing */ to match opening /*"),
        # Runtime errors
        ("Divide by zero error", "runtime",
         "Division by 0", "Check divisor before dividing"),
        ("Null value occurred", "runtime",
         "Operation on null", "Use ifnull() or null check"),
        ("Index greater than list size", "runtime",
         "List index out of bounds", "Check size() first"),
        ("Invalid JSON Format String", "runtime",
         "Bad JSON text", "Validate JSON structure"),
        ("UnParsable date", "runtime",
         "Invalid date format", "Use correct date format"),
        ("Cannot cast to MAP", "runtime",
         "Wrong type where map expected", "Provide correct collection type"),
        ("Cannot cast to BIGINT", "runtime",
         "Text provided where number required", "Provide number value"),
    ]
    cur.executemany("INSERT OR REPLACE INTO error_messages VALUES (?, ?, ?, ?)", rows)


def populate_banned_patterns(cur: sqlite3.Cursor) -> None:
    rows = [
        ("lpad", "function", "lpad() does not exist in Deluge. Use manual string padding.", "ERROR"),
        ("rpad", "function", "rpad() does not exist in Deluge. Use manual string padding.", "ERROR"),
        ("zoho.loginuserrole", "variable",
         "zoho.loginuserrole does NOT exist. Use thisapp.permissions.isUserInRole().", "ERROR"),
    ]
    # Discovery log entries (runtime-discovered constraints)
    cur.execute(
        "INSERT OR REPLACE INTO error_messages VALUES (?, ?, ?, ?)",
        ("Added_User only accepts zoho.loginuser or zoho.adminuser", "save",
         "Used zoho.adminuserid (email) in Added_User field",
         "Change to zoho.adminuser (username) or zoho.loginuser. See DL-001."),
    )
    cur.executemany("INSERT OR REPLACE INTO banned_patterns VALUES (?, ?, ?, ?)", rows)


def build_database(db_path: str) -> None:
    """Build the complete database."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    create_schema(cur)
    populate_data_types(cur)
    populate_reserved_words(cur)
    populate_operators(cur)
    populate_zoho_variables(cur)
    populate_functions(cur)
    populate_builtin_tasks(cur)
    populate_form_fields(cur)
    populate_valid_values(cur)
    populate_error_messages(cur)
    populate_banned_patterns(cur)

    conn.commit()

    # Print summary
    tables = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print(f"Database built: {db_path}")
    for (table,) in tables:
        count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
        print(f"  {table}: {count} rows")

    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Deluge language SQLite database")
    parser.add_argument("--force", action="store_true", help="Recreate database from scratch")
    args = parser.parse_args()

    if args.force and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing {DB_PATH}")

    build_database(DB_PATH)


if __name__ == "__main__":
    main()
