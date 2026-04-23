"""Stdlib-only JSON Schema (draft-07 subset) validator for plugin-manifest.json.

Supported keywords:
  type, required, enum, pattern, minLength, properties, items,
  additionalProperties (bool form only).

Intentionally limited. Promote to `jsonschema` as soft-optional dep
if the subset proves inadequate.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from forgeds._shared.diagnostics import Diagnostic, Severity

SCHEMA_PATH = Path(__file__).parent / "configs" / "plugin-manifest.schema.json"

_JSON_TYPES = {
    "string":  str,
    "integer": int,
    "number":  (int, float),
    "boolean": bool,
    "array":   list,
    "object":  dict,
    "null":    type(None),
}


def _diag(file: str, line: int, severity: Severity, code: str, message: str) -> Diagnostic:
    return Diagnostic(file=file, line=line, rule=code, severity=severity, message=message)


def _validate(
    instance, schema: dict, path: str, file: str, out: list[Diagnostic],
) -> None:
    t = schema.get("type")
    if t is not None:
        py = _JSON_TYPES.get(t)
        if t == "integer" and isinstance(instance, bool):
            out.append(_diag(file, 1, Severity.ERROR, "WG-SCHEMA",
                             f"{path}: expected integer, got boolean"))
            return
        if py is not None and not isinstance(instance, py):
            out.append(_diag(file, 1, Severity.ERROR, "WG-SCHEMA",
                             f"{path}: expected {t}, got {type(instance).__name__}"))
            return

    if "enum" in schema and instance not in schema["enum"]:
        out.append(_diag(file, 1, Severity.ERROR, "WG-SCHEMA",
                         f"{path}: value {instance!r} not in enum {schema['enum']}"))

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            out.append(_diag(file, 1, Severity.ERROR, "WG-SCHEMA",
                             f"{path}: string shorter than minLength {schema['minLength']}"))
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            out.append(_diag(file, 1, Severity.ERROR, "WG-SCHEMA",
                             f"{path}: does not match pattern {schema['pattern']!r} (value: {instance!r})"))

    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                out.append(_diag(file, 1, Severity.ERROR, "WG-SCHEMA",
                                 f"{path}: missing required property {req!r}"))
        props = schema.get("properties", {})
        for key, val in instance.items():
            if key in props:
                _validate(val, props[key], f"{path}.{key}" if path else key, file, out)
            elif schema.get("additionalProperties") is False:
                out.append(_diag(file, 1, Severity.ERROR, "WG-SCHEMA",
                                 f"{path}: additional property {key!r} not allowed"))

    if isinstance(instance, list):
        items_schema = schema.get("items")
        if items_schema is not None:
            for i, item in enumerate(instance):
                _validate(item, items_schema, f"{path}[{i}]", file, out)


def validate_manifest_file(path: str) -> list[Diagnostic]:
    """Validate one plugin-manifest.json file. Returns list of Diagnostics."""
    p = Path(path)
    if not p.exists():
        return [_diag(path, 1, Severity.ERROR, "WG-SCHEMA",
                      f"plugin-manifest.json not found at {path}")]

    try:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
    except OSError as exc:
        return [_diag(path, 1, Severity.ERROR, "WG-SCHEMA",
                      f"failed to load schema: {exc}")]

    try:
        with open(p, encoding="utf-8") as f:
            instance = json.load(f)
    except json.JSONDecodeError as exc:
        return [_diag(path, exc.lineno, Severity.ERROR, "WG-SCHEMA",
                      f"invalid JSON: {exc.msg}")]
    except OSError as exc:
        return [_diag(path, 1, Severity.ERROR, "WG-SCHEMA",
                      f"could not read file: {exc}")]

    diagnostics: list[Diagnostic] = []
    _validate(instance, schema, path="", file=path, out=diagnostics)
    return diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Zoho Creator plugin-manifest.json files against the ForgeDS schema."
    )
    parser.add_argument("paths", nargs="+", help="plugin-manifest.json file paths")
    args = parser.parse_args()

    all_diags: list[Diagnostic] = []
    for path in args.paths:
        all_diags.extend(validate_manifest_file(path))

    for d in all_diags:
        print(str(d))

    if any(d.severity == Severity.ERROR for d in all_diags):
        return 2
    if any(d.severity == Severity.WARNING for d in all_diags):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
