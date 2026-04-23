import { useCallback, useMemo, useRef } from "react";
import type { DockviewApi, IDockviewPanelProps } from "dockview-react";
import { ActivityBar } from "./ActivityBar";
import { DockviewHost, type PanelRegistry } from "./DockviewHost";
import { DockviewErrorBoundary } from "./DockviewErrorBoundary";
import { ConsolePanel } from "./ConsolePanel";
import { EditorPanel } from "./EditorPanel";
import { RepoExplorer } from "./RepoExplorer";
import { AppTreeExplorer } from "./AppTreeExplorer";
import { InspectorPanel } from "./InspectorPanel";
import { SourceControlPanel } from "./SourceControlPanel";
import { useIdeStore } from "../../stores/ideStore";
import { useLayoutStore } from "../../stores/layoutStore";
import { useBridgeStore } from "../../stores/bridgeStore";
import { useIdeBootstrap } from "../../hooks/useIdeBootstrap";

/** Adapt our non-dockview panel components to dockview's IDockviewPanelProps shape
 *  by discarding the props (our components pull their state from Zustand stores). */
function panelWrapper(Component: React.ComponentType) {
  const Wrapper = (_props: IDockviewPanelProps) => <Component />;
  Wrapper.displayName = `DockviewPanel(${Component.displayName ?? Component.name ?? "Anonymous"})`;
  return Wrapper;
}

const WrappedInspectorPanel = panelWrapper(InspectorPanel);
const WrappedSourceControlPanel = panelWrapper(SourceControlPanel);

export function IdeShell() {
  const apiRef = useRef<DockviewApi | null>(null);

  const bridgeStatus = useBridgeStore((s) => s.status);
  const appStructure = useIdeStore((s) => s.appStructure);
  const activeConsoleCategory = useIdeStore((s) => s.activeConsoleCategory);
  const setActiveConsoleCategory = useIdeStore((s) => s.setActiveConsoleCategory);
  const setAppLoadSource = useIdeStore((s) => s.setAppLoadSource);

  const togglePanel = useLayoutStore((s) => s.togglePanel);
  const resetLayout = useLayoutStore((s) => s.resetLayout);
  const visiblePanels = useLayoutStore((s) => s.visiblePanels);

  const { runLint, loadDsFromContent } = useIdeBootstrap();

  const handleRepoFileSelect = useCallback(
    (path: string, content: string) => {
      const name = path.split("/").pop() ?? path;
      const ext = (name.split(".").pop() ?? "").toLowerCase();
      const langMap: Record<string, string> = {
        dg: "deluge", ds: "plaintext", py: "python", json: "json",
        yaml: "yaml", yml: "yaml", md: "markdown", sql: "sql",
        csv: "plaintext", txt: "plaintext",
      };
      const tab = {
        id: path,
        name,
        path,
        content,
        language: langMap[ext] ?? "plaintext",
        isDirty: false,
      };
      useIdeStore.getState().openTab(tab);

      if (ext === "ds") {
        setAppLoadSource("repo");
        loadDsFromContent(name, content);
      }
    },
    [loadDsFromContent, setAppLoadSource],
  );

  const handleUpload = useCallback(
    async (file: File) => {
      const content = await file.text();
      loadDsFromContent(file.name, content);
    },
    [loadDsFromContent],
  );

  const registry = useMemo<PanelRegistry>(
    () => ({
      "editor": {
        title: "Editor",
        component: EditorPanel,
        closable: false,
      },
      "repo-explorer": {
        title: "Repo",
        component: (_props: IDockviewPanelProps) => (
          <RepoExplorer onFileSelect={handleRepoFileSelect} />
        ),
      },
      "ds-tree": {
        title: ".ds Tree",
        component: (_props: IDockviewPanelProps) => (
          <AppTreeExplorer onLoadDsFile={handleUpload} />
        ),
      },
      "inspector": {
        title: "Inspector",
        component: WrappedInspectorPanel,
      },
      "source-control": {
        title: "Source Control",
        component: WrappedSourceControlPanel,
      },
      "console": {
        title: "Console",
        component: (_props: IDockviewPanelProps) => <ConsolePanel />,
      },
    }),
    [handleRepoFileSelect, handleUpload],
  );

  const handleConsoleCategory = useCallback(
    (cat: "scripts" | "devtools") => {
      const consoleVisible = visiblePanels.has("console");
      if (!consoleVisible) {
        togglePanel("console");
        setActiveConsoleCategory(cat);
        return;
      }
      if (activeConsoleCategory !== cat) {
        setActiveConsoleCategory(cat);
        return;
      }
      togglePanel("console");
    },
    [visiblePanels, activeConsoleCategory, togglePanel, setActiveConsoleCategory],
  );

  const handleReady = useCallback((api: DockviewApi) => {
    apiRef.current = api;
  }, []);

  return (
    <div className="flex h-full flex-col overflow-hidden bg-gray-900 text-gray-100">
      <div className="flex h-9 items-center gap-2 border-b border-gray-700 bg-gray-800 px-2">
        <button
          type="button"
          onClick={resetLayout}
          className="rounded px-2 py-0.5 text-xs font-medium text-gray-300 hover:bg-gray-700 hover:text-white"
          title="Reset layout to default"
        >
          Reset Layout
        </button>
        <div className="mx-1 h-4 w-px bg-gray-600" />
        {bridgeStatus === "connected" && (
          <button
            type="button"
            onClick={runLint}
            className="rounded px-2 py-0.5 text-xs font-medium text-gray-300 hover:bg-gray-700 hover:text-white"
          >
            Lint
          </button>
        )}
        {bridgeStatus !== "connected" && (
          <span className="text-[10px] text-gray-500">
            {appStructure
              ? `Bridge offline — ${appStructure.displayName} loaded locally`
              : "Bridge offline — upload a .ds file to explore"}
          </span>
        )}
      </div>
      <div className="flex min-h-0 flex-1">
        <ActivityBar onToggle={togglePanel} onConsoleCategory={handleConsoleCategory} />
        <div className="min-w-0 flex-1">
          <DockviewErrorBoundary>
            <DockviewHost registry={registry} onReady={handleReady} />
          </DockviewErrorBoundary>
        </div>
      </div>
    </div>
  );
}
