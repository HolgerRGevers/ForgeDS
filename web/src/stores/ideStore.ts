import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ConsoleEntry, EditorTab, IdeStore } from "../types/ide";
import { bridge } from "../services/bridge";
import { useRepoStore } from "./repoStore";

let consoleSeq = 0;

/** Set to true after persist middleware rehydrates tabs from localStorage. */
let _tabsRestoredFromStorage = false;

/** Check whether tabs were just restored from storage (resets after first read). */
export function consumeTabsRestored(): boolean {
  if (_tabsRestoredFromStorage) {
    _tabsRestoredFromStorage = false;
    return true;
  }
  return false;
}

export const useIdeStore = create<IdeStore>()(persist(
  (set, get) => ({
  // --- State ---
  appStructure: null,
  selectedNodeId: null,
  treeFilter: "",

  tabs: [],
  activeTabId: null,
  diagnostics: [],

  inspectorData: null,

  consoleEntries: [],
  activeConsoleTab: "lint",

  // --- Actions ---

  loadAppStructure: (structure) => {
    set({ appStructure: structure, selectedNodeId: null });
  },

  selectNode: (nodeId) => {
    const { appStructure, tabs, activeTabId } = get();
    set({ selectedNodeId: nodeId });

    if (!appStructure) return;

    const node = appStructure.nodeIndex.get(nodeId);
    if (!node?.filePath) return;

    // If the file is already open, just activate its tab
    const existing = tabs.find((t) => t.path === node.filePath);
    if (existing) {
      if (activeTabId !== existing.id) {
        set({ activeTabId: existing.id });
      }
      return;
    }

    // Open a new tab for this file
    const lang = node.filePath.endsWith(".dg") ? "deluge" : "plaintext";
    const newTab: EditorTab = {
      id: `tab-${nodeId}`,
      name: node.label,
      path: node.filePath,
      content: "", // content loaded asynchronously by consumers
      language: lang,
      isDirty: false,
    };

    set({
      tabs: [...tabs, newTab],
      activeTabId: newTab.id,
    });
  },

  toggleNode: (nodeId) => {
    const { appStructure } = get();
    if (!appStructure) return;

    const node = appStructure.nodeIndex.get(nodeId);
    if (node) {
      node.isExpanded = !node.isExpanded;
      // Trigger re-render by replacing the structure reference
      set({ appStructure: { ...appStructure } });
    }
  },

  setTreeFilter: (filter) => {
    set({ treeFilter: filter });
  },

  openTab: (tab) => {
    const { tabs } = get();
    const existing = tabs.find((t) => t.id === tab.id);
    if (existing) {
      set({ activeTabId: tab.id });
      return;
    }
    set({ tabs: [...tabs, tab], activeTabId: tab.id });
  },

  closeTab: (tabId) => {
    const { tabs, activeTabId } = get();
    const idx = tabs.findIndex((t) => t.id === tabId);
    if (idx === -1) return;

    const next = tabs.filter((t) => t.id !== tabId);

    let nextActive = activeTabId;
    if (activeTabId === tabId) {
      if (next.length === 0) {
        nextActive = null;
      } else if (idx < next.length) {
        nextActive = next[idx].id;
      } else {
        nextActive = next[next.length - 1].id;
      }
    }

    set({ tabs: next, activeTabId: nextActive });
  },

  setActiveTab: (tabId) => {
    set({ activeTabId: tabId });
  },

  loadGeneratedFiles: (files) => {
    const existing = get().tabs;
    const existingIds = new Set(existing.map((t) => t.id));

    const newTabs: EditorTab[] = files
      .filter((f) => !existingIds.has(f.path)) // skip duplicates
      .map((f) => {
        const ext = f.name.split(".").pop() ?? "";
        const langMap: Record<string, string> = {
          dg: "deluge", ds: "plaintext", py: "python", json: "json",
          yaml: "yaml", yml: "yaml", md: "markdown", sql: "sql",
          csv: "plaintext", txt: "plaintext", js: "javascript",
          ts: "typescript",
        };
        return {
          id: f.path,
          name: f.name,
          path: f.path,
          content: f.content,
          language: langMap[ext] ?? f.language ?? "plaintext",
          isDirty: false,
        };
      });

    const merged = [...existing, ...newTabs];
    set({
      tabs: merged,
      activeTabId: newTabs[0]?.id ?? get().activeTabId ?? merged[0]?.id ?? null,
    });
  },

  updateTabContent: (tabId, content) => {
    set({
      tabs: get().tabs.map((t) =>
        t.id === tabId ? { ...t, content, isDirty: true } : t,
      ),
    });
  },

  saveFile: async (tabId) => {
    const tab = get().tabs.find((t) => t.id === tabId);
    if (!tab) return false;

    try {
      const result = await bridge.send("write_file", {
        file_path: tab.path,
        content: tab.content,
      });

      if ((result as Record<string, unknown>).error) {
        get().addConsoleEntry({
          type: "error",
          message: `Save failed: ${(result as Record<string, unknown>).error}`,
        });
        return false;
      }

      // Clear dirty flag on success
      set({
        tabs: get().tabs.map((t) =>
          t.id === tabId ? { ...t, isDirty: false } : t,
        ),
      });

      // Stage the change in repoStore if a repo is selected
      const repoState = useRepoStore.getState();
      if (repoState.selectedRepo) {
        repoState.stageChange(tab.path, tab.content, "update");
      }

      return true;
    } catch (err) {
      get().addConsoleEntry({
        type: "error",
        message: `Save failed: ${err instanceof Error ? err.message : String(err)}`,
      });
      return false;
    }
  },

  hasDirtyTabs: () => {
    return get().tabs.some((t) => t.isDirty);
  },

  setDiagnostics: (diagnostics) => {
    set({ diagnostics });
  },

  setInspectorData: (data) => {
    set({ inspectorData: data });
  },

  addConsoleEntry: (entry) => {
    const full: ConsoleEntry = {
      ...entry,
      id: `console-${++consoleSeq}`,
      timestamp: new Date().toISOString(),
    };
    set({ consoleEntries: [full, ...get().consoleEntries] });
  },

  clearConsole: () => {
    set({ consoleEntries: [] });
  },

  setActiveConsoleTab: (tab) => {
    set({ activeConsoleTab: tab });
  },
}),
  {
    name: "forgeds-ide-tabs",
    partialize: (state) => ({
      tabs: state.tabs,
      activeTabId: state.activeTabId,
    }),
    onRehydrateStorage: () => (state) => {
      if (state && state.tabs.length > 0) {
        _tabsRestoredFromStorage = true;
      }
    },
  },
));
