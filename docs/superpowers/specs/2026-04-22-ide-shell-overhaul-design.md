# ForgeDS IDE: Shell Overhaul Design

**Date:** 2026-04-22
**Status:** Draft — pending implementation plan
**Scope:** Replace the current fixed-layout IDE shell with a VS Code–style movable-panel system, redesign the bottom console to resemble Creator's Workflow page, and add a Complete Script entry-point. Spec 1 of a 4-spec series.

## Relationship to Other Specs

This is the first of four planned specs for the IDE overhaul:

1. **Shell Overhaul** (this spec) — movable panels + workflow-style console + Complete Script default view.
2. **Polish Pass** (next) — fix stubbed/broken features in existing panels (lint `onFileClick`, inspector idle state, bridge-offline fallbacks, etc.).
3. **Hybrid Gap Close** — finish features promised in `2026-04-21-hybrid-ide-design.md` but not yet shipped.
4. **Creator Parity Surfaces** (series) — one spec per Creator page cloned into the IDE (Forms Designer, Reports, Pages, Blueprints, Schedules, Approvals…).

The Shell Overhaul is the skeleton the rest hang off. Workflow-tab data extraction (Q13 decision) is punted to Polish Pass — this spec renders empty states for all 7 workflow tabs.

## Problem

The IDE (`web/src/pages/IdePage.tsx`) uses a rigid CSS-grid layout: Explorer fixed at 250 px left, Inspector/Source Control fixed at 300 px right, Console fixed at 200 px bottom. Panels cannot be moved, reordered, or docked elsewhere. The bottom console exposes four dev-tool tabs (Lint, Build, Relationships, AI Chat) with no connection to the app's actual script surface. When a user loads an app, they land on an empty editor with no visible entry point into the app's scripts.

Users familiar with Zoho Creator expect a Workflow page that organizes scripts by type (form workflows, schedules, approvals, blueprints, batch workflows, functions), with forms on the left and workflow items on the right. The ForgeDS IDE does not mirror this mental model.

## Decision

Rebuild the IDE shell on `dockview-react` (VS Code–style fixed-zone docking), add a vertical activity bar for view toggling, and redesign the bottom console as a two-level tabbed container with a Scripts category (Creator-style Workflow page tabs + Complete Script) and a Dev Tools category (the existing four tabs).

### Why dockview-react

- Purpose-built for VS Code–like docking — drag-between-zones, split-on-drop, tab-reorder, keyboard nav, drop indicators all solved.
- MIT-licensed, TypeScript-native, actively maintained.
- Layout serialization (`toJSON()` / `fromJSON()`) maps directly to the localStorage persistence requirement.
- ~80 kB gzipped — a real dependency cost but justified by the surface area bought.

Alternatives considered: `react-resizable-panels` + custom DnD (2× the build time, UX risk on drop indicators and keyboard nav); minimal splitter-only extension of the current grid (does not satisfy the "dynamically movable" requirement).

## Architecture

### Zone Model

dockview manages the entire area below the top bar. Its grid model lets panels snap into five positions — left, right, top, bottom, center — nested arbitrarily. Tabs within a group are reorderable; groups are resizable via splitters.

### Default Layout

```
┌─────┬─ TopBar ───────────────────────────────────────┐
│ A   ├─ Left Sidebar ─┬─ Editor ─┬─ Right Sidebar ─┤
│ B   │ [Repo Explorer] │ Monaco     │ [Inspector]      │
│ C   │ [.ds Tree]      │ tabs       │ [Source Ctrl]    │
│ D   ├─────────────────┴────────────┴──────────────────┤
│ E   │ Bottom Panel                                     │
│ F   │  Category: Scripts ◉  |  Dev Tools               │
│     │  Sub-tabs: Complete Script* | Form Workflows | … │
└─────┴──────────────────────────────────────────────────┘
```

- Left activity bar: ~48 px vertical strip with 6 icons.
- Top bar: bridge status, Lint action, Load .ds action, Reset Layout command.
- Sidebar groups stack views as tabs (Repo + .ds Tree on left; Inspector + Source Control on right).
- Bottom zone contains a single `Console` dockview panel with internal two-level tabs.

