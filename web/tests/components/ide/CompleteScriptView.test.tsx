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
