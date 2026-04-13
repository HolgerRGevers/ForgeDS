"""Type inference for Deluge AST nodes.

Walks a parsed Program and populates ``resolved_type`` on every Expr
node using the SchemaRegistry for field lookups and the type algebra
in ``forgeds.schema.types`` for binary operations.

Usage::

    from forgeds.compiler.type_checker import check_types

    tree = parse_source(source)
    check_types(tree, form_name="expense_claims")
    # tree now has resolved_type on all Expr nodes
"""

from __future__ import annotations

from forgeds.lang import ast_nodes as ast
from forgeds.schema import (
    DelugeType,
    LITERAL_KIND_MAP,
    get_registry,
    result_type,
)


# Well-known zoho variable types
_ZOHO_VAR_TYPES: dict[str, DelugeType] = {
    "zoho.loginuser": DelugeType.TEXT,
    "zoho.loginuserid": DelugeType.TEXT,
    "zoho.adminuser": DelugeType.TEXT,
    "zoho.adminuserid": DelugeType.TEXT,
    "zoho.currentdate": DelugeType.DATE,
    "zoho.currenttime": DelugeType.DATETIME,
    "zoho.appname": DelugeType.TEXT,
    "zoho.appuri": DelugeType.TEXT,
    "zoho.ipaddress": DelugeType.TEXT,
    "zoho.creator.url": DelugeType.TEXT,
}

# Common built-in function return types
_FUNCTION_RETURN_TYPES: dict[str, DelugeType] = {
    # String functions
    "length": DelugeType.NUMBER,
    "size": DelugeType.NUMBER,
    "count": DelugeType.NUMBER,
    "trim": DelugeType.TEXT,
    "toLower": DelugeType.TEXT,
    "toUpper": DelugeType.TEXT,
    "toLowerCase": DelugeType.TEXT,
    "toUpperCase": DelugeType.TEXT,
    "substring": DelugeType.TEXT,
    "getSuffix": DelugeType.TEXT,
    "getPrefix": DelugeType.TEXT,
    "replaceAll": DelugeType.TEXT,
    "replaceFirst": DelugeType.TEXT,
    "contains": DelugeType.BOOLEAN,
    "startsWith": DelugeType.BOOLEAN,
    "endsWith": DelugeType.BOOLEAN,
    "matches": DelugeType.BOOLEAN,
    "isEmpty": DelugeType.BOOLEAN,
    "equals": DelugeType.BOOLEAN,
    "equalsIgnoreCase": DelugeType.BOOLEAN,
    "indexOf": DelugeType.NUMBER,
    "lastIndexOf": DelugeType.NUMBER,
    # Numeric functions
    "toNumber": DelugeType.NUMBER,
    "toLong": DelugeType.NUMBER,
    "toDecimal": DelugeType.DECIMAL,
    "round": DelugeType.DECIMAL,
    "ceil": DelugeType.NUMBER,
    "floor": DelugeType.NUMBER,
    "abs": DelugeType.DECIMAL,
    # Type conversion
    "toString": DelugeType.TEXT,
    "toText": DelugeType.TEXT,
    "toDate": DelugeType.DATE,
    "toTime": DelugeType.TIME,
    "toDateTime": DelugeType.DATETIME,
    # Date functions
    "now": DelugeType.DATETIME,
    "today": DelugeType.DATE,
    "zoho.currentdate": DelugeType.DATE,
    "daysBetween": DelugeType.NUMBER,
    "hoursBetween": DelugeType.NUMBER,
    "minutesBetween": DelugeType.NUMBER,
    "addDay": DelugeType.DATE,
    "addMonth": DelugeType.DATE,
    "addYear": DelugeType.DATE,
    "subDay": DelugeType.DATE,
    "subMonth": DelugeType.DATE,
    "subYear": DelugeType.DATE,
    "getDay": DelugeType.NUMBER,
    "getMonth": DelugeType.NUMBER,
    "getYear": DelugeType.NUMBER,
    # Collection / Map / List
    "toMap": DelugeType.MAP,
    "toList": DelugeType.LIST,
    "toJSONList": DelugeType.LIST,
    "Map": DelugeType.MAP,
    "List": DelugeType.LIST,
    "Collection": DelugeType.COLLECTION,
    "get": DelugeType.ANY,
    "put": DelugeType.VOID,
    "keys": DelugeType.LIST,
    "values": DelugeType.LIST,
    # Boolean
    "isNull": DelugeType.BOOLEAN,
    "isNumber": DelugeType.BOOLEAN,
    "isBlank": DelugeType.BOOLEAN,
    # I/O
    "getUrl": DelugeType.TEXT,
    "postUrl": DelugeType.TEXT,
    "invokeUrl": DelugeType.MAP,
    # Misc
    "ifnull": DelugeType.ANY,
    "isnull": DelugeType.BOOLEAN,
    "zoho.encryption.aesEncrypt": DelugeType.TEXT,
    "zoho.encryption.aesDecrypt": DelugeType.TEXT,
}


