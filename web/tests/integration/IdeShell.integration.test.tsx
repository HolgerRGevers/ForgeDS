import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useIdeStore } from "../../src/stores/ideStore";
import { useLayoutStore, LAYOUT_STORAGE_KEY } from "../../src/stores/layoutStore";

// jsdom does not implement ResizeObserver; stub it so ConsolePanel doesn't throw.
if (typeof ResizeObserver === "undefined") {
  global.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

// Prevent RepoExplorer's fetchRepos from throwing "Not authenticated" in test.
vi.mock("../../src/stores/repoStore", async () => {
  const { create } = await import("zustand");
  const noop = () => {};
  const noopAsync = async () => {};
  const stub = {
    repos: [] as unknown[],
    selectedRepo: null,
    selectedBranch: null,
    branches: [] as unknown[],
    repoTree: [] as unknown[],
    repoLoading: false,
    pendingChanges: new Map(),
    fetchRepos: noop,
    selectRepo: noop,
    selectBranch: noop,
    fetchFileContent: noopAsync,
  };
  const useRepoStore = create(() => stub);
  return { useRepoStore };
});

vi.mock("dockview-react", () => {
  return {
    DockviewReact: ({
      components,
      onReady,
    }: {
      components: Record<string, React.ComponentType>;
      onReady: (event: { api: unknown }) => void;
    }) => {
      const panels = new Map<
        string,
        { id: string; group: { panels: Array<{ id: string }> } }
      >();
      const api = {
        addPanel(opts: { id: string; component: string; title: string }) {
          const panel = {
            id: opts.id,
            group: { panels: [] as Array<{ id: string }> },
            focus() {},
          };
          panels.set(opts.id, panel);
          return panel;
        },
        getPanel(id: string) {
          return panels.get(id);
        },
        removePanel(panel: { id: string }) {
          panels.delete(panel.id);
        },
        toJSON() {
          return { panels: Array.from(panels.keys()) };
        },
        fromJSON(_json: unknown) {},
        onDidLayoutChange(_cb: () => void) {
          return { dispose() {} };
        },
      };
      queueMicrotask(() => onReady({ api }));
      return (
        <div data-testid="dockview-stub">
          {Object.entries(components).map(([id, Comp]) => (
            <div key={id} data-panel={id}>
              <Comp />
            </div>
          ))}
        </div>
      );
    },
  };
});

beforeEach(() => {
  localStorage.clear();
  useIdeStore.setState({
    appStructure: null,
    tabs: [],
    activeTabId: null,
    activeConsoleCategory: "devtools",
    activeScriptsTab: "blueprints",
    activeDevToolsTab: "lint",
    appLoadSource: null,
    completeScriptShownForApps: new Set<string>(),
    inspectorData: null,
    consoleEntries: [],
    diagnostics: [],
    selectedNodeId: null,
    treeFilter: "",
  });
  useLayoutStore.setState({
    layoutJson: null,
    visiblePanels: new Set([
      "editor",
      "repo-explorer",
      "ds-tree",
      "inspector",
      "source-control",
      "console",
    ]),
    lastKnownPositions: {},
  });
});

async function renderShell() {
  const { IdeShell } = await import("../../src/components/ide/IdeShell");
  return render(
    <MemoryRouter>
      <IdeShell />
    </MemoryRouter>,
  );
}

describe("IdeShell integration", () => {
  it("registers all 6 dockable panel IDs on mount", async () => {
    await act(async () => {
      await renderShell();
    });
    const stub = await screen.findByTestId("dockview-stub");
    for (const id of [
      "editor",
      "repo-explorer",
      "ds-tree",
      "inspector",
      "source-control",
      "console",
    ]) {
      expect(stub.querySelector(`[data-panel="${id}"]`)).not.toBeNull();
    }
  });

  it("first-load UI fires when appLoadSource='wizard' and an app is loaded", async () => {
    await act(async () => {
      await renderShell();
    });
    await act(async () => {
      useIdeStore.getState().setAppLoadSource("wizard");
      useIdeStore.getState().loadAppStructure({
        name: "demoapp",
        displayName: "Demo App",
        tree: [],
        nodeIndex: new Map(),
      });
    });
    const s = useIdeStore.getState();
    expect(s.activeConsoleCategory).toBe("scripts");
    expect(s.activeScriptsTab).toBe("complete");
    expect(s.tabs.some((t) => t.path === "demoapp.ds")).toBe(true);
  });

  it("falls back to default layout when localStorage has corrupt JSON", async () => {
    localStorage.setItem(LAYOUT_STORAGE_KEY, "{not json");
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    await act(async () => {
      await renderShell();
    });
    await screen.findByTestId("dockview-stub");
    expect(warnSpy).toHaveBeenCalled();
    warnSpy.mockRestore();
  });
});
