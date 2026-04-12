"""Token types and Token dataclass for the Deluge lexer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    """Every token type in the Deluge language."""

    # --- Literals ---
    NUMBER = auto()          # 42, -7, 3.14
    STRING = auto()          # "double-quoted text"
    DATE_LITERAL = auto()    # 'dd-MMM-yyyy' or 'yyyy-MM-dd HH:mm:ss'
    TRUE = auto()            # true
    FALSE = auto()           # false
    NULL = auto()            # null

    # --- Identifiers ---
    IDENT = auto()           # variable names, form names, field names

    # --- Keywords ---
    IF = auto()
    ELSE = auto()
    FOR = auto()
    EACH = auto()
    IN = auto()
    WHILE = auto()
    RETURN = auto()
    TRY = auto()
    CATCH = auto()
    VOID = auto()
    THISAPP = auto()         # thisapp

    # --- Statement keywords ---
    INSERT = auto()          # insert
    INTO = auto()            # into
    DELETE = auto()          # delete
    FROM = auto()            # from
    UPDATE = auto()          # update
    WHERE = auto()           # where
    ALERT = auto()           # alert
    INFO = auto()            # info
    CANCEL = auto()          # cancel
    SUBMIT = auto()          # submit
    SENDMAIL = auto()        # sendmail
    SENDSMS = auto()         # sendsms
    INVOKE_URL = auto()      # invokeUrl
    OPEN_URL = auto()        # openUrl

    # --- Arithmetic operators ---
    PLUS = auto()            # +
    MINUS = auto()           # -
    STAR = auto()            # *
    SLASH = auto()           # /
    PERCENT = auto()         # %

    # --- Assignment operators ---
    EQ = auto()              # =
    PLUS_EQ = auto()         # +=
    MINUS_EQ = auto()        # -=
    STAR_EQ = auto()         # *=
    SLASH_EQ = auto()        # /=
    PERCENT_EQ = auto()      # %=

    # --- Comparison operators ---
    EQEQ = auto()            # ==
    BANGEQ = auto()          # !=
    LT = auto()              # <
    GT = auto()              # >
    LTEQ = auto()            # <=
    GTEQ = auto()            # >=

    # --- Logical operators ---
    AND = auto()             # &&
    OR = auto()              # ||
    BANG = auto()            # !

    # --- Delimiters ---
    LPAREN = auto()          # (
    RPAREN = auto()          # )
    LBRACKET = auto()        # [
    RBRACKET = auto()        # ]
    LBRACE = auto()          # {
    RBRACE = auto()          # }
    SEMICOLON = auto()       # ;
    COLON = auto()           # :
    DOT = auto()             # .
    COMMA = auto()           # ,

    # --- Special ---
    NEWLINE = auto()         # \n (significant in some contexts)
    EOF = auto()             # end of input
    COMMENT = auto()         # // ... or /* ... */ (usually skipped)


# Keywords mapped from source text to token type.
KEYWORDS: dict[str, TokenType] = {
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "for": TokenType.FOR,
    "each": TokenType.EACH,
    "in": TokenType.IN,
    "while": TokenType.WHILE,
    "return": TokenType.RETURN,
    "try": TokenType.TRY,
    "catch": TokenType.CATCH,
    "void": TokenType.VOID,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "null": TokenType.NULL,
    "thisapp": TokenType.THISAPP,
    "insert": TokenType.INSERT,
    "into": TokenType.INTO,
    "delete": TokenType.DELETE,
    "from": TokenType.FROM,
    "update": TokenType.UPDATE,
    "where": TokenType.WHERE,
    "alert": TokenType.ALERT,
    "info": TokenType.INFO,
    "cancel": TokenType.CANCEL,
    "submit": TokenType.SUBMIT,
    "sendmail": TokenType.SENDMAIL,
    "sendsms": TokenType.SENDSMS,
    "invokeUrl": TokenType.INVOKE_URL,
    "openUrl": TokenType.OPEN_URL,
}


@dataclass(frozen=True, slots=True)
class SourceSpan:
    """Location in source code.  Every AST node carries one."""
    start_line: int    # 1-based
    start_col: int     # 0-based
    end_line: int
    end_col: int

    @staticmethod
    def from_token(tok: Token) -> SourceSpan:
        return SourceSpan(tok.line, tok.col, tok.line, tok.col + len(tok.value))


@dataclass(frozen=True, slots=True)
class Token:
    """A single lexical token."""
    type: TokenType
    value: str
    line: int          # 1-based
    col: int           # 0-based
    offset: int        # byte offset into source

    def span(self) -> SourceSpan:
        return SourceSpan.from_token(self)