### Activity Bar

Six icon buttons, each bound to a panel ID:

| Icon | Panel ID | Label |
|---|---|---|
| 📁 | `repo-explorer` | Repo Explorer |
| 🌲 | `ds-tree` | .ds Tree |
| 🔍 | `inspector` | Inspector |
| ⇄ | `source-control` | Source Control |
| 📜 | `console` (scripts) | Console — Scripts |
| 🛠 | `console` (devtools) | Console — Dev Tools |

Click-to-toggle behavior:

- **Icons A–D** (single-panel views): hidden → show in last-known dock position; visible → hide.
- **Icons E, F** (both bound to the `console` panel): hidden → show + activate the matching category; visible with a *different* category active → switch category without toggling visibility; visible with the *matching* category active → hide the panel.

The icon row never moves with the panel — it's always on the activity bar. See Data Flow for the full toggle algorithm.

### Panel Registry

```ts
const PANELS = {
  "editor":         { title: "Editor",         component: EditorPanel,    closable: false },
  "repo-explorer":  { title: "Repo",           component: RepoExplorer },
  "ds-tree":        { title: ".ds Tree",       component: AppTreeExplorer },
  "inspector":      { title: "Inspector",      component: InspectorPanel },
  "source-control": { title: "Source Control", component: SourceControlPanel },
  "console":        { title: "Console",        component: ConsolePanel },
};
```

Editor is `closable: false` — it's always visible; other panels can be hidden via the activity bar.

### Console Panel Internal Structure

The `Console` dockview panel contains pure-React two-level tabs — dockview sees one panel, not twelve.

**Scripts category sub-tabs (8):**
- `complete` — Complete Script (hybrid model — focuses `.ds` editor tab, shows compact summary inline)
- `form-workflows`
- `schedules`
- `approvals`
- `payments`
- `blueprints`
- `batch-workflows`
- `functions`

**Dev Tools category sub-tabs (4):**
- `lint` — existing LintTab
- `build` — existing BuildTab
- `relationships` — existing RelationshipsTab
- `ai` — existing AiChatTab

Category and sub-tab selection persist in `ideStore` (not in dockview JSON) — see Data Flow.

### Workflow Tab UX

Each of the 7 Creator-style workflow tabs renders a `WorkflowTabView` with:

- **Left sidebar (`WorkflowFormSidebar`)**: two sections — "Forms with [type]" and "Forms without [type]". Mirrors Creator's Workflow page.
- **Right pane (`WorkflowDetailTable`)**: rows with `[Name] [Status] [Created On]` columns.

Row click → opens the corresponding `.dg` file as an editor tab (top pane). One editing surface — the editor — matches existing .ds Tree / Repo Explorer behavior.

For this spec, data extraction is deferred: `WorkflowTabView` shows "No [type] found in this app — data extraction pending (Polish Pass spec)" empty state. The container, sidebar, and table render; they just receive empty arrays.

### Complete Script View

`CompleteScriptView` renders in the Scripts category when `activeScriptsTab === "complete"`. Content:

- File name of the loaded `.ds`
- Form count, script count, file size (bytes)
- Parse status (local JS parser / bridge-enriched / unparsed)
- Primary action: "Open in editor" button → focuses existing `.ds` editor tab, or opens it if missing.

First-load behavior (see Data Flow) pre-activates this tab when an app is freshly acquired.

## Components

### New Components

| Component | Responsibility |
|---|---|
| `IdeShell` | Top-level replacement for current `IdePage` layout — top bar + activity bar + dockview container. |
| `ActivityBar` | Vertical icon strip on the far left. Click toggles panel visibility via `layoutStore`. |
| `DockviewHost` | Wraps `<DockviewReact />` — registers panels, restores layout from localStorage, debounced serialize on change. |
| `ConsolePanel` | Single dockview panel for the bottom zone. Internal two-level tabs (category + sub-tab). |
| `CompleteScriptView` | Scripts category sub-tab content — summary + open-in-editor action. |
| `WorkflowTabView` | Generic container for all 7 Creator-style workflow tabs. Takes `workflowType` prop. |
| `WorkflowFormSidebar` | Left column of `WorkflowTabView` — "Forms with [type]" / "Forms without [type]" sections. |
| `WorkflowDetailTable` | Right column of `WorkflowTabView` — row list with Name/Status/Created columns. |
| `DevToolsCategory` | Renamed from `DevConsole`. Wraps the existing four tab components as sub-tabs. |
| `useIdeBootstrap` | Custom hook extracting the current `IdePage` effects (bridge connect, parse_ds, read_file, inspect_element). |

