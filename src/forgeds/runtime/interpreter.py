"""Tree-walking interpreter for the Deluge language.

Evaluates a Deluge AST directly. Side effects (sendmail, insert into,
invokeUrl) are logged stubs. input.* fields come from a provided dict.
zoho.* variables use test defaults.

Usage:
    from forgeds.runtime.interpreter import Interpreter

    result = Interpreter.run_source(source, input_data={"Name": "Test"})
    print(result.side_effects.summary())
    print(result.variables)

    # Or for more control:
    interp = Interpreter(input_data={"Name": "Test"})
    interp.execute(source)
    print(interp.side_effects.summary())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from forgeds._shared.diagnostics import Severity, Diagnostic, build_ai_prompt
from forgeds.lang import ast_nodes as ast
from forgeds.lang.parser import parse_source
from forgeds.runtime.environment import Environment
from forgeds.runtime.stubs import (
    SideEffectLog, BUILTIN_FUNCTIONS, METHOD_STUBS,
)


# ============================================================
# Control flow signals (exceptions used for flow control)
# ============================================================

class ReturnSignal(Exception):
    """Raised to unwind the stack on a return statement."""
    def __init__(self, value: Any = None) -> None:
        self.value = value


class BreakSignal(Exception):
    """Raised on break (not yet in Deluge AST, but prepared)."""
    pass


class CancelSubmitSignal(Exception):
    """Raised on cancel submit — halts form workflow execution."""
    pass


class InterpreterError(Exception):
    """Runtime error during script execution."""
    def __init__(self, message: str, line: int = 0) -> None:
        super().__init__(message)
        self.line = line


# ============================================================
# Execution result
# ============================================================

@dataclass
class ExecutionResult:
    """Result of executing a Deluge script."""
    return_value: Any = None
    variables: dict[str, Any] = field(default_factory=dict)
    side_effects: SideEffectLog = field(default_factory=SideEffectLog)
    info_log: list[str] = field(default_factory=list)
    alert_log: list[str] = field(default_factory=list)
    cancelled: bool = False
    errors: list[Diagnostic] = field(default_factory=list)


# ============================================================
# Interpreter
# ============================================================

class Interpreter(ast.Visitor):
    """Tree-walking evaluator for Deluge AST."""

    def __init__(
        self,
        input_data: dict[str, Any] | None = None,
        zoho_overrides: dict[str, Any] | None = None,
        filename: str = "<script>",
    ) -> None:
        self.env = Environment(input_data)
        self.side_effects = SideEffectLog()
        self.info_log: list[str] = []
        self.alert_log: list[str] = []
        self._return_value: Any = None
        self._cancelled = False
        self._errors: list[Diagnostic] = []
        self._filename = filename
        self._source_lines: list[str] = []

        # Apply zoho overrides
        if zoho_overrides:
            for k, v in zoho_overrides.items():
                self.env.set_zoho(k, v)

        # Pre-define input as an accessible object
        self.env.define("input", _InputProxy(self.env))

    def _runtime_diag(self, line: int, message: str, technical: str = "") -> Diagnostic:
        """Build a Diagnostic for a runtime error."""
        src_line = ""
        if self._source_lines and 0 < line <= len(self._source_lines):
            src_line = self._source_lines[line - 1]
        return Diagnostic(
            file=self._filename, line=line, rule="RT001",
            severity=Severity.ERROR, message=message,
            ai_prompt=build_ai_prompt(
                file=self._filename, line=line, rule="RT001",
                message=message, source_line=src_line,
                context="This is a runtime error from the local Deluge interpreter.",
            ),
            technical=technical or f"InterpreterError at line {line}: {message}",
            source_line=src_line,
        )

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    def execute(self, source: str) -> ExecutionResult:
        """Parse and execute a Deluge script."""
        self._source_lines = source.splitlines()

        try:
            tree = parse_source(source)
        except Exception as e:
            from forgeds.lang.lexer import LexError
            line = getattr(e, "line", 1)
            if isinstance(e, LexError):
                line = e.line
            elif hasattr(e, "token"):
                line = e.token.line
            return ExecutionResult(errors=[Diagnostic(
                file=self._filename, line=line, rule="RT000",
                severity=Severity.ERROR,
                message=f"Script could not be parsed: {e}",
                ai_prompt=build_ai_prompt(
                    file=self._filename, line=line, rule="RT000",
                    message=str(e),
                    context="This is a parse error — the script cannot be executed.",
                ),
                technical=f"{type(e).__name__}: {e}",
            )])

        try:
            self.visit(tree)
        except ReturnSignal as r:
            self._return_value = r.value
        except CancelSubmitSignal:
            self._cancelled = True
        except InterpreterError as e:
            self._errors.append(self._runtime_diag(e.line, str(e)))
        except Exception as e:
            self._errors.append(self._runtime_diag(0, f"Unexpected runtime error: {e}",
                                                   technical=f"{type(e).__name__}: {e}"))

        return ExecutionResult(
            return_value=self._return_value,
            variables=self.env.dump(),
            side_effects=self.side_effects,
            info_log=self.info_log,
            alert_log=self.alert_log,
            cancelled=self._cancelled,
            errors=self._errors,
        )

    @staticmethod
    def run_source(
        source: str,
        input_data: dict[str, Any] | None = None,
        zoho_overrides: dict[str, Any] | None = None,
        filename: str = "<script>",
    ) -> ExecutionResult:
        """Convenience: create interpreter, execute, return result."""
        interp = Interpreter(input_data=input_data, zoho_overrides=zoho_overrides,
                             filename=filename)
        return interp.execute(source)

    # ----------------------------------------------------------
    # Program
    # ----------------------------------------------------------

    def visit_Program(self, node: ast.Program) -> None:
        for stmt in node.body:
            self.visit(stmt)

    # ----------------------------------------------------------
    # Statements
    # ----------------------------------------------------------

    def visit_Block(self, node: ast.Block) -> None:
        # Deluge blocks don't create new variable scopes — variables
        # defined inside if/for/while are visible outside.
        for stmt in node.body:
            self.visit(stmt)

    def visit_IfStmt(self, node: ast.IfStmt) -> None:
        condition = self.visit(node.condition)
        if _truthy(condition):
            self.visit(node.body)
        elif node.else_body is not None:
            self.visit(node.else_body)

    def visit_ForEachStmt(self, node: ast.ForEachStmt) -> None:
        collection = self.visit(node.collection)
        if collection is None:
            return
        if isinstance(collection, dict):
            items = list(collection.values())
        elif isinstance(collection, (list, tuple)):
            items = list(collection)
        else:
            items = [collection]

        self.env.push_scope()
        try:
            for item in items:
                self.env.define(node.var_name, item)
                self.visit(node.body)
        finally:
            self.env.pop_scope()

    def visit_WhileStmt(self, node: ast.WhileStmt) -> None:
        max_iterations = 10000  # Safety limit
        count = 0
        while _truthy(self.visit(node.condition)):
            self.visit(node.body)
            count += 1
            if count >= max_iterations:
                raise InterpreterError(
                    f"While loop exceeded {max_iterations} iterations",
                    node.span.start_line,
                )

    def visit_TryCatchStmt(self, node: ast.TryCatchStmt) -> None:
        try:
            self.visit(node.try_body)
        except (InterpreterError, Exception) as e:
            self.env.push_scope()
            self.env.define(node.catch_var, str(e))
            try:
                self.visit(node.catch_body)
            finally:
                self.env.pop_scope()

    def visit_ReturnStmt(self, node: ast.ReturnStmt) -> None:
        value = None
        if node.value is not None:
            value = self.visit(node.value)
        raise ReturnSignal(value)

    def visit_ExprStmt(self, node: ast.ExprStmt) -> None:
        self.visit(node.expr)

    # ----------------------------------------------------------
    # Assignment
    # ----------------------------------------------------------

    def visit_Assignment(self, node: ast.Assignment) -> None:
        value = self.visit(node.value)

        if isinstance(node.target, ast.Identifier):
            name = node.target.name
            if node.op == "=":
                self.env.set(name, value)
            else:
                current = self.env.get(name)
                self.env.set(name, _compound_assign(current, node.op, value))

        elif isinstance(node.target, ast.FieldAccess):
            # input.Field = value or obj.field = value
            self._set_field(node.target, value, node.op)

    def _set_field(self, target: ast.FieldAccess, value: Any, op: str) -> None:
        """Handle field assignment: obj.field = value."""
        # input.Field = value
        if isinstance(target.object, ast.Identifier) and target.object.name == "input":
            if op == "=":
                self.env.set_input(target.field, value)
            else:
                current = self.env.get_input(target.field)
                self.env.set_input(target.field, _compound_assign(current, op, value))
            return

        # General case: obj.field = value
        obj = self.visit(target.object)
        if isinstance(obj, dict):
            if op == "=":
                obj[target.field] = value
            else:
                obj[target.field] = _compound_assign(obj.get(target.field), op, value)

    # ----------------------------------------------------------
    # Action statements (side effects)
    # ----------------------------------------------------------

    def visit_InsertStmt(self, node: ast.InsertStmt) -> None:
        params = self._eval_params(node.params)
        result = self.side_effects.record("insert", {
            "table": node.table, **params,
        })
        if node.result_var:
            self.env.set(node.result_var, result)

    def visit_DeleteStmt(self, node: ast.DeleteStmt) -> None:
        condition = self.visit(node.condition) if node.condition else None
        self.side_effects.record("delete", {
            "table": node.table, "condition": condition,
        })

    def visit_UpdateStmt(self, node: ast.UpdateStmt) -> None:
        condition = self.visit(node.condition) if node.condition else None
        self.side_effects.record("update", {
            "table": node.table, "condition": condition,
        })

    def visit_SendmailStmt(self, node: ast.SendmailStmt) -> None:
        params = self._eval_params(node.params)
        self.side_effects.record("sendmail", params)

    def visit_SendsmsStmt(self, node: ast.SendsmsStmt) -> None:
        params = self._eval_params(node.params)
        self.side_effects.record("sendsms", params)

    def visit_InvokeUrlStmt(self, node: ast.InvokeUrlStmt) -> None:
        params = self._eval_params(node.params)
        result = self.side_effects.record("invokeUrl", params)
        if node.result_var:
            self.env.set(node.result_var, result)

    def visit_AlertStmt(self, node: ast.AlertStmt) -> None:
        message = self.visit(node.message)
        self.alert_log.append(str(message))
        self.side_effects.record("alert", {"message": str(message)})

    def visit_InfoStmt(self, node: ast.InfoStmt) -> None:
        value = self.visit(node.expr)
        self.info_log.append(str(value))
        self.side_effects.record("info", {"value": str(value)})

    def visit_CancelSubmitStmt(self, node: ast.CancelSubmitStmt) -> None:
        self.side_effects.record("cancel_submit", {})
        raise CancelSubmitSignal()

    def visit_OpenUrlStmt(self, node: ast.OpenUrlStmt) -> None:
        url = self.visit(node.url)
        target = self.visit(node.target) if node.target else None
        self.side_effects.record("openUrl", {"url": url, "target": target})

    # ----------------------------------------------------------
    # Param block evaluation
    # ----------------------------------------------------------

    def _eval_params(self, block: ast.ParamBlock) -> dict[str, Any]:
        return {p.name: self.visit(p.value) for p in block.params}

    # ----------------------------------------------------------
    # Expressions
    # ----------------------------------------------------------

    def visit_Literal(self, node: ast.Literal) -> Any:
        return node.value

    def visit_Identifier(self, node: ast.Identifier) -> Any:
        name = node.name
        # Check built-in constructors
        if name == "Map":
            return dict  # Return the type for Map() calls
        if name == "List":
            return list
        try:
            return self.env.get(name)
        except NameError:
            return None  # Undefined variables return null in Deluge

    def visit_ZohoVariable(self, node: ast.ZohoVariable) -> Any:
        return self.env.get_zoho(node.path)

    def visit_FieldAccess(self, node: ast.FieldAccess) -> Any:
        obj = self.visit(node.object)

        # input.FieldName
        if isinstance(node.object, ast.Identifier) and node.object.name == "input":
            return self.env.get_input(node.field)

        # zoho.* chain
        if isinstance(node.object, ast.Identifier) and node.object.name == "zoho":
            return self.env.get_zoho(f"zoho.{node.field}")
        # zoho.device.type and similar deeper chains
        if isinstance(node.object, ast.FieldAccess):
            full_path = _dotted_path(node)
            if full_path.startswith("zoho."):
                return self.env.get_zoho(full_path)

        # Dict access: obj.field -> obj["field"]
        if isinstance(obj, dict):
            return obj.get(node.field)

        # Object attribute access
        if obj is not None and hasattr(obj, node.field):
            return getattr(obj, node.field)

        return None

    def visit_BinaryExpr(self, node: ast.BinaryExpr) -> Any:
        left = self.visit(node.left)
        # Short-circuit evaluation for logical operators
        if node.op == "&&":
            return left if not _truthy(left) else self.visit(node.right)
        if node.op == "||":
            return left if _truthy(left) else self.visit(node.right)

        right = self.visit(node.right)
        return _binary_op(left, node.op, right, node.span.start_line)

    def visit_UnaryExpr(self, node: ast.UnaryExpr) -> Any:
        operand = self.visit(node.operand)
        if node.op == "!":
            return not _truthy(operand)
        if node.op == "-":
            if isinstance(operand, (int, float)):
                return -operand
            return 0
        return operand

    def visit_FunctionCall(self, node: ast.FunctionCall) -> Any:
        # Method call: obj.method(args)
        if isinstance(node.callee, ast.FieldAccess):
            obj = self.visit(node.callee.object)
            method_name = node.callee.field
            args = [self.visit(a) for a in node.args]

            # Check method stubs
            if method_name in METHOD_STUBS:
                stub = METHOD_STUBS[method_name]
                try:
                    return stub(obj, *args)
                except (TypeError, AttributeError):
                    return None

            # Dict/list native methods
            if isinstance(obj, dict) and method_name == "keys":
                return list(obj.keys())
            if isinstance(obj, dict) and method_name == "values":
                return list(obj.values())

            return None

        # Standalone function call: func(args)
        if isinstance(node.callee, ast.Identifier):
            func_name = node.callee.name
            args = [self.visit(a) for a in node.args]

            # Constructor calls: Map(), List()
            if func_name == "Map":
                return {}
            if func_name == "List":
                return list(args) if args else []
            if func_name == "Collection":
                return list(args) if args else []

            # Built-in functions
            if func_name in BUILTIN_FUNCTIONS:
                try:
                    return BUILTIN_FUNCTIONS[func_name](*args)
                except (TypeError, ValueError):
                    return None

            # Unknown function — return None
            return None

        return None

    def visit_FormQuery(self, node: ast.FormQuery) -> Any:
        # Form queries return a stubbed list
        # In a real interpreter this would query a data store
        return []

    def visit_IndexAccess(self, node: ast.IndexAccess) -> Any:
        obj = self.visit(node.object)
        index = self.visit(node.index)
        if isinstance(obj, list) and isinstance(index, int):
            return obj[index] if 0 <= index < len(obj) else None
        if isinstance(obj, dict):
            return obj.get(str(index))
        return None

    def visit_ListExpr(self, node: ast.ListExpr) -> Any:
        return [self.visit(e) for e in node.elements]

    def visit_MapExpr(self, node: ast.MapExpr) -> Any:
        result: dict[str, Any] = {}
        for key, val in node.entries:
            k = self.visit(key)
            v = self.visit(val)
            result[str(k) if k is not None else ""] = v
        return result

    def visit_ConditionalExpr(self, node: ast.ConditionalExpr) -> Any:
        condition = self.visit(node.condition)
        if _truthy(condition):
            return self.visit(node.true_expr)
        return self.visit(node.false_expr)


# ============================================================
# Helpers
# ============================================================

class _InputProxy:
    """Proxy object for input.* field access."""
    def __init__(self, env: Environment) -> None:
        self._env = env

    def __getattr__(self, name: str) -> Any:
        return self._env.get_input(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            self._env.set_input(name, value)


def _dotted_path(node: ast.Expr) -> str:
    """Flatten a FieldAccess chain to a dotted string."""
    if isinstance(node, ast.Identifier):
        return node.name
    if isinstance(node, ast.FieldAccess):
        return _dotted_path(node.object) + "." + node.field
    return ""


def _truthy(value: Any) -> bool:
    """Deluge truthiness: null/false/0/empty string are falsy."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return len(value) > 0
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def _binary_op(left: Any, op: str, right: Any, line: int = 0) -> Any:
    """Evaluate a binary operation."""
    # String concatenation
    if op == "+" and (isinstance(left, str) or isinstance(right, str)):
        return str(left if left is not None else "") + str(right if right is not None else "")

    # Arithmetic
    if op == "+":
        return _num(left) + _num(right)
    if op == "-":
        return _num(left) - _num(right)
    if op == "*":
        return _num(left) * _num(right)
    if op == "/":
        r = _num(right)
        if r == 0:
            raise InterpreterError("Division by zero", line)
        return _num(left) / r
    if op == "%":
        r = _num(right)
        if r == 0:
            raise InterpreterError("Modulo by zero", line)
        return _num(left) % r

    # Comparison
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == "<":
        return _num(left) < _num(right)
    if op == ">":
        return _num(left) > _num(right)
    if op == "<=":
        return _num(left) <= _num(right)
    if op == ">=":
        return _num(left) >= _num(right)

    return None


def _num(value: Any) -> int | float:
    """Coerce to number for arithmetic."""
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            return int(value) if "." not in value else float(value)
        except ValueError:
            return 0
    return 0


def _compound_assign(current: Any, op: str, value: Any) -> Any:
    """Evaluate compound assignment: +=, -=, *=, /=, %=."""
    if op == "+=":
        if isinstance(current, str) or isinstance(value, str):
            return str(current or "") + str(value or "")
        return _num(current) + _num(value)
    if op == "-=":
        return _num(current) - _num(value)
    if op == "*=":
        return _num(current) * _num(value)
    if op == "/=":
        r = _num(value)
        return _num(current) / r if r != 0 else 0
    if op == "%=":
        r = _num(value)
        return _num(current) % r if r != 0 else 0
    return value
