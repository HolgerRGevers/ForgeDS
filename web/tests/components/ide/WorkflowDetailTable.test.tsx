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
