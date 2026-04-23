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
    expect(screen.getAllByText(/forms/i).length).toBeGreaterThanOrEqual(2);
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
