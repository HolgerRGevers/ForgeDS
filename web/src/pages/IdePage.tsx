import { useCallback, useEffect, useRef, useState } from "react";
import { useBlocker } from "react-router-dom";
import {
  AppTreeExplorer,
  DevConsole,
  GlobalSearchPanel,
  IdeEditor,
  InspectorPanel,
  QuickOpenModal,
  RepoExplorer,
  SourceControlPanel,
} from "../components/ide";
import { useIdeStore, consumeTabsRestored } from "../stores/ideStore";
import { useBridgeStore } from "../stores/bridgeStore";
import type { AppStructure, InspectorData, TreeNode } from "../types/ide";

type ExplorerMode = "repo" | "ds" | "search";

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

/** Hook to detect screen size category. */
function useBreakpoint() {
  const [bp, setBp] = useState<"mobile" | "tablet" | "desktop">("desktop");
  useEffect(() => {
    const check = () => {
      const w = window.innerWidth;
      setBp(w < 640 ? "mobile" : w < 1024 ? "tablet" : "desktop");
    };
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);
  return bp;
}

export default function IdePage() {
  const bp = useBreakpoint();
  const isMobile = bp === "mobile";
  const isTablet = bp === "tablet";

  // On mobile/tablet, panels start collapsed
  const [showExplorer, setShowExplorer] = useState(!isMobile);
  const [showInspector, setShowInspector] = useState(false);
  const [showConsole, setShowConsole] = useState(!isMobile);
  const [explorerMode, setExplorerMode] = useState<ExplorerMode>("repo");
  const [showSourceControl, setShowSourceControl] = useState(false);
  const [showQuickOpen, setShowQuickOpen] = useState(false);

  // On mobile, show a bottom sheet for active panel
  const [mobilePanel, setMobilePanel] = useState<"none" | "explorer" | "inspector" | "console" | "source">("none");

  // Track the previous explorer mode so we can restore it when search closes
  const prevExplorerMode = useRef<ExplorerMode>("repo");

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

  // Auto-collapse panels when resizing down
  useEffect(() => {
    if (isMobile) {
      setShowExplorer(false);
      setShowInspector(false);
      setShowConsole(false);
    }
  }, [isMobile]);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  // Staleness check
  const hasDoneStaleCheck = useRef(false);
  useEffect(() => {
    if (status !== "connected" || hasDoneStaleCheck.current) return;
    if (!consumeTabsRestored()) return;
    hasDoneStaleCheck.current = true;

    const currentTabs = useIdeStore.getState().tabs;
    for (const tab of currentTabs) {
      if (tab.isDirty || !tab.content) continue;
      loadedTabsRef.current.add(tab.id);
      send("read_file", { file_path: tab.path })
        .then((response) => {
          const data = response as unknown as { content: string };
          if (data.content && data.content !== tab.content) {
            updateTabContent(tab.id, data.content);
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
        .catch(() => {});
    }
  }, [status, send, updateTabContent, addConsoleEntry]);

  // Load file content into new tabs
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

  // Fetch inspector data
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
        dg: "deluge", ds: "plaintext", py: "python", json: "json",
        yaml: "yaml", yml: "yaml", md: "markdown", sql: "sql",
        csv: "plaintext", txt: "plaintext",
      };
      const tab = {
        id: path, name, path, content,
        language: langMap[ext] ?? "plaintext",
        isDirty: false,
      };
      useIdeStore.getState().openTab(tab);
      // Close mobile panel after selecting a file
      if (isMobile) setMobilePanel("none");
    },
    [isMobile],
  );

  // --- Keyboard shortcuts ---
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const ctrl = e.ctrlKey || e.metaKey;

      if (ctrl && e.shiftKey && e.key === "F") {
        e.preventDefault();
        if (isMobile) {
          setMobilePanel("explorer");
        } else {
          if (explorerMode !== "search") {
            prevExplorerMode.current = explorerMode === "search" ? "repo" : explorerMode;
          }
          setExplorerMode("search");
          setShowExplorer(true);
        }
        return;
      }
      if (ctrl && e.key === "p") {
        e.preventDefault();
        setShowQuickOpen((v) => !v);
        return;
      }
      if (ctrl && e.key === "b") {
        e.preventDefault();
        if (isMobile) {
          setMobilePanel((v) => v === "explorer" ? "none" : "explorer");
        } else {
          setShowExplorer((v) => !v);
        }
        return;
      }
      if (ctrl && e.key === "j") {
        e.preventDefault();
        if (isMobile) {
          setMobilePanel((v) => v === "console" ? "none" : "console");
        } else {
          setShowConsole((v) => !v);
        }
        return;
      }
      if (ctrl && e.shiftKey && e.key === "I") {
        e.preventDefault();
        if (isMobile) {
          setMobilePanel((v) => v === "inspector" ? "none" : "inspector");
        } else {
          setShowInspector((v) => !v);
        }
        return;
      }
      if (ctrl && e.shiftKey && e.key === "G") {
        e.preventDefault();
        if (isMobile) {
          setMobilePanel((v) => v === "source" ? "none" : "source");
        } else {
          setShowSourceControl((v) => !v);
        }
        return;
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [explorerMode, isMobile]);

  const handleSearchClose = useCallback(() => {
    setExplorerMode(prevExplorerMode.current);
  }, []);

  // --- Render helpers for mobile panels ---
  const renderExplorerContent = () => {
    if (explorerMode === "search") return <GlobalSearchPanel onClose={handleSearchClose} />;
    if (explorerMode === "repo") return <RepoExplorer onFileSelect={handleRepoFileSelect} />;
    return <AppTreeExplorer />;
  };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Quick Open Modal */}
      {showQuickOpen && (
        <QuickOpenModal onClose={() => setShowQuickOpen(false)} />
      )}

      {/* Toolbar */}
      <div className="flex items-center gap-1 overflow-x-auto border-b border-gray-700 bg-gray-850 px-2 py-1">
        {/* Panel toggles — on mobile these control the bottom sheet */}
        <ToolbarToggle
          label={isMobile ? "Files" : "Explorer"}
          active={isMobile ? mobilePanel === "explorer" : showExplorer}
          onClick={() => isMobile ? setMobilePanel((v) => v === "explorer" ? "none" : "explorer") : setShowExplorer((v) => !v)}
          shortcut="Ctrl+B"
        />
        <ToolbarToggle
          label="Inspector"
          active={isMobile ? mobilePanel === "inspector" : showInspector}
          onClick={() => isMobile ? setMobilePanel((v) => v === "inspector" ? "none" : "inspector") : setShowInspector((v) => !v)}
          shortcut="Ctrl+Shift+I"
        />
        <ToolbarToggle
          label="Console"
          active={isMobile ? mobilePanel === "console" : showConsole}
          onClick={() => isMobile ? setMobilePanel((v) => v === "console" ? "none" : "console") : setShowConsole((v) => !v)}
          shortcut="Ctrl+J"
        />
        <ToolbarToggle
          label={isMobile ? "SCM" : "Source Control"}
          active={isMobile ? mobilePanel === "source" : showSourceControl}
          onClick={() => isMobile ? setMobilePanel((v) => v === "source" ? "none" : "source") : setShowSourceControl((v) => !v)}
          shortcut="Ctrl+Shift+G"
        />
        <div className="mx-1 h-4 w-px bg-gray-600 sm:mx-2" />

        {/* Explorer mode toggle (desktop/tablet only when explorer visible) */}
        {(showExplorer || mobilePanel === "explorer") && !isMobile && (
          <div className="inline-flex rounded border border-gray-700 bg-gray-800 p-0.5">
            <button
              type="button"
              onClick={() => setExplorerMode("repo")}
              className={`rounded px-2 py-0.5 text-[10px] font-medium transition-colors ${explorerMode === "repo" ? "bg-blue-600 text-white" : "text-gray-400 hover:text-gray-200"}`}
              title="GitHub repository files"
            >
              Repo
            </button>
            <button
              type="button"
              onClick={() => setExplorerMode("ds")}
              className={`rounded px-2 py-0.5 text-[10px] font-medium transition-colors ${explorerMode === "ds" ? "bg-blue-600 text-white" : "text-gray-400 hover:text-gray-200"}`}
              title=".ds export structure"
            >
              .ds
            </button>
            <button
              type="button"
              onClick={() => {
                if (explorerMode !== "search") prevExplorerMode.current = explorerMode === "search" ? "repo" : explorerMode;
                setExplorerMode("search");
              }}
              className={`rounded px-2 py-0.5 text-[10px] font-medium transition-colors ${explorerMode === "search" ? "bg-blue-600 text-white" : "text-gray-400 hover:text-gray-200"}`}
              title="Search (Ctrl+Shift+F)"
            >
              Search
            </button>
          </div>
        )}

        <div className="mx-1 h-4 w-px bg-gray-600 sm:mx-2" />
        {status === "connected" && (
          <>
            <ToolbarButton label="Lint" onClick={runLint} />
            <ToolbarButton label="Load .ds" onClick={loadDs} />
          </>
        )}
        {status !== "connected" && (
          <span className="whitespace-nowrap text-[10px] text-gray-500">
            Bridge offline
          </span>
        )}
      </div>

      {/* Main content area — desktop layout */}
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex min-h-0 flex-1">
          {/* Left panel: Explorer (hidden on mobile, uses bottom sheet) */}
          {!isMobile && showExplorer && (
            <div className={`h-full shrink-0 border-r border-gray-700 overflow-hidden ${isTablet ? "w-[200px]" : "w-[250px]"}`}>
              {renderExplorerContent()}
            </div>
          )}

          {/* Center panel: Editor */}
          <div className="min-w-0 flex-1 overflow-hidden">
            <IdeEditor />
          </div>

          {/* Right panel: Inspector or Source Control (hidden on mobile) */}
          {!isMobile && (showInspector || showSourceControl) && (
            <div className={`h-full shrink-0 border-l border-gray-700 overflow-hidden ${isTablet ? "w-[240px]" : "w-[300px]"}`}>
              {showSourceControl ? <SourceControlPanel /> : <InspectorPanel />}
            </div>
          )}
        </div>

        {/* Bottom panel: Console (desktop/tablet) */}
        {!isMobile && showConsole && (
          <div className={`shrink-0 border-t border-gray-700 overflow-hidden ${isTablet ? "h-[150px]" : "h-[200px]"}`}>
            <DevConsole />
          </div>
        )}

        {/* Mobile bottom sheet panel */}
        {isMobile && mobilePanel !== "none" && (
          <div className="h-[50vh] shrink-0 border-t border-gray-700 overflow-hidden">
            <div className="flex items-center justify-between border-b border-gray-700 bg-gray-800 px-3 py-1.5">
              <span className="text-xs font-medium text-gray-300 capitalize">{mobilePanel}</span>

              {/* Explorer mode toggle in mobile sheet */}
              {mobilePanel === "explorer" && (
                <div className="inline-flex rounded border border-gray-700 bg-gray-800 p-0.5">
                  <button type="button" onClick={() => setExplorerMode("repo")}
                    className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${explorerMode === "repo" ? "bg-blue-600 text-white" : "text-gray-400"}`}>Repo</button>
                  <button type="button" onClick={() => setExplorerMode("ds")}
                    className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${explorerMode === "ds" ? "bg-blue-600 text-white" : "text-gray-400"}`}>.ds</button>
                  <button type="button" onClick={() => { if (explorerMode !== "search") prevExplorerMode.current = explorerMode === "search" ? "repo" : explorerMode; setExplorerMode("search"); }}
                    className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${explorerMode === "search" ? "bg-blue-600 text-white" : "text-gray-400"}`}>Search</button>
                </div>
              )}

              <button
                type="button"
                onClick={() => setMobilePanel("none")}
                className="rounded px-1.5 py-0.5 text-xs text-gray-500 hover:bg-gray-700 hover:text-gray-300"
              >
                Close
              </button>
            </div>
            <div className="h-[calc(100%-32px)] overflow-hidden">
              {mobilePanel === "explorer" && renderExplorerContent()}
              {mobilePanel === "inspector" && <InspectorPanel />}
              {mobilePanel === "console" && <DevConsole />}
              {mobilePanel === "source" && <SourceControlPanel />}
            </div>
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
  shortcut,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  shortcut?: string;
}) {
  return (
    <button
      onClick={onClick}
      title={shortcut}
      className={`whitespace-nowrap rounded px-1.5 py-0.5 text-[11px] font-medium transition-colors sm:px-2 sm:text-xs ${
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
      className="whitespace-nowrap rounded px-1.5 py-0.5 text-[11px] font-medium text-gray-300 bg-gray-700 hover:bg-gray-600 hover:text-white transition-colors sm:px-2 sm:text-xs"
    >
      {label}
    </button>
  );
}