### Modified Components

| Component | Change |
|---|---|
| `IdePage.tsx` | Slimmed to `<IdeShell />`. All layout logic moves out. |
| `DevConsole.tsx` | Renamed to `DevToolsCategory.tsx` and moved under `ConsolePanel`. Top-level `<DevConsole>` header/collapse UI deleted — dockview's tab strip replaces it. |

### File Layout

```
web/src/
  components/ide/
    IdeShell.tsx              (new)
    ActivityBar.tsx           (new)
    DockviewHost.tsx          (new)
    ConsolePanel.tsx          (new)
    CompleteScriptView.tsx    (new)
    WorkflowTabView.tsx       (new)
    WorkflowFormSidebar.tsx   (new)
    WorkflowDetailTable.tsx   (new)
    DevToolsCategory.tsx      (renamed from DevConsole.tsx)
    DevConsole.tsx            (deleted)
  hooks/
    useIdeBootstrap.ts        (new)
  pages/
    IdePage.tsx               (slimmed to wrapper)
  stores/
    layoutStore.ts            (new)
    ideStore.ts               (extended — console category state, appLoadSource)
```

## Data Flow

### State Shape

```ts
// types/ide.ts (EXTENDED)
type ScriptsTab =
  | "complete"
  | "form-workflows"
  | "schedules"
  | "approvals"
  | "payments"
  | "blueprints"
  | "batch-workflows"
  | "functions";

// Remembered drop location for a panel that has been hidden via the activity bar.
// Used when re-adding the panel so it returns to where the user last had it.
interface PanelDockHint {
  referencePanelId?: string;           // dockview anchor panel
  direction?: "left" | "right" | "above" | "below" | "within";
}

// layoutStore.ts (NEW — Zustand)
interface LayoutStore {
  layoutJson: string | null;                    // serialized dockview state
  visiblePanels: Set<string>;                   // derived from current dockview layout
  lastKnownPositions: Record<string, PanelDockHint>;  // per-panel hint for re-show
  setLayoutJson(json: string): void;            // from dockview onDidLayoutChange
  togglePanel(panelId: string): void;           // activity-bar click
  resetLayout(): void;                          // "Reset Layout" top-bar action
}

// ideStore.ts (EXTENDED)
interface IdeStore {
  // ... existing fields (tabs, appStructure, diagnostics, etc.)

  activeConsoleCategory: "scripts" | "devtools";         // NEW
  activeScriptsTab: ScriptsTab;                          // NEW
  activeDevToolsTab: ConsoleTab;                         // RENAMED from activeConsoleTab
  appLoadSource: "wizard" | "repo" | "upload" | "bridge-auto" | null;  // NEW — drives first-load logic
  completeScriptShownForApps: Set<string>;               // NEW — session-scoped dedupe
}
```

**togglePanel semantics** — when hiding a panel, record its current dockview position in `lastKnownPositions[panelId]` before calling `api.removePanel()`. When showing a panel, add it back at `lastKnownPositions[panelId]` if a hint exists, otherwise use the panel's registry-defined default position. This preserves user-customized layouts across show/hide cycles without keeping invisible panels in the dockview tree.

### Layout Persistence Contract

- Storage key: `forgeds-ide-layout-v1`. Bump suffix to v2 if panel IDs change.
- Serialize on `onDidLayoutChange`, debounced 300 ms.
- On mount: read → `dockview.fromJSON()`. If parse throws or references unknown panel IDs: silently reset to default layout, `console.warn` with cause.
- "Reset Layout" action: clears localStorage key, re-initializes dockview with default layout.
- Console category/sub-tab state persists separately in `forgeds-ide-console-state-v1`. Keeps dockview JSON geometry-only.

### First-Load Trigger

