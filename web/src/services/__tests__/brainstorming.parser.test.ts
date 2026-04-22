import { describe, it, expect } from "vitest";
import { parseQuestionBatchResponse } from "../brainstorming";

describe("parseQuestionBatchResponse", () => {
  it("accepts a valid paired-question payload", () => {
    const raw = JSON.stringify({
      questions: [
        {
          kind: "paired",
          id: "q1",
          stem: "Who approves?",
          context: "ctx",
          optionA: { title: "A", reason: "r", consequence: "c" },
          optionB: { title: "B", reason: "r2", consequence: "c2" },
          aiPreference: "A",
        },
      ],
      done: false,
    });
    const out = parseQuestionBatchResponse(raw);
    expect(out.questions).toHaveLength(1);
    expect(out.questions[0].kind).toBe("paired");
    expect(out.done).toBe(false);
  });

  it("accepts a valid free-text-question payload", () => {
    const raw = JSON.stringify({
      questions: [
        { kind: "free-text", id: "q1", stem: "Pain point?", context: "", placeholder: "..." },
      ],
      done: true,
    });
    const out = parseQuestionBatchResponse(raw);
    expect(out.questions[0].kind).toBe("free-text");
    expect(out.done).toBe(true);
  });

  it("throws on missing fields", () => {
    expect(() => parseQuestionBatchResponse("{}")).toThrow();
  });

  it("throws on invalid JSON", () => {
    expect(() => parseQuestionBatchResponse("not json")).toThrow();
  });

  it("throws when paired option lacks required subfields", () => {
    const raw = JSON.stringify({
      questions: [
        { kind: "paired", id: "q1", stem: "?", context: "", optionA: { title: "A" }, optionB: {}, aiPreference: "A" },
      ],
      done: false,
    });
    expect(() => parseQuestionBatchResponse(raw)).toThrow();
  });
});
