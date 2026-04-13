"""SchemaRegistry — single source of truth for all schema data.

Loads form schemas, field definitions, FK relationships, and
picklist constraints from:

1. deluge_lang.db  (form_fields, valid_statuses, valid_actions)
2. access_vba_lang.db  (access_table_fields, type_mappings,
   field_name_mappings, access_constraints) — optional
3. forgeds.yaml  (schema section: fk_relationships,
   mandatory_zoho_fields, table_to_form)

All consumers share a single instance via ``get_registry()``.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from forgeds._shared.config import load_config, get_db_dir
from forgeds.schema.types import DelugeType, FIELD_TYPE_MAP
from forgeds.schema.fields import FieldDef, FormSchema
from forgeds.schema.relations import ForeignKey, RelationGraph
from forgeds.schema.constraints import PicklistConstraint, NotNullConstraint


class SchemaRegistry:
    """Unified schema model — the ``information_schema`` of ForgeDS."""

    def __init__(self) -> None:
        # -- Form schemas --
        self._forms: dict[str, FormSchema] = {}

        # -- Relationships --
        self._relations: RelationGraph = RelationGraph()
        self._table_to_form: dict[str, str] = {}  # Access table -> Zoho form

        # -- Constraints --
        self._picklists: dict[tuple[str, str], PicklistConstraint] = {}
        self._not_nulls: list[NotNullConstraint] = []

        # -- Access migration data (optional) --
        self._access_fields: dict[tuple[str, str], str] = {}       # (table, field) -> access_type
        self._fields_by_table: dict[str, dict[str, str]] = {}      # table -> {field: type}
        self._type_mappings: dict[str, dict[str, str]] = {}         # access_type -> {zoho_type, notes, risk}
        self._field_mappings: dict[tuple[str, str], dict[str, str]] = {}  # (access_tbl, access_fld) -> {zoho_form, zoho_fld}
        self._access_constraints: list[dict[str, str]] = []

    # ================================================================
    # Loading
    # ================================================================

    def load_deluge_db(self, db_path: Path | None = None) -> None:
        """Load form schemas and picklist constraints from deluge_lang.db."""
        if db_path is None:
            db_path = get_db_dir() / "deluge_lang.db"
        if not db_path.exists():
            raise FileNotFoundError(
                f"Deluge language DB not found at {db_path}. "
                "Run: python -m forgeds.core.build_deluge_db"
            )

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Form fields -> FormSchema + FieldDef
        try:
            for row in conn.execute(
                "SELECT form_name, field_link, display, field_type, notes "
                "FROM form_fields"
            ):
                form_name = row["form_name"]
                if form_name not in self._forms:
                    self._forms[form_name] = FormSchema(name=form_name)
                fd = FieldDef.from_db_row(
                    field_link=row["field_link"],
                    display=row["display"] or "",
                    field_type=row["field_type"],
                    notes=row["notes"] or "",
                )
                self._forms[form_name].add_field(fd)
        except sqlite3.OperationalError:
            pass

        # Valid statuses -> picklist constraint
        try:
            values = frozenset(
                row[0] for row in conn.execute(
                    "SELECT value FROM valid_statuses"
                )
            )
            if values:
                self._picklists[("*", "status")] = PicklistConstraint(
                    "*", "status", values,
                )
        except sqlite3.OperationalError:
            pass

        # Valid actions -> picklist constraint
        try:
            values = frozenset(
                row[0] for row in conn.execute(
                    "SELECT value FROM valid_actions"
                )
            )
            if values:
                self._picklists[("approval_history", "action_1")] = (
                    PicklistConstraint("approval_history", "action_1", values)
                )
        except sqlite3.OperationalError:
            pass

        conn.close()

    def load_access_db(self, db_path: Path | None = None) -> None:
        """Load Access migration data from access_vba_lang.db."""
        if db_path is None:
            db_path = get_db_dir() / "access_vba_lang.db"
        if not db_path.exists():
            raise FileNotFoundError(
                f"Access VBA DB not found at {db_path}."
            )

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # access_table_fields
        try:
            for row in conn.execute(
                "SELECT table_name, field_name, access_type "
                "FROM access_table_fields"
            ):
                tname = row["table_name"]
                fname = row["field_name"]
                atype = row["access_type"]
                self._access_fields[(tname, fname)] = atype
                self._fields_by_table.setdefault(tname, {})[fname] = atype
        except sqlite3.OperationalError:
            pass

        # type_mappings
        try:
            for row in conn.execute(
                "SELECT access_type, zoho_type, conversion_notes, "
                "data_loss_risk FROM type_mappings"
            ):
                self._type_mappings[row["access_type"]] = {
                    "zoho_type": row["zoho_type"],
                    "notes": row["conversion_notes"],
                    "risk": row["data_loss_risk"],
                }
        except sqlite3.OperationalError:
            pass

        # field_name_mappings
        try:
            for row in conn.execute(
                "SELECT access_table, access_field, zoho_form, zoho_field "
                "FROM field_name_mappings"
            ):
                self._field_mappings[(row["access_table"], row["access_field"])] = {
                    "zoho_form": row["zoho_form"],
                    "zoho_field": row["zoho_field"],
                }
        except sqlite3.OperationalError:
            pass

        # access_constraints
        try:
            for row in conn.execute(
                "SELECT table_name, field_name, constraint_type, "
                "ref_table, ref_field FROM access_constraints"
            ):
                self._access_constraints.append({
                    "table": row["table_name"],
                    "field": row["field_name"],
                    "type": row["constraint_type"],
                    "ref_table": row["ref_table"] or "",
                    "ref_field": row["ref_field"] or "",
                })
        except sqlite3.OperationalError:
            pass

        conn.close()

    def load_config(self) -> None:
        """Load schema information from forgeds.yaml."""
        config = load_config()
        schema = config.get("schema", {})

        # table_to_form
        self._table_to_form = schema.get("table_to_form", {})

        # fk_relationships
        for entry in schema.get("fk_relationships", []):
            if isinstance(entry, dict):
                child = entry.get("child", [])
                parent = entry.get("parent", [])
                if len(child) >= 2 and len(parent) >= 2:
                    self._relations.add(ForeignKey(
                        child_form=child[0],
                        child_field=child[1],
                        parent_form=parent[0],
                        parent_field=parent[1],
                    ))

        # mandatory_zoho_fields -> NotNullConstraint
        for entry in schema.get("mandatory_zoho_fields", []):
            if isinstance(entry, list) and len(entry) >= 2:
                self._not_nulls.append(
                    NotNullConstraint(form=entry[0], field=entry[1])
                )

    # ================================================================
    # Form / field queries
    # ================================================================

    def get_form(self, name: str) -> FormSchema | None:
        return self._forms.get(name)

    def all_forms(self) -> dict[str, FormSchema]:
        return dict(self._forms)

    def all_field_names(self) -> set[str]:
        """Return the union of all field link names across all forms."""
        result: set[str] = set()
        for schema in self._forms.values():
            result.update(schema.field_names())
        return result

    def field_type(self, form: str, field: str) -> DelugeType:
        """Look up a field's Deluge type. Returns UNKNOWN if not found."""
        fs = self._forms.get(form)
        if fs:
            return fs.field_type(field)
        return DelugeType.UNKNOWN

    def has_field(self, form: str, field: str) -> bool:
        fs = self._forms.get(form)
        return fs.has_field(field) if fs else False

    # ================================================================
    # Constraint queries
    # ================================================================

    def get_picklist(self, form: str, field: str) -> PicklistConstraint | None:
        """Return the picklist constraint for a form.field pair.

        Falls back to wildcard form ("*") if no form-specific constraint.
        """
        return (
            self._picklists.get((form, field))
            or self._picklists.get(("*", field))
        )

    def is_valid_picklist_value(self, form: str, field: str, value: str) -> bool:
        pc = self.get_picklist(form, field)
        return pc.is_valid(value) if pc else True  # no constraint = valid

    def valid_statuses(self) -> frozenset[str]:
        pc = self._picklists.get(("*", "status"))
        return pc.valid_values if pc else frozenset()

    def valid_actions(self) -> frozenset[str]:
        pc = self._picklists.get(("approval_history", "action_1"))
        return pc.valid_values if pc else frozenset()

    def not_null_constraints(self) -> list[NotNullConstraint]:
        return list(self._not_nulls)

    # ================================================================
    # Relationship queries
    # ================================================================

    def get_relations(self) -> RelationGraph:
        return self._relations

    def table_to_form(self) -> dict[str, str]:
        return dict(self._table_to_form)

    def upload_order(self) -> list[str]:
        """Compute upload order from FK graph (parents before children).

        Includes all forms from table_to_form plus any in the FK graph.
        """
        extra = set(self._table_to_form.keys())
        try:
            return self._relations.topological_order(extra_forms=extra)
        except ValueError:
            # Cycle — fall back to config order or alphabetical
            return sorted(extra | self._relations.all_forms())

    # ================================================================
    # Access migration queries
    # ================================================================

    def access_type_for(self, table: str, field: str) -> str | None:
        return self._access_fields.get((table, field))

    def access_fields_for_table(self, table: str) -> dict[str, str]:
        return dict(self._fields_by_table.get(table, {}))

    def zoho_type_for_access(self, access_type: str) -> str | None:
        m = self._type_mappings.get(access_type)
        return m["zoho_type"] if m else None

    def zoho_mapping_for(
        self, access_table: str, access_field: str,
    ) -> tuple[str, str] | None:
        m = self._field_mappings.get((access_table, access_field))
        return (m["zoho_form"], m["zoho_field"]) if m else None

    def access_tables(self) -> set[str]:
        return set(self._fields_by_table.keys())

    def access_constraints(self) -> list[dict[str, str]]:
        return list(self._access_constraints)


# ================================================================
# Module-level singleton
# ================================================================

_registry: SchemaRegistry | None = None


def get_registry() -> SchemaRegistry:
    """Return the shared SchemaRegistry, loading it on first call.

    Loads: forgeds.yaml (always), deluge_lang.db (if present),
    access_vba_lang.db (if present).
    """
    global _registry
    if _registry is None:
        _registry = SchemaRegistry()
        _registry.load_config()
        try:
            _registry.load_deluge_db()
        except FileNotFoundError:
            pass
        try:
            _registry.load_access_db()
        except FileNotFoundError:
            pass
    return _registry


def reset_registry() -> None:
    """Clear the singleton (for testing or config reload)."""
    global _registry
    _registry = None
