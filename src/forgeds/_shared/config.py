"""Project configuration loader for ForgeDS.

Reads forgeds.yaml from the consumer project root and provides
typed access to project-specific settings. Falls back to sensible
defaults when no config file is found, so tools work out-of-the-box.
"""

import os
from pathlib import Path

from forgeds._shared.diagnostics import Diagnostic, Severity

_PRIMITIVE_TYPES = {"string", "integer", "number", "boolean", "any"}


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
                active_list.append(_parse_inline_list(item_text))
            # Inline dict item: - { key: value, ... }
            elif item_text.startswith("{") and item_text.endswith("}"):
                active_list.append(_parse_inline_dict(item_text))
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


def _split_respecting_brackets(text: str, delim: str = ",") -> list[str]:
    """Split `text` on `delim` but ignore separators inside [] / {} / quotes."""
    parts: list[str] = []
    depth_sq = depth_cu = 0
    in_single = in_double = False
    buf: list[str] = []
    for ch in text:
        if ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "'" and not in_double:
            in_single = not in_single
        elif not (in_single or in_double):
            if ch == "[":
                depth_sq += 1
            elif ch == "]":
                depth_sq -= 1
            elif ch == "{":
                depth_cu += 1
            elif ch == "}":
                depth_cu -= 1
            elif ch == delim and depth_sq == 0 and depth_cu == 0:
                parts.append("".join(buf).strip())
                buf = []
                continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _parse_inline_dict(text: str) -> dict:
    """Parse `{ k: v, k2: v2, ... }` into a dict. Nested inline collections supported."""
    inner = text.strip()[1:-1].strip()
    if not inner:
        return {}
    out: dict = {}
    for part in _split_respecting_brackets(inner, ","):
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        out[k.strip().strip('"').strip("'")] = _parse_value(v.strip())
    return out


def _parse_inline_list(text: str) -> list:
    """Parse `[a, b, {k: v}]` into a list."""
    inner = text.strip()[1:-1].strip()
    if not inner:
        return []
    return [_parse_value(p) for p in _split_respecting_brackets(inner, ",")]


def _parse_value(text: str):
    """Parse a YAML scalar or inline-collection value."""
    text = text.strip()
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1]
    if text.startswith("'") and text.endswith("'"):
        return text[1:-1]
    if text.startswith("{") and text.endswith("}"):
        return _parse_inline_dict(text)
    if text.startswith("[") and text.endswith("]"):
        return _parse_inline_list(text)
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


def _cfg_diag(rule: str, severity: Severity, message: str, file: str = "forgeds.yaml") -> Diagnostic:
    return Diagnostic(file=file, line=1, rule=rule, severity=severity, message=message)


def _base_type(type_str: str) -> str:
    """Strip a trailing `[]` to get the element type."""
    t = type_str.strip()
    while t.endswith("[]"):
        t = t[:-2]
    return t


