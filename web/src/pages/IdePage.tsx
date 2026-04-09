import { useCallback, useEffect, useState } from "react";
import {
  AppTreeExplorer,
  DevConsole,
  IdeEditor,
  InspectorPanel,
} from "../components/ide";
import { useIdeStore } from "../stores/ideStore";
import { useBridgeStore } from "../stores/bridgeStore";
import type { AppStructure, TreeNode } from "../types/ide";

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

  const connect = useBridgeStore((s) => s.connect);
  const status = useBridgeStore((s) => s.status);
  const send = useBridgeStore((s) => s.send);

  const loadAppStructure = useIdeStore((s) => s.loadAppStructure);
  const addConsoleEntry = useIdeStore((s) => s.addConsoleEntry);
  const setDiagnostics = useIdeStore((s) => s.setDiagnostics);

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
        <div className="mx-2 h-4 w-px bg-gray-600" />
        <ToolbarButton label="Lint" onClick={runLint} />
        <ToolbarButton label="Load .ds" onClick={loadDs} />
      </div>

      {/* Main content area */}
      <div className="flex min-h-0 flex-1 flex-col">
        {/* Top row: explorer + editor + inspector */}
        <div className="flex min-h-0 flex-1">
          {/* Left panel: Explorer */}
          {showExplorer && (
            <div className="h-full w-[250px] shrink-0 border-r border-gray-700 overflow-hidden">
              <AppTreeExplorer />
            </div>
          )}

          {/* Center panel: Editor */}
          <div className="min-w-0 flex-1 overflow-hidden">
            <IdeEditor />
          </div>

          {/* Right panel: Inspector */}
          {showInspector && (
            <div className="h-full w-[300px] shrink-0 border-l border-gray-700 overflow-hidden">
              <InspectorPanel />
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
