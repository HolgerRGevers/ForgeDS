"""
Convert DSParser output (FormDef/ScriptDef lists) into the TreeNode dict
hierarchy expected by the ForgeDS frontend.

Python equivalent of the TypeScript ds-tree-builder.ts.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from forgeds.core.parse_ds_export import FormDef, ScriptDef


def _slugify(name: str) -> str:
    """Lower-case the name and replace spaces/special chars with underscores."""
    return re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_")


def _form_file_path(form_name: str, event: str) -> str:
    """Build the expected .dg file path for a form workflow script."""
    event_underscored = event.replace(" ", "_")
    return f"src/deluge/form-workflows/{form_name}.{event_underscored}.dg"


def build_tree_response(
    forms: list,
    scripts: list,
    file_path: str,
) -> dict:
    """
    Build the TreeNode hierarchy dict for the frontend.

    Parameters
    ----------
    forms:
        List of FormDef objects produced by DSParser.
    scripts:
        List of ScriptDef objects produced by DSParser.
    file_path:
        Path (or bare filename) of the source .ds file — used to derive the
        app name.

    Returns
    -------
    dict with keys: name, displayName, tree
    """
    # Derive app name from file basename without extension
    basename = Path(file_path).stem if file_path else "app"
    app_name = basename
    display_name = basename.replace("_", " ").title()

    # ------------------------------------------------------------------ forms
    form_nodes = []
    for form in forms:
        form_slug = _slugify(form.name)

        # Fields subsection
        field_nodes = []
        for f in form.fields:
            field_slug = _slugify(f.link_name)
            field_nodes.append(
                {
                    "id": f"field-{form_slug}-{field_slug}",
                    "label": f.display_name or f.link_name,
                    "type": "field",
                    "fieldType": f.field_type,
                }
            )

        fields_section = {
            "id": f"fields-section-{form_slug}",
            "label": "Fields",
            "type": "section",
            "isExpanded": False,
            "children": field_nodes,
        }

        # Workflows subsection — only scripts that belong to this form
        wf_nodes = []
        for script in scripts:
            if script.context != "form-workflow":
                continue
            if script.form != form.name:
                continue
            wf_slug = _slugify(script.name)
            wf_nodes.append(
                {
                    "id": f"wf-{wf_slug}",
                    "label": script.display_name or script.name,
                    "type": "workflow",
                    "trigger": script.trigger,
                    "filePath": _form_file_path(form.name, script.event),
                }
            )

        workflows_section = {
            "id": f"wf-section-{form_slug}",
            "label": "Workflows",
            "type": "section",
            "isExpanded": False,
            "children": wf_nodes,
        }

        form_nodes.append(
            {
                "id": f"form-{form_slug}",
                "label": form.display_name or form.name,
                "type": "form",
                "isExpanded": False,
                "children": [fields_section, workflows_section],
            }
        )

    forms_section = {
        "id": "forms-section",
        "label": "Forms",
        "type": "section",
        "isExpanded": True,
        "children": form_nodes,
    }

    # --------------------------------------------------------------- schedules
    schedule_nodes = []
    for script in scripts:
        if script.context != "scheduled":
            continue
        sched_slug = _slugify(script.name)
        schedule_nodes.append(
            {
                "id": f"schedule-{sched_slug}",
                "label": script.display_name or script.name,
                "type": "schedule",
                "trigger": script.trigger,
                "filePath": f"src/deluge/scheduled/{script.name}.dg",
            }
        )

    schedules_section = {
        "id": "schedules-section",
        "label": "Schedules",
        "type": "section",
        "isExpanded": False,
        "children": schedule_nodes,
    }

    # -------------------------------------------------------- approval processes
    approval_nodes = []
    for script in scripts:
        if script.context != "approval":
            continue
        approval_slug = _slugify(script.name)
        approval_nodes.append(
            {
                "id": f"approval-{approval_slug}",
                "label": script.display_name or script.name,
                "type": "approval",
                "trigger": script.trigger,
                "filePath": f"src/deluge/approval-scripts/{script.name}.dg",
            }
        )

    approvals_section = {
        "id": "approvals-section",
        "label": "Approval Processes",
        "type": "section",
        "isExpanded": False,
        "children": approval_nodes,
    }

    # --------------------------------------------------------------- root node
    root = {
        "id": "app-root",
        "label": display_name,
        "type": "application",
        "isExpanded": True,
        "children": [forms_section, schedules_section, approvals_section],
    }

    return {
        "name": app_name,
        "displayName": display_name,
        "tree": [root],
    }
