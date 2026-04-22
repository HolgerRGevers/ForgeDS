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
