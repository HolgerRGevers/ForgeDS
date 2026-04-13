"""ForgeDS schema module — unified form/field/type/relationship model.

This is the relational backbone of ForgeDS: every tool that needs to
know about forms, fields, types, or relationships queries the
SchemaRegistry rather than loading its own SQLite caches.

Quick start::

    from forgeds.schema import get_registry

    reg = get_registry()
    form = reg.get_form("expense_claims")
    if form and form.has_field("amount_zar"):
        print(form.field_type("amount_zar"))  # DelugeType.DECIMAL
"""

from forgeds.schema.types import (
    DelugeType,
    FIELD_TYPE_MAP,
    LITERAL_KIND_MAP,
    can_coerce,
    result_type,
)
from forgeds.schema.fields import FieldDef, FormSchema
from forgeds.schema.relations import ForeignKey, RelationGraph
from forgeds.schema.constraints import PicklistConstraint, NotNullConstraint
from forgeds.schema.registry import SchemaRegistry, get_registry, reset_registry

__all__ = [
    # types
    "DelugeType", "FIELD_TYPE_MAP", "LITERAL_KIND_MAP",
    "can_coerce", "result_type",
    # fields
    "FieldDef", "FormSchema",
    # relations
    "ForeignKey", "RelationGraph",
    # constraints
    "PicklistConstraint", "NotNullConstraint",
    # registry
    "SchemaRegistry", "get_registry", "reset_registry",
]
