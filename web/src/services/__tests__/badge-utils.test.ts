import { describe, it, expect } from "vitest";
import { deriveBadgeInitials, hashToBadgeColor } from "../../lib/badge-utils";

describe("deriveBadgeInitials", () => {
  it("returns first letters of words for multi-word names", () => {
    expect(deriveBadgeInitials("expense reimbursement manager")).toBe("ERM");
    expect(deriveBadgeInitials("Invoice Overdue")).toBe("INO");
  });
  it("returns first 3 chars of single words", () => {
    expect(deriveBadgeInitials("travel")).toBe("TRA");
  });
  it("handles hyphens and underscores as word separators", () => {
    expect(deriveBadgeInitials("incident-reports")).toBe("INR");
    expect(deriveBadgeInitials("incident_report_sync")).toBe("IRS");
  });
  it("uppercases output", () => {
    expect(deriveBadgeInitials("foo bar")).toBe("FOB");
  });
  it("returns at most 3 chars", () => {
    expect(deriveBadgeInitials("a b c d e")).toBe("ABC");
  });
});

describe("hashToBadgeColor", () => {
  it("returns one of the palette colors", () => {
    const palette = ["#c2662d", "#7c3aed", "#22c55e", "#0ea5e9", "#ec4899", "#f59e0b"];
    expect(palette).toContain(hashToBadgeColor("foo"));
  });
  it("is deterministic for the same input", () => {
    expect(hashToBadgeColor("foo")).toBe(hashToBadgeColor("foo"));
  });
});
