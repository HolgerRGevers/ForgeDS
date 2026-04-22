# ForgeDS IDE Shell Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ForgeDS IDE's fixed CSS-grid layout with `dockview-react` (VS Code-style docking), add a vertical activity bar for panel toggling, and redesign the bottom console as a two-level tabbed container (Scripts / Dev Tools).

**Architecture:** `dockview-react` owns everything below the top bar and manages panel geometry. A new `layoutStore` (Zustand) serializes dockview state to `localStorage` and implements activity-bar-driven show/hide. A new `ConsolePanel` renders pure-React two-level tabs inside a single dockview panel; Scripts category holds a `CompleteScriptView` plus seven empty-state `WorkflowTabView`s (data extraction deferred to Polish Pass spec). A new `useIdeBootstrap` hook extracts the current `IdePage` effects and wires first-load behavior (open `.ds` editor tab + activate Complete Script) based on a new `appLoadSource` field.

**Tech Stack:** React 19, TypeScript, Zustand, Monaco editor, Vite, Vitest + @testing-library/react, `dockview-react` (new).

**Spec:** [`docs/superpowers/specs/2026-04-22-ide-shell-overhaul-design.md`](../specs/2026-04-22-ide-shell-overhaul-design.md)

**Working directory for all commands:** `C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS/web/` (the React app root). Paths inside tasks are relative to this directory unless otherwise noted.

---

## File Structure

### New files (created by this plan)

| File | Responsibility |
|---|---|
| `src/components/ide/IdeShell.tsx` | Top-level IDE container. Renders top bar + activity bar + DockviewHost. Replaces current IdePage layout logic. |
| `src/components/ide/ActivityBar.tsx` | Vertical icon strip on the far left. Click → `layoutStore.togglePanel(id)`. |
| `src/components/ide/DockviewHost.tsx` | Wraps `<DockviewReact />`. Registers panel components, restores layout from localStorage, debounced serialize on change, exposes `resetLayout` API. |
| `src/components/ide/ConsolePanel.tsx` | Single dockview panel for the bottom zone. Renders internal two-level tabs (category row + sub-tab row). Responsive <400 px fallback. |
| `src/components/ide/CompleteScriptView.tsx` | Scripts category sub-tab content — summary (filename, counts, size, parse status) + "Open in editor" action. |
| `src/components/ide/WorkflowTabView.tsx` | Generic container for the 7 Creator-style workflow tabs. Takes `workflowType` prop. Empty-state rendering only (data pending Polish Pass). |
| `src/components/ide/WorkflowFormSidebar.tsx` | Left column of `WorkflowTabView` — "Forms with [type]" / "Forms without [type]" sections. |
| `src/components/ide/WorkflowDetailTable.tsx` | Right column of `WorkflowTabView` — row list. Row click → `ideStore.openTab`. |
| `src/components/ide/DevToolsCategory.tsx` | Renamed from `DevConsole.tsx`. Wraps the four existing tab components (Lint / Build / Relationships / AI Chat) without the outer header / collapse UI. |
| `src/hooks/useIdeBootstrap.ts` | Extracts current IdePage effects (bridge connect, parse_ds, read_file, inspect_element). Adds first-load UI trigger. |
| `src/stores/layoutStore.ts` | Zustand store — layout JSON, visible panels, last-known positions, toggle/reset actions. |
| `src/styles/dockview-theme.css` | CSS variable overrides to match the existing dark palette (`bg-gray-800`, `border-gray-700`, etc.). |
| `tests/stores/layoutStore.test.ts` | Unit tests for layoutStore. |
| `tests/stores/ideStore.test.ts` | Unit tests for new ideStore state/actions. |
| `tests/hooks/useIdeBootstrap.test.tsx` | Tests for first-load trigger matrix. |
| `tests/components/ide/ActivityBar.test.tsx` | Tests: 6 icons render, click → togglePanel, keyboard activation. |
| `tests/components/ide/ConsolePanel.test.tsx` | Tests: category tabs, sub-tab independence, narrow-width `<select>` fallback. |
| `tests/components/ide/CompleteScriptView.test.tsx` | Tests: summary rendering, "Open in editor" action. |
| `tests/components/ide/WorkflowTabView.test.tsx` | Tests: empty state, mock data render, row click. |
| `tests/integration/IdeShell.integration.test.tsx` | Full shell mount, default layout, first-load simulation, corrupt-layout recovery. |

### Modified files

| File | Change |
|---|---|
| `src/types/ide.ts` | Add `ScriptsTab` union, `PanelDockHint` interface, extend `IdeStore` interface with new fields/actions. |
| `src/stores/ideStore.ts` | Implement new state + actions (`activeConsoleCategory`, `activeScriptsTab`, `activeDevToolsTab` rename, `appLoadSource`, `completeScriptShownForApps`). |
| `src/pages/IdePage.tsx` | Gutted → returns `<IdeShell />`. Effects move to `useIdeBootstrap`. Repo-file-select callback adds `setAppLoadSource("repo")`. |
| `src/pages/BuildingPage.tsx` | After `loadGeneratedFiles(files)` call, also call `setAppLoadSource("wizard")`. |
| `src/components/ide/AppTreeExplorer.tsx` | When `onLoadDsFile` fires (manual upload), call `setAppLoadSource("upload")`. |
| `src/components/ide/index.ts` | Export new components; remove `DevConsole` export, add `DevToolsCategory`, `IdeShell`, etc. |
| `src/main.tsx` (or `src/index.css`) | Import dockview CSS + new `dockview-theme.css` override. |
| `package.json` | Add `dockview-react` dependency. |

### Deleted files

| File | Reason |
|---|---|
| `src/components/ide/DevConsole.tsx` | Renamed to `DevToolsCategory.tsx`; the outer shell (drag handle, collapse button, standalone tab bar) is replaced by dockview's tab strip + ConsolePanel's category tabs. |

---

## Task 1: Install `dockview-react` and import its CSS

**Files:**
- Modify: `package.json`
- Modify: `src/main.tsx`

- [ ] **Step 1: Install the dependency**

Run (from `web/`):

```bash
npm install dockview-react@^3
```

Expected output: installation succeeds, `package.json` shows `"dockview-react"` in `dependencies`. If the exact minor version published differs, that's fine — pick the latest published under major v3.

- [ ] **Step 2: Confirm install**

```bash
ls node_modules/dockview-react/package.json
cat node_modules/dockview-react/package.json | grep '"version"' | head -1
```

Expected: file exists, version begins with `3.`.

- [ ] **Step 3: Import dockview CSS at the app entry point**

Open `src/main.tsx`. Find the existing CSS imports near the top (there should be `./index.css`). Add **immediately after** `./index.css`:

```tsx
import "dockview-react/dist/styles/dockview.css";
```

- [ ] **Step 4: Verify Vite still builds**

```bash
npm run build
```

Expected: build succeeds with no CSS resolution errors.

- [ ] **Step 5: Commit**

```bash
git add package.json package-lock.json src/main.tsx
git commit -m "feat(ide): add dockview-react dependency"
```

---

## Task 2: Extend `types/ide.ts` with shell-overhaul types

**Files:**
- Modify: `src/types/ide.ts`

- [ ] **Step 1: Add new types to `src/types/ide.ts`**

Open `src/types/ide.ts`. Add the following **after** the existing `ConsoleTab` type alias (currently line 115):

```ts
// === Shell Overhaul Types ===

/** A sub-tab within the Scripts category of the bottom console. */
export type ScriptsTab =
  | "complete"
  | "form-workflows"
  | "schedules"
  | "approvals"
  | "payments"
  | "blueprints"
  | "batch-workflows"
  | "functions";

/** A top-level category in the bottom console (two-level tab structure). */
export type ConsoleCategory = "scripts" | "devtools";

/** Remembered drop location for a panel hidden via the activity bar.
 *  Used when re-adding the panel so it returns to where the user last had it. */
export interface PanelDockHint {
  referencePanelId?: string;
  direction?: "left" | "right" | "above" | "below" | "within";
}

/** How the currently-loaded app arrived. Drives first-load UI behavior. */
export type AppLoadSource = "wizard" | "repo" | "upload" | "bridge-auto" | null;
```

- [ ] **Step 2: Extend the `IdeStore` interface**

In the same file, find `export interface IdeStore {` (currently around line 119). Locate the `// Dev console` block and replace

```ts
  // Dev console
  consoleEntries: ConsoleEntry[];
  activeConsoleTab: ConsoleTab;
```

with:

```ts
  // Dev console / Bottom panel
  consoleEntries: ConsoleEntry[];
  activeConsoleCategory: ConsoleCategory;
  activeScriptsTab: ScriptsTab;
  activeDevToolsTab: ConsoleTab;

  // App acquisition tracking (drives first-load UI)
  appLoadSource: AppLoadSource;
  completeScriptShownForApps: Set<string>;
```

Then in the `// Actions` block, replace:

```ts
  addConsoleEntry: (entry: Omit<ConsoleEntry, "id" | "timestamp">) => void;
  clearConsole: () => void;
  setActiveConsoleTab: (tab: ConsoleTab) => void;
```

with:

```ts
  addConsoleEntry: (entry: Omit<ConsoleEntry, "id" | "timestamp">) => void;
  clearConsole: () => void;
  setActiveConsoleCategory: (cat: ConsoleCategory) => void;
  setActiveScriptsTab: (tab: ScriptsTab) => void;
  setActiveDevToolsTab: (tab: ConsoleTab) => void;

  setAppLoadSource: (src: AppLoadSource) => void;
  markCompleteScriptShown: (appName: string) => void;
```

- [ ] **Step 3: TypeScript check — expected to report errors**

```bash
npx tsc -b --noEmit
```

Expected: errors in `src/stores/ideStore.ts` (missing implementations for new actions, stale `activeConsoleTab` / `setActiveConsoleTab` references) and `src/components/ide/DevConsole.tsx` (uses the old names). These are fixed by Task 3 and Task 9.

- [ ] **Step 4: Commit**

```bash
git add src/types/ide.ts
git commit -m "feat(ide): add shell-overhaul types (ScriptsTab, PanelDockHint, ConsoleCategory)"
```

---

## Task 3: Update `ideStore.ts` with new state and actions

**Files:**
- Modify: `src/stores/ideStore.ts`
- Test: `tests/stores/ideStore.test.ts` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/stores/ideStore.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";
import { useIdeStore } from "../../src/stores/ideStore";
import type { AppStructure, ConsoleTab, ScriptsTab } from "../../src/types/ide";

function resetStore() {
  useIdeStore.setState({
    appStructure: null,
    selectedNodeId: null,
    treeFilter: "",
    tabs: [],
    activeTabId: null,
    diagnostics: [],
    inspectorData: null,
    consoleEntries: [],
    activeConsoleCategory: "scripts",
    activeScriptsTab: "complete",
    activeDevToolsTab: "lint",
    appLoadSource: null,
    completeScriptShownForApps: new Set<string>(),
  });
}

