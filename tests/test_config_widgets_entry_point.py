"""Tests for widgets[name].entry_point resolution (Phase 2B Task 1)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from forgeds._shared.config import load_config, resolve_widget_entry_point


def _write_yaml(tmp: str, body: str) -> Path:
    path = Path(tmp) / "forgeds.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_widget_without_entry_point_defaults_to_none_in_config():
    yaml = (
        "widgets:\n"
        "  w:\n"
        "    root: src/widgets/w/\n"
        "    consumes_apis: [a]\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        _write_yaml(tmp, yaml)
        cfg = load_config(start=tmp)
        assert cfg["widgets"]["w"].get("entry_point") is None


def test_widget_with_entry_point_parses_string():
    yaml = (
        "widgets:\n"
        "  w:\n"
        "    root: src/widgets/w/\n"
        "    entry_point: src/main.js\n"
        "    consumes_apis: [a]\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        _write_yaml(tmp, yaml)
        cfg = load_config(start=tmp)
        assert cfg["widgets"]["w"]["entry_point"] == "src/main.js"


def test_resolve_entry_point_defaults_to_root_index_js():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        widget_root = root / "src" / "widgets" / "w"
        widget_root.mkdir(parents=True)
        widget_def = {"root": "src/widgets/w/", "consumes_apis": ["a"]}
        resolved = resolve_widget_entry_point(widget_def, root)
        assert resolved == (widget_root / "index.js").resolve()


def test_resolve_entry_point_uses_override_when_present():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        widget_root = root / "src" / "widgets" / "w"
        widget_root.mkdir(parents=True)
        widget_def = {
            "root": "src/widgets/w/",
            "entry_point": "main.js",
            "consumes_apis": ["a"],
        }
        resolved = resolve_widget_entry_point(widget_def, root)
        assert resolved == (widget_root / "main.js").resolve()


def test_resolve_entry_point_is_relative_to_root_not_project_root():
    """`entry_point: src/main.js` resolves under the widget root, not the project root."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        widget_root = root / "src" / "widgets" / "w"
        widget_root.mkdir(parents=True)
        widget_def = {
            "root": "src/widgets/w/",
            "entry_point": "src/main.js",
        }
        resolved = resolve_widget_entry_point(widget_def, root)
        assert resolved == (widget_root / "src" / "main.js").resolve()


def test_resolve_entry_point_missing_root_uses_project_root():
    """Safety net: if `root` is absent, fall back to project root / index.js."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        widget_def = {}
        resolved = resolve_widget_entry_point(widget_def, root)
        assert resolved == (root / "index.js").resolve()
