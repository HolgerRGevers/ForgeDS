import { beforeEach, describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { act } from "react";
import { useIdeStore } from "../../src/stores/ideStore";
import { useIdeBootstrap } from "../../src/hooks/useIdeBootstrap";
import type { AppStructure } from "../../src/types/ide";

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
    act(() => {
      useIdeStore.getState().setAppLoadSource("wizard");
      useIdeStore.getState().loadAppStructure(mockStructure("e"));
    });
    expect(useIdeStore.getState().tabs.length).toBe(firstTabCount);
  });
});
