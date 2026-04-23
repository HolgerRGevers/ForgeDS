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
  const connect = useBridgeStore((s) => (s as { connect: () => void }).connect);
  const status = useBridgeStore((s) => (s as { status: string }).status);
  const send = useBridgeStore(
    (s) => (s as { send: (type: string, data: unknown) => Promise<unknown> }).send,
  );

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
      const diagnostics = (
        result as unknown as {
          diagnostics: Array<{
            file: string;
            line: number;
            rule: string;
            severity: "error" | "warning" | "info";
            message: string;
          }>;
        }
      ).diagnostics ?? [];
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
