import { useCallback } from "react";
import { useIdeStore } from "../../stores/ideStore";
import type { AppStructure, EditorTab, TreeNode } from "../../types/ide";

function countByType(
  tree: TreeNode[],
  predicate: (n: TreeNode) => boolean,
): number {
  let count = 0;
  const walk = (nodes: TreeNode[]) => {
    for (const n of nodes) {
      if (predicate(n)) count++;
      if (n.children) walk(n.children);
    }
  };
  walk(tree);
  return count;
}

function deriveStats(app: AppStructure) {
  const forms = countByType(app.tree, (n) => n.type === "form");
  const scripts = countByType(app.tree, (n) => n.type === "workflow" || n.type === "schedule");
  return { forms, scripts };
}

export function CompleteScriptView() {
  const appStructure = useIdeStore((s) => s.appStructure);
  const tabs = useIdeStore((s) => s.tabs);
  const openTab = useIdeStore((s) => s.openTab);
  const setActiveTab = useIdeStore((s) => s.setActiveTab);

  const handleOpenInEditor = useCallback(() => {
    if (!appStructure) return;
    const dsPath = `${appStructure.name}.ds`;
    const existing = tabs.find((t) => t.path === dsPath || t.name === dsPath);
    if (existing) {
      setActiveTab(existing.id);
      return;
    }
    const newTab: EditorTab = {
      id: dsPath,
      name: dsPath,
      path: dsPath,
      content: "",
      language: "plaintext",
      isDirty: false,
    };
    openTab(newTab);
  }, [appStructure, tabs, openTab, setActiveTab]);

  if (!appStructure) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-sm text-gray-500">
        No app loaded — open a repo or upload a .ds file.
      </div>
    );
  }

  const stats = deriveStats(appStructure);
  const enrichment = appStructure.enrichmentLevel ?? "unparsed";

  return (
    <div className="flex h-full flex-col gap-2 p-4 text-sm text-gray-300">
      <h3 className="text-base font-semibold text-gray-100">
        {appStructure.displayName}
      </h3>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-400">
        <dt>Filename</dt>
        <dd className="font-mono text-gray-200">{appStructure.name}.ds</dd>
        <dt>Forms</dt>
        <dd className="text-gray-200">{stats.forms} form{stats.forms === 1 ? "" : "s"}</dd>
        <dt>Scripts</dt>
        <dd className="text-gray-200">{stats.scripts} script{stats.scripts === 1 ? "" : "s"}</dd>
        <dt>Parse status</dt>
        <dd className="text-gray-200">{enrichment}</dd>
      </dl>
      <button
        type="button"
        onClick={handleOpenInEditor}
        className="mt-2 self-start rounded bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500"
      >
        Open in editor
      </button>
      <p className="mt-auto text-[11px] text-gray-500">
        Tip: editing the .ds file is equivalent to editing every script in the app.
      </p>
    </div>
  );
}
