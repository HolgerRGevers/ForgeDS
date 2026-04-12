"""AST-based Deluge lint rules (DG001–DG021).

Reimplements all 21 lint rules from core/lint_deluge.py as AST Visitor
methods. Each rule walks the typed AST instead of scanning raw text
with regexes, giving precise span information and structural context.

Usage:
    from forgeds.lang.parser import parse_source
    from forgeds.compiler.lint_rules import ASTLinter

    tree = parse_source(source)
    linter = ASTLinter(db, filename, file_type)
    linter.visit(tree)
    diagnostics = linter.diagnostics
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from forgeds._shared.diagnostics import Severity, Diagnostic
from forgeds.lang import ast_nodes as ast
from forgeds.lang.tokens import SourceSpan


# ============================================================
# Constants (mirror core/lint_deluge.py)
# ============================================================

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}(:\d{2})?)?$")
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}(:\d{2})?$")
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

VALID_ADDED_USER_VALUES = {"zoho.loginuser", "zoho.adminuser"}


# ============================================================
# File type detection (same as original)
# ============================================================

class FileType:
    FORM_WORKFLOW = "form-workflow"
    APPROVAL_SCRIPT = "approval-script"
    SCHEDULED = "scheduled"
    CUSTOM_API = "custom-api"


def detect_file_type(filepath: str) -> str:
    """Determine script context from file path or header comment."""
    normalized = filepath.replace("\\", "/")
    if "/scheduled/" in normalized:
        return FileType.SCHEDULED
    if "/approval-scripts/" in normalized:
        return FileType.APPROVAL_SCRIPT
    if "/custom-api/" in normalized:
        return FileType.CUSTOM_API
    try:
        with open(filepath, encoding="utf-8") as f:
            head = f.read(512)
        if "context: custom-api" in head.lower() or (
            "custom api" in head.lower() and "microservices" in head.lower()
        ):
            return FileType.CUSTOM_API
    except (OSError, UnicodeDecodeError):
        pass
    return FileType.FORM_WORKFLOW


# ============================================================
# Helper
# ============================================================

def _diag(filename: str, line: int, severity: Severity, code: str, message: str) -> Diagnostic:
    return Diagnostic(file=filename, line=line, rule=code, severity=severity, message=message)


def _expr_to_dotted(expr: ast.Expr) -> str:
    """Flatten a FieldAccess chain to a dotted string: input.Name -> 'input.Name'."""
    if isinstance(expr, ast.Identifier):
        return expr.name
    if isinstance(expr, ast.FieldAccess):
        return _expr_to_dotted(expr.object) + "." + expr.field
    return ""


def _collect_string_values(expr: ast.Expr) -> list[str]:
    """Collect all string literal values reachable from an expression."""
    results: list[str] = []
    if isinstance(expr, ast.Literal) and expr.kind == "string":
        results.append(str(expr.value))
    elif isinstance(expr, ast.BinaryExpr):
        results.extend(_collect_string_values(expr.left))
        results.extend(_collect_string_values(expr.right))
    elif isinstance(expr, ast.FunctionCall):
        for arg in expr.args:
            results.extend(_collect_string_values(arg))
    return results


# ============================================================
# AST Linter — Visitor that collects diagnostics
# ============================================================

class ASTLinter(ast.Visitor):
    """Walk the AST and collect lint diagnostics for DG001–DG021."""

    def __init__(self, db: Any, filename: str, file_type: str) -> None:
        self.db = db
        self.filename = filename
        self.file_type = file_type
        self.diagnostics: list[Diagnostic] = []

        # DG005 tracking: query vars and their null-guard status
        self._query_vars: dict[str, int] = {}  # var_name -> assignment line
        self._guarded_vars: set[str] = set()
        self._guard_stack: list[str] = []  # vars guarded by current if-chain
        self._dg005_reported: set[str] = set()

        # DG020 tracking
        self._has_map_constructor = False
        self._has_put_call = False

        # Load config-driven thresholds
        from forgeds._shared.config import load_config
        _config = load_config()
        _lint_cfg = _config.get("lint", {})
        self._threshold_fallback = float(_lint_cfg.get("threshold_fallback", "999.99"))
        self._dual_threshold_fallback = float(_lint_cfg.get("dual_threshold_fallback", "5000.00"))
        self._valid_thresholds = {self._threshold_fallback, self._dual_threshold_fallback}
        self._demo_email_domains = set(_lint_cfg.get(
            "demo_email_domains", ["yourdomain.com", "example.com", "placeholder.com"]
        ))

    def _emit(self, line: int, severity: Severity, code: str, message: str) -> None:
        self.diagnostics.append(_diag(self.filename, line, severity, code, message))

    # ----------------------------------------------------------
    # Program (root) — file-scoped rules
    # ----------------------------------------------------------

    def visit_Program(self, node: ast.Program) -> None:
        # Walk all children first to collect state
        for stmt in node.body:
            self.visit(stmt)

        # DG020: Custom API should build a response Map
        if self.file_type == FileType.CUSTOM_API:
            if not self._has_map_constructor and not self._has_put_call:
                self._emit(1, Severity.WARNING, "DG020",
                           "Custom API script does not appear to build a response Map. "
                           "Custom APIs should construct a Map() response matching the Response step definition.")

    # ----------------------------------------------------------
    # Statements
    # ----------------------------------------------------------

    def visit_Block(self, node: ast.Block) -> None:
        for stmt in node.body:
            self.visit(stmt)

    def visit_IfStmt(self, node: ast.IfStmt) -> None:
        self.visit(node.condition)

        # DG005: detect null guard pattern: if (var != null)
        guarded = self._detect_null_guard(node.condition)
        if guarded:
            self._guarded_vars.add(guarded)
            self._guard_stack.append(guarded)

        self.visit(node.body)

        if guarded:
            self._guard_stack.pop()
            self._guarded_vars.discard(guarded)

        if node.else_body is not None:
            self.visit(node.else_body)

    def visit_ForEachStmt(self, node: ast.ForEachStmt) -> None:
        self.visit(node.collection)
        self.visit(node.body)

    def visit_WhileStmt(self, node: ast.WhileStmt) -> None:
        self.visit(node.condition)
        self.visit(node.body)

    def visit_TryCatchStmt(self, node: ast.TryCatchStmt) -> None:
        self.visit(node.try_body)
        self.visit(node.catch_body)

    def visit_ReturnStmt(self, node: ast.ReturnStmt) -> None:
        if node.value is not None:
            self.visit(node.value)

    def visit_ExprStmt(self, node: ast.ExprStmt) -> None:
        self.visit(node.expr)

    # ----------------------------------------------------------
    # Assignment — triggers DG005, DG011, DG017, DG019
    # ----------------------------------------------------------

    def visit_Assignment(self, node: ast.Assignment) -> None:
        line = node.span.start_line

        # DG017: Reserved word as variable name
        if isinstance(node.target, ast.Identifier):
            var_name = node.target.name
            if var_name in self.db.reserved_words:
                self._emit(line, Severity.ERROR, "DG017",
                           f"Reserved word '{var_name}' cannot be used as a variable name. "
                           f"Reserved: {', '.join(sorted(self.db.reserved_words))}")

        # DG011: Unknown status value
        if isinstance(node.target, ast.FieldAccess) and node.target.field == "status":
            if isinstance(node.value, ast.Literal) and node.value.kind == "string":
                status = str(node.value.value)
                if status not in self.db.valid_statuses:
                    self._emit(line, Severity.WARNING, "DG011",
                               f'Unknown status value "{status}". '
                               f"Valid: {', '.join(sorted(self.db.valid_statuses))}")

        # DG019: Added_User = zoho.adminuserid
        if isinstance(node.target, ast.FieldAccess) or isinstance(node.target, ast.Identifier):
            target_name = _expr_to_dotted(node.target)
            if target_name.endswith("Added_User"):
                val_str = _expr_to_dotted(node.value)
                if val_str == "zoho.adminuserid":
                    self._emit(line, Severity.ERROR, "DG019",
                               "Added_User only accepts zoho.loginuser or zoho.adminuser. "
                               "zoho.adminuserid (email) is rejected by Creator. See discovery-log.md DL-001.")

        # DG005: Track query assignments (var = FormName[criteria] or var = name[criteria])
        if isinstance(node.target, ast.Identifier) and node.op == "=":
            if isinstance(node.value, (ast.FormQuery, ast.IndexAccess)):
                self._query_vars[node.target.name] = line

        # DG014: threshold assignment
        if isinstance(node.target, ast.Identifier):
            name_lower = node.target.name.lower()
            if "threshold" in name_lower and isinstance(node.value, ast.Literal) and node.value.kind == "number":
                val = float(node.value.value)
                if val not in self._valid_thresholds:
                    self._emit(line, Severity.WARNING, "DG014",
                               f"Threshold fallback value is {node.value.value}, "
                               f"expected {self._threshold_fallback} (tier 1) or "
                               f"{self._dual_threshold_fallback} (dual).")

        self.visit(node.value)

    # ----------------------------------------------------------
    # Insert statement — DG006, DG007, DG009, DG012
    # ----------------------------------------------------------

    def visit_InsertStmt(self, node: ast.InsertStmt) -> None:
        line = node.span.start_line
        table = node.table

        if table == "approval_history":
            param_names = {p.name for p in node.params.params}

            # DG006: Missing Added_User
            if "Added_User" not in param_names:
                self._emit(line, Severity.ERROR, "DG006",
                           "Missing 'Added_User = zoho.loginuser' in insert into approval_history block.")

            # DG007: Wrong Added_User value
            for p in node.params.params:
                if p.name == "Added_User":
                    val_str = _expr_to_dotted(p.value)
                    if val_str and val_str not in VALID_ADDED_USER_VALUES:
                        self._emit(p.span.start_line, Severity.ERROR, "DG007",
                                   f"Added_User must be 'zoho.loginuser' (or 'zoho.adminuser' "
                                   f"for scheduled tasks), got '{val_str}'.")

            # DG012: Unknown action_1 value
            for p in node.params.params:
                if p.name == "action_1":
                    if isinstance(p.value, ast.Literal) and p.value.kind == "string":
                        val = str(p.value.value)
                        if val not in self.db.valid_actions:
                            self._emit(p.span.start_line, Severity.WARNING, "DG012",
                                       f'Unknown action_1 value "{val}". '
                                       f"Valid: {', '.join(sorted(self.db.valid_actions))}")

        # DG009: Colon separator in insert block
        for p in node.params.params:
            if p.separator == ":":
                self._emit(p.span.start_line, Severity.ERROR, "DG009",
                           f"Field '{p.name}' uses ':' separator in insert block. "
                           "Use '=' (colons are for sendmail).")

        # Visit param values for other rules
        for p in node.params.params:
            self.visit(p.value)

    # ----------------------------------------------------------
    # Sendmail — DG010, DG015, DG016
    # ----------------------------------------------------------

    def visit_SendmailStmt(self, node: ast.SendmailStmt) -> None:
        line = node.span.start_line

        # DG010: Missing required params
        param_names = {p.name.lower().strip() for p in node.params.params}
        for req in self.db.sendmail_required:
            if req not in param_names:
                self._emit(line, Severity.ERROR, "DG010",
                           f"Missing required sendmail parameter '{req}'.")

        # Visit param values (emails checked via visit_Literal)
        for p in node.params.params:
            self.visit(p.value)

    # ----------------------------------------------------------
    # InvokeUrl — DG010
    # ----------------------------------------------------------

    def visit_InvokeUrlStmt(self, node: ast.InvokeUrlStmt) -> None:
        line = node.span.start_line

        # DG010: Missing required params
        param_names = {p.name.lower().strip() for p in node.params.params}
        for req in self.db.invoke_url_required:
            if req not in param_names:
                self._emit(line, Severity.ERROR, "DG010",
                           f"Missing required invokeUrl parameter '{req}'.")

        for p in node.params.params:
            self.visit(p.value)

    # ----------------------------------------------------------
    # Alert / CancelSubmit — DG021
    # ----------------------------------------------------------

    def visit_AlertStmt(self, node: ast.AlertStmt) -> None:
        if self.file_type == FileType.CUSTOM_API:
            self._emit(node.span.start_line, Severity.ERROR, "DG021",
                       "Form-specific task 'alert' used in Custom API context. "
                       "Custom APIs have no form context -- use response Map for error reporting.")
        self.visit(node.message)

    def visit_InfoStmt(self, node: ast.InfoStmt) -> None:
        self.visit(node.expr)

    def visit_CancelSubmitStmt(self, node: ast.CancelSubmitStmt) -> None:
        if self.file_type == FileType.CUSTOM_API:
            self._emit(node.span.start_line, Severity.ERROR, "DG021",
                       "Form-specific task 'cancel submit' used in Custom API context. "
                       "Custom APIs have no form context -- use response Map for error reporting.")

    # ----------------------------------------------------------
    # Expressions
    # ----------------------------------------------------------

    def visit_FunctionCall(self, node: ast.FunctionCall) -> None:
        line = node.span.start_line

        # Extract function name
        func_name = ""
        if isinstance(node.callee, ast.Identifier):
            func_name = node.callee.name
        elif isinstance(node.callee, ast.FieldAccess):
            func_name = node.callee.field

        # DG001: Banned function call
        for banned, msg in self.db.banned_functions.items():
            if func_name == banned:
                self._emit(line, Severity.ERROR, "DG001", msg)

        # DG003: hoursBetween in scheduled scripts
        if self.file_type == FileType.SCHEDULED and func_name == "hoursBetween":
            self._emit(line, Severity.ERROR, "DG003",
                       "hoursBetween not available on Free Trial daily schedules. Use daysBetween.")

        # DG020: Map() or .put() detection
        if func_name == "Map":
            self._has_map_constructor = True
        if func_name == "put":
            self._has_put_call = True

        # DG014: ifnull with threshold context
        if func_name == "ifnull" and len(node.args) >= 2:
            # Check if first arg mentions threshold
            first_str = _expr_to_dotted(node.args[0])
            if "threshold" in first_str.lower():
                if isinstance(node.args[1], ast.Literal) and node.args[1].kind == "number":
                    val = float(node.args[1].value)
                    if val not in self._valid_thresholds:
                        self._emit(line, Severity.WARNING, "DG014",
                                   f"Threshold ifnull fallback is {node.args[1].value}, "
                                   f"expected {self._threshold_fallback} (tier 1) or "
                                   f"{self._dual_threshold_fallback} (dual).")

        # Recurse into callee and args
        self.visit(node.callee)
        for arg in node.args:
            self.visit(arg)

    def visit_FieldAccess(self, node: ast.FieldAccess) -> None:
        line = node.span.start_line
        dotted = _expr_to_dotted(node)

        # DG002: Banned variable reference
        for banned, msg in self.db.banned_variables.items():
            if dotted == banned:
                self._emit(line, Severity.ERROR, "DG002", msg)

        # DG004: Unknown input.FieldName
        if isinstance(node.object, ast.Identifier) and node.object.name == "input":
            if self.file_type != FileType.CUSTOM_API:
                field_name = node.field
                if field_name not in self.db.expense_fields:
                    self._emit(line, Severity.ERROR, "DG004",
                               f"Unknown field 'input.{field_name}'. "
                               "Valid fields: check docs/build-guide/field-link-names.md")

        # DG005: Unguarded query result access
        if isinstance(node.object, ast.Identifier):
            var_name = node.object.name
            if (var_name in self._query_vars
                    and var_name not in self._guarded_vars
                    and var_name not in self._dg005_reported):
                self._dg005_reported.add(var_name)
                self._emit(line, Severity.ERROR, "DG005",
                           f"Query result '{var_name}' accessed without null guard. "
                           f"Add: if ({var_name} != null && {var_name}.count() > 0)")

        # DG018: Unknown zoho system variable
        if dotted.startswith("zoho."):
            if dotted not in self.db.zoho_variable_names:
                # Skip if handled by DG002
                if dotted not in self.db.banned_variables:
                    self._emit(line, Severity.WARNING, "DG018",
                               f"Unknown Zoho variable '{dotted}'. "
                               f"Known: {', '.join(sorted(self.db.zoho_variable_names))}")

        self.visit(node.object)

    def visit_Identifier(self, node: ast.Identifier) -> None:
        # DG002: Banned variable (single-word, e.g. if any are single-word)
        name = node.name
        if name in self.db.banned_variables:
            self._emit(node.span.start_line, Severity.ERROR, "DG002",
                       self.db.banned_variables[name])

    def visit_BinaryExpr(self, node: ast.BinaryExpr) -> None:
        # DG013: Mixed && and || in same expression tree
        if self._has_mixed_logical(node):
            self._emit(node.span.start_line, Severity.WARNING, "DG013",
                       "Mixed && and || on same line. Creator evaluates OR before AND "
                       "(opposite of most languages). Use explicit parentheses.")
        # Don't re-check children for DG013 (already checked the tree)
        # but still visit for other rules
        self.visit(node.left)
        self.visit(node.right)

    def visit_Literal(self, node: ast.Literal) -> None:
        line = node.span.start_line

        # DG008: Single quotes used for text (date literals in the AST have kind="date")
        if node.kind == "date":
            # The lexer already wrapped this in single quotes.
            # Check if the content is actually a date/time or misused text
            content = str(node.value)
            # Strip surrounding quotes if present
            if content.startswith("'") and content.endswith("'"):
                content = content[1:-1]
            if content and not DATE_PATTERN.match(content) and not TIME_PATTERN.match(content):
                self._emit(line, Severity.ERROR, "DG008",
                           f"Single quotes used for text '{content}'. "
                           "Use double quotes for strings; single quotes are for dates/times only.")

        # DG015/DG016: Hardcoded emails in string literals
        if node.kind == "string":
            self._check_emails_in_string(str(node.value), line)

    def visit_FormQuery(self, node: ast.FormQuery) -> None:
        if node.criteria is not None:
            self.visit(node.criteria)

    def visit_IndexAccess(self, node: ast.IndexAccess) -> None:
        self.visit(node.object)
        self.visit(node.index)

    def visit_ListExpr(self, node: ast.ListExpr) -> None:
        for el in node.elements:
            self.visit(el)

    def visit_MapExpr(self, node: ast.MapExpr) -> None:
        for key, val in node.entries:
            self.visit(key)
            self.visit(val)

    def visit_UnaryExpr(self, node: ast.UnaryExpr) -> None:
        self.visit(node.operand)

    def visit_ZohoVariable(self, node: ast.ZohoVariable) -> None:
        pass  # handled via FieldAccess chain

    def visit_ConditionalExpr(self, node: ast.ConditionalExpr) -> None:
        self.visit(node.condition)
        self.visit(node.true_expr)
        self.visit(node.false_expr)

    def visit_OpenUrlStmt(self, node: ast.OpenUrlStmt) -> None:
        self.visit(node.url)
        if node.target is not None:
            self.visit(node.target)

    def visit_DeleteStmt(self, node: ast.DeleteStmt) -> None:
        if node.condition is not None:
            self.visit(node.condition)

    def visit_UpdateStmt(self, node: ast.UpdateStmt) -> None:
        if node.condition is not None:
            self.visit(node.condition)

    def visit_SendsmsStmt(self, node: ast.SendsmsStmt) -> None:
        for p in node.params.params:
            self.visit(p.value)

    # ----------------------------------------------------------
    # DG005 helpers
    # ----------------------------------------------------------

    def _detect_null_guard(self, expr: ast.Expr) -> str | None:
        """Check if expression is a null guard: var != null."""
        if isinstance(expr, ast.BinaryExpr):
            if expr.op == "!=":
                if isinstance(expr.left, ast.Identifier) and isinstance(expr.right, ast.Literal):
                    if expr.right.kind == "null" and expr.left.name in self._query_vars:
                        return expr.left.name
                if isinstance(expr.right, ast.Identifier) and isinstance(expr.left, ast.Literal):
                    if expr.left.kind == "null" and expr.right.name in self._query_vars:
                        return expr.right.name
            # Also check AND-chained guards: var != null && var.count() > 0
            if expr.op == "&&":
                left_guard = self._detect_null_guard(expr.left)
                if left_guard:
                    return left_guard
                return self._detect_null_guard(expr.right)
        return None

    # ----------------------------------------------------------
    # DG013 helper
    # ----------------------------------------------------------

    def _has_mixed_logical(self, node: ast.BinaryExpr) -> bool:
        """Check if a binary expression tree mixes && and || at the same level."""
        ops = set()
        self._collect_logical_ops(node, ops)
        return "&&" in ops and "||" in ops

    def _collect_logical_ops(self, node: ast.Expr, ops: set[str]) -> None:
        if isinstance(node, ast.BinaryExpr):
            if node.op in ("&&", "||"):
                ops.add(node.op)
                self._collect_logical_ops(node.left, ops)
                self._collect_logical_ops(node.right, ops)

    # ----------------------------------------------------------
    # DG015/DG016 helpers
    # ----------------------------------------------------------

    def _check_emails_in_expr(self, expr: ast.Expr) -> None:
        """Check for hardcoded emails in an expression tree."""
        strings = _collect_string_values(expr)
        for s in strings:
            self._check_emails_in_string(s, expr.span.start_line)

    def _check_emails_in_string(self, text: str, line: int) -> None:
        """Check a string value for hardcoded email addresses."""
        # Skip if zoho.adminuserid or zoho.loginuserid context
        for match in EMAIL_PATTERN.finditer(text):
            email = match.group(0)
            domain = email.split("@")[1].lower() if "@" in email else ""
            if any(d in domain for d in self._demo_email_domains) or "demo" in email.lower():
                self._emit(line, Severity.WARNING, "DG015",
                           f"Hardcoded demo/placeholder email '{email}'. "
                           "Replace with role-based lookup for production.")
            else:
                self._emit(line, Severity.INFO, "DG016",
                           f"Hardcoded email '{email}'. Consider using role-based lookup.")


# ============================================================
# Public API
# ============================================================

def lint_source(db: Any, filename: str, source: str, file_type: str | None = None) -> list[Diagnostic]:
    """Parse and lint Deluge source code, return diagnostics.

    Args:
        db: DelugeDB instance with loaded caches.
        filename: Path for diagnostic reporting.
        source: Deluge source code string.
        file_type: Override file type detection.

    Returns:
        List of Diagnostic objects sorted by line.
    """
    if file_type is None:
        file_type = detect_file_type(filename)

    try:
        from forgeds.lang.parser import parse_source, Parser
        from forgeds.lang.lexer import Lexer
        tokens = Lexer(source).tokenize()
        parser = Parser(tokens)
        tree = parser.parse()
    except Exception as e:
        return [_diag(filename, 1, Severity.ERROR, "DG000", f"Parse error: {e}")]

    linter = ASTLinter(db, filename, file_type)
    linter.visit(tree)

    # DG017: Also check for reserved words used as variables via raw source,
    # because keywords like 'return' are consumed by the parser before
    # reaching Assignment nodes (e.g. `return = 42;` is a parse error).
    _check_dg017_raw(db, filename, source, linter.diagnostics)

    # Sort by line number
    linter.diagnostics.sort(key=lambda d: d.line)
    return linter.diagnostics


def _check_dg017_raw(db: Any, filename: str, source: str, diags: list[Diagnostic]) -> None:
    """Supplement DG017: catch reserved-word assignments the parser can't represent."""
    # Lines already reported by the AST visitor
    reported_lines = {d.line for d in diags if d.rule == "DG017"}
    for i, line in enumerate(source.splitlines()):
        lineno = i + 1
        if lineno in reported_lines:
            continue
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        m = re.match(r"(\w+)\s*=[^=]", stripped)
        if m:
            var_name = m.group(1)
            if var_name in db.reserved_words:
                diags.append(_diag(filename, lineno, Severity.ERROR, "DG017",
                                   f"Reserved word '{var_name}' cannot be used as a variable name. "
                                   f"Reserved: {', '.join(sorted(db.reserved_words))}"))


def lint_file(db: Any, filepath: str) -> list[Diagnostic]:
    """Read and lint a .dg file."""
    try:
        with open(filepath, encoding="utf-8") as f:
            source = f.read()
    except (OSError, UnicodeDecodeError) as e:
        return [_diag(filepath, 0, Severity.ERROR, "DG000", f"Cannot read file: {e}")]

    return lint_source(db, filepath, source)
