"""Project configuration loader for ForgeDS.

Reads forgeds.yaml from the consumer project root and provides
typed access to project-specific settings. Falls back to sensible
defaults when no config file is found, so tools work out-of-the-box.
"""

import os
from pathlib import Path


def _load_yaml_simple(path: str) -> dict:
    """Minimal YAML loader — handles the subset used by forgeds.yaml.

    Supports: scalars, lists (``- item``), nested dicts via indentation,
    multi-key list items (``- key: val\\n  key2: val2``), inline lists
    ``[a, b]``, and quoted strings. Does NOT support anchors, tags, or
    multi-line scalars.
    """
    lines = []
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip()
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(line) - len(stripped)
            lines.append((indent, stripped))

    result = {}
    # stack entries: (container, indent) where container is a dict
    stack = [(result, -1)]
    # When we see ``key:`` with no value, the key could be a dict or list.
    # We record (parent_dict, key, indent) so we can convert on first child.
    pending_key = None  # (parent_dict, key_name, key_indent)
    # Active list being appended to, plus the indent of its ``- `` items.
    active_list = None  # the list object
    active_list_indent = -1
    # When a list item is a dict (``- key: value``), additional keys at
    # a deeper indent belong to the same dict entry.
    active_list_item = None  # the dict being built
    active_list_item_indent = -1

    for idx, (indent, stripped) in enumerate(lines):

        # --- List item --------------------------------------------------
        if stripped.startswith("- "):
            item_text = stripped[2:].strip()

            # If there's a pending empty key, convert it to a list.
            if pending_key is not None:
                p_dict, p_key, p_indent = pending_key
                lst = []
                p_dict[p_key] = lst
                active_list = lst
                active_list_indent = indent
                pending_key = None
                # Pop any placeholder dict that was pushed for this key.
                while len(stack) > 1 and stack[-1][1] >= indent:
                    stack.pop()
            elif active_list is not None and indent != active_list_indent:
                # Indent changed — this belongs to a different level.
                # Walk up the stack to find the right container.
                while len(stack) > 1 and stack[-1][1] >= indent:
                    stack.pop()
                # Reset list state — the pending-key path above will
                # handle this if there was one; otherwise this is an
                # error in the YAML but we do our best.
                active_list = None

            # Close any prior multi-key list-item dict.
            active_list_item = None

            if active_list is None:
                # First list item without a pending key — find or create
                # the list on the stack. This handles the rare case where
                # the YAML starts with ``- item`` at the top level.
                active_list = []
                stack[-1][0]["_list"] = active_list
                active_list_indent = indent

            # Inline list item: - [a, b]
            if item_text.startswith("[") and item_text.endswith("]"):
                inner = item_text[1:-1]
                parts = [p.strip().strip('"').strip("'") for p in inner.split(",")]
                active_list.append(parts)
            # Dict list item: - key: value
            elif ": " in item_text and not item_text.startswith('"'):
                k, v = item_text.split(": ", 1)
                entry = {k.strip(): _parse_value(v.strip())}
                active_list.append(entry)
                active_list_item = entry
                # Content indent for continuation keys = indent of "- " + 2
                active_list_item_indent = indent + 2
            else:
                # Simple scalar
                active_list.append(_parse_value(item_text))

            continue

        # --- Continuation of a multi-key list item ----------------------
        if (active_list_item is not None
                and indent >= active_list_item_indent
                and ":" in stripped):
            colon_pos = stripped.index(":")
            key = stripped[:colon_pos].strip()
            rest = stripped[colon_pos + 1:].strip()
            active_list_item[key] = _parse_value(rest) if rest else rest
            continue

        # --- Key: value pair --------------------------------------------
        if ":" in stripped:
            # We're no longer in a list-item context.
            active_list_item = None

            colon_pos = stripped.index(":")
            key = stripped[:colon_pos].strip()
            rest = stripped[colon_pos + 1:].strip()

            # Resolve pending empty key — if we reach here it was a dict.
            if pending_key is not None:
                # The pending key already created a dict on the stack;
                # just clear the flag.
                pending_key = None

            # Pop stack to find the right parent dict.
            while len(stack) > 1 and stack[-1][1] >= indent:
                stack.pop()
            parent = stack[-1][0]

            # Reset list state when we leave list territory.
            if active_list is not None and indent <= active_list_indent:
                active_list = None
                active_list_indent = -1

            if rest == "" or rest == "|":
                new_dict = {}
                parent[key] = new_dict
                stack.append((new_dict, indent))
                pending_key = (parent, key, indent)
            elif rest.startswith("[") and rest.endswith("]"):
                inner = rest[1:-1]
                if inner.strip():
                    items = [p.strip().strip('"').strip("'") for p in inner.split(",")]
                else:
                    items = []
                parent[key] = items
            else:
                parent[key] = _parse_value(rest)

    return result


def _parse_value(text: str):
    """Parse a YAML scalar value."""
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1]
    if text.startswith("'") and text.endswith("'"):
        return text[1:-1]
    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False
    if text.lower() == "null" or text == "~":
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text


def find_project_root(start: str = None) -> Path:
    """Walk up from start (default: cwd) looking for forgeds.yaml."""
    current = Path(start) if start else Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / "forgeds.yaml").exists():
            return parent
    return Path.cwd()


def load_config(start: str = None) -> dict:
    """Load forgeds.yaml from the project root.

    Returns the parsed config dict, or an empty dict with sensible
    defaults if no config file is found.
    """
    root = find_project_root(start)
    config_path = root / "forgeds.yaml"

    if config_path.exists():
        return _load_yaml_simple(str(config_path))

    # Sensible defaults when no config exists
    return {
        "project": {"name": "Unknown", "version": "0.0.0"},
        "lint": {
            "threshold_fallback": "999.99",
            "dual_threshold_fallback": "5000.00",
            "demo_email_domains": ["yourdomain.com", "example.com", "placeholder.com"],
        },
        "schema": {
            "mandatory_zoho_fields": [],
            "table_to_form": {},
            "fk_relationships": [],
            "upload_order": [],
            "exclude_fields": ["ID", "Added_User"],
        },
        "seed_data_dir": "config/seed-data",
        "custom_apis": [],
        "widgets": {},
    }


def get_db_dir() -> Path:
    """Return the directory where ForgeDS stores generated .db files.

    Uses FORGEDS_DB_DIR env var if set, otherwise the tool's own
    package directory (backward-compatible with ERM layout).
    """
    env_dir = os.environ.get("FORGEDS_DB_DIR")
    if env_dir:
        return Path(env_dir)
    # Default: next to the consumer project root
    root = find_project_root()
    tools_dir = root / "tools"
    if tools_dir.is_dir():
        return tools_dir
    return root
