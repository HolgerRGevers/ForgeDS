import { useCallback, useEffect, useRef, useState } from "react";
import { useBlocker } from "react-router-dom";
import {
  AppTreeExplorer,
  DevConsole,
  IdeEditor,
  InspectorPanel,
  RepoExplorer,
  SourceControlPanel,
} from "../components/ide";
import { useIdeStore, consumeTabsRestored } from "../stores/ideStore";
import { useBridgeStore } from "../stores/bridgeStore";
import type { AppStructure, InspectorData, TreeNode } from "../types/ide";

type ExplorerMode = "repo" | "ds";

/** Build the flat nodeIndex from a tree of TreeNodes. */
function buildNodeIndex(tree: TreeNode[]): Map<string, TreeNode> {
  const index = new Map<string, TreeNode>();
  const walk = (nodes: TreeNode[]) => {
    for (const n of nodes) {
      index.set(n.id, n);
      if (n.children) walk(n.children);
    }
  };
  walk(tree);
  return index;
}

export default function IdePage() {
  const [showExplorer, setShowExplorer] = useState(true);
  const [showInspector, setShowInspector] = useState(true);
  const [showConsole, setShowConsole] = useState(true);
  const [explorerMode, setExplorerMode] = useState<ExplorerMode>("repo");
  const [showSourceControl, setShowSourceControl] = useState(false);

  const connect = useBridgeStore((s) => s.connect);
  const status = useBridgeStore((s) => s.status);
  const send = useBridgeStore((s) => s.send);



  const tabs = useIdeStore((s) => s.tabs);
  const selectedNodeId = useIdeStore((s) => s.selectedNodeId);
  const appStructure = useIdeStore((s) => s.appStructure);
  const loadAppStructure = useIdeStore((s) => s.loadAppStructure);
  const updateTabContent = useIdeStore((s) => s.updateTabContent);
  const addConsoleEntry = useIdeStore((s) => s.addConsoleEntry);
  const setDiagnostics = useIdeStore((s) => s.setDiagnostics);
  const setInspectorData = useIdeStore((s) => s.setInspectorData);

  const hasDirtyTabs = useIdeStore((s) => s.hasDirtyTabs);
  const dirty = hasDirtyTabs();

  // Block in-app navigation when there are unsaved changes
  useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirty && currentLocation.pathname !== nextLocation.pathname &&
      !window.confirm("You have unsaved changes. Leave this page?"),
  );

  // Block browser close / external navigation
  useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  // Track which tabs have had their content loaded
  const loadedTabsRef = useRef<Set<string>>(new Set());

  const loadDs = useCallback(async () => {
    try {
      const result = await send("parse_ds", {});
      const data = result as unknown as {
        name: string;
        displayName: string;
        tree: TreeNode[];
      };
      const structure: AppStructure = {
        name: data.name,
        displayName: data.displayName,
        tree: data.tree,
        nodeIndex: buildNodeIndex(data.tree),
      };
      loadAppStructure(structure);
      addConsoleEntry({
        type: "info",
        message: `App structure loaded: ${structure.displayName}`,
      });
    } catch (err) {
      addConsoleEntry({
        type: "error",
        message: `Failed to load app structure: ${err instanceof Error ? err.message : String(err)}`,
      });
    }
  }, [send, loadAppStructure, addConsoleEntry]);

  const runLint = useCallback(async () => {
    try {
      addConsoleEntry({ type: "info", message: "Running lint check..." });
      const result = await send("lint_check", {});
      const diagnostics = (result as unknown as { diagnostics: Array<{
        file: string;
        line: number;
        rule: string;
        severity: "error" | "warning" | "info";
        message: string;
      }> }).diagnostics ?? [];
      setDiagnostics(diagnostics);
      addConsoleEntry({
        type: "lint",
        message: `Lint complete: ${diagnostics.length} issue(s) found`,
      });
    } catch (err) {
      addConsoleEntry({
        type: "error",
        message: `Lint failed: ${err instanceof Error ? err.message : String(err)}`,
      });
    }
  }, [send, addConsoleEntry, setDiagnostics]);

  // On mount: connect and load
  useEffect(() => {
    if (status === "disconnected") {
      connect();
    }
  }, [status, connect]);

  useEffect(() => {
    if (status === "connected") {
      loadDs();
    }
    // Only run when status transitions to connected
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  // Staleness check: when bridge connects after a page refresh, re-fetch
  // content for restored (non-dirty) tabs and silently update if changed.
  const hasDoneStaleCheck = useRef(false);
  useEffect(() => {
    if (status !== "connected" || hasDoneStaleCheck.current) return;
    if (!consumeTabsRestored()) return;
    hasDoneStaleCheck.current = true;

    const currentTabs = useIdeStore.getState().tabs;
    for (const tab of currentTabs) {
      if (tab.isDirty || !tab.content) continue;
      loadedTabsRef.current.add(tab.id); // mark as loaded so the next effect skips it
      send("read_file", { file_path: tab.path })
        .then((response) => {
          const data = response as unknown as { content: string };
          if (data.content && data.content !== tab.content) {
            updateTabContent(tab.id, data.content);
            // Clear the dirty flag the content update just set — this is a
            // silent refresh, not a user edit.
            const { tabs: latest } = useIdeStore.getState();
            useIdeStore.setState({
              tabs: latest.map((t) =>
                t.id === tab.id ? { ...t, isDirty: false } : t,
              ),
            });
            addConsoleEntry({
              type: "info",
              message: `Refreshed ${tab.name} — file changed on disk`,
            });
          }
        })
        .catch(() => {
          // File may have been deleted; leave tab as-is
        });
    }
  }, [status, send, updateTabContent, addConsoleEntry]);

  // Critical #1: Load file content into new tabs via read_file bridge call
  useEffect(() => {
    if (status !== "connected") return;

    for (const tab of tabs) {
      if (tab.content === "" && !loadedTabsRef.current.has(tab.id)) {
        loadedTabsRef.current.add(tab.id);
        send("read_file", { file_path: tab.path })
          .then((response) => {
            const data = response as unknown as { content: string; language: string };
            if (data.content) {
              updateTabContent(tab.id, data.content);
            }
          })
          .catch((err) => {
            addConsoleEntry({
              type: "error",
              message: `Failed to load ${tab.path}: ${err instanceof Error ? err.message : String(err)}`,
            });
          });
      }
    }
  }, [tabs, status, send, updateTabContent, addConsoleEntry]);

  // Important #2: Fetch rich inspector data when selectedNodeId changes
  useEffect(() => {
    if (status !== "connected" || !selectedNodeId || !appStructure) return;

    const node = appStructure.nodeIndex.get(selectedNodeId);
    if (!node) return;

    send("inspect_element", { element_id: selectedNodeId, element_type: node.type })
      .then((response) => {
        const data = response as unknown as {
          properties: Record<string, unknown>;
          relationships: Array<{ target: string; type: string }>;
          usages: Array<{ script: string; line: number; context: string }>;
        };

        const properties = Object.entries(data.properties ?? {}).map(
          ([key, value]) => ({ label: key, value: String(value) }),
        );

        const relationships = (data.relationships ?? []).map((rel) => ({
          targetId: rel.target,
          targetLabel: rel.target,
          targetType: node.type,
          relationship: rel.type,
        }));

        const usages = (data.usages ?? []).map((u) => ({
          file: u.script,
          line: u.line,
          context: u.context,
        }));

        const inspectorData: InspectorData = {
          type: node.type === "field" ? "field" : node.type === "form" ? "form" : "variable",
          name: node.label,
          properties,
          relationships,
          usages,
        };
        setInspectorData(inspectorData);
      })
      .catch((err) => {
        addConsoleEntry({
          type: "error",
          message: `Inspector failed: ${err instanceof Error ? err.message : String(err)}`,
        });
      });
  }, [selectedNodeId, status, appStructure, send, setInspectorData, addConsoleEntry]);

  /** Handle file selection from the RepoExplorer. */
  const handleRepoFileSelect = useCallback(
    (path: string, content: string) => {
      const name = path.split("/").pop() ?? path;
      const ext = name.split(".").pop() ?? "";
      const langMap: Record<string, string> = {
        dg: "deluge",
        ds: "plaintext",
        py: "python",
        json: "json",
        yaml: "yaml",
        yml: "yaml",
        md: "markdown",
        sql: "sql",
        csv: "plaintext",
        txt: "plaintext",
      };
      const tab = {
        id: path,
        name,
        path,
        content,
        language: langMap[ext] ?? "plaintext",
        isDirty: false,
      };
      // Open the tab in the IDE editor
      const { openTab } = useIdeStore.getState();
      openTab(tab);
    },
    [],
  );

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-1 border-b border-gray-700 bg-gray-850 px-2 py-1">
        <ToolbarToggle
          label="Explorer"
          active={showExplorer}
          onClick={() => setShowExplorer((v) => !v)}
        />
        <ToolbarToggle
          label="Inspector"
          active={showInspector}
          onClick={() => setShowInspector((v) => !v)}
        />
        <ToolbarToggle
          label="Console"
          active={showConsole}
          onClick={() => setShowConsole((v) => !v)}
        />
        <ToolbarToggle
          label="Source Control"
          active={showSourceControl}
          onClick={() => setShowSourceControl((v) => !v)}
        />
        <div className="mx-2 h-4 w-px bg-gray-600" />

        {/* Explorer mode toggle */}
        {showExplorer && (
          <div className="inline-flex rounded border border-gray-700 bg-gray-800 p-0.5">
            <button
              type="button"
              onClick={() => setExplorerMode("repo")}
              className={`rounded px-2 py-0.5 text-[10px] font-medium transition-colors ${
                explorerMode === "repo"
                  ? "bg-blue-600 text-white"
                  : "text-gray-400 hover:text-gray-200"
              }`}
              title="GitHub repository files"
            >
              Repo
            </button>
            <button
              type="button"
              onClick={() => setExplorerMode("ds")}
              className={`rounded px-2 py-0.5 text-[10px] font-medium transition-colors ${
                explorerMode === "ds"
                  ? "bg-blue-600 text-white"
                  : "text-gray-400 hover:text-gray-200"
              }`}
              title=".ds export structure"
            >
              .ds Tree
            </button>
          </div>
        )}

        <div className="mx-2 h-4 w-px bg-gray-600" />
        {status === "connected" && (
          <>
            <ToolbarButton label="Lint" onClick={runLint} />
            <ToolbarButton label="Load .ds" onClick={loadDs} />
          </>
        )}
        {status !== "connected" && (
          <span className="text-[10px] text-gray-500">
            Bridge offline — GitHub mode active
          </span>
        )}
      </div>

      {/* Main content area */}
      <div className="flex min-h-0 flex-1 flex-col">
        {/* Top row: explorer + editor + inspector */}
        <div className="flex min-h-0 flex-1">
          {/* Left panel: Explorer */}
          {showExplorer && (
            <div className="h-full w-[250px] shrink-0 border-r border-gray-700 overflow-hidden">
              {explorerMode === "repo" ? (
                <RepoExplorer onFileSelect={handleRepoFileSelect} />
              ) : (
                <AppTreeExplorer />
              )}
            </div>
          )}

          {/* Center panel: Editor */}
          <div className="min-w-0 flex-1 overflow-hidden">
            <IdeEditor />
          </div>

          {/* Right panel: Inspector or Source Control */}
          {(showInspector || showSourceControl) && (
            <div className="h-full w-[300px] shrink-0 border-l border-gray-700 overflow-hidden">
              {showSourceControl ? <SourceControlPanel /> : <InspectorPanel />}
            </div>
          )}
        </div>

        {/* Bottom panel: Console */}
        {showConsole && (
          <div className="h-[200px] shrink-0 border-t border-gray-700 overflow-hidden">
            <DevConsole />
          </div>
        )}
      </div>
    </div>
  );
}

// --- Small toolbar sub-components ---

function ToolbarToggle({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded px-2 py-0.5 text-xs font-medium transition-colors ${
        active
          ? "bg-blue-600 text-white"
          : "bg-gray-700 text-gray-400 hover:bg-gray-600 hover:text-gray-200"
      }`}
    >
      {label}
    </button>
  );
}

function ToolbarButton({
  label,
  onClick,
}: {
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="rounded px-2 py-0.5 text-xs font-medium text-gray-300 bg-gray-700 hover:bg-gray-600 hover:text-white transition-colors"
    >
      {label}
    </button>
  );
}
