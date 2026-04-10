/**
 * Claude API client for ForgeDS IDE.
 *
 * Communicates with the Cloudflare Worker proxy that forwards
 * requests to the Anthropic Claude API. The user's GitHub token
 * is sent for auth — the Worker validates it before proxying.
 */

import { TokenExpiredError } from "./github-api";

const CLAUDE_PROXY = import.meta.env.VITE_CLAUDE_API_PROXY ?? "";

export class ClaudeApiNotConfiguredError extends Error {
  constructor() {
    super("AI code generation is not configured. The Claude API proxy URL is missing.");
    this.name = "ClaudeApiNotConfiguredError";
  }
}

// ── Types ────────────────────────────────────────────────────────────────

export interface RefineRequest {
  prompt: string;
  files: string[];
  repoContext: Array<{ path: string; content: string; source: string }>;
  mode: "plan" | "code";
}

export interface RefinedSectionRaw {
  id: string;
  title: string;
  icon: string;
  content: string;
  items: string[];
  isEditable: boolean;
}

export interface RefineResponse {
  sections: RefinedSectionRaw[];
  planSteps?: string[];
}

export interface BuildRequest {
  sections: RefinedSectionRaw[];
  prompt: string;
}

export interface BuildChunk {
  step?: number;
  total?: number;
  message: string;
  type?: "info" | "success" | "error" | "warning";
  done?: boolean;
  files?: Array<{ name: string; path: string; content: string; language: string }>;
}

export interface BuildResponse {
  files: Array<{ name: string; path: string; content: string; language: string }>;
}

// ── Helpers ──────────────────────────────────────────────────────────────

function ensureConfigured() {
  if (!CLAUDE_PROXY) {
    throw new ClaudeApiNotConfiguredError();
  }
}

async function handleErrorResponse(res: Response): Promise<never> {
  const body = await res.text().catch(() => "");
  if (res.status === 401) {
    throw new TokenExpiredError();
  }
  let message = `Claude API error (${res.status})`;
  try {
    const json = JSON.parse(body);
    if (json.error) message = json.error;
  } catch {
    if (body) message = body;
  }
  throw new Error(message);
}

// ── API Functions ────────────────────────────────────────────────────────

export async function refinePrompt(
  token: string,
  data: RefineRequest,
): Promise<RefineResponse> {
  ensureConfigured();

  const res = await fetch(`${CLAUDE_PROXY}/api/refine`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });

  if (!res.ok) {
    return handleErrorResponse(res);
  }

  return res.json();
}

export async function buildProject(
  token: string,
  data: BuildRequest,
  onChunk: (chunk: BuildChunk) => void,
): Promise<BuildResponse> {
  ensureConfigured();

  // Send progress updates while waiting for the API
  onChunk({ message: "Sending specification to Claude...", type: "info" });

  const res = await fetch(`${CLAUDE_PROXY}/api/build`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });

  if (!res.ok) {
    return handleErrorResponse(res);
  }

  onChunk({ message: "Parsing generated files...", type: "info" });

  const result: BuildResponse = await res.json();

  if (result.files && result.files.length > 0) {
    onChunk({
      message: `Generated ${result.files.length} file(s)`,
      type: "success",
    });
  }

  return result;
}

export function isConfigured(): boolean {
  return !!CLAUDE_PROXY;
}
