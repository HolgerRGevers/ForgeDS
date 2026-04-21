// web/src/lib/ds-tree-builder.ts

import type { TreeNode } from "../types/ide";
import type { FormDef, ScriptDef } from "./ds-parser";

export function buildAppTree(
  forms: FormDef[],
  scripts: ScriptDef[],
  appName: string,
  appDisplayName: string
): TreeNode[] {
  const root: TreeNode = {
    id: "app-root",
    label: appDisplayName,
    type: "application",
    isExpanded: true,
    children: [],
  };

  // --- Forms section ---
  const formsSection: TreeNode = {
    id: "forms-section",
    label: "Forms",
    type: "section",
    isExpanded: true,
    children: [],
  };

  for (const form of forms) {
    const formNode: TreeNode = {
      id: `form-${form.name.toLowerCase()}`,
      label: form.displayName,
      type: "form",
      isExpanded: false,
      children: [],
    };

    // Fields subsection
    if (form.fields.length > 0) {
      const fieldsSection: TreeNode = {
        id: `field-section-${form.name.toLowerCase()}`,
        label: "Fields",
        type: "section",
        isExpanded: false,
        children: form.fields.map((f) => ({
          id: `field-${form.name.toLowerCase()}-${f.linkName.toLowerCase()}`,
          label: f.linkName,
          type: "field" as const,
          fieldType: f.fieldType,
          metadata: {
            displayName: f.displayName,
            notes: f.notes,
          },
        })),
      };
      formNode.children!.push(fieldsSection);
    }

    // Workflows subsection
    const formWorkflows = scripts.filter(
      (s) => s.form === form.name && s.context === "form-workflow"
    );
    if (formWorkflows.length > 0) {
      const wfSection: TreeNode = {
        id: `wf-section-${form.name.toLowerCase()}`,
        label: "Workflows",
        type: "section",
        isExpanded: false,
        children: formWorkflows.map((s) => ({
          id: `wf-${s.name.toLowerCase()}`,
          label: s.displayName,
          type: "workflow" as const,
          trigger: s.trigger,
          filePath: `src/deluge/form-workflows/${s.form}.${s.event.replace(/ /g, "_")}.dg`,
          metadata: { code: s.code, context: s.context },
        })),
      };
      formNode.children!.push(wfSection);
    }

    formsSection.children!.push(formNode);
  }

  root.children!.push(formsSection);

  // --- Schedules section ---
  const schedules = scripts.filter((s) => s.context === "scheduled");
  if (schedules.length > 0) {
    root.children!.push({
      id: "schedules-section",
      label: "Schedules",
      type: "section",
      isExpanded: false,
      children: schedules.map((s) => ({
        id: `schedule-${s.name.toLowerCase()}`,
        label: s.displayName,
        type: "schedule" as const,
        trigger: s.trigger,
        filePath: `src/deluge/scheduled/${s.name}.dg`,
        metadata: { code: s.code },
      })),
    });
  }

  // --- Approval Processes section ---
  const approvals = scripts.filter((s) => s.context === "approval");
  if (approvals.length > 0) {
    root.children!.push({
      id: "approvals-section",
      label: "Approval Processes",
      type: "section",
      isExpanded: false,
      children: approvals.map((s) => ({
        id: `approval-${s.name.toLowerCase()}`,
        label: s.displayName,
        type: "workflow" as const,
        trigger: s.trigger,
        filePath: `src/deluge/approval-scripts/${s.name}.dg`,
        metadata: { code: s.code, event: s.event },
      })),
    });
  }

  return [root];
}
