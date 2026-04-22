import { useCallback, useEffect, useMemo, useRef } from "react";
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
  component: React.FunctionComponent<IDockviewPanelProps>;
  /** Default dockview position when the panel is added by activity-bar click
   *  and no lastKnownPosition exists. */
  defaultPosition?: PanelDockHint;
  /** If true, panel cannot be closed via its tab UI. */
  closable?: boolean;
}

export type PanelRegistry = Record<string, PanelRegistryEntry>;

interface DockviewHostProps {
  /** Component registry (panel ID -> factory).
   *  Must be referentially stable across renders — callers should wrap in `useMemo`. */
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
    title: registry.editor?.title ?? "Editor",
  });

  api.addPanel({
    id: "repo-explorer",
    component: "repo-explorer",
    title: registry["repo-explorer"]?.title ?? "Explorer",
    position: { referencePanel: "editor", direction: "left" },
  });
  api.addPanel({
    id: "ds-tree",
    component: "ds-tree",
    title: registry["ds-tree"]?.title ?? "DS Tree",
    position: { referencePanel: "repo-explorer", direction: "within" },
  });
  api.addPanel({
    id: "inspector",
    component: "inspector",
    title: registry.inspector?.title ?? "Inspector",
    position: { referencePanel: "editor", direction: "right" },
  });
  api.addPanel({
    id: "source-control",
    component: "source-control",
    title: registry["source-control"]?.title ?? "Source Control",
    position: { referencePanel: "inspector", direction: "within" },
  });
  api.addPanel({
    id: "console",
    component: "console",
    title: registry.console?.title ?? "Console",
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
  if (!panel) return { referencePanelId: "editor", direction: "right" };
  const group = panel.group;
  if (!group) return { referencePanelId: "editor", direction: "right" };
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
  const layoutChangeDisposableRef = useRef<{ dispose: () => void } | null>(null);

  const { setLayoutJson, recordLastKnownPosition, visiblePanels } =
    useLayoutStore();

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

      layoutChangeDisposableRef.current = event.api.onDidLayoutChange(() => {
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

  // Cleanup on unmount: cancel pending save timer and dispose layout-change listener.
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }
      layoutChangeDisposableRef.current?.dispose();
      layoutChangeDisposableRef.current = null;
    };
  }, []);

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
        const panel = api.getPanel(id);
        if (panel) {
          api.removePanel(panel);
        }
      } else if (!panelExists && shouldBeVisible) {
        const hint =
          useLayoutStore.getState().lastKnownPositions[id] ??
          registry[id]?.defaultPosition;
        const position =
          hint?.referencePanelId && api.getPanel(hint.referencePanelId)
            ? {
                referencePanel: hint.referencePanelId,
                direction: hint.direction,
              }
            : undefined;
        api.addPanel({
          id,
          component: id,
          title: registry[id]?.title ?? id,
          ...(position ? { position } : {}),
        });
      }
    }
  }, [visiblePanels, registry, recordLastKnownPosition]);

  // Build dockview `components` map from registry — memoised to avoid a new
  // object reference on every render (DockviewReact uses referential equality).
  const components = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(registry).map(([id, entry]) => [id, entry.component]),
      ),
    [registry],
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
