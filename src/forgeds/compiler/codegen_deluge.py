"""AST-to-Deluge code generator (pretty-printer).

Walks the typed AST and emits syntactically valid Deluge source code.
Closes the round-trip: parse .dg -> AST -> codegen -> identical .dg.

Usage:
    from forgeds.lang.parser import parse_source
    from forgeds.compiler.codegen_deluge import generate

    tree = parse_source(source)
    output = generate(tree)
"""

from __future__ import annotations

from forgeds.lang import ast_nodes as ast


class DelugeGenerator(ast.Visitor):
    """Walk the AST and emit Deluge source code."""

    def __init__(self) -> None:
        self._lines: list[str] = []
        self._indent = 0
        self._indent_str = "\t"

    # ----------------------------------------------------------
    # Output helpers
    # ----------------------------------------------------------

    def _emit(self, text: str) -> None:
        """Emit a line at current indentation."""
        prefix = self._indent_str * self._indent
        self._lines.append(prefix + text)

    def _emit_raw(self, text: str) -> None:
        """Emit a line with no indentation."""
        self._lines.append(text)

    def _push(self) -> None:
        self._indent += 1

    def _pop(self) -> None:
        self._indent = max(0, self._indent - 1)

    def result(self) -> str:
        return "\n".join(self._lines)

    # ----------------------------------------------------------
    # Program
    # ----------------------------------------------------------

    def visit_Program(self, node: ast.Program) -> None:
        for i, stmt in enumerate(node.body):
            self.visit(stmt)
            # Add blank line between top-level statements for readability
            if i < len(node.body) - 1:
                self._emit_raw("")

    # ----------------------------------------------------------
    # Statements
    # ----------------------------------------------------------

    def visit_Block(self, node: ast.Block) -> None:
        self._emit("{")
        self._push()
        for stmt in node.body:
            self.visit(stmt)
        self._pop()
        self._emit("}")

    def visit_IfStmt(self, node: ast.IfStmt) -> None:
        cond = self._expr(node.condition)
        self._emit(f"if ({cond})")
        self._emit_block(node.body)
        if node.else_body is not None:
            if isinstance(node.else_body, ast.IfStmt):
                # else if — emit on same conceptual level
                self._lines[-1] = self._lines[-1]  # keep closing }
                self._emit("else " + self._generate_if_inline(node.else_body))
            else:
                self._emit("else")
                self._emit_block(node.else_body)

    def _generate_if_inline(self, node: ast.IfStmt) -> str:
        """Generate an if statement as a string for else-if chaining."""
        # Save state, generate, restore
        saved_lines = self._lines
        saved_indent = self._indent
        self._lines = []
        self.visit_IfStmt(node)
        result = "\n".join(self._lines)
        self._lines = saved_lines
        self._indent = saved_indent
        return result

    def visit_ForEachStmt(self, node: ast.ForEachStmt) -> None:
        coll = self._expr(node.collection)
        self._emit(f"for each {node.var_name} in {coll}")
        self._emit_block(node.body)

    def visit_WhileStmt(self, node: ast.WhileStmt) -> None:
        cond = self._expr(node.condition)
        self._emit(f"while ({cond})")
        self._emit_block(node.body)

    def visit_TryCatchStmt(self, node: ast.TryCatchStmt) -> None:
        self._emit("try")
        self._emit_block(node.try_body)
        self._emit(f"catch ({node.catch_var})")
        self._emit_block(node.catch_body)

    def visit_ReturnStmt(self, node: ast.ReturnStmt) -> None:
        if node.value is not None:
            self._emit(f"return {self._expr(node.value)};")
        else:
            self._emit("return;")

    def visit_AlertStmt(self, node: ast.AlertStmt) -> None:
        self._emit(f"alert {self._expr(node.message)};")

    def visit_InfoStmt(self, node: ast.InfoStmt) -> None:
        self._emit(f"info {self._expr(node.expr)};")

    def visit_CancelSubmitStmt(self, node: ast.CancelSubmitStmt) -> None:
        self._emit("cancel submit;")

    def visit_Assignment(self, node: ast.Assignment) -> None:
        target = self._expr(node.target)
        value = self._expr(node.value)
        self._emit(f"{target} {node.op} {value};")

    def visit_ExprStmt(self, node: ast.ExprStmt) -> None:
        self._emit(f"{self._expr(node.expr)};")

    def visit_InsertStmt(self, node: ast.InsertStmt) -> None:
        prefix = ""
        if node.result_var:
            prefix = f"{node.result_var} = "
        self._emit(f"{prefix}insert into {node.table}")
        self._emit_param_block(node.params)
        self._emit(";")

    def visit_DeleteStmt(self, node: ast.DeleteStmt) -> None:
        parts = ["delete from", node.table]
        if node.condition is not None:
            parts.append("where")
            parts.append(self._expr(node.condition))
        self._emit(" ".join(parts) + ";")

    def visit_UpdateStmt(self, node: ast.UpdateStmt) -> None:
        parts = ["update", node.table]
        if node.condition is not None:
            parts.append("where")
            parts.append(self._expr(node.condition))
        self._emit(" ".join(parts) + ";")

    def visit_SendmailStmt(self, node: ast.SendmailStmt) -> None:
        self._emit("sendmail")
        self._emit_param_block(node.params)
        self._emit(";")

    def visit_SendsmsStmt(self, node: ast.SendsmsStmt) -> None:
        self._emit("sendsms")
        self._emit_param_block(node.params)
        self._emit(";")

    def visit_InvokeUrlStmt(self, node: ast.InvokeUrlStmt) -> None:
        prefix = ""
        if node.result_var:
            prefix = f"{node.result_var} = "
        self._emit(f"{prefix}invokeUrl")
        self._emit_param_block(node.params)
        self._emit(";")

    def visit_OpenUrlStmt(self, node: ast.OpenUrlStmt) -> None:
        args = [self._expr(node.url)]
        if node.target is not None:
            args.append(self._expr(node.target))
        self._emit(f"openUrl({', '.join(args)});")

    # ----------------------------------------------------------
    # Param block
    # ----------------------------------------------------------

    def _emit_param_block(self, block: ast.ParamBlock) -> None:
        self._emit("[")
        self._push()
        for p in block.params:
            val = self._expr(p.value)
            self._emit(f"{p.name} {p.separator} {val}")
        self._pop()
        self._emit("]")

    # ----------------------------------------------------------
    # Block helper
    # ----------------------------------------------------------

    def _emit_block(self, stmt: ast.Stmt) -> None:
        """Emit a block statement (wraps in {} if not already a Block)."""
        if isinstance(stmt, ast.Block):
            self._emit("{")
            self._push()
            for s in stmt.body:
                self.visit(s)
            self._pop()
            self._emit("}")
        else:
            self._emit("{")
            self._push()
            self.visit(stmt)
            self._pop()
            self._emit("}")

    # ----------------------------------------------------------
    # Expressions (returned as strings, not emitted)
    # ----------------------------------------------------------

    def _expr(self, node: ast.Expr) -> str:
        """Convert an expression AST node to a string."""
        if isinstance(node, ast.Literal):
            return self._literal(node)
        if isinstance(node, ast.Identifier):
            return node.name
        if isinstance(node, ast.ZohoVariable):
            return node.path
        if isinstance(node, ast.FieldAccess):
            return f"{self._expr(node.object)}.{node.field}"
        if isinstance(node, ast.BinaryExpr):
            left = self._expr(node.left)
            right = self._expr(node.right)
            return f"{left} {node.op} {right}"
        if isinstance(node, ast.UnaryExpr):
            return f"{node.op}{self._expr(node.operand)}"
        if isinstance(node, ast.FunctionCall):
            callee = self._expr(node.callee)
            args = ", ".join(self._expr(a) for a in node.args)
            return f"{callee}({args})"
        if isinstance(node, ast.FormQuery):
            if node.criteria is not None:
                return f"{node.form}[{self._expr(node.criteria)}]"
            return f"{node.form}[]"
        if isinstance(node, ast.IndexAccess):
            return f"{self._expr(node.object)}[{self._expr(node.index)}]"
        if isinstance(node, ast.ListExpr):
            elements = ", ".join(self._expr(e) for e in node.elements)
            return "{" + elements + "}"
        if isinstance(node, ast.MapExpr):
            entries = ", ".join(
                f"{self._expr(k)}: {self._expr(v)}" for k, v in node.entries
            )
            return "{" + entries + "}"
        if isinstance(node, ast.ConditionalExpr):
            return (f"{self._expr(node.condition)} ? "
                    f"{self._expr(node.true_expr)} : "
                    f"{self._expr(node.false_expr)}")
        return f"<unknown:{type(node).__name__}>"

    def _literal(self, node: ast.Literal) -> str:
        if node.kind == "string":
            # Re-add surrounding double quotes
            val = str(node.value).replace("\\", "\\\\").replace('"', '\\"')
            return f'"{val}"'
        if node.kind == "number":
            val = node.value
            if isinstance(val, float) and val == int(val):
                return str(int(val))
            return str(val)
        if node.kind == "bool":
            return "true" if node.value else "false"
        if node.kind == "null":
            return "null"
        if node.kind == "date":
            # Date literals are stored with surrounding quotes
            val = str(node.value)
            if not val.startswith("'"):
                return f"'{val}'"
            return val
        return str(node.value)


# ============================================================
# Public API
# ============================================================

def generate(tree: ast.Program) -> str:
    """Generate Deluge source code from an AST."""
    gen = DelugeGenerator()
    gen.visit(tree)
    return gen.result()


def round_trip(source: str) -> str:
    """Parse Deluge source and re-generate it. For testing."""
    from forgeds.lang.parser import parse_source
    tree = parse_source(source)
    return generate(tree)
