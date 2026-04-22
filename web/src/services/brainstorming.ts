import type {
  QuestionBatchResponse,
  WizardQuestion,
  WizardDepth,
  PairedQuestion,
  FreeTextQuestion,
  DataAnalysis,
} from "../types/wizard";

const CLAUDE_PROXY = import.meta.env.VITE_CLAUDE_API_PROXY ?? "";

export class BrainstormingNotConfiguredError extends Error {
  constructor() {
    super("Claude API proxy is not configured");
    this.name = "BrainstormingNotConfiguredError";
  }
}

function ensureConfigured() {
  if (!CLAUDE_PROXY) throw new BrainstormingNotConfiguredError();
}

export function parseQuestionBatchResponse(raw: string): QuestionBatchResponse {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error("Brainstorming response was not valid JSON");
  }
  if (!parsed || typeof parsed !== "object") {
    throw new Error("Brainstorming response shape invalid");
  }
  const obj = parsed as Record<string, unknown>;
  if (!Array.isArray(obj.questions)) {
    throw new Error("Brainstorming response missing questions array");
  }
  if (typeof obj.done !== "boolean") {
    throw new Error("Brainstorming response missing done flag");
  }
  const questions: WizardQuestion[] = (obj.questions as unknown[]).map((q, i) =>
    parseQuestion(q, i),
  );
  return { questions, done: obj.done };
}

function parseQuestion(q: unknown, idx: number): WizardQuestion {
  if (!q || typeof q !== "object") {
    throw new Error(`Question ${idx} is not an object`);
  }
  const o = q as Record<string, unknown>;
  if (o.kind === "paired") return parsePaired(o, idx);
  if (o.kind === "free-text") return parseFreeText(o, idx);
  throw new Error(`Question ${idx} has unknown kind: ${String(o.kind)}`);
}

function parsePaired(o: Record<string, unknown>, idx: number): PairedQuestion {
  const required = ["id", "stem", "context", "optionA", "optionB", "aiPreference"];
  for (const k of required) {
    if (!(k in o)) throw new Error(`Paired question ${idx} missing ${k}`);
  }
  const a = o.optionA as Record<string, unknown>;
  const b = o.optionB as Record<string, unknown>;
  for (const k of ["title", "reason", "consequence"]) {
    if (typeof a?.[k] !== "string")
      throw new Error(`Paired question ${idx} optionA.${k} invalid`);
    if (typeof b?.[k] !== "string")
      throw new Error(`Paired question ${idx} optionB.${k} invalid`);
  }
  return {
    kind: "paired",
    id: String(o.id),
    stem: String(o.stem),
    context: String(o.context),
    optionA: {
      title: String(a.title),
      reason: String(a.reason),
      consequence: String(a.consequence),
    },
    optionB: {
      title: String(b.title),
      reason: String(b.reason),
      consequence: String(b.consequence),
    },
    aiPreference: o.aiPreference === "B" ? "B" : "A",
  };
}

function parseFreeText(o: Record<string, unknown>, idx: number): FreeTextQuestion {
  for (const k of ["id", "stem", "context", "placeholder"]) {
    if (typeof o[k] !== "string")
      throw new Error(`Free-text question ${idx} ${k} invalid`);
  }
  return {
    kind: "free-text",
    id: String(o.id),
    stem: String(o.stem),
    context: String(o.context),
    placeholder: String(o.placeholder),
  };
}

// ── Public API ──

export async function generateOpener(
  token: string,
  coreIdea: string,
  dataAnalysis?: DataAnalysis | null,
): Promise<{ gist: string }> {
  ensureConfigured();
  const res = await fetch(`${CLAUDE_PROXY}/api/brainstorm/opener`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ coreIdea, dataAnalysis }),
  });
  if (!res.ok) throw new Error(`Opener request failed (${res.status})`);
  const json = await res.json();
  return { gist: typeof json.gist === "string" ? json.gist : "" };
}

export async function generateQuestionBatch(params: {
  token: string;
  coreIdea: string;
  depth: WizardDepth;
  midSeedAnswers: string[];
  priorQuestions: WizardQuestion[];
  priorAnswers: Record<string, "A" | "B" | string>;
  dataAnalysis?: DataAnalysis | null;
  needsFreeTextSeed?: boolean;
}): Promise<QuestionBatchResponse> {
  ensureConfigured();
  const { token, ...payload } = params;
  const res = await fetch(`${CLAUDE_PROXY}/api/brainstorm/questions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Question request failed (${res.status})`);
  const text = await res.text();
  return parseQuestionBatchResponse(text);
}
