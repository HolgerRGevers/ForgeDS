import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ActivityBar } from "../../../src/components/ide/ActivityBar";

describe("ActivityBar", () => {
  it("renders six icon buttons with accessible labels", () => {
    render(<ActivityBar onToggle={() => {}} onConsoleCategory={() => {}} />);
    expect(screen.getByRole("button", { name: /repo/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /\.ds tree/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /inspector/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /source control/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /console — scripts/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /console — dev tools/i })).toBeTruthy();
  });

  it("click on a single-panel icon calls onToggle with its panel id", () => {
    const onToggle = vi.fn();
    render(<ActivityBar onToggle={onToggle} onConsoleCategory={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /inspector/i }));
    expect(onToggle).toHaveBeenCalledWith("inspector");
  });

  it("click on Console Scripts calls onConsoleCategory('scripts')", () => {
    const onConsoleCategory = vi.fn();
    render(
      <ActivityBar onToggle={() => {}} onConsoleCategory={onConsoleCategory} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /console — scripts/i }));
    expect(onConsoleCategory).toHaveBeenCalledWith("scripts");
  });

  it("click on Console Dev Tools calls onConsoleCategory('devtools')", () => {
    const onConsoleCategory = vi.fn();
    render(
      <ActivityBar onToggle={() => {}} onConsoleCategory={onConsoleCategory} />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /console — dev tools/i }),
    );
    expect(onConsoleCategory).toHaveBeenCalledWith("devtools");
  });

  it("Enter key on an icon button triggers onToggle", () => {
    const onToggle = vi.fn();
    render(<ActivityBar onToggle={onToggle} onConsoleCategory={() => {}} />);
    const btn = screen.getByRole("button", { name: /inspector/i });
    btn.focus();
    fireEvent.keyDown(btn, { key: "Enter", code: "Enter" });
    fireEvent.click(btn);
    expect(onToggle).toHaveBeenCalled();
  });
});