class TypeChecker(ast.Visitor):
    """Infer and populate ``resolved_type`` on every Expr node.

    After ``visit(program)``, each Expr in the AST will have its
    ``resolved_type`` set to a ``DelugeType`` value.  Statements are
    visited for their side-effects on the type environment (variable
    scope tracking).
    """

    def __init__(self, form_name: str | None = None) -> None:
        self._reg = get_registry()
        self._form_name = form_name
        # Variable scope: var_name -> DelugeType
        self._env: dict[str, DelugeType] = {}

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------

    def _set(self, node: ast.Expr, ty: DelugeType) -> DelugeType:
        """Assign resolved_type and return it (for chaining)."""
        node.resolved_type = ty
        return ty

    def _resolve_input_field(self, field_name: str) -> DelugeType:
        """Look up an input.* field type via the registry."""
        if self._form_name:
            return self._reg.field_type(self._form_name, field_name)
        # No specific form — search all forms for the field
        for schema in self._reg.all_forms().values():
            fd = schema.get_field(field_name)
            if fd is not None:
                return fd.deluge_type
        return DelugeType.UNKNOWN

    def _func_return_type(self, name: str) -> DelugeType:
        """Look up the return type for a built-in function/method name."""
        return _FUNCTION_RETURN_TYPES.get(name, DelugeType.ANY)

    # ----------------------------------------------------------
    # Expressions — each returns the inferred DelugeType
    # ----------------------------------------------------------

    def visit_Literal(self, node: ast.Literal) -> DelugeType:
        ty = LITERAL_KIND_MAP.get(node.kind, DelugeType.UNKNOWN)
        # Detect integer vs decimal for number literals
        if ty is DelugeType.NUMBER and isinstance(node.value, float):
            ty = DelugeType.DECIMAL
        return self._set(node, ty)

    def visit_Identifier(self, node: ast.Identifier) -> DelugeType:
        ty = self._env.get(node.name, DelugeType.UNKNOWN)
        return self._set(node, ty)

    def visit_ZohoVariable(self, node: ast.ZohoVariable) -> DelugeType:
        ty = _ZOHO_VAR_TYPES.get(node.path, DelugeType.TEXT)
        return self._set(node, ty)

    def visit_FieldAccess(self, node: ast.FieldAccess) -> DelugeType:
        obj_type = self.visit(node.object)

        # input.FieldName — resolve from schema
        if isinstance(node.object, ast.Identifier) and node.object.name == "input":
            ty = self._resolve_input_field(node.field)
            return self._set(node, ty)

        # zoho.* chains — check known map
        if isinstance(node.object, ast.ZohoVariable):
            full = node.object.path + "." + node.field
            ty = _ZOHO_VAR_TYPES.get(full, DelugeType.ANY)
            return self._set(node, ty)
        if isinstance(node.object, ast.Identifier) and node.object.name == "zoho":
            full = "zoho." + node.field
            ty = _ZOHO_VAR_TYPES.get(full, DelugeType.ANY)
            return self._set(node, ty)

        # Method-like access on known types (e.g. str.length())
        # The actual function call type is handled in visit_FunctionCall
        # For bare field access, propagate the object type or ANY
        return self._set(node, DelugeType.ANY)

    def visit_BinaryExpr(self, node: ast.BinaryExpr) -> DelugeType:
        left_ty = self.visit(node.left)
        right_ty = self.visit(node.right)
        ty = result_type(left_ty, node.op, right_ty)
        return self._set(node, ty if ty is not None else DelugeType.UNKNOWN)

    def visit_UnaryExpr(self, node: ast.UnaryExpr) -> DelugeType:
        operand_ty = self.visit(node.operand)
        if node.op == "!":
            return self._set(node, DelugeType.BOOLEAN)
        if node.op == "-" and operand_ty.is_numeric():
            return self._set(node, operand_ty)
        return self._set(node, operand_ty)

    def visit_FunctionCall(self, node: ast.FunctionCall) -> DelugeType:
        # Visit callee and args for their side-effects
        self.visit(node.callee)
        for arg in node.args:
            self.visit(arg)

        # Determine function name
        func_name = ""
        if isinstance(node.callee, ast.Identifier):
            func_name = node.callee.name
        elif isinstance(node.callee, ast.FieldAccess):
            func_name = node.callee.field

        # Special case: ifnull(a, b) returns type of b (the fallback)
        if func_name == "ifnull" and len(node.args) >= 2:
            ty = node.args[1].resolved_type or DelugeType.ANY
            return self._set(node, ty)

        ty = self._func_return_type(func_name)
        return self._set(node, ty)

    def visit_FormQuery(self, node: ast.FormQuery) -> DelugeType:
        if node.criteria is not None:
            self.visit(node.criteria)
        return self._set(node, DelugeType.COLLECTION)

    def visit_IndexAccess(self, node: ast.IndexAccess) -> DelugeType:
        self.visit(node.object)
        self.visit(node.index)
        return self._set(node, DelugeType.ANY)

    def visit_ListExpr(self, node: ast.ListExpr) -> DelugeType:
        for el in node.elements:
            self.visit(el)
        return self._set(node, DelugeType.LIST)

    def visit_MapExpr(self, node: ast.MapExpr) -> DelugeType:
        for key, val in node.entries:
            self.visit(key)
            self.visit(val)
        return self._set(node, DelugeType.MAP)

    def visit_ConditionalExpr(self, node: ast.ConditionalExpr) -> DelugeType:
        self.visit(node.condition)
        true_ty = self.visit(node.true_expr)
        false_ty = self.visit(node.false_expr)
        # If both branches agree, use that; otherwise ANY
        ty = true_ty if true_ty is false_ty else DelugeType.ANY
        return self._set(node, ty)

    # ----------------------------------------------------------
    # Statements — visited for scope side-effects
    # ----------------------------------------------------------

    def visit_Program(self, node: ast.Program) -> None:
        for stmt in node.body:
            self.visit(stmt)

    def visit_Block(self, node: ast.Block) -> None:
        for stmt in node.body:
            self.visit(stmt)

    def visit_ExprStmt(self, node: ast.ExprStmt) -> None:
        self.visit(node.expr)

    def visit_Assignment(self, node: ast.Assignment) -> None:
        rhs_ty = self.visit(node.value)

        # Track variable type in scope
        if isinstance(node.target, ast.Identifier) and node.op == "=":
            self._env[node.target.name] = rhs_ty

        # Visit target (for input.* field access type resolution)
        if isinstance(node.target, ast.FieldAccess):
            self.visit(node.target)
        elif isinstance(node.target, ast.Identifier):
            self._set(node.target, rhs_ty)

    def visit_IfStmt(self, node: ast.IfStmt) -> None:
        self.visit(node.condition)

        # Type narrowing: if (var != null ...), narrow var from
        # COLLECTION to COLLECTION in the guarded block
        narrowed = self._detect_null_guard(node.condition)
        old_types: dict[str, DelugeType] = {}
        if narrowed:
            for var in narrowed:
                old_types[var] = self._env.get(var, DelugeType.UNKNOWN)
                # Narrow: if the var was COLLECTION (which is nullable
                # from a FormQuery), keep it as COLLECTION but note it's
                # non-null. For now we just keep the type as-is since
                # DelugeType doesn't have a nullable wrapper — the
                # narrowing is used by the linter (DG005), not here.

        self.visit(node.body)

        # Restore narrowed types for else branch
        for var, old in old_types.items():
            self._env[var] = old

        if node.else_body is not None:
            self.visit(node.else_body)

    def visit_ForEachStmt(self, node: ast.ForEachStmt) -> None:
        coll_ty = self.visit(node.collection)
        # The loop variable gets the element type
        if coll_ty is DelugeType.LIST:
            self._env[node.var_name] = DelugeType.ANY
        elif coll_ty is DelugeType.COLLECTION:
            self._env[node.var_name] = DelugeType.ANY  # record row
        else:
            self._env[node.var_name] = DelugeType.ANY
        self.visit(node.body)

    def visit_WhileStmt(self, node: ast.WhileStmt) -> None:
        self.visit(node.condition)
        self.visit(node.body)

    def visit_TryCatchStmt(self, node: ast.TryCatchStmt) -> None:
        self.visit(node.try_body)
        self._env[node.catch_var] = DelugeType.TEXT  # exception message
        self.visit(node.catch_body)

    def visit_ReturnStmt(self, node: ast.ReturnStmt) -> None:
        if node.value is not None:
            self.visit(node.value)

    def visit_InsertStmt(self, node: ast.InsertStmt) -> None:
        for p in node.params.params:
            self.visit(p.value)
        if node.result_var:
            self._env[node.result_var] = DelugeType.COLLECTION

    def visit_DeleteStmt(self, node: ast.DeleteStmt) -> None:
        if node.condition is not None:
            self.visit(node.condition)

    def visit_UpdateStmt(self, node: ast.UpdateStmt) -> None:
        if node.condition is not None:
            self.visit(node.condition)

    def visit_SendmailStmt(self, node: ast.SendmailStmt) -> None:
        for p in node.params.params:
            self.visit(p.value)

    def visit_SendsmsStmt(self, node: ast.SendsmsStmt) -> None:
        for p in node.params.params:
            self.visit(p.value)

    def visit_InvokeUrlStmt(self, node: ast.InvokeUrlStmt) -> None:
        for p in node.params.params:
            self.visit(p.value)
        if node.result_var:
            self._env[node.result_var] = DelugeType.MAP

    def visit_AlertStmt(self, node: ast.AlertStmt) -> None:
        self.visit(node.message)

    def visit_InfoStmt(self, node: ast.InfoStmt) -> None:
        self.visit(node.expr)

    def visit_CancelSubmitStmt(self, _node: ast.CancelSubmitStmt) -> None:
        pass

    def visit_OpenUrlStmt(self, node: ast.OpenUrlStmt) -> None:
        self.visit(node.url)
        if node.target is not None:
            self.visit(node.target)

    # ----------------------------------------------------------
    # Null-guard detection (for type narrowing)
    # ----------------------------------------------------------

    def _detect_null_guard(self, expr: ast.Expr) -> list[str]:
        """Return variable names guarded by a != null check."""
        guarded: list[str] = []
        if isinstance(expr, ast.BinaryExpr):
            if expr.op == "!=" and self._is_null_check(expr):
                name = self._null_check_var(expr)
                if name:
                    guarded.append(name)
            elif expr.op == "&&":
                guarded.extend(self._detect_null_guard(expr.left))
                guarded.extend(self._detect_null_guard(expr.right))
        return guarded

    @staticmethod
    def _is_null_check(expr: ast.BinaryExpr) -> bool:
        return (
            (isinstance(expr.right, ast.Literal) and expr.right.kind == "null")
            or (isinstance(expr.left, ast.Literal) and expr.left.kind == "null")
        )

    @staticmethod
    def _null_check_var(expr: ast.BinaryExpr) -> str | None:
        if isinstance(expr.left, ast.Identifier) and isinstance(expr.right, ast.Literal):
            return expr.left.name
        if isinstance(expr.right, ast.Identifier) and isinstance(expr.left, ast.Literal):
            return expr.right.name
        return None


# ============================================================
# Public API
# ============================================================

def check_types(tree: ast.Program, form_name: str | None = None) -> None:
    """Run type inference on a parsed AST, populating resolved_type fields.

    Args:
        tree: Parsed Program AST (from parser).
        form_name: Optional form name for input.* field resolution.
            If None, searches all forms in the registry.
    """
    checker = TypeChecker(form_name=form_name)
    checker.visit(tree)
