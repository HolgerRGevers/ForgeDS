"""Form and field schema definitions for ForgeDS.

Analogous to SQL's CREATE TABLE / column definitions — each FormSchema
holds typed FieldDefs that tools can query at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from forgeds.schema.types import DelugeType, FIELD_TYPE_MAP


@dataclass(frozen=True)
class FieldDef:
    """A single field (column) in a Zoho Creator form.

    Immutable so it can be stored in sets and used as dict keys.
    """

    link_name: str         # e.g. "Employee_Name1"
    display_name: str      # e.g. "Employee Name"
    deluge_type: DelugeType
    field_type_raw: str    # original DB string: "text", "picklist", etc.
    nullable: bool = True
    notes: str = ""

    @staticmethod
    def from_db_row(
        field_link: str,
        display: str = "",
        field_type: str = "text",
        notes: str = "",
    ) -> FieldDef:
        """Construct from a deluge_lang.db form_fields row."""
        return FieldDef(
            link_name=field_link,
            display_name=display or field_link,
            deluge_type=FIELD_TYPE_MAP.get(
                field_type.lower(), DelugeType.UNKNOWN,
            ),
            field_type_raw=field_type,
            notes=notes or "",
        )


@dataclass
class FormSchema:
    """Schema for a single Zoho Creator form (analogous to a SQL table).

    ``fields`` maps field link names to their definitions.
    """

    name: str                                             # e.g. "expense_claims"
    display_name: str = ""
    fields: dict[str, FieldDef] = field(default_factory=dict)

    def has_field(self, link_name: str) -> bool:
        return link_name in self.fields

    def get_field(self, link_name: str) -> FieldDef | None:
        return self.fields.get(link_name)

    def field_type(self, link_name: str) -> DelugeType:
        """Return the Deluge type for a field, or UNKNOWN if not found."""
        fd = self.fields.get(link_name)
        return fd.deluge_type if fd else DelugeType.UNKNOWN

    def field_names(self) -> set[str]:
        """Return the set of all field link names."""
        return set(self.fields)

    def add_field(self, fd: FieldDef) -> None:
        self.fields[fd.link_name] = fd
