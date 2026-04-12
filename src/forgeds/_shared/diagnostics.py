"""Shared diagnostic types used by all ForgeDS linters and tools.

Provides a common Severity enum and Diagnostic dataclass so that
lint_deluge, lint_access, lint_hybrid, the parser, and the interpreter
emit structurally identical output without duplicating type definitions.

The Diagnostic carries three layers of information:

1. **message** — Plain explanation. Written for someone who may not know
   Deluge syntax. Says what happened and what to do about it.
2. **ai_prompt** — Copy-pasteable prompt for the user's AI assistant.
   Structured so any LLM can diagnose the issue with full context.
3. **technical** — Raw details (token, AST node, stack trace) for
   debugging. Hidden by default in the UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(Enum):
    """Diagnostic severity levels — shared across all linters."""
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class Diagnostic:
    """A single finding from linting, parsing, or execution.

    Two audiences read every diagnostic: the user and the user's AI.
    The fields serve them differently:

        message     -> The user reads this. Plain language, no jargon.
        ai_prompt   -> The user copies this into their AI. Structured
                       context so the AI can diagnose and fix.
        technical   -> Hidden dropdown. Token positions, AST node types,
                       stack traces. For when the user or their AI needs
                       to dig deeper.

    Backward-compatible: the original 5 fields (file, line, rule,
    severity, message) remain required. The new fields are optional.
    """
    file: str
    line: int
    rule: str
    severity: Severity
    message: str
    ai_prompt: str = ""
    technical: str = ""
    source_line: str = ""       # The actual line of code (for context)
    col: int = 0                # 0-based column for precise pointing
    end_line: int = 0           # End of the span (for multi-line issues)
    end_col: int = 0

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: [{self.rule}] {self.severity.value}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output (web IDE, bridge API)."""
        d: dict[str, Any] = {
            "file": self.file,
            "line": self.line,
            "rule": self.rule,
            "severity": self.severity.value,
            "message": self.message,
        }
        if self.ai_prompt:
            d["ai_prompt"] = self.ai_prompt
        if self.technical:
            d["technical"] = self.technical
        if self.source_line:
            d["source_line"] = self.source_line
        if self.col:
            d["col"] = self.col
        return d


# ============================================================
# AI prompt builder
# ============================================================

def build_ai_prompt(
    file: str,
    line: int,
    rule: str,
    message: str,
    source_line: str = "",
    context: str = "",
) -> str:
    """Generate a structured prompt the user can paste into their AI.

    The prompt gives the AI everything it needs to diagnose and fix
    the issue without asking follow-up questions.
    """
    parts = [
        f"I have a Deluge script issue in `{file}` at line {line}.",
        f"The tool reports [{rule}]: {message}",
    ]
    if source_line:
        parts.append(f"The line of code is: `{source_line.strip()}`")
    if context:
        parts.append(context)
    parts.append("What is the correct fix? Show me the corrected code.")
    return "\n".join(parts)


# ============================================================
# Rich CLI formatter
# ============================================================

# ANSI escape codes
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_WHITE = "\033[37m"
_BG_RED = "\033[41m"
_BG_YELLOW = "\033[43m"
_BG_CYAN = "\033[46m"

_SEVERITY_STYLE = {
    Severity.ERROR: (_RED, _BOLD, "ERROR"),
    Severity.WARNING: (_YELLOW, "", "WARN "),
    Severity.INFO: (_CYAN, "", "INFO "),
}

_COPY_ICON = "\u2398"   # ⎘ (copy symbol — prints in most terminals)
_ARROW = "\u2192"       # →
_DOT = "\u2022"         # •


