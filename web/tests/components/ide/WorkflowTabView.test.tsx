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
    expect(screen.getByText("Expense Claims")).toBeTruthy();
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
