"""Schema constraints for ForgeDS.

Analogous to SQL CHECK and NOT NULL constraints — validates that
field values conform to allowed sets (picklists, valid statuses,
valid actions) and mandatory presence.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PicklistConstraint:
    """Valid values for a picklist / status / action field.

    Replaces the ad-hoc ``valid_statuses`` and ``valid_actions`` sets
    scattered across DelugeDB, HybridDB, and ValidatorDB.
    """

    form: str
    field: str
    valid_values: frozenset[str]

    def is_valid(self, value: str) -> bool:
        return value in self.valid_values

    def add_value(self, value: str) -> PicklistConstraint:
        """Return a new constraint with an additional valid value."""
        return PicklistConstraint(
            self.form, self.field,
            self.valid_values | {value},
        )


@dataclass(frozen=True)
class NotNullConstraint:
    """Field must not be null/empty (analogous to SQL NOT NULL)."""

    form: str
    field: str
