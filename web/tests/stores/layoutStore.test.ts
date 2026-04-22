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

  it("recordLastKnownPosition merges hints without clobbering others", () => {
    const { recordLastKnownPosition } = useLayoutStore.getState();
    recordLastKnownPosition("inspector", { referencePanelId: "editor", direction: "right" });
    recordLastKnownPosition("console", { referencePanelId: "editor", direction: "below" });
    const { lastKnownPositions } = useLayoutStore.getState();
    expect(lastKnownPositions.inspector?.direction).toBe("right");
    expect(lastKnownPositions.console?.direction).toBe("below");
  });

  it("setLayoutJson updates state and writes to localStorage", () => {
    const json = '{"panels":[]}';
    useLayoutStore.getState().setLayoutJson(json);
    expect(useLayoutStore.getState().layoutJson).toBe(json);
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
    useLayoutStore.setState({
      lastKnownPositions: {
        inspector: { referencePanelId: "editor", direction: "right" },
      },
    });
    const { togglePanel, lastKnownPositions } = useLayoutStore.getState();
    expect(lastKnownPositions.inspector?.direction).toBe("right");
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
