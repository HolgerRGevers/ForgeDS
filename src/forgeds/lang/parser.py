"""Recursive descent parser for the Deluge scripting language.

Uses Pratt parsing for expressions (handles operator precedence).
Produces an AST rooted at a Program node.

Usage:
    from forgeds.lang.lexer import Lexer
    from forgeds.lang.parser import Parser

    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
"""

from __future__ import annotations

from forgeds.lang.tokens import Token, TokenType, SourceSpan
from forgeds.lang import ast_nodes as ast


class ParseError(Exception):
    """Raised on unrecoverable parse errors."""

    def __init__(self, message: str, token: Token) -> None:
        super().__init__(message)
        self.token = token


# ============================================================
# Operator precedence for Pratt parsing
# ============================================================

# Higher number = tighter binding
PRECEDENCE: dict[TokenType, int] = {
    TokenType.OR: 10,
    TokenType.AND: 20,
    TokenType.EQEQ: 30,
    TokenType.BANGEQ: 30,
    TokenType.LT: 40,
    TokenType.GT: 40,
    TokenType.LTEQ: 40,
    TokenType.GTEQ: 40,
    TokenType.PLUS: 50,
    TokenType.MINUS: 50,
    TokenType.STAR: 60,
    TokenType.SLASH: 60,
    TokenType.PERCENT: 60,
}

BINARY_OPS = set(PRECEDENCE.keys())

# Keywords that can appear as identifiers in certain positions
# (field names after '.', parameter names in [] blocks)
KEYWORDS_AS_IDENTS = {
    TokenType.INSERT, TokenType.INTO, TokenType.DELETE, TokenType.FROM,
    TokenType.UPDATE, TokenType.WHERE, TokenType.ALERT, TokenType.INFO,
    TokenType.CANCEL, TokenType.SUBMIT, TokenType.SENDMAIL, TokenType.SENDSMS,
    TokenType.INVOKE_URL, TokenType.OPEN_URL, TokenType.RETURN, TokenType.VOID,
    TokenType.IF, TokenType.ELSE, TokenType.FOR, TokenType.EACH, TokenType.IN,
    TokenType.WHILE, TokenType.TRY, TokenType.CATCH, TokenType.THISAPP,
    TokenType.TRUE, TokenType.FALSE, TokenType.NULL,
}

ASSIGN_OPS = {
    TokenType.EQ, TokenType.PLUS_EQ, TokenType.MINUS_EQ,
    TokenType.STAR_EQ, TokenType.SLASH_EQ, TokenType.PERCENT_EQ,
}


