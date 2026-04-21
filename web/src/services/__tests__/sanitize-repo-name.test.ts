import { describe, it, expect } from "vitest";
import { sanitizeRepoName } from "../../lib/sanitize-repo-name";

describe("sanitizeRepoName", () => {
  it("lowercases", () => {
    expect(sanitizeRepoName("Travel Expense")).toBe("travel-expense");
  });
  it("replaces spaces with hyphens", () => {
    expect(sanitizeRepoName("a b c")).toBe("a-b-c");
  });
  it("strips invalid characters", () => {
    expect(sanitizeRepoName("foo!bar@baz.qux")).toBe("foo-bar-baz.qux");
  });
  it("dedupes consecutive hyphens", () => {
    expect(sanitizeRepoName("foo   bar")).toBe("foo-bar");
    expect(sanitizeRepoName("foo!!bar")).toBe("foo-bar");
  });
  it("trims leading/trailing hyphens", () => {
    expect(sanitizeRepoName("-foo-")).toBe("foo");
  });
  it("caps at 100 chars", () => {
    const long = "a".repeat(150);
    expect(sanitizeRepoName(long)).toHaveLength(100);
  });
  it("returns 'untitled' for empty/all-invalid input", () => {
    expect(sanitizeRepoName("")).toBe("untitled");
    expect(sanitizeRepoName("!!!")).toBe("untitled");
  });
});