```
wizard completes            → setAppLoadSource("wizard")      + loadAppStructure(...)  → first-load UI fires
repo .ds selected           → setAppLoadSource("repo")        + loadAppStructure(...)  → first-load UI fires
bridge reconnect            → setAppLoadSource("bridge-auto") + loadAppStructure(...)  → no first-load UI
.ds uploaded manually       → setAppLoadSource("upload")      + loadAppStructure(...)  → no first-load UI

useIdeBootstrap effect watches appStructure.
  When appStructure changes AND appLoadSource ∈ {"wizard", "repo"}
                          AND !completeScriptShownForApps.has(appStructure.name):
    openTab(.ds)
    setActiveConsoleCategory("scripts")
    setActiveScriptsTab("complete")
    completeScriptShownForApps.add(appStructure.name)
    setAppLoadSource(null)  // clear after consumption to avoid re-fire
```

`completeScriptShownForApps` is not persisted — each page reload is a fresh session and a fresh acquisition fires the UI once.

### Activity Bar → Layout Flow

```
ActivityBar onClick(panelId)
  → layoutStore.togglePanel(panelId)
    → if visiblePanels.has(panelId):
        record lastKnownPositions[panelId] = current dock hint
        dockviewApi.removePanel(panelId)
      else:
        dockviewApi.addPanel({ id: panelId, ...lastKnownPositions[panelId] ?? defaultPosition })
    → dockview onDidLayoutChange fires
    → layoutStore.setLayoutJson(new JSON)
    → debounce 300 ms → localStorage.setItem(KEY, json)

Icons E (Scripts) and F (Dev Tools) share the `console` panel:
  - If `console` is hidden: show it AND setActiveConsoleCategory to the matching category.
  - If `console` is visible: setActiveConsoleCategory to the matching category (do not toggle visibility on the second click of the *other* icon).
  - If `console` is visible AND already showing the matching category: hide the panel.
```

### Workflow Row Click Flow

```
WorkflowDetailTable row onClick(workflowItem)
  → ideStore.openTab({ id: workflowItem.filePath, path: workflowItem.filePath, ... })
  → editor tab bar updates
  → useIdeBootstrap read_file effect loads content for unloaded tabs
```

## Error Handling & Edge Cases

| Scenario | Handling |
|---|---|
| Corrupt / unparseable layout JSON | `try/catch` around `fromJSON` → reset to default. `console.warn` with parse error. No user-facing alert. |
| Unknown panel ID in saved layout | Dockview throws on `fromJSON` → same path: reset + warn. |
| localStorage quota exceeded / disabled | Save silently fails; layout doesn't persist this session. Log once. |
| `AppStructure` is null | Workflow sub-tabs render "No app loaded" empty state. Complete Script view shows same. |
| First-load race (`appLoadSource` set before `appStructure` arrives) | `useIdeBootstrap` effect watches `appStructure`; `appLoadSource` is sticky until consumed, then cleared to `null`. |
| Narrow Console (<400 px wide, e.g., dragged to side zone) | Category tabs collapse to `<select>` dropdown; sub-tabs use horizontal scroll. Ugly but functional. Not blocked at drop time. |
| Activity bar click on a non-active tab | First click focuses it in its group; second click hides. Matches VS Code. |
| Dockview fails to render | Top-level error boundary around `DockviewHost` → shows "Layout failed to initialize. [Reset Layout] [Reload]". |
| Panel registry missing a view | TypeScript catches at compile; runtime shows empty panel with title. |

### Out of Scope (Deferred to Later Specs)

- Workflow tab data extraction from `.ds` — Polish Pass spec.
- Bridge-offline fallbacks for lint / relationships / AI chat — Polish Pass or Hybrid Gap Close.
- Named layout presets (save/load) — future enhancement.
- Tear-off floating panels beyond dockview's default support — future enhancement.

## Testing

Using the existing `vitest` + `@testing-library/react` setup.

### Unit Tests — Stores & Hooks

