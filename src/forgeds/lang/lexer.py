"""Single-pass lexer for the Deluge scripting language.

Produces a stream of Token objects from source text.
Handles: strings, date literals, numbers, identifiers/keywords,
operators, delimiters, comments.
"""

from __future__ import annotations

from forgeds.lang.tokens import Token, TokenType, KEYWORDS

# Module-level operator lookup tables (avoids dict construction per token)
_TWO_CHAR_OPS: dict[str, TokenType] = {
    "==": TokenType.EQEQ,
    "!=": TokenType.BANGEQ,
    "<=": TokenType.LTEQ,
    ">=": TokenType.GTEQ,
    "&&": TokenType.AND,
    "||": TokenType.OR,
    "+=": TokenType.PLUS_EQ,
    "-=": TokenType.MINUS_EQ,
    "*=": TokenType.STAR_EQ,
    "/=": TokenType.SLASH_EQ,
    "%=": TokenType.PERCENT_EQ,
}

_ONE_CHAR_OPS: dict[str, TokenType] = {
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.STAR,
    "/": TokenType.SLASH,
    "%": TokenType.PERCENT,
    "=": TokenType.EQ,
    "<": TokenType.LT,
    ">": TokenType.GT,
    "!": TokenType.BANG,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "[": TokenType.LBRACKET,
    "]": TokenType.RBRACKET,
    "{": TokenType.LBRACE,
    "}": TokenType.RBRACE,
    ";": TokenType.SEMICOLON,
    ":": TokenType.COLON,
    ".": TokenType.DOT,
    ",": TokenType.COMMA,
}

_WHITESPACE = frozenset(" \t\r\n")


class LexError(Exception):
    """Raised on unrecoverable lexer errors."""

    def __init__(self, message: str, line: int, col: int) -> None:
        super().__init__(message)
        self.line = line
        self.col = col