def validate_custom_apis(cfg: dict) -> list[Diagnostic]:
    """Validate `custom_apis` (Form A or Form B) and widget cross-refs.

    Emits:
      - CFG010 ERROR  when mixed list/dict forms detected
      - CFG011 INFO   once per config when Form A (bare list) is used
      - CFG012 ERROR  when widgets[*].consumes_apis[i] is not declared
      - CFG013 WARNING when `returns` or `params[i].type` is an unknown named type
      - CFG014 ERROR  when a param dict is missing `name` or `type`
      - CFG015 ERROR  when `permissions` is not a list of strings
    """
    diags: list[Diagnostic] = []
    apis = cfg.get("custom_apis")
    if apis is None:
        apis = []

    form_a = isinstance(apis, list) and all(isinstance(x, str) for x in apis)
    form_b = isinstance(apis, dict)
    list_with_dicts = isinstance(apis, list) and any(isinstance(x, dict) for x in apis)

    if list_with_dicts or (isinstance(apis, list) and not form_a and apis):
        diags.append(_cfg_diag(
            "CFG010", Severity.ERROR,
            "custom_apis: mixes bare-list and dict forms. Pick one per project.",
        ))
        return diags

    if form_a and apis:
        diags.append(_cfg_diag(
            "CFG011", Severity.INFO,
            "custom_apis declared in short (bare-list) form; typegen will skip.",
        ))

    if form_b:
        known_types = {name for name in apis.keys()} | _PRIMITIVE_TYPES
        for api_name, api_def in apis.items():
            if not isinstance(api_def, dict):
                continue

            params = api_def.get("params") or []
            if not isinstance(params, list):
                continue
            for i, p in enumerate(params):
                if not isinstance(p, dict):
                    continue
                missing = [k for k in ("name", "type") if k not in p]
                if missing:
                    diags.append(_cfg_diag(
                        "CFG014", Severity.ERROR,
                        f"custom_apis.{api_name}.params[{i}] missing required key(s): "
                        f"{', '.join(missing)}",
                    ))
                    continue
                p_type = p.get("type")
                if isinstance(p_type, str):
                    base = _base_type(p_type)
                    if base not in known_types:
                        diags.append(_cfg_diag(
                            "CFG013", Severity.WARNING,
                            f"custom_apis.{api_name}.params[{i}].type references "
                            f"unknown named type {base!r}",
                        ))

            returns = api_def.get("returns")
            if isinstance(returns, str) and returns:
                base = _base_type(returns)
                if base not in known_types:
                    diags.append(_cfg_diag(
                        "CFG013", Severity.WARNING,
                        f"custom_apis.{api_name}.returns references unknown named type "
                        f"{base!r}",
                    ))

            perms = api_def.get("permissions")
            if perms is not None:
                if not (isinstance(perms, list) and all(isinstance(s, str) for s in perms)):
                    diags.append(_cfg_diag(
                        "CFG015", Severity.ERROR,
                        f"custom_apis.{api_name}.permissions must be a list of strings",
                    ))

    # CFG012 — widget consumes_apis[i] must appear in custom_apis
    declared = set()
    if form_a:
        declared = set(apis)
    elif form_b:
        declared = set(apis.keys())

    widgets = cfg.get("widgets") or {}
    if isinstance(widgets, dict):
        for w_name, w_def in widgets.items():
            if not isinstance(w_def, dict):
                continue
            for api_ref in w_def.get("consumes_apis") or []:
                if api_ref not in declared:
                    diags.append(_cfg_diag(
                        "CFG012", Severity.ERROR,
                        f"widget {w_name!r} consumes_apis entry {api_ref!r} "
                        "is not in custom_apis",
                    ))
    return diags


def normalize_custom_apis(cfg: dict) -> dict:
    """Return a new cfg dict with custom_apis in dict-of-dicts form (in-memory).

    Form A (`["a", "b"]`) → `{"a": {}, "b": {}}`. Form B is returned unchanged.
    The original form is recorded at `cfg["_custom_apis_form"]` = `"A" | "B"`.
    """
    out = dict(cfg)
    apis = cfg.get("custom_apis")
    if isinstance(apis, list) and all(isinstance(x, str) for x in apis):
        out["custom_apis"] = {name: {} for name in apis}
        out["_custom_apis_form"] = "A"
    elif isinstance(apis, dict):
        out["custom_apis"] = apis
        out["_custom_apis_form"] = "B"
    else:
        out["_custom_apis_form"] = "A"
    return out


def load_config_with_diagnostics(start: str = None) -> tuple[dict, list[Diagnostic]]:
    """Load forgeds.yaml and return (cfg, CFG diagnostics).

    The returned cfg is normalized (custom_apis always a dict) with the
    original shape recorded at cfg['_custom_apis_form'].
    """
    raw = load_config(start)
    diags = validate_custom_apis(raw)
    return normalize_custom_apis(raw), diags


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
