"""Shared diagnostic types used by all ForgeDS linters.

Provides a common Severity enum and Diagnostic dataclass so that
lint_deluge, lint_access, and lint_hybrid emit structurally identical
output without duplicating type definitions.
"""

from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    """Diagnostic severity levels — shared across all linters."""
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class Diagnostic:
    """A single lint finding.

    Attributes:
        file: Path to the source file (relative or absolute).
        line: 1-based line number where the issue was found.
        rule: Rule code (e.g. "DG001", "AV003", "HY010").
        severity: ERROR, WARNING, or INFO.
        message: Human-readable description of the issue.
    """
    file: str
    line: int
    rule: str
    severity: Severity
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: [{self.rule}] {self.severity.value}: {self.message}"
