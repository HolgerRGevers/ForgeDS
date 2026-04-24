"""Tests for forgeds.widgets.build_widget_sdk_db — zoho_widget_sdk.db builder."""

from __future__ import annotations

import sqlite3
import sys, os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from forgeds.widgets.build_widget_sdk_db import build_db


def test_build_db_creates_all_tables(tmp_path):
    """Builder should create 5 tables with correct names."""
    db_path = tmp_path / "zoho_widget_sdk.db"
    build_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cur.fetchall()]
        assert set(tables) == {
            "sdk_namespaces",
            "sdk_methods",
            "sdk_events",
            "sdk_permissions",
            "zoho_widget_globals",
        }
    finally:
        conn.close()


def test_build_db_populates_namespaces(tmp_path):
    db_path = tmp_path / "zoho_widget_sdk.db"
    build_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sdk_namespaces")
        names = {row[0] for row in cur.fetchall()}
        assert "ZOHO.CREATOR.API" in names
        assert "ZOHO.embeddedApp" in names
    finally:
        conn.close()


def test_build_db_populates_methods(tmp_path):
    db_path = tmp_path / "zoho_widget_sdk.db"
    build_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sdk_methods")
        count = cur.fetchone()[0]
        assert count >= 20, f"expected >=20 seeded methods, got {count}"
        cur.execute("SELECT name FROM sdk_methods WHERE namespace='ZOHO.CREATOR.API' AND name='getRecords'")
        assert cur.fetchone() is not None
    finally:
        conn.close()


def test_build_db_populates_globals(tmp_path):
    db_path = tmp_path / "zoho_widget_sdk.db"
    build_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM zoho_widget_globals")
        names = {row[0] for row in cur.fetchall()}
        assert names == {"ZOHO", "Creator", "$"}
    finally:
        conn.close()