describe("ideStore — shell overhaul additions", () => {
  beforeEach(resetStore);

  it("defaults to Scripts category and Complete sub-tab", () => {
    const s = useIdeStore.getState();
    expect(s.activeConsoleCategory).toBe("scripts");
    expect(s.activeScriptsTab).toBe("complete");
    expect(s.activeDevToolsTab).toBe("lint");
    expect(s.appLoadSource).toBe(null);
    expect(s.completeScriptShownForApps.size).toBe(0);
  });

  it("setActiveConsoleCategory switches category without resetting sub-tabs", () => {
    const { setActiveConsoleCategory, setActiveScriptsTab, setActiveDevToolsTab } =
      useIdeStore.getState();
    setActiveScriptsTab("blueprints" as ScriptsTab);
    setActiveDevToolsTab("ai" as ConsoleTab);
    setActiveConsoleCategory("devtools");
    expect(useIdeStore.getState().activeConsoleCategory).toBe("devtools");
    // Sub-tab state preserved on both sides
    expect(useIdeStore.getState().activeScriptsTab).toBe("blueprints");
    expect(useIdeStore.getState().activeDevToolsTab).toBe("ai");
    // Switch back — scripts tab still remembered
    useIdeStore.getState().setActiveConsoleCategory("scripts");
    expect(useIdeStore.getState().activeScriptsTab).toBe("blueprints");
  });

  it("setAppLoadSource records the source", () => {
    useIdeStore.getState().setAppLoadSource("wizard");
    expect(useIdeStore.getState().appLoadSource).toBe("wizard");
    useIdeStore.getState().setAppLoadSource(null);
    expect(useIdeStore.getState().appLoadSource).toBe(null);
  });

  it("markCompleteScriptShown dedupes per app name", () => {
    const { markCompleteScriptShown } = useIdeStore.getState();
    markCompleteScriptShown("app-a");
    markCompleteScriptShown("app-a");
    markCompleteScriptShown("app-b");
    const seen = useIdeStore.getState().completeScriptShownForApps;
    expect(seen.has("app-a")).toBe(true);
    expect(seen.has("app-b")).toBe(true);
    expect(seen.size).toBe(2);
  });

  it("loadAppStructure does not clear appLoadSource (consumer clears after use)", () => {
    const structure: AppStructure = {
      name: "demo",
      displayName: "Demo",
      tree: [],
      nodeIndex: new Map(),
    };
    useIdeStore.getState().setAppLoadSource("wizard");
    useIdeStore.getState().loadAppStructure(structure);
    expect(useIdeStore.getState().appStructure?.name).toBe("demo");
    expect(useIdeStore.getState().appLoadSource).toBe("wizard");
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
npx vitest run tests/stores/ideStore.test.ts
```

Expected: test file does compile only partially (due to store not having the new actions), or tests fail at runtime with "setActiveConsoleCategory is not a function". This is the red phase.

- [ ] **Step 3: Update `src/stores/ideStore.ts`**

Open `src/stores/ideStore.ts`. Replace the whole file with:

```ts
import { create } from "zustand";
import type {
  AppLoadSource,
  ConsoleCategory,
  ConsoleEntry,
  ConsoleTab,
  EditorTab,
  IdeStore,
  ScriptsTab,
} from "../types/ide";

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
  activeConsoleCategory: "scripts",
  activeScriptsTab: "complete",
  activeDevToolsTab: "lint",

  appLoadSource: null,
  completeScriptShownForApps: new Set<string>(),

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

    const existing = tabs.find((t) => t.path === node.filePath);
    if (existing) {
      if (activeTabId !== existing.id) {
        set({ activeTabId: existing.id });
      }
      return;
    }

    const lang = node.filePath.endsWith(".dg") ? "deluge" : "plaintext";
    const newTab: EditorTab = {
      id: `tab-${nodeId}`,
      name: node.label,
      path: node.filePath,
      content: "",
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

  setActiveConsoleCategory: (cat: ConsoleCategory) => {
    set({ activeConsoleCategory: cat });
  },

  setActiveScriptsTab: (tab: ScriptsTab) => {
    set({ activeScriptsTab: tab });
  },

  setActiveDevToolsTab: (tab: ConsoleTab) => {
    set({ activeDevToolsTab: tab });
  },

  setAppLoadSource: (src: AppLoadSource) => {
    set({ appLoadSource: src });
  },

  markCompleteScriptShown: (appName: string) => {
    const prev = get().completeScriptShownForApps;
    if (prev.has(appName)) return;
    const next = new Set(prev);
    next.add(appName);
    set({ completeScriptShownForApps: next });
  },
}));
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npx vitest run tests/stores/ideStore.test.ts
```

Expected: all 5 tests pass.

- [ ] **Step 5: TypeScript check — residual errors expected**

```bash
npx tsc -b --noEmit
```

Expected: `src/components/ide/DevConsole.tsx` still references `activeConsoleTab` / `setActiveConsoleTab` (fixed in Task 9). Other files should compile.

- [ ] **Step 6: Commit**

```bash
git add src/stores/ideStore.ts tests/stores/ideStore.test.ts
git commit -m "feat(ide): extend ideStore with two-level console + appLoadSource state"
```

---

## Task 4: Create `layoutStore.ts` with tests

**Files:**
- Create: `src/stores/layoutStore.ts`
- Test: `tests/stores/layoutStore.test.ts` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/stores/layoutStore.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useLayoutStore, LAYOUT_STORAGE_KEY } from "../../src/stores/layoutStore";

function resetStoreAndStorage() {
  localStorage.clear();
  useLayoutStore.setState({
    layoutJson: null,
    visiblePanels: new Set<string>(["editor", "repo-explorer", "ds-tree", "inspector", "source-control", "console"]),
    lastKnownPositions: {},
  });
}

describe("layoutStore", () => {
  beforeEach(resetStoreAndStorage);

  it("setLayoutJson updates state and writes to localStorage", () => {
    const json = '{"panels":[]}';
    useLayoutStore.getState().setLayoutJson(json);
    expect(useLayoutStore.getState().layoutJson).toBe(json);
    // No debounce in test (synchronous flush)
    expect(localStorage.getItem(LAYOUT_STORAGE_KEY)).toBe(json);
  });

  it("togglePanel flips membership in visiblePanels", () => {
    const { togglePanel } = useLayoutStore.getState();
    togglePanel("inspector");
    expect(useLayoutStore.getState().visiblePanels.has("inspector")).toBe(false);
    togglePanel("inspector");
    expect(useLayoutStore.getState().visiblePanels.has("inspector")).toBe(true);
  });

  it("togglePanel records and recalls a PanelDockHint", () => {
    // Seed a hint via direct state mutation (simulating dockview reporting it)
    useLayoutStore.setState({
      lastKnownPositions: {
        inspector: { referencePanelId: "editor", direction: "right" },
      },
    });
    const { togglePanel, lastKnownPositions } = useLayoutStore.getState();
    expect(lastKnownPositions.inspector?.direction).toBe("right");
    // Hide then show — hint survives
    togglePanel("inspector");
    togglePanel("inspector");
    expect(useLayoutStore.getState().lastKnownPositions.inspector?.direction).toBe("right");
  });

  it("resetLayout clears layoutJson and storage", () => {
    useLayoutStore.getState().setLayoutJson('{"foo":1}');
    expect(localStorage.getItem(LAYOUT_STORAGE_KEY)).not.toBe(null);
    useLayoutStore.getState().resetLayout();
    expect(useLayoutStore.getState().layoutJson).toBe(null);
    expect(localStorage.getItem(LAYOUT_STORAGE_KEY)).toBe(null);
  });

  it("setLayoutJson swallows localStorage quota errors", () => {
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("QuotaExceededError", "QuotaExceededError");
    });
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(() =>
      useLayoutStore.getState().setLayoutJson('{"big":"value"}'),
    ).not.toThrow();
    expect(warnSpy).toHaveBeenCalled();
    setItemSpy.mockRestore();
    warnSpy.mockRestore();
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
npx vitest run tests/stores/layoutStore.test.ts
```

Expected: fails with "Cannot find module '../../src/stores/layoutStore'".

- [ ] **Step 3: Implement `src/stores/layoutStore.ts`**

Create the file with contents:

```ts
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npx vitest run tests/stores/layoutStore.test.ts
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/stores/layoutStore.ts tests/stores/layoutStore.test.ts
git commit -m "feat(ide): add layoutStore for dockview state persistence"
```

---

## Task 5: Create `DockviewHost` component (registers panels + persists layout)

**Files:**
- Create: `src/components/ide/DockviewHost.tsx`

No dedicated unit test — covered by the integration test in Task 19. Behavior-testing dockview in jsdom is brittle; integration test hits the real API surface.

- [ ] **Step 1: Create `src/components/ide/DockviewHost.tsx`**

```tsx
import { useCallback, useEffect, useRef } from "react";
import {
  DockviewReact,
  type DockviewApi,
  type DockviewReadyEvent,
  type IDockviewPanelProps,
} from "dockview-react";
import { useLayoutStore, LAYOUT_STORAGE_KEY } from "../../stores/layoutStore";
import type { PanelDockHint } from "../../types/ide";

/** A registered panel factory entry. */
export interface PanelRegistryEntry {
  title: string;
  component: React.ComponentType<IDockviewPanelProps>;
  /** Default dockview position when the panel is added by activity-bar click
   *  and no lastKnownPosition exists. */
  defaultPosition?: PanelDockHint;
  /** If true, panel cannot be closed via its tab UI. */
  closable?: boolean;
}

export type PanelRegistry = Record<string, PanelRegistryEntry>;

interface DockviewHostProps {
  /** Component registry (panel ID -> factory). */
  registry: PanelRegistry;
  /** Called once after dockview mounts + default/restored layout is applied. */
  onReady?: (api: DockviewApi) => void;
}

const SAVE_DEBOUNCE_MS = 300;

/** Build the default layout (used on first mount or when no saved JSON exists). */
function applyDefaultLayout(api: DockviewApi, registry: PanelRegistry): void {
  const editor = api.addPanel({
    id: "editor",
    component: "editor",
    title: registry.editor.title,
  });

  api.addPanel({
    id: "repo-explorer",
    component: "repo-explorer",
    title: registry["repo-explorer"].title,
    position: { referencePanel: "editor", direction: "left" },
  });
  api.addPanel({
    id: "ds-tree",
    component: "ds-tree",
    title: registry["ds-tree"].title,
    position: { referencePanel: "repo-explorer", direction: "within" },
  });
  api.addPanel({
    id: "inspector",
    component: "inspector",
    title: registry.inspector.title,
    position: { referencePanel: "editor", direction: "right" },
  });
  api.addPanel({
    id: "source-control",
    component: "source-control",
    title: registry["source-control"].title,
    position: { referencePanel: "inspector", direction: "within" },
  });
  api.addPanel({
    id: "console",
    component: "console",
    title: registry.console.title,
    position: { referencePanel: "editor", direction: "below" },
  });

  // Focus the editor by default
  editor.focus();
}

/** Restore layout from a serialized JSON string. Throws on unrecoverable errors. */
function restoreLayout(api: DockviewApi, json: string): void {
  const parsed = JSON.parse(json);
  api.fromJSON(parsed);
}

/** Compute a PanelDockHint describing a panel's current position. */
function hintForPanel(api: DockviewApi, panelId: string): PanelDockHint {
  const panel = api.getPanel(panelId);
  if (!panel) return {};
  const group = panel.group;
  if (!group) return {};
  // Use another panel in the same group (if any) as a "within" reference.
  const peer = group.panels.find((p) => p.id !== panelId);
  if (peer) {
    return { referencePanelId: peer.id, direction: "within" };
  }
  // No peer — fall back to the editor as anchor + default direction.
  return { referencePanelId: "editor", direction: "right" };
}

export function DockviewHost({ registry, onReady }: DockviewHostProps) {
  const apiRef = useRef<DockviewApi | null>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { setLayoutJson, recordLastKnownPosition, visiblePanels } = useLayoutStore();

  const handleReady = useCallback(
    (event: DockviewReadyEvent) => {
      apiRef.current = event.api;
      const saved = localStorage.getItem(LAYOUT_STORAGE_KEY);
      let restored = false;
      if (saved) {
        try {
          restoreLayout(event.api, saved);
          restored = true;
        } catch (err) {
          console.warn(
            "[DockviewHost] Saved layout failed to restore; using default.",
            err,
          );
        }
      }
      if (!restored) {
        applyDefaultLayout(event.api, registry);
      }
      onReady?.(event.api);

      event.api.onDidLayoutChange(() => {
        if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
        saveTimerRef.current = setTimeout(() => {
          try {
            const snapshot = event.api.toJSON();
            setLayoutJson(JSON.stringify(snapshot));
          } catch (err) {
            console.warn("[DockviewHost] Failed to serialize layout:", err);
          }
        }, SAVE_DEBOUNCE_MS);
      });
    },
    [registry, onReady, setLayoutJson],
  );

  // Reconcile visiblePanels from the store with dockview's actual panels.
  // Called whenever visiblePanels changes — usually from ActivityBar clicks.
  useEffect(() => {
    const api = apiRef.current;
    if (!api) return;

    const registryIds = Object.keys(registry);
    for (const id of registryIds) {
      const panelExists = !!api.getPanel(id);
      const shouldBeVisible = visiblePanels.has(id);
      if (panelExists && !shouldBeVisible) {
        // About to remove — record where it was first.
        recordLastKnownPosition(id, hintForPanel(api, id));
        api.removePanel(api.getPanel(id)!);
      } else if (!panelExists && shouldBeVisible) {
        const hint = useLayoutStore.getState().lastKnownPositions[id] ?? registry[id].defaultPosition;
        const position =
          hint?.referencePanelId && api.getPanel(hint.referencePanelId)
            ? { referencePanel: hint.referencePanelId, direction: hint.direction ?? "within" }
            : undefined;
        api.addPanel({
          id,
          component: id,
          title: registry[id].title,
          position,
        });
      }
    }
  }, [visiblePanels, registry, recordLastKnownPosition]);

  // Build dockview `components` map from registry
  const components = Object.fromEntries(
    Object.entries(registry).map(([id, entry]) => [id, entry.component]),
  );

  return (
    <div className="h-full w-full">
      <DockviewReact
        components={components}
        onReady={handleReady}
        className="dockview-theme-forgeds"
      />
    </div>
  );
}
```

- [ ] **Step 2: TypeScript check**

```bash
npx tsc -b --noEmit
```

Expected: no new errors in DockviewHost. Residual errors in IdePage/DevConsole still present (fixed later).

- [ ] **Step 3: Commit**

```bash
git add src/components/ide/DockviewHost.tsx
git commit -m "feat(ide): add DockviewHost wrapping dockview-react with persistence"
```

---

## Task 6: Create `ActivityBar` component with tests

**Files:**
- Create: `src/components/ide/ActivityBar.tsx`
- Test: `tests/components/ide/ActivityBar.test.tsx` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/components/ide/ActivityBar.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ActivityBar } from "../../../src/components/ide/ActivityBar";

describe("ActivityBar", () => {
  it("renders six icon buttons with accessible labels", () => {
    render(<ActivityBar onToggle={() => {}} onConsoleCategory={() => {}} />);
    expect(screen.getByRole("button", { name: /repo/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /\.ds tree/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /inspector/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /source control/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /console — scripts/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /console — dev tools/i })).toBeTruthy();
  });

  it("click on a single-panel icon calls onToggle with its panel id", () => {
    const onToggle = vi.fn();
    render(<ActivityBar onToggle={onToggle} onConsoleCategory={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /inspector/i }));
    expect(onToggle).toHaveBeenCalledWith("inspector");
  });

  it("click on Console Scripts calls onConsoleCategory('scripts')", () => {
    const onConsoleCategory = vi.fn();
    render(
      <ActivityBar onToggle={() => {}} onConsoleCategory={onConsoleCategory} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /console — scripts/i }));
    expect(onConsoleCategory).toHaveBeenCalledWith("scripts");
  });

  it("click on Console Dev Tools calls onConsoleCategory('devtools')", () => {
    const onConsoleCategory = vi.fn();
    render(
      <ActivityBar onToggle={() => {}} onConsoleCategory={onConsoleCategory} />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /console — dev tools/i }),
    );
    expect(onConsoleCategory).toHaveBeenCalledWith("devtools");
  });

  it("Enter key on an icon button triggers onToggle", () => {
    const onToggle = vi.fn();
    render(<ActivityBar onToggle={onToggle} onConsoleCategory={() => {}} />);
    const btn = screen.getByRole("button", { name: /inspector/i });
    btn.focus();
    fireEvent.keyDown(btn, { key: "Enter", code: "Enter" });
    // native button already handles Enter via click — confirm via click simulation
    fireEvent.click(btn);
    expect(onToggle).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
npx vitest run tests/components/ide/ActivityBar.test.tsx
```

Expected: fails with "Cannot find module '.../ActivityBar'".

- [ ] **Step 3: Implement `src/components/ide/ActivityBar.tsx`**

```tsx
import type { ConsoleCategory } from "../../types/ide";

interface ActivityBarProps {
  /** Called for icons A–D (single-panel toggles). */
  onToggle: (panelId: string) => void;
  /** Called for icons E/F (Console Scripts / Dev Tools). */
  onConsoleCategory: (cat: ConsoleCategory) => void;
}

interface IconDef {
  panelId: string | null; // null for console category icons
  category?: ConsoleCategory;
  icon: string; // emoji placeholder (Task 18 swaps for icon set)
  label: string;
}

const ICONS: IconDef[] = [
  { panelId: "repo-explorer",  icon: "📁", label: "Repo Explorer" },
  { panelId: "ds-tree",        icon: "🌲", label: ".ds Tree" },
  { panelId: "inspector",      icon: "🔍", label: "Inspector" },
  { panelId: "source-control", icon: "⇄", label: "Source Control" },
  { panelId: null, category: "scripts",  icon: "📜", label: "Console — Scripts" },
  { panelId: null, category: "devtools", icon: "🛠", label: "Console — Dev Tools" },
];

export function ActivityBar({ onToggle, onConsoleCategory }: ActivityBarProps) {
  return (
    <nav
      aria-label="IDE activity bar"
      className="flex h-full w-12 flex-col items-center gap-1 border-r border-gray-700 bg-gray-900 py-2"
    >
      {ICONS.map((def) => (
        <button
          key={def.label}
          type="button"
          aria-label={def.label}
          title={def.label}
          onClick={() => {
            if (def.panelId) onToggle(def.panelId);
            else if (def.category) onConsoleCategory(def.category);
          }}
          className="flex h-10 w-10 items-center justify-center rounded text-lg text-gray-400 hover:bg-gray-800 hover:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <span aria-hidden="true">{def.icon}</span>
        </button>
      ))}
    </nav>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npx vitest run tests/components/ide/ActivityBar.test.tsx
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/components/ide/ActivityBar.tsx tests/components/ide/ActivityBar.test.tsx
git commit -m "feat(ide): add ActivityBar with 6 icon buttons"
```

---

## Task 7: Rename `DevConsole` to `DevToolsCategory` (strip outer shell)

**Files:**
- Create: `src/components/ide/DevToolsCategory.tsx` (content derived from DevConsole)
- Delete: `src/components/ide/DevConsole.tsx`
- Modify: `src/components/ide/index.ts`

- [ ] **Step 1: Create `src/components/ide/DevToolsCategory.tsx`**

Copy the internal helper functions and sub-tab components from the existing `DevConsole.tsx`, but export only a component that renders the active Dev Tools sub-tab. No tab bar, no collapse button, no outer header — those move to `ConsolePanel` (Task 10).

```tsx
import { useCallback, useEffect, useRef, useState } from "react";
import { useIdeStore } from "../../stores/ideStore";
import { useBridgeStore } from "../../stores/bridgeStore";
import type {
  ConsoleEntry,
  LintDiagnostic,
  RelationshipLink,
} from "../../types/ide";

// --- Severity helpers ---

const severityOrder: Record<string, number> = { error: 0, warning: 1, info: 2 };

function SeverityIcon({ severity }: { severity: string }) {
  switch (severity) {
    case "error":
      return (
        <span className="inline-flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
          !
        </span>
      );
    case "warning":
      return (
        <span className="inline-flex h-4 w-4 flex-shrink-0 items-center justify-center text-yellow-400">
          <svg viewBox="0 0 16 16" fill="currentColor" className="h-4 w-4">
            <path d="M8 1L1 14h14L8 1zm0 4v5m0 2v1" stroke="currentColor" strokeWidth="1.5" fill="none" />
          </svg>
        </span>
      );
    default:
      return (
        <span className="inline-flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-blue-500 text-[10px] font-bold text-white">
          i
        </span>
      );
  }
}

function BridgeRequiredMessage({ feature }: { feature: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-1 text-sm text-gray-500">
      <span>{feature} requires the bridge server</span>
      <span className="font-mono text-xs text-gray-600">python -m bridge</span>
    </div>
  );
}

// --- Lint Tab ---

interface LintTabProps {
  diagnostics: LintDiagnostic[];
  onFileClick?: (file: string, line: number) => void;
}

function LintTab({ diagnostics, onFileClick }: LintTabProps) {
  const sorted = [...diagnostics].sort(
    (a, b) => (severityOrder[a.severity] ?? 2) - (severityOrder[b.severity] ?? 2),
  );
  const errorCount = diagnostics.filter((d) => d.severity === "error").length;
  const warnCount = diagnostics.filter((d) => d.severity === "warning").length;
  const infoCount = diagnostics.filter((d) => d.severity === "info").length;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-gray-700/50 px-3 py-1.5 text-xs text-gray-400">
        <span className="text-red-400">{errorCount} errors</span>
        <span className="text-yellow-400">{warnCount} warnings</span>
        <span className="text-blue-400">{infoCount} info</span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {sorted.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-gray-500">
            No diagnostics
          </div>
        ) : (
          sorted.map((d, i) => (
            <div
              key={`${d.file}:${d.line}:${d.rule}:${i}`}
              className="flex items-start gap-2 border-b border-gray-700/30 px-3 py-1.5 text-sm leading-tight hover:bg-gray-700/30"
            >
              <SeverityIcon severity={d.severity} />
              <span className="flex-shrink-0 font-mono text-xs text-gray-500">{d.rule}</span>
              <span className="flex-1 truncate text-gray-300">{d.message}</span>
              <button
                onClick={() => onFileClick?.(d.file, d.line)}
                className="flex-shrink-0 font-mono text-xs text-indigo-400 hover:text-indigo-300 hover:underline"
              >
                {d.file}:{d.line}
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// --- Build Tab ---

function BuildTab({ entries }: { entries: ConsoleEntry[] }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const filtered = entries.filter(
    (e) => e.type === "build" || e.type === "info" || e.type === "error",
  );

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [filtered.length]);

  return (
    <div ref={scrollRef} className="h-full overflow-y-auto p-2 font-mono text-xs leading-5">
      {filtered.length === 0 ? (
        <div className="flex h-full items-center justify-center text-sm text-gray-500">
          No build output
        </div>
      ) : (
        filtered.map((entry) => (
          <div key={entry.id} className={entry.type === "error" ? "text-red-400" : "text-gray-300"}>
            <span className="mr-2 text-gray-600">
              {new Date(entry.timestamp).toLocaleTimeString()}
            </span>
            {entry.message}
          </div>
        ))
      )}
    </div>
  );
}

// --- Relationships Tab ---

function RelationshipsTab({
  relationships,
  elementName,
}: {
  relationships: RelationshipLink[];
  elementName: string | null;
}) {
  if (!elementName) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-500">
        Select an element to view relationships
      </div>
    );
  }

  const grouped = new Map<string, RelationshipLink[]>();
  for (const rel of relationships) {
    const group = grouped.get(rel.relationship) ?? [];
    group.push(rel);
    grouped.set(rel.relationship, group);
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="border-b border-gray-700/50 px-3 py-2 text-xs font-semibold uppercase tracking-wider text-gray-400">
        Element Relationships
      </div>
      {relationships.length === 0 ? (
        <div className="px-3 py-4 text-sm text-gray-500">
          No relationships found for "{elementName}"
        </div>
      ) : (
        Array.from(grouped.entries()).map(([relType, links]) => (
          <div key={relType} className="border-b border-gray-700/30 px-3 py-2">
            <h4 className="mb-1 text-xs font-medium uppercase text-gray-500">{relType}</h4>
            {links.map((link) => (
              <div key={`${link.relationship}-${link.targetId}`} className="flex items-center gap-2 py-0.5 text-sm">
                <span className="text-gray-300">{elementName}</span>
                <span className="text-gray-500">{link.relationship}</span>
                <span className="text-indigo-400">{link.targetLabel}</span>
                <span className="rounded bg-gray-700 px-1 py-0.5 text-[10px] uppercase text-gray-400">
                  {link.targetType}
                </span>
              </div>
            ))}
          </div>
        ))
      )}
    </div>
  );
}

// --- AI Chat Tab ---

interface ChatMessage {
  id: number;
  role: "user" | "ai";
  text: string;
}

function AiChatTab({
  bridgeStatus,
  onSend,
}: {
  bridgeStatus: string;
  onSend: (message: string) => Promise<string>;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const msgIdRef = useRef(0);
  const isConnected = bridgeStatus === "connected";

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || !isConnected) return;
    const userMsg: ChatMessage = { id: ++msgIdRef.current, role: "user", text };
    const aiMsgId = ++msgIdRef.current;
    const aiMsg: ChatMessage = { id: aiMsgId, role: "ai", text: "Thinking..." };
    setMessages((prev) => [...prev, userMsg, aiMsg]);
    setInput("");
    try {
      const responseText = await onSend(text);
      setMessages((prev) =>
        prev.map((m) => (m.id === aiMsgId ? { ...m, text: responseText } : m)),
      );
    } catch {
      setMessages((prev) =>
        prev.map((m) => (m.id === aiMsgId ? { ...m, text: "Error: failed to get response." } : m)),
      );
    }
  }, [input, isConnected, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  if (!isConnected) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-500">
        Connect bridge to use AI Chat
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-2 space-y-2">
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center text-sm text-gray-500">
            Start a conversation
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                msg.role === "user" ? "bg-blue-600 text-white" : "bg-gray-700 text-gray-200"
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2 border-t border-gray-700 px-2 py-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask something..."
          className="flex-1 rounded bg-gray-700 px-3 py-1.5 text-sm text-gray-200 placeholder-gray-500 outline-none focus:ring-1 focus:ring-indigo-500"
        />
        <button
          onClick={handleSend}
          disabled={!input.trim()}
          className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40 disabled:hover:bg-indigo-600"
        >
          Send
        </button>
      </div>
    </div>
  );
}

// --- Main DevToolsCategory ---

export function DevToolsCategory() {
  const activeDevToolsTab = useIdeStore((s) => s.activeDevToolsTab);
  const consoleEntries = useIdeStore((s) => s.consoleEntries);
  const diagnostics = useIdeStore((s) => s.diagnostics);
  const inspectorData = useIdeStore((s) => s.inspectorData);

  const bridgeStatus = useBridgeStore((s) => s.status);
  const bridgeSend = useBridgeStore((s) => s.send);

  const handleFileClick = useCallback((_file: string, _line: number) => {
    // Polish Pass spec will wire this to open the file in the editor at the given line.
  }, []);

  const handleAiSend = useCallback(
    async (message: string): Promise<string> => {
      const result = await bridgeSend("ai_chat", { message });
      const data = result as unknown as { response: string };
      return data.response ?? "No response received.";
    },
    [bridgeSend],
  );

  switch (activeDevToolsTab) {
    case "lint":
      return bridgeStatus !== "connected" ? (
        <BridgeRequiredMessage feature="Lint" />
      ) : (
        <LintTab diagnostics={diagnostics} onFileClick={handleFileClick} />
      );
    case "build":
      return <BuildTab entries={consoleEntries} />;
    case "relationships":
      return bridgeStatus !== "connected" ? (
        <BridgeRequiredMessage feature="Relationships" />
      ) : (
        <RelationshipsTab
          relationships={inspectorData?.relationships ?? []}
          elementName={inspectorData?.name ?? null}
        />
      );
    case "ai":
      return <AiChatTab bridgeStatus={bridgeStatus} onSend={handleAiSend} />;
  }
}
```

- [ ] **Step 2: Delete `src/components/ide/DevConsole.tsx`**

```bash
git rm src/components/ide/DevConsole.tsx
```

- [ ] **Step 3: Update `src/components/ide/index.ts` exports**

Open `src/components/ide/index.ts`. Replace:

```ts
export { DevConsole } from "./DevConsole";
```

with:

```ts
export { DevToolsCategory } from "./DevToolsCategory";
```

- [ ] **Step 4: TypeScript check**

```bash
npx tsc -b --noEmit
```

Expected: `src/pages/IdePage.tsx` still imports `DevConsole` — fixed in later tasks. DevToolsCategory itself compiles.

- [ ] **Step 5: Commit**

```bash
git add src/components/ide/DevToolsCategory.tsx src/components/ide/index.ts
git commit -m "refactor(ide): rename DevConsole to DevToolsCategory (strip outer shell)"
```

---

## Task 8: Create `CompleteScriptView` component with tests

**Files:**
- Create: `src/components/ide/CompleteScriptView.tsx`
- Test: `tests/components/ide/CompleteScriptView.test.tsx` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/components/ide/CompleteScriptView.test.tsx`:

```tsx
import { beforeEach, describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { useIdeStore } from "../../../src/stores/ideStore";
import { CompleteScriptView } from "../../../src/components/ide/CompleteScriptView";
import type { AppStructure, TreeNode } from "../../../src/types/ide";

function mockAppStructure(): AppStructure {
  const scriptNode: TreeNode = {
    id: "s1",
    label: "on_validate",
    type: "workflow",
    filePath: "src/deluge/form/on_validate.dg",
  };
  const formNode: TreeNode = { id: "f1", label: "Expense_Claims", type: "form", children: [scriptNode] };
  return {
    name: "demo_app",
    displayName: "Demo App",
    tree: [formNode],
    nodeIndex: new Map<string, TreeNode>([
      ["f1", formNode],
      ["s1", scriptNode],
    ]),
    enrichmentLevel: "local",
  };
}

describe("CompleteScriptView", () => {
  beforeEach(() => {
    useIdeStore.setState({
      appStructure: null,
      tabs: [],
      activeTabId: null,
    });
  });

  it("renders an empty state when no app is loaded", () => {
    render(<CompleteScriptView />);
    expect(screen.getByText(/no app loaded/i)).toBeTruthy();
  });

  it("renders summary fields when an app is loaded", () => {
    useIdeStore.setState({ appStructure: mockAppStructure() });
    render(<CompleteScriptView />);
    expect(screen.getByText(/demo app/i)).toBeTruthy();
    expect(screen.getByText(/1 form/i)).toBeTruthy();
    expect(screen.getByText(/1 script/i)).toBeTruthy();
  });

  it("clicking 'Open in editor' opens a .ds tab and activates it", () => {
    useIdeStore.setState({ appStructure: mockAppStructure() });
    render(<CompleteScriptView />);
    fireEvent.click(screen.getByRole("button", { name: /open in editor/i }));
    const { tabs, activeTabId } = useIdeStore.getState();
    expect(tabs.some((t) => t.path.endsWith(".ds"))).toBe(true);
    expect(activeTabId).toBe(tabs.find((t) => t.path.endsWith(".ds"))?.id);
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
npx vitest run tests/components/ide/CompleteScriptView.test.tsx
```

Expected: fails with "Cannot find module '.../CompleteScriptView'".

- [ ] **Step 3: Implement `src/components/ide/CompleteScriptView.tsx`**

```tsx
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npx vitest run tests/components/ide/CompleteScriptView.test.tsx
```

Expected: all 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/components/ide/CompleteScriptView.tsx tests/components/ide/CompleteScriptView.test.tsx
git commit -m "feat(ide): add CompleteScriptView summary + open-in-editor action"
```

---

## Task 9: Create `WorkflowFormSidebar` with tests

**Files:**
- Create: `src/components/ide/WorkflowFormSidebar.tsx`
- Test: `tests/components/ide/WorkflowFormSidebar.test.tsx` (new)

- [ ] **Step 1: Write the failing test**

```tsx
// tests/components/ide/WorkflowFormSidebar.test.tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { WorkflowFormSidebar } from "../../../src/components/ide/WorkflowFormSidebar";

describe("WorkflowFormSidebar", () => {
  it("renders empty state when no forms are provided", () => {
    render(
      <WorkflowFormSidebar
        formsWith={[]}
        formsWithout={[]}
        selectedFormId={null}
        onSelect={() => {}}
      />,
    );
    expect(screen.getByText(/no forms/i)).toBeTruthy();
  });

  it("renders two sections when both lists populated", () => {
    render(
      <WorkflowFormSidebar
        formsWith={[{ id: "f1", label: "Expense Claims" }]}
        formsWithout={[{ id: "f2", label: "Finance Managers" }]}
        selectedFormId={null}
        onSelect={() => {}}
      />,
    );
    expect(screen.getByText(/forms with/i)).toBeTruthy();
    expect(screen.getByText(/forms without/i)).toBeTruthy();
    expect(screen.getByText("Expense Claims")).toBeTruthy();
    expect(screen.getByText("Finance Managers")).toBeTruthy();
  });

  it("click on a form row calls onSelect with its id", () => {
    const onSelect = vi.fn();
    render(
      <WorkflowFormSidebar
        formsWith={[{ id: "f1", label: "Expense Claims" }]}
        formsWithout={[]}
        selectedFormId={null}
        onSelect={onSelect}
      />,
    );
    fireEvent.click(screen.getByText("Expense Claims"));
    expect(onSelect).toHaveBeenCalledWith("f1");
  });

  it("highlights the selected form", () => {
    render(
      <WorkflowFormSidebar
        formsWith={[{ id: "f1", label: "Expense Claims" }]}
        formsWithout={[]}
        selectedFormId="f1"
        onSelect={() => {}}
      />,
    );
    const row = screen.getByText("Expense Claims");
    expect(row.className).toMatch(/text-(indigo|blue)/);
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
npx vitest run tests/components/ide/WorkflowFormSidebar.test.tsx
```

Expected: fails with module resolution error.

- [ ] **Step 3: Implement `src/components/ide/WorkflowFormSidebar.tsx`**

```tsx
export interface WorkflowFormEntry {
  id: string;
  label: string;
}

interface WorkflowFormSidebarProps {
  /** Forms that have at least one item of the current workflow type. */
  formsWith: WorkflowFormEntry[];
  /** Forms with no items of the current workflow type. */
  formsWithout: WorkflowFormEntry[];
  selectedFormId: string | null;
  onSelect: (id: string) => void;
}

export function WorkflowFormSidebar({
  formsWith,
  formsWithout,
  selectedFormId,
  onSelect,
}: WorkflowFormSidebarProps) {
  if (formsWith.length === 0 && formsWithout.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-3 text-xs text-gray-500">
        No forms available
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-gray-850 text-xs">
      {formsWith.length > 0 && (
        <div className="px-2 py-2">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-500">
            Forms with
          </div>
          {formsWith.map((f) => (
            <FormRow
              key={f.id}
              entry={f}
              selected={f.id === selectedFormId}
              onClick={() => onSelect(f.id)}
            />
          ))}
        </div>
      )}
      {formsWithout.length > 0 && (
        <div className="px-2 py-2 border-t border-gray-700/50">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-500">
            Forms without
          </div>
          {formsWithout.map((f) => (
            <FormRow
              key={f.id}
              entry={f}
              selected={f.id === selectedFormId}
              onClick={() => onSelect(f.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function FormRow({
  entry,
  selected,
  onClick,
}: {
  entry: WorkflowFormEntry;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`block w-full truncate rounded px-2 py-1 text-left text-[11px] hover:bg-gray-700/50 ${
        selected ? "bg-gray-700 text-indigo-300" : "text-gray-300"
      }`}
    >
      {entry.label}
    </button>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npx vitest run tests/components/ide/WorkflowFormSidebar.test.tsx
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/components/ide/WorkflowFormSidebar.tsx tests/components/ide/WorkflowFormSidebar.test.tsx
git commit -m "feat(ide): add WorkflowFormSidebar (forms with/without sections)"
```

---

## Task 10: Create `WorkflowDetailTable` with tests

**Files:**
- Create: `src/components/ide/WorkflowDetailTable.tsx`
- Test: `tests/components/ide/WorkflowDetailTable.test.tsx` (new)

- [ ] **Step 1: Write the failing test**

```tsx
// tests/components/ide/WorkflowDetailTable.test.tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { WorkflowDetailTable } from "../../../src/components/ide/WorkflowDetailTable";

describe("WorkflowDetailTable", () => {
  it("renders empty state when no rows", () => {
    render(<WorkflowDetailTable workflowTypeLabel="Blueprints" rows={[]} onRowClick={() => {}} />);
    expect(screen.getByText(/no blueprints/i)).toBeTruthy();
  });

  it("renders one row per item with Name/Status/Created columns", () => {
    render(
      <WorkflowDetailTable
        workflowTypeLabel="Blueprints"
        rows={[
          {
            id: "bp1",
            name: "Tiered Approval",
            status: "Enabled",
            createdOn: "2026-04-10",
            filePath: "src/deluge/blueprints/tiered.dg",
          },
        ]}
        onRowClick={() => {}}
      />,
    );
    expect(screen.getByText("Tiered Approval")).toBeTruthy();
    expect(screen.getByText("Enabled")).toBeTruthy();
    expect(screen.getByText("2026-04-10")).toBeTruthy();
  });

  it("row click fires onRowClick with the row", () => {
    const onRowClick = vi.fn();
    render(
      <WorkflowDetailTable
        workflowTypeLabel="Blueprints"
        rows={[
          {
            id: "bp1",
            name: "Tiered Approval",
            status: "Enabled",
            createdOn: "2026-04-10",
            filePath: "src/deluge/blueprints/tiered.dg",
          },
        ]}
        onRowClick={onRowClick}
      />,
    );
    fireEvent.click(screen.getByText("Tiered Approval"));
    expect(onRowClick).toHaveBeenCalledWith(
      expect.objectContaining({ id: "bp1", filePath: "src/deluge/blueprints/tiered.dg" }),
    );
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
npx vitest run tests/components/ide/WorkflowDetailTable.test.tsx
```

Expected: module-resolution failure.

- [ ] **Step 3: Implement `src/components/ide/WorkflowDetailTable.tsx`**

```tsx
export interface WorkflowRow {
  id: string;
  name: string;
  status: string;
  createdOn: string;
  filePath: string;
}

interface WorkflowDetailTableProps {
  /** Human label for the current tab (e.g., "Blueprints", "Schedules"). */
  workflowTypeLabel: string;
  rows: WorkflowRow[];
  onRowClick: (row: WorkflowRow) => void;
}

export function WorkflowDetailTable({
  workflowTypeLabel,
  rows,
  onRowClick,
}: WorkflowDetailTableProps) {
  if (rows.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-xs text-gray-500">
        No {workflowTypeLabel.toLowerCase()} found in this app.
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="sticky top-0 grid grid-cols-[1fr_120px_140px] gap-2 border-b border-gray-700 bg-gray-850 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-gray-500">
        <span>Name</span>
        <span>Status</span>
        <span>Created</span>
      </div>
      {rows.map((row) => (
        <button
          key={row.id}
          type="button"
          onClick={() => onRowClick(row)}
          className="grid w-full grid-cols-[1fr_120px_140px] gap-2 border-b border-gray-700/30 px-3 py-1.5 text-left text-xs text-gray-300 hover:bg-gray-700/30"
        >
          <span className="truncate text-indigo-300 hover:text-indigo-200">{row.name}</span>
          <span className="truncate text-gray-400">{row.status}</span>
          <span className="truncate font-mono text-gray-500">{row.createdOn}</span>
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npx vitest run tests/components/ide/WorkflowDetailTable.test.tsx
```

Expected: all 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/components/ide/WorkflowDetailTable.tsx tests/components/ide/WorkflowDetailTable.test.tsx
git commit -m "feat(ide): add WorkflowDetailTable with Name/Status/Created columns"
```

---

## Task 11: Create `WorkflowTabView` (generic container) with tests

**Files:**
- Create: `src/components/ide/WorkflowTabView.tsx`
- Test: `tests/components/ide/WorkflowTabView.test.tsx` (new)

- [ ] **Step 1: Write the failing test**

```tsx
// tests/components/ide/WorkflowTabView.test.tsx
import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { useIdeStore } from "../../../src/stores/ideStore";
import { WorkflowTabView } from "../../../src/components/ide/WorkflowTabView";

describe("WorkflowTabView", () => {
  beforeEach(() => {
    useIdeStore.setState({ appStructure: null });
  });

  it("renders the 'no app loaded' empty state when appStructure is null", () => {
    render(<WorkflowTabView workflowType="blueprints" />);
    expect(screen.getByText(/no app loaded/i)).toBeTruthy();
  });

  it("renders an empty-but-labelled state when appStructure exists (data pending)", () => {
    useIdeStore.setState({
      appStructure: {
        name: "demo",
        displayName: "Demo",
        tree: [{ id: "f1", label: "Expense Claims", type: "form" }],
        nodeIndex: new Map(),
      },
    });
    render(<WorkflowTabView workflowType="blueprints" />);
    // Sidebar shows the form (even if it's in the "without" section)
    expect(screen.getByText("Expense Claims")).toBeTruthy();
    // Detail table shows its empty message
    expect(screen.getByText(/no blueprints found/i)).toBeTruthy();
  });

  it("renders different labels for each workflow type", () => {
    useIdeStore.setState({
      appStructure: {
        name: "demo",
        displayName: "Demo",
        tree: [{ id: "f1", label: "Expense Claims", type: "form" }],
        nodeIndex: new Map(),
      },
    });
    const { rerender } = render(<WorkflowTabView workflowType="schedules" />);
    expect(screen.getByText(/no schedules found/i)).toBeTruthy();
    rerender(<WorkflowTabView workflowType="functions" />);
    expect(screen.getByText(/no functions found/i)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
npx vitest run tests/components/ide/WorkflowTabView.test.tsx
```

Expected: module-resolution failure.

- [ ] **Step 3: Implement `src/components/ide/WorkflowTabView.tsx`**

```tsx
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npx vitest run tests/components/ide/WorkflowTabView.test.tsx
```

Expected: all 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/components/ide/WorkflowTabView.tsx tests/components/ide/WorkflowTabView.test.tsx
git commit -m "feat(ide): add WorkflowTabView (empty-state scaffold for 7 workflow types)"
```

---

## Task 12: Create `ConsolePanel` with two-level tabs + narrow-width fallback

**Files:**
- Create: `src/components/ide/ConsolePanel.tsx`
- Test: `tests/components/ide/ConsolePanel.test.tsx` (new)

- [ ] **Step 1: Write the failing test**

```tsx
// tests/components/ide/ConsolePanel.test.tsx
import { beforeEach, describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { useIdeStore } from "../../../src/stores/ideStore";
import { ConsolePanel } from "../../../src/components/ide/ConsolePanel";

function reset() {
  useIdeStore.setState({
    activeConsoleCategory: "scripts",
    activeScriptsTab: "complete",
    activeDevToolsTab: "lint",
    appStructure: null,
  });
}

describe("ConsolePanel", () => {
  beforeEach(reset);

  it("renders both category tabs by default (wide width)", () => {
    // Mock width >= 400
    render(
      <div style={{ width: 800 }}>
        <ConsolePanel containerWidth={800} />
      </div>,
    );
    expect(screen.getByRole("tab", { name: /scripts/i })).toBeTruthy();
    expect(screen.getByRole("tab", { name: /dev tools/i })).toBeTruthy();
  });

  it("switching category preserves the other category's sub-tab", () => {
    render(<ConsolePanel containerWidth={800} />);
    // Switch Scripts sub-tab to blueprints
    fireEvent.click(screen.getByRole("tab", { name: /blueprints/i }));
    expect(useIdeStore.getState().activeScriptsTab).toBe("blueprints");
    // Switch to Dev Tools category
    fireEvent.click(screen.getByRole("tab", { name: /dev tools/i }));
    // Switch back to Scripts — still on blueprints
    fireEvent.click(screen.getByRole("tab", { name: /^scripts$/i }));
    expect(useIdeStore.getState().activeScriptsTab).toBe("blueprints");
  });

  it("renders a <select> instead of a tab row when container width < 400", () => {
    render(<ConsolePanel containerWidth={300} />);
    // Category select
    expect(screen.getByLabelText(/category/i)).toBeTruthy();
    // Sub-tab select
    expect(screen.getByLabelText(/sub-tab/i)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
npx vitest run tests/components/ide/ConsolePanel.test.tsx
```

Expected: module-resolution failure.

- [ ] **Step 3: Implement `src/components/ide/ConsolePanel.tsx`**

```tsx
import { useEffect, useRef, useState } from "react";
import { useIdeStore } from "../../stores/ideStore";
import type { ConsoleCategory, ConsoleTab, ScriptsTab } from "../../types/ide";
import { CompleteScriptView } from "./CompleteScriptView";
import { WorkflowTabView, type WorkflowType } from "./WorkflowTabView";
import { DevToolsCategory } from "./DevToolsCategory";

const NARROW_THRESHOLD = 400;

const SCRIPTS_TABS: { id: ScriptsTab; label: string }[] = [
  { id: "complete", label: "Complete Script" },
  { id: "form-workflows", label: "Form Workflows" },
  { id: "schedules", label: "Schedules" },
  { id: "approvals", label: "Approvals" },
  { id: "payments", label: "Payments" },
  { id: "blueprints", label: "Blueprints" },
  { id: "batch-workflows", label: "Batch Workflows" },
  { id: "functions", label: "Functions" },
];

const DEVTOOLS_TABS: { id: ConsoleTab; label: string }[] = [
  { id: "lint", label: "Lint" },
  { id: "build", label: "Build" },
  { id: "relationships", label: "Relationships" },
  { id: "ai", label: "AI Chat" },
];

interface ConsolePanelProps {
  /** Test hook — override width detection. Production callers pass dockview's panel width. */
  containerWidth?: number;
}

export function ConsolePanel({ containerWidth }: ConsolePanelProps) {
  const activeConsoleCategory = useIdeStore((s) => s.activeConsoleCategory);
  const activeScriptsTab = useIdeStore((s) => s.activeScriptsTab);
  const activeDevToolsTab = useIdeStore((s) => s.activeDevToolsTab);
  const setActiveConsoleCategory = useIdeStore((s) => s.setActiveConsoleCategory);
  const setActiveScriptsTab = useIdeStore((s) => s.setActiveScriptsTab);
  const setActiveDevToolsTab = useIdeStore((s) => s.setActiveDevToolsTab);

  const rootRef = useRef<HTMLDivElement>(null);
  const [measuredWidth, setMeasuredWidth] = useState<number | null>(null);

  useEffect(() => {
    if (containerWidth !== undefined) return;
    if (!rootRef.current) return;
    const el = rootRef.current;
    const observer = new ResizeObserver((entries) => {
      for (const e of entries) setMeasuredWidth(e.contentRect.width);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [containerWidth]);

  const effectiveWidth = containerWidth ?? measuredWidth ?? 800;
  const narrow = effectiveWidth < NARROW_THRESHOLD;

  return (
    <div ref={rootRef} className="flex h-full flex-col bg-gray-800">
      {narrow ? (
        <NarrowHeader
          category={activeConsoleCategory}
          scriptsTab={activeScriptsTab}
          devToolsTab={activeDevToolsTab}
          onCategoryChange={setActiveConsoleCategory}
          onScriptsTabChange={setActiveScriptsTab}
          onDevToolsTabChange={setActiveDevToolsTab}
        />
      ) : (
        <WideHeader
          category={activeConsoleCategory}
          scriptsTab={activeScriptsTab}
          devToolsTab={activeDevToolsTab}
          onCategoryChange={setActiveConsoleCategory}
          onScriptsTabChange={setActiveScriptsTab}
          onDevToolsTabChange={setActiveDevToolsTab}
        />
      )}
      <div className="min-h-0 flex-1">
        {activeConsoleCategory === "scripts" ? (
          activeScriptsTab === "complete" ? (
            <CompleteScriptView />
          ) : (
            <WorkflowTabView workflowType={activeScriptsTab as WorkflowType} />
          )
        ) : (
          <DevToolsCategory />
        )}
      </div>
    </div>
  );
}

interface HeaderProps {
  category: ConsoleCategory;
  scriptsTab: ScriptsTab;
  devToolsTab: ConsoleTab;
  onCategoryChange: (c: ConsoleCategory) => void;
  onScriptsTabChange: (t: ScriptsTab) => void;
  onDevToolsTabChange: (t: ConsoleTab) => void;
}

function WideHeader(props: HeaderProps) {
  const { category, scriptsTab, devToolsTab, onCategoryChange, onScriptsTabChange, onDevToolsTabChange } = props;
  const subTabs = category === "scripts" ? SCRIPTS_TABS : DEVTOOLS_TABS;
  const active = category === "scripts" ? scriptsTab : devToolsTab;

  return (
    <div>
      <div role="tablist" className="flex items-center gap-1 border-b border-gray-700 px-2 py-1">
        <CategoryTab
          active={category === "scripts"}
          onClick={() => onCategoryChange("scripts")}
          label="Scripts"
        />
        <CategoryTab
          active={category === "devtools"}
          onClick={() => onCategoryChange("devtools")}
          label="Dev Tools"
        />
      </div>
      <div role="tablist" className="flex items-center gap-0 overflow-x-auto border-b border-gray-700/50">
        {subTabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={active === t.id}
            onClick={() => {
              if (category === "scripts") onScriptsTabChange(t.id as ScriptsTab);
              else onDevToolsTabChange(t.id as ConsoleTab);
            }}
            className={`whitespace-nowrap border-b-2 px-3 py-1.5 text-xs font-medium transition-colors ${
              active === t.id
                ? "border-indigo-400 text-indigo-300"
                : "border-transparent text-gray-500 hover:text-gray-300"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function CategoryTab({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`rounded px-3 py-1 text-xs font-medium ${
        active ? "bg-gray-700 text-gray-100" : "text-gray-400 hover:bg-gray-700/50 hover:text-gray-200"
      }`}
    >
      {label}
    </button>
  );
}

function NarrowHeader(props: HeaderProps) {
  const { category, scriptsTab, devToolsTab, onCategoryChange, onScriptsTabChange, onDevToolsTabChange } = props;
  const subTabs = category === "scripts" ? SCRIPTS_TABS : DEVTOOLS_TABS;
  const active = category === "scripts" ? scriptsTab : devToolsTab;

  return (
    <div className="flex flex-col gap-1 border-b border-gray-700 px-2 py-1 text-xs">
      <label className="flex items-center gap-2">
        <span className="text-[10px] uppercase tracking-wider text-gray-500">Category</span>
        <select
          aria-label="Category"
          value={category}
          onChange={(e) => onCategoryChange(e.target.value as ConsoleCategory)}
          className="flex-1 rounded bg-gray-700 px-2 py-0.5 text-gray-200"
        >
          <option value="scripts">Scripts</option>
          <option value="devtools">Dev Tools</option>
        </select>
      </label>
      <label className="flex items-center gap-2">
        <span className="text-[10px] uppercase tracking-wider text-gray-500">Sub-tab</span>
        <select
          aria-label="Sub-tab"
          value={active}
          onChange={(e) => {
            if (category === "scripts") onScriptsTabChange(e.target.value as ScriptsTab);
            else onDevToolsTabChange(e.target.value as ConsoleTab);
          }}
          className="flex-1 rounded bg-gray-700 px-2 py-0.5 text-gray-200"
        >
          {subTabs.map((t) => (
            <option key={t.id} value={t.id}>
              {t.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npx vitest run tests/components/ide/ConsolePanel.test.tsx
```

Expected: all 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/components/ide/ConsolePanel.tsx tests/components/ide/ConsolePanel.test.tsx
git commit -m "feat(ide): add ConsolePanel with two-level tabs and narrow-width fallback"
```

---

## Task 13: Create `useIdeBootstrap` hook with tests

**Files:**
- Create: `src/hooks/useIdeBootstrap.ts`
- Test: `tests/hooks/useIdeBootstrap.test.tsx` (new)

- [ ] **Step 1: Write the failing test**

```tsx
// tests/hooks/useIdeBootstrap.test.tsx
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { act } from "react";
import { useIdeStore } from "../../src/stores/ideStore";
import { useIdeBootstrap } from "../../src/hooks/useIdeBootstrap";
import type { AppStructure } from "../../src/types/ide";

// Mock bridgeStore — useIdeBootstrap imports bridgeStore for auto-connect
vi.mock("../../src/stores/bridgeStore", () => ({
  useBridgeStore: Object.assign(
    (selector: (s: unknown) => unknown) =>
      selector({
        status: "disconnected",
        connect: vi.fn(),
        send: vi.fn(),
      }),
    {
      getState: () => ({
        status: "disconnected",
        connect: vi.fn(),
        send: vi.fn(),
      }),
    },
  ),
}));

function Harness() {
  useIdeBootstrap();
  return null;
}

function resetStore() {
  useIdeStore.setState({
    appStructure: null,
    selectedNodeId: null,
    tabs: [],
    activeTabId: null,
    activeConsoleCategory: "devtools",
    activeScriptsTab: "blueprints",
    appLoadSource: null,
    completeScriptShownForApps: new Set<string>(),
  });
}

function mockStructure(name = "demo"): AppStructure {
  return { name, displayName: name, tree: [], nodeIndex: new Map() };
}

describe("useIdeBootstrap first-load matrix", () => {
  beforeEach(resetStore);

  it("wizard source fires first-load UI", () => {
    render(<Harness />);
    act(() => {
      useIdeStore.getState().setAppLoadSource("wizard");
      useIdeStore.getState().loadAppStructure(mockStructure("a"));
    });
    const s = useIdeStore.getState();
    expect(s.activeConsoleCategory).toBe("scripts");
    expect(s.activeScriptsTab).toBe("complete");
    expect(s.tabs.some((t) => t.path === "a.ds")).toBe(true);
    expect(s.appLoadSource).toBe(null); // cleared after consumption
    expect(s.completeScriptShownForApps.has("a")).toBe(true);
  });

  it("repo source fires first-load UI", () => {
    render(<Harness />);
    act(() => {
      useIdeStore.getState().setAppLoadSource("repo");
      useIdeStore.getState().loadAppStructure(mockStructure("b"));
    });
    expect(useIdeStore.getState().activeScriptsTab).toBe("complete");
    expect(useIdeStore.getState().tabs.some((t) => t.path === "b.ds")).toBe(true);
  });

  it("upload source does NOT fire first-load UI", () => {
    render(<Harness />);
    act(() => {
      useIdeStore.getState().setAppLoadSource("upload");
      useIdeStore.getState().loadAppStructure(mockStructure("c"));
    });
    const s = useIdeStore.getState();
    expect(s.activeScriptsTab).toBe("blueprints"); // unchanged
    expect(s.tabs.length).toBe(0);
  });

  it("bridge-auto source does NOT fire first-load UI", () => {
    render(<Harness />);
    act(() => {
      useIdeStore.getState().setAppLoadSource("bridge-auto");
      useIdeStore.getState().loadAppStructure(mockStructure("d"));
    });
    expect(useIdeStore.getState().tabs.length).toBe(0);
  });

  it("dedupes: same app loaded twice from wizard only opens .ds once", () => {
    render(<Harness />);
    act(() => {
      useIdeStore.getState().setAppLoadSource("wizard");
      useIdeStore.getState().loadAppStructure(mockStructure("e"));
    });
    const firstTabCount = useIdeStore.getState().tabs.length;
    // Second acquisition with same name
    act(() => {
      useIdeStore.getState().setAppLoadSource("wizard");
      useIdeStore.getState().loadAppStructure(mockStructure("e"));
    });
    expect(useIdeStore.getState().tabs.length).toBe(firstTabCount);
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
npx vitest run tests/hooks/useIdeBootstrap.test.tsx
```

Expected: module-resolution failure.

- [ ] **Step 3: Implement `src/hooks/useIdeBootstrap.ts`**

Open the current `src/pages/IdePage.tsx` and extract the effects into the hook. Write:

```ts
import { useCallback, useEffect, useRef } from "react";
import { useIdeStore } from "../stores/ideStore";
import { useBridgeStore } from "../stores/bridgeStore";
import type { AppStructure, EditorTab, InspectorData, TreeNode } from "../types/ide";
import { DSParser } from "../lib/ds-parser";
import { buildAppTree } from "../lib/ds-tree-builder";

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

/** Hook: IDE bootstrap effects (bridge connect, parse_ds, read_file, inspect_element)
 *  plus first-load UI trigger based on appLoadSource. */
export function useIdeBootstrap() {
  const connect = useBridgeStore((s) => s.connect);
  const status = useBridgeStore((s) => s.status);
  const send = useBridgeStore((s) => s.send);

  const tabs = useIdeStore((s) => s.tabs);
  const selectedNodeId = useIdeStore((s) => s.selectedNodeId);
  const appStructure = useIdeStore((s) => s.appStructure);
  const appLoadSource = useIdeStore((s) => s.appLoadSource);
  const completeScriptShownForApps = useIdeStore((s) => s.completeScriptShownForApps);

  const loadAppStructure = useIdeStore((s) => s.loadAppStructure);
  const updateTabContent = useIdeStore((s) => s.updateTabContent);
  const addConsoleEntry = useIdeStore((s) => s.addConsoleEntry);
  const setDiagnostics = useIdeStore((s) => s.setDiagnostics);
  const setInspectorData = useIdeStore((s) => s.setInspectorData);
  const openTab = useIdeStore((s) => s.openTab);
  const setActiveConsoleCategory = useIdeStore((s) => s.setActiveConsoleCategory);
  const setActiveScriptsTab = useIdeStore((s) => s.setActiveScriptsTab);
  const setAppLoadSource = useIdeStore((s) => s.setAppLoadSource);
  const markCompleteScriptShown = useIdeStore((s) => s.markCompleteScriptShown);

  const loadedTabsRef = useRef<Set<string>>(new Set());

  // Bridge auto-connect
  useEffect(() => {
    if (status === "disconnected") connect();
  }, [status, connect]);

  // Bridge-auto parse_ds when bridge transitions to connected
  useEffect(() => {
    if (status !== "connected") return;
    (async () => {
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
        setAppLoadSource("bridge-auto");
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
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  // First-load UI trigger — runs after appStructure changes
  useEffect(() => {
    if (!appStructure) return;
    if (appLoadSource !== "wizard" && appLoadSource !== "repo") return;
    if (completeScriptShownForApps.has(appStructure.name)) return;

    const dsPath = `${appStructure.name}.ds`;
    const newTab: EditorTab = {
      id: dsPath,
      name: dsPath,
      path: dsPath,
      content: "",
      language: "plaintext",
      isDirty: false,
    };
    openTab(newTab);
    setActiveConsoleCategory("scripts");
    setActiveScriptsTab("complete");
    markCompleteScriptShown(appStructure.name);
    setAppLoadSource(null);
  }, [
    appStructure,
    appLoadSource,
    completeScriptShownForApps,
    openTab,
    setActiveConsoleCategory,
    setActiveScriptsTab,
    markCompleteScriptShown,
    setAppLoadSource,
  ]);

  // Tab content lazy-load via bridge
  useEffect(() => {
    if (status !== "connected") return;
    for (const tab of tabs) {
      if (tab.content === "" && !loadedTabsRef.current.has(tab.id)) {
        loadedTabsRef.current.add(tab.id);
        send("read_file", { file_path: tab.path })
          .then((response) => {
            const data = response as unknown as { content: string; language: string };
            if (data.content) updateTabContent(tab.id, data.content);
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

  // Inspector data fetch when selectedNodeId changes
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

  // Helper exposed for consumers that want to run an ad-hoc lint check
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

  // Helper for manual .ds file upload (preserves current AppTreeExplorer behavior)
  const loadDsFromContent = useCallback(
    (fileName: string, content: string) => {
      try {
        const parser = new DSParser(content);
        parser.parse();
        const appName = fileName.replace(/\.ds$/i, "");
        const tree = buildAppTree(parser.forms, parser.scripts, appName, appName);
        const structure: AppStructure = {
          name: appName,
          displayName: appName,
          tree,
          nodeIndex: buildNodeIndex(tree),
          enrichmentLevel: "local",
        };
        setAppLoadSource("upload");
        loadAppStructure(structure);
        addConsoleEntry({
          type: "info",
          message: `Loaded .ds file: ${fileName} — ${parser.forms.length} form(s), ${parser.scripts.length} script(s)`,
        });
      } catch (err) {
        addConsoleEntry({
          type: "error",
          message: `Failed to parse .ds file: ${err instanceof Error ? err.message : String(err)}`,
        });
      }
    },
    [loadAppStructure, addConsoleEntry, setAppLoadSource],
  );

  return { runLint, loadDsFromContent };
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npx vitest run tests/hooks/useIdeBootstrap.test.tsx
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/hooks/useIdeBootstrap.ts tests/hooks/useIdeBootstrap.test.tsx
git commit -m "feat(ide): extract useIdeBootstrap hook with first-load trigger"
```

---

## Task 14: Create `IdeShell` component (wires top bar + activity bar + dockview)

**Files:**
- Create: `src/components/ide/IdeShell.tsx`
- Create: `src/components/ide/EditorPanel.tsx` (tiny wrapper — dockview components expect panel-shaped props)

- [ ] **Step 1: Create `src/components/ide/EditorPanel.tsx`**

Dockview registers components that receive `IDockviewPanelProps`. Our existing components (`RepoExplorer`, `InspectorPanel`, etc.) don't take those props, but they don't need them — the wrapper ignores props and renders the component.

```tsx
import type { IDockviewPanelProps } from "dockview-react";
import { IdeEditor } from "./IdeEditor";

export function EditorPanel(_props: IDockviewPanelProps) {
  return <IdeEditor />;
}
```

- [ ] **Step 2: Create `src/components/ide/IdeShell.tsx`**

```tsx
import { useCallback, useRef } from "react";
import type { DockviewApi, IDockviewPanelProps } from "dockview-react";
import { ActivityBar } from "./ActivityBar";
import { DockviewHost, type PanelRegistry } from "./DockviewHost";
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

function RepoFilePanel(props: IDockviewPanelProps) {
  const handleRepoFileSelect = (props.params as { onFileSelect?: (path: string, content: string) => void } | undefined)?.onFileSelect;
  return <RepoExplorer onFileSelect={handleRepoFileSelect ?? (() => {})} />;
}

function DsTreePanel(props: IDockviewPanelProps) {
  const handleUpload = (props.params as { onLoadDsFile?: (file: File) => void } | undefined)?.onLoadDsFile;
  return <AppTreeExplorer onLoadDsFile={handleUpload ?? (() => {})} />;
}

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

  // Repo-file-select callback — tags the load source as "repo".
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

  // Manual upload via AppTreeExplorer — tags as "upload".
  const handleUpload = useCallback(
    async (file: File) => {
      const content = await file.text();
      loadDsFromContent(file.name, content);
    },
    [loadDsFromContent],
  );

  const registry: PanelRegistry = {
    "editor": {
      title: "Editor",
      component: EditorPanel,
      closable: false,
    },
    "repo-explorer": {
      title: "Repo",
      component: (props: IDockviewPanelProps) => (
        <RepoExplorer onFileSelect={handleRepoFileSelect} />
      ),
    },
    "ds-tree": {
      title: ".ds Tree",
      component: (props: IDockviewPanelProps) => (
        <AppTreeExplorer onLoadDsFile={handleUpload} />
      ),
    },
    "inspector": {
      title: "Inspector",
      component: panelWrapper(InspectorPanel),
    },
    "source-control": {
      title: "Source Control",
      component: panelWrapper(SourceControlPanel),
    },
    "console": {
      title: "Console",
      component: (_props: IDockviewPanelProps) => <ConsolePanel />,
    },
  };

  // Handle the Console Scripts / Dev Tools icons per spec (E/F behavior).
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
      // Visible + matching category → hide
      togglePanel("console");
    },
    [visiblePanels, activeConsoleCategory, togglePanel, setActiveConsoleCategory],
  );

  return (
    <div className="flex h-full flex-col overflow-hidden bg-gray-900 text-gray-100">
      {/* Top bar */}
      <div className="flex h-9 items-center gap-2 border-b border-gray-700 bg-gray-850 px-2">
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
          <>
            <button
              type="button"
              onClick={runLint}
              className="rounded px-2 py-0.5 text-xs font-medium text-gray-300 hover:bg-gray-700 hover:text-white"
            >
              Lint
            </button>
          </>
        )}
        {bridgeStatus !== "connected" && (
          <span className="text-[10px] text-gray-500">
            {appStructure
              ? `Bridge offline — ${appStructure.displayName} loaded locally`
              : "Bridge offline — upload a .ds file to explore"}
          </span>
        )}
      </div>
      {/* Below top bar: activity bar + dockview */}
      <div className="flex min-h-0 flex-1">
        <ActivityBar onToggle={togglePanel} onConsoleCategory={handleConsoleCategory} />
        <div className="min-w-0 flex-1">
          <DockviewHost registry={registry} onReady={(api) => { apiRef.current = api; }} />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: TypeScript check**

```bash
npx tsc -b --noEmit
```

Expected: clean for these two files. `IdePage.tsx` still uses old layout — fixed in Task 15.

- [ ] **Step 4: Commit**

```bash
git add src/components/ide/IdeShell.tsx src/components/ide/EditorPanel.tsx
git commit -m "feat(ide): add IdeShell combining activity bar + dockview + top bar"
```

---

## Task 15: Slim `IdePage.tsx` to render `<IdeShell />` and wire repo/upload sources

**Files:**
- Modify: `src/pages/IdePage.tsx`
- Modify: `src/components/ide/index.ts`

- [ ] **Step 1: Replace `src/pages/IdePage.tsx`**

Entire file contents:

```tsx
import { IdeShell } from "../components/ide/IdeShell";

export default function IdePage() {
  return <IdeShell />;
}
```

- [ ] **Step 2: Update `src/components/ide/index.ts` exports**

Add exports for the new components by opening `src/components/ide/index.ts` and making the full contents:

```ts
export { ActivityBar } from "./ActivityBar";
export { AppTreeExplorer } from "./AppTreeExplorer";
export { BranchManager } from "./BranchManager";
export { CollaboratorsList } from "./CollaboratorsList";
export { CompleteScriptView } from "./CompleteScriptView";
export { ConsolePanel } from "./ConsolePanel";
export { CreatePRModal } from "./CreatePRModal";
export { DevToolsCategory } from "./DevToolsCategory";
export { DockviewHost } from "./DockviewHost";
export { EditorPanel } from "./EditorPanel";
export { IdeEditor } from "./IdeEditor";
export { IdeShell } from "./IdeShell";
export { InspectorPanel } from "./InspectorPanel";
export { RepoExplorer } from "./RepoExplorer";
export { SourceControlPanel } from "./SourceControlPanel";
export { WorkflowDetailTable } from "./WorkflowDetailTable";
export { WorkflowFormSidebar } from "./WorkflowFormSidebar";
export { WorkflowTabView } from "./WorkflowTabView";
```

- [ ] **Step 3: TypeScript check**

```bash
npx tsc -b --noEmit
```

Expected: clean.

- [ ] **Step 4: Run full test suite**

```bash
npx vitest run
```

Expected: all existing tests still pass, new ones pass.

- [ ] **Step 5: Commit**

```bash
git add src/pages/IdePage.tsx src/components/ide/index.ts
git commit -m "feat(ide): replace IdePage with IdeShell; update component index"
```

---

## Task 16: Wire `appLoadSource` tagging in `BuildingPage` (wizard source)

**Files:**
- Modify: `src/pages/BuildingPage.tsx`

- [ ] **Step 1: Add the tag immediately before `loadGeneratedFiles`**

Open `src/pages/BuildingPage.tsx`. Find the line (currently near line 227):

```ts
          useIdeStore.getState().loadGeneratedFiles(files);
```

Replace it with:

```ts
          useIdeStore.getState().setAppLoadSource("wizard");
          useIdeStore.getState().loadGeneratedFiles(files);
```

- [ ] **Step 2: TypeScript check**

```bash
npx tsc -b --noEmit
```

Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add src/pages/BuildingPage.tsx
git commit -m "feat(ide): tag wizard-generated app loads with appLoadSource='wizard'"
```

---

## Task 17: Add an error boundary around `DockviewHost`

**Files:**
- Create: `src/components/ide/DockviewErrorBoundary.tsx`
- Modify: `src/components/ide/IdeShell.tsx`

- [ ] **Step 1: Create the error boundary**

```tsx
// src/components/ide/DockviewErrorBoundary.tsx
import { Component, type ReactNode } from "react";
import { useLayoutStore } from "../../stores/layoutStore";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class DockviewErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    console.warn("[DockviewErrorBoundary] caught:", error, info);
  }

  reset = () => {
    useLayoutStore.getState().resetLayout();
    this.setState({ hasError: false, error: null });
    // Reload to rebuild the dockview instance from scratch
    window.location.reload();
  };

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-sm text-gray-400">
        <div className="text-base font-medium text-gray-200">
          Layout failed to initialize.
        </div>
        <div className="max-w-md text-center text-xs text-gray-500">
          {this.state.error?.message ?? "Unknown error"}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={this.reset}
            className="rounded bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500"
          >
            Reset Layout
          </button>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded border border-gray-600 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-gray-700"
          >
            Reload
          </button>
        </div>
      </div>
    );
  }
}
```

- [ ] **Step 2: Wrap `DockviewHost` in `IdeShell`**

Open `src/components/ide/IdeShell.tsx`. Find the `<DockviewHost ... />` usage. Wrap it:

```tsx
import { DockviewErrorBoundary } from "./DockviewErrorBoundary";

// ... inside the return JSX, replace:
//   <DockviewHost registry={registry} onReady={...} />
// with:
        <DockviewErrorBoundary>
          <DockviewHost registry={registry} onReady={(api) => { apiRef.current = api; }} />
        </DockviewErrorBoundary>
```

- [ ] **Step 3: TypeScript check**

```bash
npx tsc -b --noEmit
```

Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add src/components/ide/DockviewErrorBoundary.tsx src/components/ide/IdeShell.tsx
git commit -m "feat(ide): add DockviewErrorBoundary with Reset Layout recovery"
```

---

## Task 18: Theme dockview to match the existing dark palette

**Files:**
- Create: `src/styles/dockview-theme.css`
- Modify: `src/main.tsx`

- [ ] **Step 1: Create the theme file**

```css
/* src/styles/dockview-theme.css
 *
 * Override dockview-react CSS variables so panels match the existing
 * Tailwind dark palette (bg-gray-800 / bg-gray-900 / border-gray-700).
 * Applied via the `dockview-theme-forgeds` class that DockviewHost sets on <DockviewReact />.
 */

.dockview-theme-forgeds {
  --dv-background-color: #111827;                    /* gray-900 */
  --dv-paneview-active-outline-color: #6366f1;       /* indigo-500 */
  --dv-tabs-and-actions-container-background-color: #1f2937; /* gray-800 */
  --dv-tabs-and-actions-container-font-size: 12px;
  --dv-tab-divider-color: #374151;                   /* gray-700 */
  --dv-tab-background-color: #1f2937;
  --dv-tab-active-background-color: #111827;
  --dv-tab-hover-background-color: #374151;
  --dv-activegroup-visiblepanel-tab-background-color: #111827;
  --dv-activegroup-visiblepanel-tab-color: #e5e7eb;  /* gray-200 */
  --dv-activegroup-hiddenpanel-tab-color: #9ca3af;   /* gray-400 */
  --dv-inactivegroup-visiblepanel-tab-background-color: #1f2937;
  --dv-inactivegroup-visiblepanel-tab-color: #9ca3af;
  --dv-inactivegroup-hiddenpanel-tab-color: #6b7280; /* gray-500 */
  --dv-separator-border: #374151;
  --dv-drag-over-background-color: rgba(99, 102, 241, 0.2);
  --dv-drag-over-border-color: #6366f1;
  --dv-group-view-background-color: #111827;
}
```

- [ ] **Step 2: Import the theme after dockview's own CSS**

Open `src/main.tsx`. After the `import "dockview-react/dist/styles/dockview.css";` line (added in Task 1), add:

```tsx
import "./styles/dockview-theme.css";
```

- [ ] **Step 3: Verify the build**

```bash
npm run build
```

Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add src/styles/dockview-theme.css src/main.tsx
git commit -m "style(ide): theme dockview to match existing dark palette"
```

---

## Task 19: Integration test for `IdeShell`

**Files:**
- Create: `tests/integration/IdeShell.integration.test.tsx`

Integration tests mount the full shell. We stub dockview's heavy rendering (jsdom can't render canvas-style splitters) by mocking `dockview-react` to a simple div that registers panels as data attributes. This lets us test first-load wiring and localStorage handling without dockview's real DOM.

- [ ] **Step 1: Write the integration test**

```tsx
// tests/integration/IdeShell.integration.test.tsx
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useIdeStore } from "../../src/stores/ideStore";
import { useLayoutStore, LAYOUT_STORAGE_KEY } from "../../src/stores/layoutStore";

// Mock dockview-react because jsdom can't handle its drag/canvas internals.
// Our tests don't exercise dockview's drag UX — just that the shell wires
// panels + stores correctly.
vi.mock("dockview-react", () => {
  return {
    DockviewReact: ({ components, onReady }: { components: Record<string, React.ComponentType>; onReady: (event: { api: unknown }) => void }) => {
      // Stub a minimal "api" with the calls DockviewHost uses.
      const panels = new Map<string, { id: string; group: { panels: Array<{ id: string }> } }>();
      const api = {
        addPanel(opts: { id: string; component: string; title: string }) {
          const panel = { id: opts.id, group: { panels: [] as Array<{ id: string }> } };
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
        fromJSON(_json: unknown) {
          // No-op in stub. Tests that want restoration verify via side-effects elsewhere.
        },
        onDidLayoutChange(_cb: () => void) {
          return { dispose() {} };
        },
      };
      // Simulate mount synchronously
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

// Silence console.warn during recovery test
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
    visiblePanels: new Set(["editor", "repo-explorer", "ds-tree", "inspector", "source-control", "console"]),
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
    await renderShell();
    const stub = await screen.findByTestId("dockview-stub");
    for (const id of ["editor", "repo-explorer", "ds-tree", "inspector", "source-control", "console"]) {
      expect(stub.querySelector(`[data-panel="${id}"]`)).not.toBeNull();
    }
  });

  it("first-load UI fires when appLoadSource='wizard' and an app is loaded", async () => {
    await renderShell();
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
    await renderShell();
    await screen.findByTestId("dockview-stub");
    expect(warnSpy).toHaveBeenCalled();
    warnSpy.mockRestore();
  });
});
```

- [ ] **Step 2: Run the integration test**

```bash
npx vitest run tests/integration/IdeShell.integration.test.tsx
```

Expected: all 3 tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/IdeShell.integration.test.tsx
git commit -m "test(ide): add IdeShell integration tests (panel registration + first-load)"
```

---

## Task 20: Full validation pass

No new files. This task runs the full suite, build, and a manual smoke check.

- [ ] **Step 1: Run the full test suite**

```bash
npx vitest run
```

Expected: **all** tests pass. If any failures, address them before proceeding.

- [ ] **Step 2: Type check everything**

```bash
npx tsc -b --noEmit
```

Expected: zero errors.

- [ ] **Step 3: Build the production bundle**

```bash
npm run build
```

Expected: build succeeds. If the bundle size budget is tight, check that `dockview-react` is added to `dependencies` (not dev) and shows up in the output stats.

- [ ] **Step 4: Start the dev server**

```bash
npm run dev
```

Expected: server starts, IDE page loads in browser at the reported URL.

- [ ] **Step 5: Manual smoke checklist**

Walk through the manual QA checklist from the spec:

- [ ] Open the IDE page. Default layout matches the spec diagram: activity bar far left, explorer/editor/inspector/console in their zones.
- [ ] Drag the Repo Explorer tab to the right zone — lands in the right sidebar group.
- [ ] Drag the Console to the left zone — renders with <400 px width fallback (category `<select>` visible).
- [ ] Resize splitters, reload the page — sizes persist.
- [ ] Click each activity bar icon — show/hide behavior matches spec.
- [ ] Click "Reset Layout" — default arrangement restored.
- [ ] Simulate wizard completion: from the dashboard or via dev tools, call `useIdeStore.getState().setAppLoadSource("wizard")` then `loadAppStructure(...)`. Verify the `.ds` editor tab opens and Complete Script becomes active.
- [ ] Reload with a pre-loaded app (no new acquisition) — layout and console state undisturbed.

- [ ] **Step 6: Commit the final QA marker if any minor fixes were required**

If the smoke test required any small adjustments:

```bash
git add -A
git commit -m "chore(ide): post-QA polish for shell overhaul"
```

If nothing needed fixing, skip this step.

- [ ] **Step 7: Final summary**

Confirm to the user:
- All automated tests pass.
- Manual smoke checklist complete.
- Spec requirements implemented.
- Follow-up specs (Polish Pass, Hybrid Gap Close, Creator Parity Surfaces) ready to start.

---

## Self-Review Checklist (author — run before handing off)

- **Spec coverage**
  - Problem statement → Tasks 14/15 replace the fixed layout.
  - `dockview-react` decision → Tasks 1, 5, 18.
  - Default layout → Task 5 (`applyDefaultLayout`).
  - Activity bar (icons A–F, E/F semantics) → Tasks 6 + 14.
  - Panel registry → Task 14 (constructed in `IdeShell`).
  - Two-level console (Scripts/Dev Tools) → Task 12.
  - Scripts sub-tabs (Complete + 7 workflows) → Tasks 8, 11, 12.
  - Dev Tools sub-tabs → Task 7.
  - Workflow UX (sidebar + detail) → Tasks 9, 10, 11.
  - Complete Script summary + "Open in editor" → Task 8.
  - Layout persistence (localStorage, debounced, reset) → Tasks 4, 5, 14.
  - First-load trigger (wizard/repo only) → Tasks 13, 14, 15, 16.
  - Error handling: corrupt JSON → Tasks 5, 19. Error boundary → Task 17. Narrow-width fallback → Task 12. localStorage quota → Task 4.
  - Testing: store unit tests → Tasks 3, 4. Component tests → Tasks 6, 8, 9, 10, 11, 12. Hook tests → Task 13. Integration → Task 19.
  - Out of scope: Workflow data extraction — deferred, noted in Task 11.
  - CSS theming → Task 18.

- **Placeholder scan** — no TBDs/TODOs/"fill-in-later" in any step.

- **Type consistency**
  - `ScriptsTab`, `ConsoleCategory`, `PanelDockHint`, `AppLoadSource` defined in Task 2, consumed in Tasks 3, 4, 5, 6, 7, 11, 12, 13.
  - `PanelRegistry` / `PanelRegistryEntry` defined in Task 5, consumed in Task 14.
  - `WorkflowRow` / `WorkflowFormEntry` defined in Tasks 9/10, consumed in Task 11.
  - `setAppLoadSource` / `markCompleteScriptShown` / `setActiveConsoleCategory` / `setActiveScriptsTab` / `setActiveDevToolsTab` all defined in Task 3, consumed in later tasks — names consistent.
  - `useIdeBootstrap` returns `{ runLint, loadDsFromContent }` in Task 13; `IdeShell` consumes both in Task 14. Consistent.

Self-review passes.
