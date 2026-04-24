"""Loader, validator, and atomic writer for widget-spec.yaml.

Phase 2C. Emits Phase 2A Diagnostics under the WSP rule prefix.

v1 restriction: `description` must be a single-line string. Multi-line
folded/block scalars (`description: >` or `description: |`) are not
supported by the stdlib YAML loader and will fail validation.

Surface:
- `load_spec(path)` — read YAML, validate against widget-spec.schema.json,
  return `(spec_dict, diagnostics)`.
- `check_cross_refs(spec, manifest, directory_name, config)` — cross-
  validate spec vs manifest vs directory name vs forgeds.yaml.
- `write_deployment_block(path, deployment)` — atomic in-place rewrite
  of just the `deployment:` sub-block. Author formatting elsewhere in
  the file is preserved.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from forgeds._shared.config import _load_yaml_simple
from forgeds._shared.diagnostics import Diagnostic, Severity

SCHEMA_PATH = Path(__file__).parent / "configs" / "widget-spec.schema.json"

_JSON_TYPES = {
    "string":  str,
    "integer": int,
    "number":  (int, float),
    "boolean": bool,
    "array":   list,
    "object":  dict,
    "null":    type(None),
}


def _diag(file: str, severity: Severity, code: str, message: str) -> Diagnostic:
    return Diagnostic(file=file, line=1, rule=code, severity=severity, message=message)


def _type_matches(instance, type_spec) -> bool:
    """Match a Draft-07 type string OR a list of type strings."""
    if isinstance(type_spec, list):
        return any(_type_matches(instance, t) for t in type_spec)
    py = _JSON_TYPES.get(type_spec)
    if py is None:
        return True
    if type_spec == "integer" and isinstance(instance, bool):
        return False
    return isinstance(instance, py)


def _validate(
    instance,
    schema: dict,
    path: str,
    file: str,
    out: list[Diagnostic],
    *,
    decorative_paths: set[str],
) -> None:
    """Recursive Draft-07 subset validator — mirrors validate_manifest._validate
    but emits WSP### codes and distinguishes load-bearing vs decorative paths.
    """
    t = schema.get("type")
    if t is not None and not _type_matches(instance, t):
        code, sev = ("WSP005", Severity.WARNING) if path in decorative_paths else ("WSP002", Severity.ERROR)
        out.append(_diag(file, sev, code,
                         f"{path}: expected {t}, got {type(instance).__name__}"))
        return

    if "enum" in schema and instance not in schema["enum"]:
        out.append(_diag(file, Severity.ERROR, "WSP002",
                         f"{path}: value {instance!r} not in enum {schema['enum']}"))
        return

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            out.append(_diag(file, Severity.ERROR, "WSP002",
                             f"{path}: string shorter than minLength {schema['minLength']}"))

    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                out.append(_diag(file, Severity.ERROR, "WSP002",
                                 f"{path or '(root)'}: missing required property {req!r}"))
        props = schema.get("properties", {})
        for key, val in instance.items():
            if key in props:
                child_path = f"{path}.{key}" if path else key
                _validate(val, props[key], child_path, file, out,
                          decorative_paths=decorative_paths)

    if isinstance(instance, list):
        items_schema = schema.get("items")
        if items_schema is not None:
            for i, item in enumerate(instance):
                _validate(item, items_schema, f"{path}[{i}]", file, out,
                          decorative_paths=decorative_paths)


# Top-level spec keys classified as "decorative" per spec §4.4 — wrong
# type becomes a WARNING (WSP005) rather than an ERROR. "Load-bearing"
# keys use WSP002 ERROR. Required-field absence always uses WSP002.
_DECORATIVE_PATHS = {"ui_primitives", "state_model", "events_bound"}


def load_spec(path: str) -> tuple[dict, list[Diagnostic]]:
    """Load + validate a widget-spec.yaml. Returns `(spec, diagnostics)`.

    On missing file → empty dict + WSP001. On parse failure → empty dict
    + WSP001. On schema violations → partial spec + WSP002/WSP005.
    """
    if not os.path.exists(path):
        return ({}, [_diag(path, Severity.ERROR, "WSP001",
                           f"widget-spec.yaml not found at {path}")])

    try:
        spec = _load_yaml_simple(path)
    except Exception as exc:
        return ({}, [_diag(path, Severity.ERROR, "WSP001",
                           f"widget-spec.yaml parse error: {exc}")])

    if not isinstance(spec, dict):
        return ({}, [_diag(path, Severity.ERROR, "WSP001",
                           "widget-spec.yaml did not parse to an object")])

    try:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
    except OSError as exc:
        return (spec, [_diag(path, Severity.ERROR, "WSP002",
                             f"failed to load widget-spec schema: {exc}")])

    diags: list[Diagnostic] = []
    _validate(spec, schema, path="", file=path, out=diags,
              decorative_paths=_DECORATIVE_PATHS)
    return (spec, diags)


def check_cross_refs(
    spec: dict,
    manifest: dict | None,
    directory_name: str | None,
    config: dict,
) -> list[Diagnostic]:
    """Cross-validate spec against manifest + directory name + forgeds.yaml.

    Emits:
      WSP003 ERROR if spec.name != manifest.name or spec.name != directory_name
      WSP004 WARNING if consumes_apis[i] not in config.custom_apis

    `manifest` and `directory_name` may be None — checks are skipped.
    """
    diags: list[Diagnostic] = []
    file_label = "widget-spec.yaml"
    spec_name = spec.get("name")

    if manifest is not None and spec_name is not None:
        m_name = manifest.get("name")
        if m_name is not None and m_name != spec_name:
            diags.append(_diag(
                file_label, Severity.ERROR, "WSP003",
                f"spec.name {spec_name!r} != manifest.name {m_name!r}",
            ))

    if directory_name is not None and spec_name is not None:
        if directory_name != spec_name:
            diags.append(_diag(
                file_label, Severity.ERROR, "WSP003",
                f"spec.name {spec_name!r} != directory name {directory_name!r}",
            ))

    consumes = spec.get("consumes_apis") or []
    custom_apis = config.get("custom_apis") or []
    # custom_apis may be list-of-strings (Form A) or dict-of-dicts (Form B)
    if isinstance(custom_apis, dict):
        declared = set(custom_apis.keys())
    elif isinstance(custom_apis, list):
        declared = set(x for x in custom_apis if isinstance(x, str))
    else:
        declared = set()

    if isinstance(consumes, list):
        for api in consumes:
            if isinstance(api, str) and declared and api not in declared:
                diags.append(_diag(
                    file_label, Severity.WARNING, "WSP004",
                    f"consumes_apis entry {api!r} is not declared in forgeds.yaml custom_apis",
                ))

    return diags


# ============================================================
# Atomic deployment-block writer
# ============================================================


_DEPLOYMENT_KEY_PATTERN = re.compile(r"^deployment\s*:\s*$")


def _format_deployment_block(deployment: dict) -> list[str]:
    """Render the deployment: sub-block as a list of output lines.

    Two-space indent under the top-level key. Values serialized as bare
    strings when possible; `null` rendered explicitly. String values are
    quoted with double quotes only if they contain special YAML chars.
    """
    def _render_value(v) -> str:
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)
        s = str(v)
        # Quote if contains colon / starts with special / contains leading-trailing spaces
        if (":" in s or s.startswith(("-", "?", "|", ">", "@", "*", "&", "[", "]", "{", "}", "#"))
                or s != s.strip()):
            return '"' + s.replace('"', '\\"') + '"'
        return s

    lines = ["deployment:"]
    # Preserve canonical ordering per spec §4.3
    canonical_order = ("last_uploaded_at", "last_uploaded_version", "last_uploaded_target")
    for key in canonical_order:
        if key in deployment:
            lines.append(f"  {key}: {_render_value(deployment[key])}")
    # Anything not in canonical_order (future-proofing) appended last
    for key, val in deployment.items():
        if key not in canonical_order:
            lines.append(f"  {key}: {_render_value(val)}")
    return lines


def write_deployment_block(path: str, deployment: dict) -> None:
    """Rewrite only the `deployment:` sub-block of a widget-spec.yaml.

    Strategy:
      1. Read full file as lines.
      2. Find the first line whose stripped form is `deployment:` (indent 0).
      3. Find the next line at indent 0 (or EOF) — that marks the end of
         the existing deployment block.
      4. Splice: [prefix lines] + [rendered new block] + [suffix lines].
      5. If no deployment: line found, append the new block at EOF
         (ensuring a trailing newline first).

    Atomicity:
      Write to `<path>.forgeds-tmp` in the same directory, then
      `os.replace()` to swap in. `os.replace` is atomic on POSIX and
      Windows for same-volume renames. On any failure during write,
      the tmp file is removed and the original is left intact.
    """
    p = Path(path)
    with open(p, "r", encoding="utf-8", newline="") as f:
        content = f.read()

    # Preserve original line-ending style. Work on lines without stripping \n.
    if "\r\n" in content:
        newline = "\r\n"
    else:
        newline = "\n"
    lines = content.split(newline)
    # split() drops the trailing empty if the file ends in newline — track it.
    had_trailing_newline = content.endswith(newline)

    dep_start: int | None = None
    for i, line in enumerate(lines):
        if _DEPLOYMENT_KEY_PATTERN.match(line):
            dep_start = i
            break

    new_block_lines = _format_deployment_block(deployment)

    if dep_start is None:
        # Append at EOF
        # Strip trailing empty entries from split() to avoid double-blank lines
        while lines and lines[-1] == "":
            lines.pop()
        combined = lines + new_block_lines
        out_text = newline.join(combined) + newline
    else:
        # Find end of existing deployment block — next top-level (indent 0)
        # non-empty, non-comment line.
        dep_end = len(lines)
        for j in range(dep_start + 1, len(lines)):
            line = lines[j]
            if line == "":
                continue
            if line.startswith("#"):
                continue
            if not line.startswith((" ", "\t")):
                dep_end = j
                break
        prefix = lines[:dep_start]
        suffix = lines[dep_end:]
        combined = prefix + new_block_lines + suffix
        out_text = newline.join(combined)
        if had_trailing_newline and not out_text.endswith(newline):
            out_text += newline

    tmp_path = str(p) + ".forgeds-tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8", newline="") as f:
            f.write(out_text)
        os.replace(tmp_path, str(p))
    except Exception:
        # Clean up tmp if it exists
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise
