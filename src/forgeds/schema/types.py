"""Deluge type algebra for ForgeDS.

Defines the runtime type system for Zoho Creator's Deluge language:
type enum, field-type-to-runtime-type mapping, coercion rules, and
binary operation result types.
"""
from __future__ import annotations

from enum import Enum


class DelugeType(Enum):
    """Runtime types in the Deluge language."""

    TEXT = "Text"
    NUMBER = "Number"
    DECIMAL = "Decimal"
    BOOLEAN = "Boolean"
    DATE = "Date"
    DATETIME = "DateTime"
    TIME = "Time"
    LIST = "List"
    MAP = "Map"
    COLLECTION = "Collection"
    FILE = "File"
    VOID = "Void"
    NULL = "Null"
    ANY = "Any"          # polymorphic / unresolved
    UNKNOWN = "Unknown"  # parser couldn't determine

    # -- predicates --

    def is_numeric(self) -> bool:
        return self in (DelugeType.NUMBER, DelugeType.DECIMAL)

    def is_temporal(self) -> bool:
        return self in (DelugeType.DATE, DelugeType.DATETIME, DelugeType.TIME)

    def is_container(self) -> bool:
        return self in (DelugeType.LIST, DelugeType.MAP, DelugeType.COLLECTION)

    def supports_arithmetic(self) -> bool:
        return self in (
            DelugeType.NUMBER, DelugeType.DECIMAL, DelugeType.TEXT,
        )

    def supports_comparison(self) -> bool:
        return self not in (
            DelugeType.VOID, DelugeType.FILE,
            DelugeType.LIST, DelugeType.MAP, DelugeType.COLLECTION,
        )


# Zoho Creator field types (lowercase DB strings) -> Deluge runtime types
FIELD_TYPE_MAP: dict[str, DelugeType] = {
    # text family
    "text": DelugeType.TEXT,
    "textarea": DelugeType.TEXT,
    "rich text": DelugeType.TEXT,
    "name": DelugeType.TEXT,
    "address": DelugeType.TEXT,
    "email": DelugeType.TEXT,
    "phone": DelugeType.TEXT,
    "url": DelugeType.TEXT,
    "picklist": DelugeType.TEXT,
    "radio": DelugeType.TEXT,
    "multi select": DelugeType.LIST,
    # numeric family
    "number": DelugeType.NUMBER,
    "autonumber": DelugeType.NUMBER,
    "formula (number)": DelugeType.NUMBER,
    "decimal": DelugeType.DECIMAL,
    "currency": DelugeType.DECIMAL,
    "percent": DelugeType.DECIMAL,
    "formula (decimal)": DelugeType.DECIMAL,
    # boolean
    "checkbox": DelugeType.BOOLEAN,
    "decision box": DelugeType.BOOLEAN,
    # temporal
    "date": DelugeType.DATE,
    "date-time": DelugeType.DATETIME,
    "datetime": DelugeType.DATETIME,
    "time": DelugeType.TIME,
    "formula (date)": DelugeType.DATE,
    "formula (datetime)": DelugeType.DATETIME,
    # relational / container
    "lookup": DelugeType.COLLECTION,
    "multi lookup": DelugeType.COLLECTION,
    "subform": DelugeType.COLLECTION,
    "list": DelugeType.LIST,
    # file
    "file": DelugeType.FILE,
    "image": DelugeType.FILE,
    "audio": DelugeType.FILE,
    "video": DelugeType.FILE,
    "signature": DelugeType.FILE,
    # system / meta
    "system": DelugeType.TEXT,
    "added by": DelugeType.TEXT,
    "modified by": DelugeType.TEXT,
    "added time": DelugeType.DATETIME,
    "modified time": DelugeType.DATETIME,
    "id": DelugeType.NUMBER,
}

# Literal kind strings (from ast_nodes.Literal.kind) -> DelugeType
LITERAL_KIND_MAP: dict[str, DelugeType] = {
    "string": DelugeType.TEXT,
    "number": DelugeType.NUMBER,
    "bool": DelugeType.BOOLEAN,
    "null": DelugeType.NULL,
    "date": DelugeType.DATE,
}


# -- Coercion rules --

# (source, target) pairs where implicit coercion is allowed
_COERCION_PAIRS: set[tuple[DelugeType, DelugeType]] = {
    # numeric widening
    (DelugeType.NUMBER, DelugeType.DECIMAL),
    # numeric -> text (string concatenation)
    (DelugeType.NUMBER, DelugeType.TEXT),
    (DelugeType.DECIMAL, DelugeType.TEXT),
    (DelugeType.BOOLEAN, DelugeType.TEXT),
    # temporal -> text
    (DelugeType.DATE, DelugeType.TEXT),
    (DelugeType.DATETIME, DelugeType.TEXT),
    (DelugeType.TIME, DelugeType.TEXT),
    # date narrowing / widening
    (DelugeType.DATE, DelugeType.DATETIME),
    # null coerces to anything (nullable)
    (DelugeType.NULL, DelugeType.TEXT),
    (DelugeType.NULL, DelugeType.NUMBER),
    (DelugeType.NULL, DelugeType.DECIMAL),
    (DelugeType.NULL, DelugeType.BOOLEAN),
    (DelugeType.NULL, DelugeType.DATE),
    (DelugeType.NULL, DelugeType.DATETIME),
    (DelugeType.NULL, DelugeType.TIME),
    (DelugeType.NULL, DelugeType.LIST),
    (DelugeType.NULL, DelugeType.MAP),
    (DelugeType.NULL, DelugeType.COLLECTION),
}


def can_coerce(source: DelugeType, target: DelugeType) -> bool:
    """Return True if *source* can be implicitly coerced to *target*."""
    if source is target:
        return True
    if source is DelugeType.ANY or target is DelugeType.ANY:
        return True
    if source is DelugeType.UNKNOWN or target is DelugeType.UNKNOWN:
        return True
    return (source, target) in _COERCION_PAIRS


# -- Binary operation result types --

def result_type(left: DelugeType, op: str, right: DelugeType) -> DelugeType | None:
    """Return the result type of ``left op right``, or None if invalid.

    Covers the operators Deluge actually supports at runtime.
    """
    # ANY / UNKNOWN propagate
    if left is DelugeType.ANY or right is DelugeType.ANY:
        return DelugeType.ANY
    if left is DelugeType.UNKNOWN or right is DelugeType.UNKNOWN:
        return DelugeType.UNKNOWN

    # Comparison / logical -> Boolean
    if op in ("==", "!=", "<", ">", "<=", ">="):
        if left.supports_comparison() and right.supports_comparison():
            return DelugeType.BOOLEAN
        return None
    if op in ("&&", "||"):
        return DelugeType.BOOLEAN

    # Arithmetic
    if op == "+":
        # Text concatenation wins if either side is Text
        if left is DelugeType.TEXT or right is DelugeType.TEXT:
            return DelugeType.TEXT
        if left.is_numeric() and right.is_numeric():
            # Decimal wins over Number
            if left is DelugeType.DECIMAL or right is DelugeType.DECIMAL:
                return DelugeType.DECIMAL
            return DelugeType.NUMBER
        return None

    if op in ("-", "*", "/", "%"):
        if left.is_numeric() and right.is_numeric():
            if left is DelugeType.DECIMAL or right is DelugeType.DECIMAL:
                return DelugeType.DECIMAL
            if op == "/":
                return DelugeType.DECIMAL  # integer division produces decimal in Deluge
            return DelugeType.NUMBER
        return None

    return None
