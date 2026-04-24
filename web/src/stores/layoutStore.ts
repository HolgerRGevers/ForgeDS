import { create } from "zustand";
import type { PanelDockHint } from "../types/ide";

export const LAYOUT_STORAGE_KEY = "forgeds-ide-layout-v1";

/** Initial visible panels for the default layout. */
const DEFAULT_VISIBLE_PANELS = new Set<string>([
  "editor",
  "repo-explorer",
  "ds-tree",
  "inspector",
  "source-control",
  "console",
]);

interface LayoutStore {
  layoutJson: string | null;
  visiblePanels: Set<string>;
  lastKnownPositions: Record<string, PanelDockHint>;

  setLayoutJson: (json: string) => void;
  recordLastKnownPosition: (panelId: string, hint: PanelDockHint) => void;
  togglePanel: (panelId: string) => void;
  resetLayout: () => void;
}

let storageWarnedThisSession = false;

function writeStorage(json: string | null): void {
  try {
    if (json === null) {
      localStorage.removeItem(LAYOUT_STORAGE_KEY);
    } else {
      localStorage.setItem(LAYOUT_STORAGE_KEY, json);
    }
  } catch (err) {
    if (!storageWarnedThisSession) {
      console.warn("[layoutStore] Failed to persist layout to localStorage:", err);
      storageWarnedThisSession = true;
    }
  }
}

export const useLayoutStore = create<LayoutStore>((set, get) => ({
  layoutJson: null,
  visiblePanels: new Set(DEFAULT_VISIBLE_PANELS),
  lastKnownPositions: {},

  setLayoutJson: (json) => {
    set({ layoutJson: json });
    writeStorage(json);
  },

  recordLastKnownPosition: (panelId, hint) => {
    set({
      lastKnownPositions: { ...get().lastKnownPositions, [panelId]: hint },
    });
  },

  togglePanel: (panelId) => {
    const visible = get().visiblePanels;
    const next = new Set(visible);
    if (next.has(panelId)) {
      next.delete(panelId);
    } else {
      next.add(panelId);
    }
    set({ visiblePanels: next });
  },

  resetLayout: () => {
    set({
      layoutJson: null,
      visiblePanels: new Set(DEFAULT_VISIBLE_PANELS),
      lastKnownPositions: {},
    });
    writeStorage(null);
  },
}));
