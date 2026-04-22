import type {
  PairedQuestion,
  WizardDepth,
  DataAnalysis,
} from "../types/wizard";

const CLAUDE_PROXY = import.meta.env.VITE_CLAUDE_API_PROXY ?? "";

export interface FanoutResult {
  drafts: Array<{ agent: string; spec: string; rationale: string }>;
  synthesised: string;
  divergences: string[];
}

export interface RoundTableResult {
  critiques: Array<{ persona: string; notes: string }>;
  revisedSpec: string;
}

export type FanoutProgress = (msg: {
  agent: string;
  phase: "started" | "done";
  preview?: string;
}) => void;

export type RoundTableProgress = (msg: {
  persona: string;
  phase: "started" | "done";
  critique?: string;
}) => void;

async function callAgent(
  token: string,
  role: string,
  prompt: string,
  opts?: { temperature?: number },
): Promise<string> {
  const res = await fetch(`${CLAUDE_PROXY}/api/agent`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      role,
      prompt,
      temperature: opts?.temperature ?? 0.7,
    }),
  });
  if (!res.ok) throw new Error(`Agent call failed: ${role} (${res.status})`);
  const json = await res.json();
  return typeof json.text === "string" ? json.text : "";
}

const PERSPECTIVES = [
  { agent: "simplicity",    system: "You are an architect who optimises for the simplest possible solution that meets the requirements." },
  { agent: "governance",    system: "You are an architect who optimises for governance, audit trail, and regulatory compliance." },
  { agent: "user-friction", system: "You are an architect who optimises for end-user friction — every form field is a tax." },
];

export async function fanoutSpec(params: {
  token: string;
  coreIdea: string;
  depth: WizardDepth;
  midSeedAnswers?: string[];
  questions: PairedQuestion[];
  answers: Record<string, "A" | "B" | string>;
  dataAnalysis?: DataAnalysis | null;
  agentCount?: number;
  onProgress?: FanoutProgress;
}): Promise<FanoutResult> {
  const count = Math.min(params.agentCount ?? 3, PERSPECTIVES.length);
  const perspectives = PERSPECTIVES.slice(0, count);
  const userInputBlock = JSON.stringify({
    coreIdea: params.coreIdea,
    depth: params.depth,
    midSeedAnswers: params.midSeedAnswers ?? [],
    questions: params.questions,
    answers: params.answers,
    dataAnalysis: params.dataAnalysis ?? null,
  });

  const draftPromises = perspectives.map(async (p) => {
    params.onProgress?.({ agent: p.agent, phase: "started" });
    try {
      const text = await callAgent(params.token, p.system, userInputBlock, {
        temperature: 0.9,
      });
      params.onProgress?.({ agent: p.agent, phase: "done", preview: text.slice(0, 80) });
      return { agent: p.agent, spec: text, rationale: "" };
    } catch (err) {
      params.onProgress?.({
        agent: p.agent,
        phase: "done",
        preview: err instanceof Error ? `failed: ${err.message}` : "failed",
      });
      return null;
    }
  });

  const settled = (await Promise.all(draftPromises)).filter(
    (d): d is { agent: string; spec: string; rationale: string } => d !== null,
  );

  if (settled.length < 2) {
    throw new Error(
      `Fanout produced only ${settled.length} draft(s); need at least 2 to synthesise.`,
    );
  }

  const synthInput = JSON.stringify({ drafts: settled, original: userInputBlock });
  const synthesised = await callAgent(
    params.token,
    "You are a synthesiser. Given multiple specification drafts written from different perspectives, merge them into one coherent spec. Favour points where drafts agreed; flag divergences explicitly at the end.",
    synthInput,
    { temperature: 0.3 },
  );

  const divergences = extractDivergences(synthesised);

  return { drafts: settled, synthesised, divergences };
}

function extractDivergences(text: string): string[] {
  const idx = text.toLowerCase().lastIndexOf("divergences:");
  if (idx < 0) return [];
  return text
    .slice(idx + "divergences:".length)
    .split("\n")
    .map((s) => s.replace(/^[-*]\s*/, "").trim())
    .filter((s) => s.length > 0);
}

const DEFAULT_PERSONAS = [
  "End User",
  "Compliance Officer",
  "Technical Architect",
  "Skeptical CFO",
];

export async function personaRoundTable(params: {
  token: string;
  spec: string;
  personas?: string[];
  onProgress?: RoundTableProgress;
}): Promise<RoundTableResult> {
  const personas = params.personas ?? DEFAULT_PERSONAS;
  const critiques: Array<{ persona: string; notes: string }> = [];

  for (const persona of personas) {
    params.onProgress?.({ persona, phase: "started" });
    try {
      const priorBlock =
        critiques.length > 0
          ? `\n\nPRIOR CRITIQUES:\n${critiques
              .map((c) => `- ${c.persona}: ${c.notes}`)
              .join("\n")}`
          : "";
      const prompt = `SPEC:\n${params.spec}${priorBlock}\n\nCritique this spec from your perspective. Be concrete.`;
      const notes = await callAgent(
        params.token,
        `You are a ${persona}. Critique the spec from your perspective only.`,
        prompt,
        { temperature: 0.5 },
      );
      critiques.push({ persona, notes });
      params.onProgress?.({ persona, phase: "done", critique: notes.slice(0, 80) });
    } catch (err) {
      params.onProgress?.({
        persona,
        phase: "done",
        critique: err instanceof Error ? `failed: ${err.message}` : "failed",
      });
      break;
    }
  }

  const synthPrompt = `ORIGINAL SPEC:\n${params.spec}\n\nCRITIQUES:\n${critiques
    .map((c) => `- ${c.persona}: ${c.notes}`)
    .join("\n")}\n\nProduce a revised spec that addresses the critiques.`;
  const revisedSpec = await callAgent(
    params.token,
    "You are a synthesiser merging critiques into a revised specification.",
    synthPrompt,
    { temperature: 0.3 },
  );

  return { critiques, revisedSpec };
}
