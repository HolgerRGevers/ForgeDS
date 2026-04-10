import { create } from "zustand";
import type { ConsoleEntry, EditorTab, IdeStore } from "../types/ide";

let consoleSeq = 0;

export const useIdeStore = create<IdeStore>((set, get) => ({
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
    const newTabs: EditorTab[] = files.map((f) => {
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
    set({
      tabs: newTabs,
      activeTabId: newTabs[0]?.id ?? null,
    });
  },

  updateTabContent: (tabId, content) => {
    set({
      tabs: get().tabs.map((t) =>
        t.id === tabId ? { ...t, content, isDirty: true } : t,
      ),
    });
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
}));