class Parser:
    """Parse a token stream into an AST."""

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    def parse(self) -> ast.Program:
        """Parse the full token stream into a Program.

        Uses panic-mode error recovery: on ParseError, skip tokens
        until a synchronization point (semicolon, closing brace, or
        statement keyword) and continue parsing.
        """
        stmts: list[ast.Stmt] = []
        self.errors: list[ParseError] = []
        while not self._at_end():
            try:
                stmt = self._statement()
                if stmt is not None:
                    stmts.append(stmt)
            except ParseError as e:
                self.errors.append(e)
                self._synchronize()
        span = SourceSpan(1, 0, self._prev().line, self._prev().col)
        return ast.Program(span=span, body=stmts)

    def _synchronize(self) -> None:
        """Skip tokens until we reach a safe point to resume parsing."""
        while not self._at_end():
            # Past a semicolon is safe
            if self._prev().type == TokenType.SEMICOLON:
                return
            # Statement-starting keywords are safe
            if self._peek().type in (
                TokenType.IF, TokenType.FOR, TokenType.WHILE, TokenType.TRY,
                TokenType.RETURN, TokenType.ALERT, TokenType.INFO,
                TokenType.CANCEL, TokenType.SENDMAIL, TokenType.SENDSMS,
                TokenType.INSERT, TokenType.DELETE, TokenType.LBRACE,
            ):
                return
            self._advance()

    # ----------------------------------------------------------
    # Token helpers
    # ----------------------------------------------------------

    def _peek(self) -> Token:
        return self.tokens[self.pos]

    def _prev(self) -> Token:
        return self.tokens[self.pos - 1] if self.pos > 0 else self.tokens[0]

    def _at_end(self) -> bool:
        return self._peek().type == TokenType.EOF

    def _check(self, *types: TokenType) -> bool:
        return self._peek().type in types

    def _advance(self) -> Token:
        tok = self._peek()
        if not self._at_end():
            self.pos += 1
        return tok

    def _match(self, *types: TokenType) -> Token | None:
        if self._peek().type in types:
            return self._advance()
        return None

    def _expect(self, ttype: TokenType, msg: str = "") -> Token:
        if self._peek().type == ttype:
            return self._advance()
        err_msg = msg or f"Expected {ttype.name}, got {self._peek().type.name}"
        raise ParseError(err_msg, self._peek())

    def _span_from(self, start: Token | ast.Node) -> SourceSpan:
        end = self._prev()
        if isinstance(start, ast.Node):
            return SourceSpan(start.span.start_line, start.span.start_col,
                              end.line, end.col + len(end.value))
        return SourceSpan(start.line, start.col, end.line, end.col + len(end.value))

    # ----------------------------------------------------------
    # Statements
    # ----------------------------------------------------------

    def _statement(self) -> ast.Stmt | None:
        tok = self._peek()

        if tok.type == TokenType.IF:
            return self._if_stmt()
        if tok.type == TokenType.FOR:
            return self._for_each_stmt()
        if tok.type == TokenType.WHILE:
            return self._while_stmt()
        if tok.type == TokenType.TRY:
            return self._try_catch_stmt()
        if tok.type == TokenType.RETURN:
            return self._return_stmt()
        if tok.type == TokenType.ALERT:
            return self._alert_stmt()
        if tok.type == TokenType.INFO:
            return self._info_stmt()
        if tok.type == TokenType.CANCEL:
            return self._cancel_submit_stmt()
        if tok.type == TokenType.SENDMAIL:
            return self._sendmail_stmt()
        if tok.type == TokenType.SENDSMS:
            return self._sendsms_stmt()
        if tok.type == TokenType.INSERT:
            return self._insert_stmt()
        if tok.type == TokenType.DELETE:
            return self._delete_stmt()
        if tok.type == TokenType.LBRACE:
            return self._block()

        # Assignment or expression statement
        # Peek ahead: could be  ident = expr  or  ident.field = expr
        #   or  ident = insert into ...  or  ident = invokeUrl [...]
        return self._assignment_or_expr_stmt()

    def _block(self) -> ast.Block:
        start = self._expect(TokenType.LBRACE)
        stmts: list[ast.Stmt] = []
        while not self._check(TokenType.RBRACE) and not self._at_end():
            stmt = self._statement()
            if stmt is not None:
                stmts.append(stmt)
        self._expect(TokenType.RBRACE, "Expected '}'")
        return ast.Block(span=self._span_from(start), body=stmts)

    def _if_stmt(self) -> ast.IfStmt:
        start = self._advance()  # if
        self._expect(TokenType.LPAREN, "Expected '(' after 'if'")
        condition = self._expression()
        self._expect(TokenType.RPAREN, "Expected ')' after condition")
        body = self._block()
        else_body: ast.Stmt | None = None
        if self._match(TokenType.ELSE):
            if self._check(TokenType.IF):
                else_body = self._if_stmt()  # else if
            else:
                else_body = self._block()
        return ast.IfStmt(span=self._span_from(start), condition=condition,
                          body=body, else_body=else_body)

    def _for_each_stmt(self) -> ast.ForEachStmt:
        start = self._advance()  # for
        self._expect(TokenType.EACH, "Expected 'each' after 'for'")
        var_tok = self._expect(TokenType.IDENT, "Expected variable name")
        self._expect(TokenType.IN, "Expected 'in'")
        collection = self._expression()
        body = self._block()
        return ast.ForEachStmt(span=self._span_from(start),
                               var_name=var_tok.value, collection=collection,
                               body=body)

    def _while_stmt(self) -> ast.WhileStmt:
        start = self._advance()  # while
        self._expect(TokenType.LPAREN, "Expected '(' after 'while'")
        condition = self._expression()
        self._expect(TokenType.RPAREN, "Expected ')'")
        body = self._block()
        return ast.WhileStmt(span=self._span_from(start), condition=condition, body=body)

    def _try_catch_stmt(self) -> ast.TryCatchStmt:
        start = self._advance()  # try
        try_body = self._block()
        self._expect(TokenType.CATCH, "Expected 'catch'")
        self._expect(TokenType.LPAREN, "Expected '(' after 'catch'")
        var_tok = self._expect(TokenType.IDENT, "Expected variable name in catch")
        self._expect(TokenType.RPAREN, "Expected ')'")
        catch_body = self._block()
        return ast.TryCatchStmt(span=self._span_from(start),
                                try_body=try_body, catch_var=var_tok.value,
                                catch_body=catch_body)

    def _return_stmt(self) -> ast.ReturnStmt:
        start = self._advance()  # return
        value: ast.Expr | None = None
        if not self._check(TokenType.SEMICOLON, TokenType.RBRACE, TokenType.EOF):
            value = self._expression()
        self._match(TokenType.SEMICOLON)
        return ast.ReturnStmt(span=self._span_from(start), value=value)

    def _alert_stmt(self) -> ast.AlertStmt:
        start = self._advance()  # alert
        message = self._expression()
        self._match(TokenType.SEMICOLON)
        return ast.AlertStmt(span=self._span_from(start), message=message)

    def _info_stmt(self) -> ast.InfoStmt:
        start = self._advance()  # info
        expr = self._expression()
        self._match(TokenType.SEMICOLON)
        return ast.InfoStmt(span=self._span_from(start), expr=expr)

    def _cancel_submit_stmt(self) -> ast.CancelSubmitStmt:
        start = self._advance()  # cancel
        self._expect(TokenType.SUBMIT, "Expected 'submit' after 'cancel'")
        self._match(TokenType.SEMICOLON)
        return ast.CancelSubmitStmt(span=self._span_from(start))

    def _sendmail_stmt(self, result_var: str | None = None) -> ast.SendmailStmt:
        start = self._advance()  # sendmail
        params = self._param_block()
        self._match(TokenType.SEMICOLON)
        return ast.SendmailStmt(span=self._span_from(start), params=params)

    def _sendsms_stmt(self) -> ast.SendsmsStmt:
        start = self._advance()  # sendsms
        params = self._param_block()
        self._match(TokenType.SEMICOLON)
        return ast.SendsmsStmt(span=self._span_from(start), params=params)

    def _insert_stmt(self, result_var: str | None = None) -> ast.InsertStmt:
        start = self._advance()  # insert
        self._expect(TokenType.INTO, "Expected 'into' after 'insert'")
        table_tok = self._expect(TokenType.IDENT, "Expected table name")
        params = self._param_block()
        self._match(TokenType.SEMICOLON)
        return ast.InsertStmt(span=self._span_from(start), table=table_tok.value,
                              params=params, result_var=result_var)

    def _delete_stmt(self) -> ast.DeleteStmt:
        start = self._advance()  # delete
        self._match(TokenType.FROM)
        table_tok = self._expect(TokenType.IDENT, "Expected table name")
        condition: ast.Expr | None = None
        if self._match(TokenType.WHERE):
            condition = self._expression()
        self._match(TokenType.SEMICOLON)
        return ast.DeleteStmt(span=self._span_from(start), table=table_tok.value,
                              condition=condition)

    def _invoke_url_stmt(self, result_var: str | None = None) -> ast.InvokeUrlStmt:
        start = self._advance()  # invokeUrl
        params = self._param_block()
        self._match(TokenType.SEMICOLON)
        return ast.InvokeUrlStmt(span=self._span_from(start), params=params,
                                 result_var=result_var)

    def _open_url_stmt(self) -> ast.OpenUrlStmt:
        start = self._advance()  # openUrl
        self._expect(TokenType.LPAREN, "Expected '(' after 'openUrl'")
        url = self._expression()
        target: ast.Expr | None = None
        if self._match(TokenType.COMMA):
            target = self._expression()
        self._expect(TokenType.RPAREN, "Expected ')'")
        self._match(TokenType.SEMICOLON)
        return ast.OpenUrlStmt(span=self._span_from(start), url=url, target=target)

    # ----------------------------------------------------------
    # Assignment or expression statement
    # ----------------------------------------------------------

    def _assignment_or_expr_stmt(self) -> ast.Stmt:
        """Parse assignment (x = expr, x.f = expr, x = insert into ...)
        or expression statement (func(), x.method()).
        """
        start = self._peek()
        expr = self._expression()

        # Check for assignment
        if self._check(*ASSIGN_OPS):
            op_tok = self._advance()
            op = op_tok.value

            # RHS could be a special statement: insert into, invokeUrl, sendmail
            if self._check(TokenType.INSERT):
                var_name = self._expr_to_var_name(expr)
                return self._insert_stmt(result_var=var_name)
            if self._check(TokenType.INVOKE_URL):
                var_name = self._expr_to_var_name(expr)
                return self._invoke_url_stmt(result_var=var_name)
            if self._check(TokenType.SENDMAIL):
                var_name = self._expr_to_var_name(expr)
                stmt = self._sendmail_stmt()
                # Sendmail doesn't have a result_var in the type, but we
                # capture the assignment target for completeness
                return ast.Assignment(span=self._span_from(start),
                                      target=expr, op=op, value=ast.Literal(
                                          span=stmt.span, value="<sendmail>", kind="string"))

            value = self._expression()
            self._match(TokenType.SEMICOLON)
            return ast.Assignment(span=self._span_from(start),
                                  target=expr, op=op, value=value)

        # Stand-alone invokeUrl/sendmail without assignment
        if isinstance(expr, ast.Identifier):
            if expr.name == "invokeUrl" and self._check(TokenType.LBRACKET):
                self.pos -= 1  # back up to invokeUrl token
                return self._invoke_url_stmt()
            if expr.name == "sendmail" and self._check(TokenType.LBRACKET):
                self.pos -= 1
                return self._sendmail_stmt()
            if expr.name == "openUrl" and self._check(TokenType.LPAREN):
                self.pos -= 1
                return self._open_url_stmt()

        self._match(TokenType.SEMICOLON)
        return ast.ExprStmt(span=self._span_from(start), expr=expr)

    def _expr_to_var_name(self, expr: ast.Expr) -> str:
        """Extract variable name from an expression for result capture."""
        if isinstance(expr, ast.Identifier):
            return expr.name
        if isinstance(expr, ast.FieldAccess):
            parts = []
            node = expr
            while isinstance(node, ast.FieldAccess):
                parts.append(node.field)
                node = node.object
            if isinstance(node, ast.Identifier):
                parts.append(node.name)
            return ".".join(reversed(parts))
        return "<unknown>"

    # ----------------------------------------------------------
    # Param block: [ field = value, field : value, ... ]
    # ----------------------------------------------------------

    def _param_block(self) -> ast.ParamBlock:
        start = self._expect(TokenType.LBRACKET, "Expected '['")
        params: list[ast.ParamAssignment] = []

        while not self._check(TokenType.RBRACKET) and not self._at_end():
            # Parameter names can be keywords (e.g. 'from', 'to', 'type')
            name_tok = self._peek()
            if name_tok.type == TokenType.IDENT or name_tok.type in KEYWORDS_AS_IDENTS:
                self._advance()
            else:
                raise ParseError("Expected parameter name", name_tok)
            sep = "="
            if self._match(TokenType.EQ):
                sep = "="
            elif self._match(TokenType.COLON):
                sep = ":"
            else:
                raise ParseError("Expected '=' or ':' after parameter name", self._peek())

            value = self._expression()
            params.append(ast.ParamAssignment(
                span=self._span_from(name_tok),
                name=name_tok.value, value=value, separator=sep,
            ))
            # Optional comma between params
            self._match(TokenType.COMMA)

        self._expect(TokenType.RBRACKET, "Expected ']'")
        return ast.ParamBlock(span=self._span_from(start), params=params)

    # ----------------------------------------------------------
    # Expressions — Pratt parser
    # ----------------------------------------------------------

    def _expression(self, min_prec: int = 0) -> ast.Expr:
        left = self._unary()

        while self._peek().type in BINARY_OPS:
            prec = PRECEDENCE[self._peek().type]
            if prec < min_prec:
                break
            op_tok = self._advance()
            right = self._expression(prec + 1)
            left = ast.BinaryExpr(
                span=SourceSpan(left.span.start_line, left.span.start_col,
                                right.span.end_line, right.span.end_col),
                left=left, op=op_tok.value, right=right,
            )

        return left

    def _unary(self) -> ast.Expr:
        if self._check(TokenType.BANG):
            op_tok = self._advance()
            operand = self._unary()
            return ast.UnaryExpr(span=self._span_from(op_tok),
                                 op=op_tok.value, operand=operand)
        if self._check(TokenType.MINUS):
            # Check if this is unary minus (not binary)
            op_tok = self._peek()
            # Save position; if next after minus is a value-like token
            # and previous was an operator or start, treat as unary
            if not self.tokens or self.pos == 0:
                op_tok = self._advance()
                operand = self._unary()
                return ast.UnaryExpr(span=self._span_from(op_tok),
                                     op="-", operand=operand)
        return self._postfix()

    def _postfix(self) -> ast.Expr:
        """Parse primary then any postfix operations: .field, (args), [index]."""
        expr = self._primary()

        while True:
            if self._match(TokenType.DOT):
                # After '.', keywords can appear as field/method names
                # (e.g. input.Line_Items.insert(), zoho.currentdate)
                field_tok = self._advance()
                if field_tok.type not in (TokenType.IDENT, *KEYWORDS_AS_IDENTS):
                    raise ParseError(f"Expected field name after '.', got {field_tok.type.name}", field_tok)
                # Check for method call: obj.method(args)
                if self._check(TokenType.LPAREN):
                    callee = ast.FieldAccess(
                        span=self._span_from(field_tok),
                        object=expr, field=field_tok.value,
                    )
                    expr = self._finish_call(callee)
                else:
                    expr = ast.FieldAccess(
                        span=self._span_from(field_tok),
                        object=expr, field=field_tok.value,
                    )
            elif self._check(TokenType.LPAREN) and isinstance(expr, ast.Identifier):
                expr = self._finish_call(expr)
            elif self._match(TokenType.LBRACKET):
                # Form query or index access: Form[criteria] or list[0]
                if isinstance(expr, ast.Identifier) and expr.name[0:1].isupper():
                    # Likely a form query: FormName[criteria]
                    if self._check(TokenType.RBRACKET):
                        self._advance()
                        expr = ast.FormQuery(span=self._span_from(expr),
                                             form=expr.name, criteria=None)
                    else:
                        criteria = self._expression()
                        self._expect(TokenType.RBRACKET, "Expected ']'")
                        expr = ast.FormQuery(span=self._span_from(expr),
                                             form=expr.name, criteria=criteria)
                else:
                    index = self._expression()
                    self._expect(TokenType.RBRACKET, "Expected ']'")
                    expr = ast.IndexAccess(span=self._span_from(expr),
                                           object=expr, index=index)
            else:
                break

        return expr

    def _finish_call(self, callee: ast.Expr) -> ast.FunctionCall:
        """Parse argument list after callee has been parsed."""
        self._expect(TokenType.LPAREN)
        args: list[ast.Expr] = []
        if not self._check(TokenType.RPAREN):
            args.append(self._expression())
            while self._match(TokenType.COMMA):
                args.append(self._expression())
        self._expect(TokenType.RPAREN, "Expected ')'")
        return ast.FunctionCall(span=self._span_from(callee), callee=callee, args=args)

    def _primary(self) -> ast.Expr:
        """Parse primary expressions: literals, identifiers, grouping."""
        tok = self._peek()

        # Number
        if tok.type == TokenType.NUMBER:
            self._advance()
            val = float(tok.value) if "." in tok.value else int(tok.value)
            return ast.Literal(span=tok.span(), value=val, kind="number")

        # String
        if tok.type == TokenType.STRING:
            self._advance()
            # Strip surrounding quotes
            return ast.Literal(span=tok.span(), value=tok.value[1:-1], kind="string")

        # Date literal
        if tok.type == TokenType.DATE_LITERAL:
            self._advance()
            return ast.Literal(span=tok.span(), value=tok.value, kind="date")

        # Boolean
        if tok.type == TokenType.TRUE:
            self._advance()
            return ast.Literal(span=tok.span(), value=True, kind="bool")
        if tok.type == TokenType.FALSE:
            self._advance()
            return ast.Literal(span=tok.span(), value=False, kind="bool")

        # Null
        if tok.type == TokenType.NULL:
            self._advance()
            return ast.Literal(span=tok.span(), value=None, kind="null")

        # Identifier (variable, form name, etc.)
        if tok.type == TokenType.IDENT:
            self._advance()
            return ast.Identifier(span=tok.span(), name=tok.value)

        # thisapp (e.g. thisapp.permissions.isUserInRole(...))
        if tok.type == TokenType.THISAPP:
            self._advance()
            return ast.Identifier(span=tok.span(), name=tok.value)

        # zoho.* handled via IDENT + postfix dot chain

        # Grouped expression
        if tok.type == TokenType.LPAREN:
            self._advance()
            expr = self._expression()
            self._expect(TokenType.RPAREN, "Expected ')'")
            return expr

        # List or map literal: { ... }
        if tok.type == TokenType.LBRACE:
            return self._collection_literal()

        raise ParseError(f"Unexpected token: {tok.type.name} ({tok.value!r})", tok)

    def _collection_literal(self) -> ast.Expr:
        """Parse { ... } as list literal or map literal.

        Map: { "key": value, "key2": value2 }
        List: { "a", "b", "c" }
        """
        start = self._advance()  # {

        if self._check(TokenType.RBRACE):
            # Empty collection — treat as empty list
            self._advance()
            return ast.ListExpr(span=self._span_from(start), elements=[])

        # Parse first element
        first = self._expression()

        # If followed by colon, it's a map
        if self._match(TokenType.COLON):
            val = self._expression()
            entries: list[tuple[ast.Expr, ast.Expr]] = [(first, val)]
            while self._match(TokenType.COMMA):
                if self._check(TokenType.RBRACE):
                    break
                key = self._expression()
                self._expect(TokenType.COLON, "Expected ':' in map literal")
                val = self._expression()
                entries.append((key, val))
            self._expect(TokenType.RBRACE, "Expected '}'")
            return ast.MapExpr(span=self._span_from(start), entries=entries)

        # Otherwise it's a list
        elements: list[ast.Expr] = [first]
        while self._match(TokenType.COMMA):
            if self._check(TokenType.RBRACE):
                break
            elements.append(self._expression())
        self._expect(TokenType.RBRACE, "Expected '}'")
        return ast.ListExpr(span=self._span_from(start), elements=elements)


# ============================================================
# Convenience function
# ============================================================

def parse_source(source: str) -> ast.Program:
    """Lex + parse Deluge source code, return AST."""
    from forgeds.lang.lexer import Lexer
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()
