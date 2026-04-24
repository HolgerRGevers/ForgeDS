import { beforeEach, describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { useIdeStore } from "../../../src/stores/ideStore";
import { ConsolePanel } from "../../../src/components/ide/ConsolePanel";

function reset() {
  useIdeStore.setState({
    activeConsoleCategory: "scripts",
    activeScriptsTab: "complete",
    activeDevToolsTab: "lint",
    appStructure: null,
  });
}

describe("ConsolePanel", () => {
  beforeEach(reset);

  it("renders both category tabs by default (wide width)", () => {
    render(
      <div style={{ width: 800 }}>
        <ConsolePanel containerWidth={800} />
      </div>,
    );
    expect(screen.getByRole("tab", { name: /scripts/i })).toBeTruthy();
    expect(screen.getByRole("tab", { name: /dev tools/i })).toBeTruthy();
  });

  it("switching category preserves the other category's sub-tab", () => {
    render(<ConsolePanel containerWidth={800} />);
    fireEvent.click(screen.getByRole("tab", { name: /blueprints/i }));
    expect(useIdeStore.getState().activeScriptsTab).toBe("blueprints");
    fireEvent.click(screen.getByRole("tab", { name: /dev tools/i }));
    fireEvent.click(screen.getByRole("tab", { name: /^scripts$/i }));
    expect(useIdeStore.getState().activeScriptsTab).toBe("blueprints");
  });

  it("renders a <select> instead of a tab row when container width < 400", () => {
    render(<ConsolePanel containerWidth={300} />);
    expect(screen.getByLabelText(/category/i)).toBeTruthy();
    expect(screen.getByLabelText(/sub-tab/i)).toBeTruthy();
  });
});
