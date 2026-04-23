"""Build zoho_widget_sdk.db from seed_data/widget_sdk_apis.json.

Mirrors the forgeds.core.build_deluge_db pattern but with an SDK-shaped
schema: namespaces + methods + events + permissions + globals.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from forgeds._shared.config import get_db_dir

SEED_FILE = Path(__file__).parent / "seed_data" / "widget_sdk_apis.json"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sdk_namespaces (
  name TEXT PRIMARY KEY,
  description TEXT
);

CREATE TABLE IF NOT EXISTS sdk_methods (
  namespace TEXT NOT NULL,
  name TEXT NOT NULL,
  signature TEXT NOT NULL,
  returns_promise INTEGER NOT NULL,
  required_permissions TEXT,
  deprecated_in TEXT,
  notes TEXT,
  PRIMARY KEY (namespace, name)
);

CREATE TABLE IF NOT EXISTS sdk_events (
  name TEXT PRIMARY KEY,
  trigger TEXT NOT NULL,
  payload_shape TEXT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS sdk_permissions (
  scope TEXT PRIMARY KEY,
  description TEXT
);

CREATE TABLE IF NOT EXISTS zoho_widget_globals (
  name TEXT PRIMARY KEY,
  kind TEXT NOT NULL
);
"""


def build_db(db_path: Path) -> None:
    """Create zoho_widget_sdk.db at db_path and populate from seed JSON."""
    if db_path.exists():
        db_path.unlink()

    with open(SEED_FILE, encoding="utf-8") as f:
        seed = json.load(f)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(SCHEMA_SQL)

        conn.executemany(
            "INSERT INTO sdk_namespaces (name, description) VALUES (?, ?)",
            [(n["name"], n.get("description")) for n in seed["namespaces"]],
        )

        conn.executemany(
            """
            INSERT INTO sdk_methods
              (namespace, name, signature, returns_promise, required_permissions, deprecated_in, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    m["namespace"],
                    m["name"],
                    m["signature"],
                    int(m["returns_promise"]),
                    m.get("required_permissions"),
                    m.get("deprecated_in"),
                    m.get("notes"),
                )
                for m in seed["methods"]
            ],
        )

        conn.executemany(
            "INSERT INTO sdk_events (name, trigger, payload_shape, notes) VALUES (?, ?, ?, ?)",
            [
                (e["name"], e["trigger"], e.get("payload_shape"), e.get("notes"))
                for e in seed["events"]
            ],
        )

        conn.executemany(
            "INSERT INTO sdk_permissions (scope, description) VALUES (?, ?)",
            [(p["scope"], p.get("description")) for p in seed["permissions"]],
        )

        conn.executemany(
            "INSERT INTO zoho_widget_globals (name, kind) VALUES (?, ?)",
            [(g["name"], g["kind"]) for g in seed["globals"]],
        )

        conn.commit()
    finally:
        conn.close()


def main() -> int:
    db_dir = get_db_dir()
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "zoho_widget_sdk.db"
    try:
        build_db(db_path)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"built {db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
