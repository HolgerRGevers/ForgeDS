"""StatusCheck dataclass — the unit of aggregate-health reporting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

StatusToken = Literal["ok", "warn", "fail", "miss", "skip"]
CheckCategory = Literal["config_sanity", "db_freshness", "toolchain", "lint_summary"]


@dataclass
class StatusCheck:
    """One row in a forgeds-status report."""
    category: CheckCategory
    id: str
    status: StatusToken
    message: str
    rule: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "id": self.id,
            "status": self.status,
            "message": self.message,
            "rule": self.rule,
        }
