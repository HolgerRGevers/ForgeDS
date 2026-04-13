"""Project configuration loader for ForgeDS.

Reads forgeds.yaml from the consumer project root and provides
typed access to project-specific settings. Falls back to sensible
defaults when no config file is found, so tools work out-of-the-box.
"""

import os
from pathlib import Path

# Module-level caches — avoids repeated filesystem walks and YAML re-parsing
_project_root_cache: dict[str | None, Path] = {}
_config_cache: dict[str | None, dict] = {}
_db_dir_cache: Path | None = None


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
    current_list_parent = None  # dict that owns current_list_key

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

                # First list item after an empty-value key: convert the
                # placeholder dict into a list.
                if current_list_key and current_list is None and current_list_parent is not None:
                    target = current_list_parent
                    if (current_list_key in target
                            and isinstance(target[current_list_key], dict)
                            and len(target[current_list_key]) == 0):
                        target[current_list_key] = []
                        current_list = target[current_list_key]

                if current_list is not None:
                    if item_text.startswith("[") and item_text.endswith("]"):
                        inner = item_text[1:-1]
                        parts = [p.strip().strip('"').strip("'") for p in inner.split(",")]
                        current_list.append(parts)
                    elif ": " in item_text and not item_text.startswith('"'):
                        k, v = item_text.split(": ", 1)
                        entry = {k.strip(): _parse_value(v.strip())}
                        current_list.append(entry)
                        # Track for continuation keys on following lines
                        self_indent = indent + 2  # expected indent for "- " content
                        stack.append((entry, self_indent))
                    else:
                        current_list.append(_parse_value(item_text))
                continue

            # Continuation key for a multi-key dict inside a list
            # e.g. "  parent: [...]" following "- child: [...]"
            if (current_list is not None and ":" in stripped
                    and len(stack) > 1 and isinstance(stack[-1][0], dict)
                    and stack[-1][0] in current_list
                    and indent >= stack[-1][1]):
                colon_pos = stripped.index(":")
                key = stripped[:colon_pos].strip()
                rest = stripped[colon_pos + 1:].strip()
                stack[-1][0][key] = _parse_value(rest)
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

                # Reset list state on any key: line
                current_list_key = None
                current_list = None
                current_list_parent = None

                if rest == "" or rest == "|":
                    # Nested dict or upcoming list — create a placeholder dict.
                    # If the first child turns out to be "- ", it will be
                    # converted to a list above.
                    new_dict = {}
                    parent[key] = new_dict
                    stack.append((new_dict, indent))
                    current_list_key = key
                    current_list_parent = parent
                elif rest.startswith("[") and rest.endswith("]"):
                    # Inline list
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
    """Parse a YAML scalar value (or inline list)."""
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1]
        if not inner.strip():
            return []
        return [p.strip().strip('"').strip("'") for p in inner.split(",")]
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
    if start in _project_root_cache:
        return _project_root_cache[start]
    current = Path(start) if start else Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / "forgeds.yaml").exists():
            _project_root_cache[start] = parent
            return parent
    result = Path.cwd()
    _project_root_cache[start] = result
    return result


def load_config(start: str = None) -> dict:
    """Load forgeds.yaml from the project root.

    Returns the parsed config dict, or an empty dict with sensible
    defaults if no config file is found.  Results are cached so
    repeated calls avoid filesystem walks and YAML re-parsing.
    """
    if start in _config_cache:
        return _config_cache[start]

    root = find_project_root(start)
    config_path = root / "forgeds.yaml"

    if config_path.exists():
        result = _load_yaml_simple(str(config_path))
        _config_cache[start] = result
        return result

    # Sensible defaults when no config exists
    defaults = {
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
    _config_cache[start] = defaults
    return defaults


def get_db_dir() -> Path:
    """Return the directory where ForgeDS stores generated .db files.

    Uses FORGEDS_DB_DIR env var if set, otherwise the tool's own
    package directory (backward-compatible with ERM layout).
    """
    global _db_dir_cache
    if _db_dir_cache is not None:
        return _db_dir_cache
    env_dir = os.environ.get("FORGEDS_DB_DIR")
    if env_dir:
        _db_dir_cache = Path(env_dir)
        return _db_dir_cache
    # Default: next to the consumer project root
    root = find_project_root()
    tools_dir = root / "tools"
    if tools_dir.is_dir():
        _db_dir_cache = tools_dir
        return _db_dir_cache
    _db_dir_cache = root
    return _db_dir_cache