- `layoutStore.test.ts` — `togglePanel` shows/hides correctly; `resetLayout` wipes state + storage; `setLayoutJson` updates without side effects; localStorage quota failure is swallowed cleanly.
- `ideStore.test.ts` (extended) — `setActiveConsoleCategory` transitions; `setActiveScriptsTab` / `setActiveDevToolsTab` independence (switching category doesn't reset the other's sub-tab).
- `useIdeBootstrap.test.ts` — four cases: `wizard` source fires first-load UI; `repo` source fires first-load UI; `upload` does NOT; `bridge-auto` does NOT. Dedupe via `completeScriptShownForApps` prevents re-fire.

### Component Tests

- `ActivityBar.test.tsx` — renders 6 icons; each click calls `togglePanel` with correct ID; keyboard `Enter`/`Space` activation works.
- `ConsolePanel.test.tsx` — category tabs render; switching category preserves the other category's active sub-tab; narrow-width fallback (<400 px) renders `<select>` instead of tab row.
- `CompleteScriptView.test.tsx` — renders summary from mocked `AppStructure`; "Open in editor" calls `openTab` with `.ds` file path.
- `WorkflowTabView.test.tsx` — null `appStructure` → empty state; mock data → sidebar + detail table render; row click → `openTab` called with target `.dg` path.

### Integration Tests

- `IdeShell.integration.test.tsx`:
  - Mounts full shell with default layout; verifies all 6 dockable views register with dockview.
  - Simulates `setAppLoadSource("wizard")` + `loadAppStructure(mock)` → asserts `.ds` editor tab opens AND Console Scripts category is active AND Complete Script is the active sub-tab.
  - Seeds localStorage with a valid serialized layout → mounts → verifies dockview starts in that layout.
  - Seeds localStorage with corrupt JSON → mounts → falls back to default layout; `console.warn` called.

### Manual QA Checklist (Not Automated)

Dockview's drag-drop UX is covered by dockview's own tests; the checklist below is a manual smoke pass when implementation completes.

- Drag Repo Explorer tab to the right zone — lands in right sidebar group.
- Drag Console to the left zone — renders with <400 px width fallback (category `<select>` visible).
- Resize splitters — sizes persist across page reload.
- Click activity bar icons — show/hide/focus behavior matches spec.
- Reset Layout command restores default arrangement.
- Wizard completion → Complete Script tab becomes active + `.ds` editor tab opens.
- Bridge reconnect with pre-loaded app → layout undisturbed.

## Build Estimate

3–5 days of focused work. Breakdown:

- Day 1: dockview integration, panel registry, default layout, activity bar, layout persistence.
- Day 2: ConsolePanel with two-level tabs; wire Dev Tools category by moving existing `DevConsole` tabs in.
- Day 3: WorkflowTabView + WorkflowFormSidebar + WorkflowDetailTable (empty-state rendering); CompleteScriptView; first-load wiring in `useIdeBootstrap`.
- Day 4: Error boundary, narrow-width responsive fallback, Reset Layout command, QA pass.
- Day 5: Tests, polish, CSS theming to match current dark aesthetic.

## Open Questions / Assumptions

- **dockview CSS theming** — the default dockview theme is close to VS Code dark but will need CSS variable overrides to match the existing `bg-gray-800` / `border-gray-700` palette. Budgeted in Day 5.
- **Activity bar icons** — spec uses emoji placeholders (📁 🌲 🔍 ⇄ 📜 🛠). Final icons should come from a consistent icon set (heroicons, lucide) decided during implementation. Not blocking the design.
- **Editor panel closability** — spec says `closable: false`. Acceptable because an IDE without an editor is meaningless. If dockview enforces at least one closable panel, we revisit.

## Summary

This design replaces the IDE's fixed-layout shell with a VS Code–style docking system via `dockview-react`, adds a vertical activity bar for panel toggling, and redesigns the bottom console as a two-level tabbed container. A "Scripts" category houses a Complete Script entry-point plus 7 Creator-style workflow tabs (rendered as empty states pending the Polish Pass spec); a "Dev Tools" category preserves the existing Lint / Build / Relationships / AI Chat tabs. Layout persists per-user in localStorage. First-load UI — Complete Script activation plus automatic `.ds` editor tab — fires only on fresh app acquisition (wizard or repo-select), not on bridge reconnects or manual uploads. Estimated 3–5 days of focused work.
