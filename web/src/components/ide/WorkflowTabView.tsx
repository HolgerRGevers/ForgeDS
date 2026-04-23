import { useMemo, useState } from "react";
import { useIdeStore } from "../../stores/ideStore";
import type { ScriptsTab, TreeNode } from "../../types/ide";
import { WorkflowFormSidebar, type WorkflowFormEntry } from "./WorkflowFormSidebar";
import { WorkflowDetailTable, type WorkflowRow } from "./WorkflowDetailTable";

export type WorkflowType = Exclude<ScriptsTab, "complete">;

const LABELS: Record<WorkflowType, string> = {
  "form-workflows": "Form Workflows",
  "schedules": "Schedules",
  "approvals": "Approvals",
  "payments": "Payments",
  "blueprints": "Blueprints",
  "batch-workflows": "Batch Workflows",
  "functions": "Functions",
};

interface WorkflowTabViewProps {
  workflowType: WorkflowType;
}

/** Extract all forms (top-level and nested) from a tree. */
function collectForms(tree: TreeNode[]): WorkflowFormEntry[] {
  const out: WorkflowFormEntry[] = [];
  const walk = (nodes: TreeNode[]) => {
    for (const n of nodes) {
      if (n.type === "form") out.push({ id: n.id, label: n.label });
      if (n.children) walk(n.children);
    }
  };
  walk(tree);
  return out;
}

export function WorkflowTabView({ workflowType }: WorkflowTabViewProps) {
  const appStructure = useIdeStore((s) => s.appStructure);
  const openTab = useIdeStore((s) => s.openTab);
  const [selectedFormId, setSelectedFormId] = useState<string | null>(null);

  const label = LABELS[workflowType];

  const { formsWith, formsWithout, rows } = useMemo(() => {
    if (!appStructure) {
      return { formsWith: [], formsWithout: [], rows: [] as WorkflowRow[] };
    }
    // DATA EXTRACTION DEFERRED to Polish Pass spec.
    // For now: every form goes into "formsWithout"; rows is always [].
    const allForms = collectForms(appStructure.tree);
    return {
      formsWith: [] as WorkflowFormEntry[],
      formsWithout: allForms,
      rows: [] as WorkflowRow[],
    };
  }, [appStructure]);

  if (!appStructure) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-sm text-gray-500">
        No app loaded — open a repo or upload a .ds file.
      </div>
    );
  }

  const handleRowClick = (row: WorkflowRow) => {
    const ext = row.filePath.split(".").pop() ?? "";
    openTab({
      id: row.filePath,
      name: row.filePath.split("/").pop() ?? row.filePath,
      path: row.filePath,
      content: "",
      language: ext === "dg" ? "deluge" : "plaintext",
      isDirty: false,
    });
  };

  return (
    <div className="grid h-full grid-cols-[160px_1fr]">
      <div className="border-r border-gray-700">
        <WorkflowFormSidebar
          formsWith={formsWith}
          formsWithout={formsWithout}
          selectedFormId={selectedFormId}
          onSelect={setSelectedFormId}
        />
      </div>
      <WorkflowDetailTable
        workflowTypeLabel={label}
        rows={rows}
        onRowClick={handleRowClick}
      />
    </div>
  );
}
