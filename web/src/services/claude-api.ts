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

export interface RefinedSectionRaw {
  id: string;
  title: string;
  icon: string;
  content: string;
  items: string[];
  isEditable: boolean;
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
  if (import.meta.env.DEV) return;
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

export async function buildProject(
  token: string,
  data: BuildRequest,
  onChunk: (chunk: BuildChunk) => void,
): Promise<BuildResponse> {
  ensureConfigured();

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

  // Read SSE stream with proper line buffering
  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response stream");

  const decoder = new TextDecoder();
  let buffer = "";
  let finalResult: BuildResponse = { files: [] };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Split on double-newline (SSE event boundary)
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const event of events) {
      for (const line of event.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        const payload = line.slice(6).trim();
        if (!payload) continue;

        try {
          const chunk = JSON.parse(payload) as BuildChunk & { error?: string };

          if (chunk.error) {
            throw new Error(chunk.error);
          }

          if (chunk.done && chunk.files) {
            finalResult = { files: chunk.files };
            onChunk({
              message: `Generated ${chunk.files.length} file(s)`,
              type: "success",
            });
          } else if (chunk.message) {
            onChunk(chunk);
          }
        } catch (err) {
          if (err instanceof Error && err.message !== "Unexpected end of JSON input") {
            throw err;
          }
        }
      }
    }
  }

  return finalResult;
}

export function isConfigured(): boolean {
  return !!CLAUDE_PROXY;
}