def format_diagnostic(
    diag: Diagnostic,
    index: int,
    *,
    use_color: bool = True,
    show_technical: bool = False,
    show_ai_prompt: bool = True,
    source_lines: list[str] | None = None,
) -> str:
    """Format a single diagnostic for terminal output.

    Renders the three-layer structure:
      [index] severity  file:line  rule
              Plain explanation
              [AI] Prompt for your AI (if present)
              [+]  Technical details (if --verbose)

    Args:
        diag: The diagnostic to format.
        index: 1-based index for numbering.
        use_color: Whether to emit ANSI colour codes.
        show_technical: Whether to show the technical dropdown.
        show_ai_prompt: Whether to show the AI prompt section.
        source_lines: If provided, show the actual source line.
    """
    color, weight, label = _SEVERITY_STYLE[diag.severity]
    lines: list[str] = []

    if use_color:
        # Header line: [1] ERROR  file.dg:10  DG001
        header = (
            f"  {_DIM}[{index}]{_RESET} "
            f"{color}{weight}{label}{_RESET}  "
            f"{_WHITE}{diag.file}:{diag.line}{_RESET}  "
            f"{_DIM}{diag.rule}{_RESET}"
        )
        lines.append(header)

        # Message (plain explanation)
        lines.append(f"      {diag.message}")

        # Source line (if available)
        src = diag.source_line
        if not src and source_lines and 0 < diag.line <= len(source_lines):
            src = source_lines[diag.line - 1]
        if src:
            lines.append(f"      {_DIM}{diag.line} | {src.rstrip()}{_RESET}")
            if diag.col > 0:
                pointer = " " * (diag.col + len(str(diag.line)) + 3) + f"{color}^{_RESET}"
                lines.append(f"      {pointer}")

        # AI prompt
        if show_ai_prompt and diag.ai_prompt:
            lines.append(f"      {_DIM}{_COPY_ICON} Prompt for your AI:{_RESET}")
            for prompt_line in diag.ai_prompt.splitlines():
                lines.append(f"        {_DIM}{prompt_line}{_RESET}")

        # Technical details
        if show_technical and diag.technical:
            lines.append(f"      {_DIM}{_DOT} Technical:{_RESET}")
            for tech_line in diag.technical.splitlines():
                lines.append(f"        {_DIM}{tech_line}{_RESET}")
    else:
        # Plain text (no ANSI)
        lines.append(f"  [{index}] {label}  {diag.file}:{diag.line}  {diag.rule}")
        lines.append(f"      {diag.message}")
        if diag.source_line:
            lines.append(f"      {diag.line} | {diag.source_line.rstrip()}")
        if show_ai_prompt and diag.ai_prompt:
            lines.append(f"      > Prompt for your AI:")
            for prompt_line in diag.ai_prompt.splitlines():
                lines.append(f"        {prompt_line}")
        if show_technical and diag.technical:
            lines.append(f"      + Technical:")
            for tech_line in diag.technical.splitlines():
                lines.append(f"        {tech_line}")

    lines.append("")  # blank line between diagnostics
    return "\n".join(lines)


def format_summary(
    diagnostics: list[Diagnostic],
    file_count: int,
    *,
    use_color: bool = True,
) -> str:
    """Format the summary line at the end of a lint run."""
    errors = sum(1 for d in diagnostics if d.severity == Severity.ERROR)
    warnings = sum(1 for d in diagnostics if d.severity == Severity.WARNING)
    infos = sum(1 for d in diagnostics if d.severity == Severity.INFO)

    parts = []
    if errors:
        e = f"{errors} error{'s' if errors != 1 else ''}"
        parts.append(f"{_RED}{_BOLD}{e}{_RESET}" if use_color else e)
    if warnings:
        w = f"{warnings} warning{'s' if warnings != 1 else ''}"
        parts.append(f"{_YELLOW}{w}{_RESET}" if use_color else w)
    if infos:
        i = f"{infos} info"
        parts.append(f"{_CYAN}{i}{_RESET}" if use_color else i)

    count_str = ", ".join(parts) if parts else "clean"
    files_str = f"{file_count} file{'s' if file_count != 1 else ''}"
    return f"\n  {_DIM}---{_RESET} {files_str}: {count_str} {_DIM}---{_RESET}" if use_color else f"\n  --- {files_str}: {', '.join(p for p in [f'{errors} error(s)', f'{warnings} warning(s)', f'{infos} info'] if True)} ---"
