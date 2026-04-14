"""Regex patterns for detecting Zoho documentation callout boxes.

Zoho docs use several callout styles (Note, Pro Tip, Important,
Very Important). These patterns detect both HTML and markdown
representations so the token parser can classify content correctly.
"""

from __future__ import annotations

import re
from forgeds.knowledge._types import ContentType

# ---------------------------------------------------------------------------
# HTML callout patterns (used by scraper when converting raw HTML)
# ---------------------------------------------------------------------------

# Zoho wraps callouts in <div class="zd-note|tip|important|...">
_HTML_NOTE = re.compile(
    r'<div[^>]*class="[^"]*\bnote\b[^"]*"[^>]*>(.*?)</div>',
    re.DOTALL | re.IGNORECASE,
)
_HTML_TIP = re.compile(
    r'<div[^>]*class="[^"]*\b(?:pro[_-]?tip|tip)\b[^"]*"[^>]*>(.*?)</div>',
    re.DOTALL | re.IGNORECASE,
)
_HTML_IMPORTANT = re.compile(
    r'<div[^>]*class="[^"]*\bimportant\b[^"]*"[^>]*>(.*?)</div>',
    re.DOTALL | re.IGNORECASE,
)
_HTML_VERY_IMPORTANT = re.compile(
    r'<div[^>]*class="[^"]*\bvery[_-]?important\b[^"]*"[^>]*>(.*?)</div>',
    re.DOTALL | re.IGNORECASE,
)

HTML_CALLOUT_PATTERNS: list[tuple[re.Pattern, ContentType]] = [
    (_HTML_VERY_IMPORTANT, ContentType.VERY_IMPORTANT),
    (_HTML_IMPORTANT, ContentType.IMPORTANT),
    (_HTML_TIP, ContentType.PRO_TIP),
    (_HTML_NOTE, ContentType.NOTE),
]

# ---------------------------------------------------------------------------
# Markdown callout patterns (used by token_parser on raw_md files)
# ---------------------------------------------------------------------------

# After conversion to markdown, callouts often appear as:
#   > **Note:** ...
#   > **Pro Tip:** ...
#   > **Important:** ...
#   > **Very Important:** ...
# Or Zoho-style bold labels without blockquote:
#   **Note:** ...

_MD_PREFIX = r"(?:>\s*)?(?:\*\*|__)"
# Colon can appear before OR after the closing bold marker:
#   **Note:** ...  (colon inside bold)  — most common in Zoho docs
#   **Note**:  ... (colon outside bold)
_MD_SUFFIX = r"[:.]?(?:\*\*|__)[:.]?\s*"

MD_NOTE = re.compile(
    rf"^{_MD_PREFIX}Note{_MD_SUFFIX}(.+)",
    re.IGNORECASE | re.MULTILINE,
)
MD_TIP = re.compile(
    rf"^{_MD_PREFIX}(?:Pro\s*Tip|Tip){_MD_SUFFIX}(.+)",
    re.IGNORECASE | re.MULTILINE,
)
MD_IMPORTANT = re.compile(
    rf"^{_MD_PREFIX}Important{_MD_SUFFIX}(.+)",
    re.IGNORECASE | re.MULTILINE,
)
MD_VERY_IMPORTANT = re.compile(
    rf"^{_MD_PREFIX}Very\s+Important{_MD_SUFFIX}(.+)",
    re.IGNORECASE | re.MULTILINE,
)

MD_CALLOUT_PATTERNS: list[tuple[re.Pattern, ContentType]] = [
    (MD_VERY_IMPORTANT, ContentType.VERY_IMPORTANT),
    (MD_IMPORTANT, ContentType.IMPORTANT),
    (MD_TIP, ContentType.PRO_TIP),
    (MD_NOTE, ContentType.NOTE),
]

# ---------------------------------------------------------------------------
# Code block detection
# ---------------------------------------------------------------------------

MD_CODE_BLOCK = re.compile(
    r"^```[\w]*\n(.*?)^```",
    re.MULTILINE | re.DOTALL,
)

# Inline function signature pattern (Zoho docs list signatures as
# <return_type> <function_name>(<params>))
MD_SIGNATURE = re.compile(
    r"^(?:void|string|int|float|bool|list|map|bigint|decimal|date|datetime)\s+"
    r"\w+\s*\(.*?\)",
    re.IGNORECASE | re.MULTILINE,
)


def classify_block(text: str) -> ContentType:
    """Determine the ContentType of a markdown text block."""
    stripped = text.strip()

    # Check callouts (most specific first)
    for pattern, ctype in MD_CALLOUT_PATTERNS:
        if pattern.search(stripped):
            return ctype

    # Code block
    if MD_CODE_BLOCK.search(stripped) or stripped.startswith("```"):
        return ContentType.CODE_EXAMPLE

    # Function signature
    if MD_SIGNATURE.match(stripped):
        return ContentType.SIGNATURE

    # Table row (pipe-delimited)
    lines = stripped.splitlines()
    if lines and all("|" in ln for ln in lines if ln.strip()):
        return ContentType.TABLE_ROW

    return ContentType.PROSE