class Lexer:
    """Tokenize Deluge source code."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 0
        self.tokens: list[Token] = []

    # ----------------------------------------------------------
    # Public API
    # ----------------------------------------------------------

    def tokenize(self) -> list[Token]:
        """Lex the entire source, return token list (excluding comments)."""
        while self.pos < len(self.source):
            self._skip_whitespace()
            if self.pos >= len(self.source):
                break

            ch = self.source[self.pos]

            # Comments
            if ch == "/" and self.pos + 1 < len(self.source):
                nxt = self.source[self.pos + 1]
                if nxt == "/":
                    self._line_comment()
                    continue
                if nxt == "*":
                    self._block_comment()
                    continue

            # String literal
            if ch == '"':
                self._string()
                continue

            # Date/time literal (single-quoted)
            if ch == "'":
                self._date_literal()
                continue

            # Number
            if ch.isdigit() or (ch == "-" and self._peek_digit()):
                self._number()
                continue

            # Identifier or keyword
            if ch.isalpha() or ch == "_":
                self._identifier()
                continue

            # Operators and punctuation
            if self._operator_or_punct():
                continue

            # Unknown character — skip to avoid infinite loop
            self._error(f"Unexpected character: {ch!r}")
            self._advance()

        self.tokens.append(Token(TokenType.EOF, "", self.line, self.col, self.pos))
        return self.tokens

    # ----------------------------------------------------------
    # Scanning helpers
    # ----------------------------------------------------------

    def _peek(self, offset: int = 0) -> str:
        i = self.pos + offset
        return self.source[i] if i < len(self.source) else "\0"

    def _peek_digit(self) -> bool:
        """Check if the char after current '-' is a digit (for negative numbers)."""
        nxt = self._peek(1)
        if not nxt.isdigit():
            return False
        # Only treat as negative number if previous token isn't a value
        # (avoids misinterpreting  expr - 1  as  expr  -1)
        if self.tokens:
            prev = self.tokens[-1].type
            if prev in (TokenType.NUMBER, TokenType.STRING, TokenType.IDENT,
                        TokenType.RPAREN, TokenType.RBRACKET, TokenType.RBRACE,
                        TokenType.TRUE, TokenType.FALSE, TokenType.NULL,
                        TokenType.DATE_LITERAL):
                return False
        return True

    def _advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 0
        else:
            self.col += 1
        return ch

    def _skip_whitespace(self) -> None:
        src = self.source
        pos = self.pos
        while pos < len(src) and src[pos] in _WHITESPACE:
            if src[pos] == "\n":
                self.line += 1
                self.col = 0
            else:
                self.col += 1
            pos += 1
        self.pos = pos

    def _emit(self, ttype: TokenType, value: str, start_line: int, start_col: int, start_offset: int) -> None:
        self.tokens.append(Token(ttype, value, start_line, start_col, start_offset))

    def _error(self, msg: str) -> None:
        raise LexError(msg, self.line, self.col)

    # ----------------------------------------------------------
    # Token scanners
    # ----------------------------------------------------------

    def _line_comment(self) -> None:
        """Skip // ... to end of line."""
        nl = self.source.find("\n", self.pos)
        if nl == -1:
            self.col += len(self.source) - self.pos
            self.pos = len(self.source)
        else:
            self.col += nl - self.pos
            self.pos = nl

    def _block_comment(self) -> None:
        """Skip /* ... */."""
        start_line = self.line
        self._advance()  # /
        self._advance()  # *
        while self.pos < len(self.source):
            if self.source[self.pos] == "*" and self._peek(1) == "/":
                self._advance()  # *
                self._advance()  # /
                return
            self._advance()
        self._error(f"Unterminated block comment starting at line {start_line}")

    def _string(self) -> None:
        """Scan a "double-quoted" string."""
        start_line, start_col, start_offset = self.line, self.col, self.pos
        self._advance()  # opening "
        buf: list[str] = []
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch == '"':
                self._advance()  # closing "
                self._emit(TokenType.STRING, '"' + "".join(buf) + '"',
                           start_line, start_col, start_offset)
                return
            if ch == "\\":
                self._advance()
                esc = self._advance() if self.pos < len(self.source) else ""
                if esc == "n":
                    buf.append("\n")
                elif esc == "t":
                    buf.append("\t")
                elif esc == "\\":
                    buf.append("\\")
                elif esc == '"':
                    buf.append('"')
                else:
                    buf.append("\\")
                    buf.append(esc)
                continue
            buf.append(self._advance())
        self._error("Unterminated string")

    def _date_literal(self) -> None:
        """Scan a 'single-quoted' date/time literal."""
        start_line, start_col, start_offset = self.line, self.col, self.pos
        self._advance()  # opening '
        buf: list[str] = []
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch == "'":
                self._advance()  # closing '
                self._emit(TokenType.DATE_LITERAL, "'" + "".join(buf) + "'",
                           start_line, start_col, start_offset)
                return
            if ch == "\n":
                break
            buf.append(self._advance())
        self._error("Unterminated date literal")

    def _number(self) -> None:
        """Scan integer or decimal number (with optional leading -)."""
        start_line, start_col, start_offset = self.line, self.col, self.pos
        src = self.source
        pos = self.pos
        if src[pos] == "-":
            pos += 1
        while pos < len(src) and src[pos].isdigit():
            pos += 1
        # Decimal part
        if pos < len(src) and src[pos] == "." and pos + 1 < len(src) and src[pos + 1].isdigit():
            pos += 1  # .
            while pos < len(src) and src[pos].isdigit():
                pos += 1
        word = src[self.pos:pos]
        self.col += len(word)
        self.pos = pos
        self._emit(TokenType.NUMBER, word, start_line, start_col, start_offset)

    def _identifier(self) -> None:
        """Scan identifier or keyword."""
        start_line, start_col, start_offset = self.line, self.col, self.pos
        src = self.source
        pos = self.pos
        while pos < len(src) and (src[pos].isalnum() or src[pos] == "_"):
            pos += 1
        word = src[self.pos:pos]
        self.col += len(word)
        self.pos = pos
        ttype = KEYWORDS.get(word, TokenType.IDENT)
        self._emit(ttype, word, start_line, start_col, start_offset)

    def _operator_or_punct(self) -> bool:
        """Try to scan an operator or punctuation token. Returns True if consumed."""
        ch = self.source[self.pos]
        start_line, start_col, start_offset = self.line, self.col, self.pos
        nxt = self._peek(1)

        # Two-char operators
        two = ch + nxt if nxt != "\0" else ""
        ttype = _TWO_CHAR_OPS.get(two)
        if ttype is not None:
            self._advance()
            self._advance()
            self._emit(ttype, two, start_line, start_col, start_offset)
            return True

        # Single-char operators & punctuation
        ttype = _ONE_CHAR_OPS.get(ch)
        if ttype is not None:
            self._advance()
            self._emit(ttype, ch, start_line, start_col, start_offset)
            return True

        return False
