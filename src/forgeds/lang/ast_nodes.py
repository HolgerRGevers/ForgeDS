"""AST node definitions for the Deluge language.

Every node carries a SourceSpan for diagnostic reporting and LSP.
The Visitor base class enables clean traversal (linter, analyzer, codegen).

Design rule enforced structurally: ParamBlock (action attributes [])
can only appear as children of statement nodes (control flow {}),
never bare.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from forgeds.lang.tokens import SourceSpan

if TYPE_CHECKING:
    from forgeds.schema.types import DelugeType


# ============================================================
# Base classes
# ============================================================

@dataclass
class Node:
    """Base for all AST nodes."""
    span: SourceSpan


@dataclass
class Expr(Node):
    """Base for all expression nodes.

    ``resolved_type`` is populated post-parse by the TypeChecker,
    not by the parser.  It remains None until type inference runs.
    """
    resolved_type: DelugeType | None = field(default=None, init=False, repr=False)


@dataclass
class Stmt(Node):
    """Base for all statement nodes."""
    pass


# ============================================================
# Expressions
# ============================================================

@dataclass
class Literal(Expr):
    """Numeric, string, boolean, null, or date literal."""
    value: Any            # int | float | str | bool | None
    kind: str = "string"  # "number", "string", "bool", "null", "date"


@dataclass
class Identifier(Expr):
    """A variable or form name reference."""
    name: str


@dataclass
class ZohoVariable(Expr):
    """A zoho.* system variable (e.g. zoho.loginuser, zoho.currentdate)."""
    path: str  # full dotted path: "zoho.loginuser"


@dataclass
class FieldAccess(Expr):
    """Dot access: object.field (input.Name, rec.Status, resp.toMap())."""
    object: Expr
    field: str


@dataclass
class BinaryExpr(Expr):
    """Binary operation: left op right."""
    left: Expr
    op: str       # "+", "-", "*", "/", "%", "==", "!=", "<", ">", "<=", ">=", "&&", "||"
    right: Expr


@dataclass
class UnaryExpr(Expr):
    """Unary operation: op operand (!, -)."""
    op: str
    operand: Expr


@dataclass
class FunctionCall(Expr):
    """Function or method call: name(args) or obj.method(args)."""
    callee: Expr               # Identifier or FieldAccess
    args: list[Expr] = field(default_factory=list)


@dataclass
class FormQuery(Expr):
    """Form query: FormName[criteria]. Returns collection or null."""
    form: str
    criteria: Expr | None = None


@dataclass
class IndexAccess(Expr):
    """Index/subscript access: list[0], map.get("key")."""
    object: Expr
    index: Expr


@dataclass
class ListExpr(Expr):
    """List literal: {"a", "b", "c"} or List()."""
    elements: list[Expr] = field(default_factory=list)


@dataclass
class MapExpr(Expr):
    """Map literal: {"key1": val1, "key2": val2} or Map()."""
    entries: list[tuple[Expr, Expr]] = field(default_factory=list)


@dataclass
class ConditionalExpr(Expr):
    """Ternary / inline conditional (if Deluge ever supports it)."""
    condition: Expr
    true_expr: Expr
    false_expr: Expr


# ============================================================
# Param blocks — action attributes inside [] brackets
# ============================================================

@dataclass
class ParamAssignment(Node):
    """Single field assignment inside a param block: field = value or field : value."""
    name: str
    value: Expr
    separator: str = "="  # "=" for insert, ":" for sendmail/invokeUrl


@dataclass
class ParamBlock(Node):
    """Bracket-delimited parameter block: [ field=val, field=val ].

    Design rule: can only appear as child of a statement node
    (InsertStmt, SendmailStmt, etc.), never bare.
    """
    params: list[ParamAssignment] = field(default_factory=list)


# ============================================================
# Statements
# ============================================================

@dataclass
class Block(Stmt):
    """A { ... } block containing a list of statements."""
    body: list[Stmt] = field(default_factory=list)


@dataclass
class ExprStmt(Stmt):
    """Expression used as a statement (e.g. standalone function call)."""
    expr: Expr


@dataclass
class Assignment(Stmt):
    """Variable assignment: target = value, or target += value, etc."""
    target: Expr          # Identifier or FieldAccess
    op: str               # "=", "+=", "-=", "*=", "/=", "%="
    value: Expr


@dataclass
class IfStmt(Stmt):
    """if (condition) { body } else { else_body }."""
    condition: Expr
    body: Stmt                     # typically a Block
    else_body: Stmt | None = None  # Block or another IfStmt (else if)


@dataclass
class ForEachStmt(Stmt):
    """for each var in collection { body }."""
    var_name: str
    collection: Expr
    body: Stmt


@dataclass
class WhileStmt(Stmt):
    """while (condition) { body }."""
    condition: Expr
    body: Stmt


@dataclass
class TryCatchStmt(Stmt):
    """try { try_body } catch (var) { catch_body }."""
    try_body: Stmt
    catch_var: str
    catch_body: Stmt


@dataclass
class ReturnStmt(Stmt):
    """return; or return expr;"""
    value: Expr | None = None


@dataclass
class InsertStmt(Stmt):
    """insert into TableName [ field = value, ... ]; or row = insert into ..."""
    table: str
    params: ParamBlock
    result_var: str | None = None  # if captured: row = insert into ...


@dataclass
class DeleteStmt(Stmt):
    """delete from TableName where criteria; (rare in Creator)."""
    table: str
    condition: Expr | None = None


@dataclass
class UpdateStmt(Stmt):
    """update TableName where criteria; (typically via rec.field = val in loop)."""
    table: str
    condition: Expr | None = None


@dataclass
class SendmailStmt(Stmt):
    """sendmail [ from: to: subject: message: ];"""
    params: ParamBlock


@dataclass
class SendsmsStmt(Stmt):
    """sendsms [ to: message: ];"""
    params: ParamBlock


@dataclass
class InvokeUrlStmt(Stmt):
    """invokeUrl [ url: type: parameters: headers: ]; or resp = invokeUrl [...]"""
    params: ParamBlock
    result_var: str | None = None


@dataclass
class AlertStmt(Stmt):
    """alert "message";"""
    message: Expr


@dataclass
class InfoStmt(Stmt):
    """info expression; (debug log)."""
    expr: Expr


@dataclass
class CancelSubmitStmt(Stmt):
    """cancel submit; (form-workflow only)."""
    pass


@dataclass
class OpenUrlStmt(Stmt):
    """openUrl(url, target);"""
    url: Expr
    target: Expr | None = None


# ============================================================
# Program root
# ============================================================

@dataclass
class Program(Node):
    """Root node: a complete Deluge script."""
    body: list[Stmt] = field(default_factory=list)


# ============================================================
# Visitor
# ============================================================

class Visitor:
    """Base visitor for AST traversal.

    Override visit_<NodeClassName> methods. Unhandled nodes call
    generic_visit which recurses into children.
    """

    def visit(self, node: Node) -> Any:
        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: Node) -> None:
        """Default: recurse into all child nodes."""
        for attr_name in vars(node):
            if attr_name == "span":
                continue
            val = getattr(node, attr_name)
            if isinstance(val, Node):
                self.visit(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, Node):
                        self.visit(item)
                    elif isinstance(item, tuple):
                        for elem in item:
                            if isinstance(elem, Node):
                                self.visit(elem)
