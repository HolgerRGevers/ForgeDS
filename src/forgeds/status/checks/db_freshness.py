"""Database freshness checks: presence + age of language DBs."""

from __future__ import annotations

import time
from pathlib import Path

from forgeds._shared.config import get_db_dir
from forgeds.status.checks import StatusCheck

STALE_THRESHOLD_DAYS = 30

REQUIRED_DBS = [
    ("deluge_lang.db",      "forgeds-build-db"),
    ("access_vba_lang.db",  "forgeds-build-access-db"),
    ("zoho_widget_sdk.db",  "forgeds-build-widget-db"),
]


def run() -> list[StatusCheck]:
    """Check presence + age of each required language DB."""
    db_dir = get_db_dir()
    now = time.time()
    checks: list[StatusCheck] = []

    for filename, rebuild_cmd in REQUIRED_DBS:
        path = db_dir / filename
        if not path.exists():
            checks.append(StatusCheck(
                category="db_freshness",
                id=filename,
                status="miss",
                message=f"missing — run: {rebuild_cmd}",
                rule="STA002",
            ))
            continue

        age_days = (now - path.stat().st_mtime) / 86400.0
        if age_days > STALE_THRESHOLD_DAYS:
            checks.append(StatusCheck(
                category="db_freshness",
                id=filename,
                status="warn",
                message=f"built {int(age_days)} days ago (threshold: {STALE_THRESHOLD_DAYS} days); "
                        f"consider running {rebuild_cmd}",
                rule="STA003",
            ))
        else:
            checks.append(StatusCheck(
                category="db_freshness",
                id=filename,
                status="ok",
                message=f"built {int(age_days)} days ago",
                rule=None,
            ))

    return checks
