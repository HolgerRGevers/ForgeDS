"""Project configuration loader for ForgeDS.

Reads forgeds.yaml from the consumer project root and provides
typed access to project-specific settings. Falls back to sensible
defaults when no config file is found, so tools work out-of-the-box.
"""

import os
from pathlib import Path


def _load_yaml_simple(path: str) -> dict:
    """Minimal YAML loader — handles the subset used by forgeds.yaml.

    Supports: scalars, lists (- item), nested dicts (key: value),
    inline lists [a, b], quoted strings. Does NOT support anchors,
    tags, or multi-line scalars.
    """
    result = {}
    stack = [(result, -1)]  # (current_dict, indent_level)
    current_list_key = None
    current_list = None

    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip()
            stripped = line.lstrip()

            # Skip empty lines and comments
            if not stripped or stripped.startswith("#"):
                continue

            indent = len(line) - len(stripped)

            # List item
            if stripped.startswith("- "):
                item_text = stripped[2:].strip()
                # Check if it's a list of inline lists like - ["a", "b"]
                if item_text.startswith("[") and item_text.endswith("]"):
                    inner = item_text[1:-1]
                    parts = [p.strip().strip('"').strip("'") for p in inner.split(",")]
                    if current_list is not None:
                        current_list.append(parts)
                    continue
                # Check if it's a dict-like list item: - key: value
                if ": " in item_text and not item_text.startswith('"'):
                    k, v = item_text.split(": ", 1)
                    entry = {k.strip(): _parse_value(v.strip())}
                    if current_list is not None:
                        current_list.append(entry)
                    continue
                # Simple scalar list item
                if current_list is not None:
                    current_list.append(_parse_value(item_text))
                continue

            # Key: value pair
            if ":" in stripped:
                colon_pos = stripped.index(":")
                key = stripped[:colon_pos].strip()
                rest = stripped[colon_pos + 1:].strip()

                # Pop stack to find the right parent dict
                while len(stack) > 1 and stack[-1][1] >= indent:
                    stack.pop()
                parent = stack[-1][0]

                if rest == "" or rest == "|":
                    # Nested dict or upcoming list
                    new_dict = {}
                    parent[key] = new_dict
                    stack.append((new_dict, indent))
                    current_list_key = None
                    current_list = None
                elif rest.startswith("[") and rest.endswith("]"):
                    # Inline list
                    inner = rest[1:-1]
                    if inner.strip():
                        items = [p.strip().strip('"').strip("'") for p in inner.split(",")]
                    else:
                        items = []
                    parent[key] = items
                    current_list_key = None
                    current_list = None
                else:
                    parent[key] = _parse_value(rest)
                    current_list_key = None
                    current_list = None

                # Check if next lines will be list items for this key
                # We detect this when the value is empty (already handled as nested dict)
                # or when we see "- " items at a deeper indent. For now, set up for list detection.
                if rest == "":
                    # Could be a dict or a list — we'll know when we see the first child.
                    # If first child is "- ", convert to list.
                    current_list_key = key
                    current_list = None
                    # We need a way to convert the dict to a list if needed
                    class _ListDetector:
                        def __init__(self, parent_dict, key_name):
                            self.parent = parent_dict
                            self.key = key_name
                            self.converted = False
                    detector = _ListDetector(parent, key)
                    stack[-1] = (parent, stack[-1][1])

            # Detect list after seeing "- " following an empty-value key
            if current_list_key and stripped.startswith("- ") and current_list is None:
                parent = stack[-1][0]
                if current_list_key in parent and isinstance(parent[current_list_key], dict) and len(parent[current_list_key]) == 0:
                    parent[current_list_key] = []
                    current_list = parent[current_list_key]
                elif current_list_key in parent and isinstance(parent[current_list_key], list):
                    current_list = parent[current_list_key]
                else:
                    current_list = []
                    parent[current_list_key] = current_list

                # Re-process this line as a list item
                item_text = stripped[2:].strip()
                if item_text.startswith("[") and item_text.endswith("]"):
                    inner = item_text[1:-1]
                    parts = [p.strip().strip('"').strip("'") for p in inner.split(",")]
                    current_list.append(parts)
                elif ": " in item_text and not item_text.startswith('"'):
                    k, v = item_text.split(": ", 1)
                    current_list.append({k.strip(): _parse_value(v.strip())})
                else:
                    current_list.append(_parse_value(item_text))

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
