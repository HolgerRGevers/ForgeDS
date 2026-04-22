import type { Plugin } from "vite";

// Dev-only plugin: mocks the 4 Claude proxy endpoints used by the wizard.
// Returns shapes that satisfy the client-side parsers (brainstorming.ts,
// multi-agent.ts, data-ingestion.ts). Responses are canned and deterministic;
// good enough for end-to-end wizard testing in development.
export function mockClaudeProxy(): Plugin {
  return {
    name: "forgeds-mock-claude-proxy",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use(async (req, res, next) => {
        if (!req.url) return next();

        // Only intercept the four proxy endpoints.
        if (
          !req.url.startsWith("/api/brainstorm/") &&
          !req.url.startsWith("/api/agent") &&
          !req.url.startsWith("/api/data-analyze")
        ) {
          return next();
        }

        const body = await readJsonBody(req);

        if (req.url.startsWith("/api/brainstorm/opener")) {
          return sendJson(res, 200, {
            gist: gistFromIdea((body?.coreIdea as string) ?? "your app"),
          });
        }

        if (req.url.startsWith("/api/brainstorm/questions")) {
          return sendJson(res, 200, buildQuestionBatch(body));
        }

        if (req.url.startsWith("/api/agent")) {
          const role = (body?.role as string) ?? "";
          return sendJson(res, 200, {
            text: `[mock-${role.slice(0, 20)}] Draft spec based on the supplied inputs. This is a deterministic dev-only response.\n\nDIVERGENCES:\n- example divergence point\n`,
          });
        }

        if (req.url.startsWith("/api/data-analyze")) {
          return sendJson(res, 200, buildDataAnalysis(body));
        }

        next();
      });
    },
  };
}

function readJsonBody(
  req: import("http").IncomingMessage,
): Promise<Record<string, unknown> | null> {
  return new Promise((resolve) => {
    const chunks: Buffer[] = [];
    req.on("data", (c: Buffer) => chunks.push(c));
    req.on("end", () => {
      if (chunks.length === 0) return resolve(null);
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString("utf8")) as Record<string, unknown>);
      } catch {
        resolve(null);
      }
    });
  });
}

function sendJson(
  res: import("http").ServerResponse,
  status: number,
  body: unknown,
) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify(body));
}

function gistFromIdea(idea: string): string {
  const snippet = idea.replace(/\s+/g, " ").trim().slice(0, 80);
  return snippet ? `an app for "${snippet}"` : "this is a solid starting point";
}

function buildQuestionBatch(body: Record<string, unknown> | null) {
  const depth = (body?.depth as string) ?? "light";
  const priorCount = Array.isArray(body?.priorQuestions)
    ? (body?.priorQuestions as unknown[]).length
    : 0;
  const needsSeed = body?.needsFreeTextSeed === true;

  if (needsSeed && priorCount === 0) {
    return {
      questions: [
        {
          kind: "free-text",
          id: "seed-1",
          stem: "What's the most painful part of how this is done today?",
          context: "One sentence is enough.",
          placeholder: "e.g. I lose track of which claims are waiting for me to approve",
        },
      ],
      done: false,
    };
  }

  // Paired questions. Count depends on depth.
  const target = depth === "light" ? 3 : depth === "mid" ? 5 : 8;
  const remaining = Math.max(0, target - priorCount);
  const batchSize = Math.min(remaining, 3);

  if (batchSize === 0) {
    return { questions: [], done: true };
  }

  const questions = Array.from({ length: batchSize }).map((_, i) => ({
    kind: "paired",
    id: `q-${priorCount + i + 1}`,
    stem: `Mock paired question ${priorCount + i + 1}`,
    context: "Mock context from the dev-only middleware.",
    optionA: {
      title: "Option A",
      reason: "Simpler to build.",
      consequence: "Less flexible later.",
    },
    optionB: {
      title: "Option B",
      reason: "More robust.",
      consequence: "Takes longer to ship.",
    },
    aiPreference: i % 2 === 0 ? "A" : "B",
  }));

  return { questions, done: priorCount + batchSize >= target };
}

function buildDataAnalysis(body: Record<string, unknown> | null) {
  const parsed = Array.isArray(body?.parsed)
    ? (body?.parsed as Record<string, unknown>[])
    : [];
  const csvFiles = parsed.filter((p) => p.kind === "csv");
  return {
    entities: csvFiles.map((p) => {
      const preview = (p.preview as Record<string, unknown>) ?? {};
      const cols = Array.isArray(preview.columns) ? (preview.columns as string[]) : [];
      return {
        name: (p.filename as string).replace(/\.csv$/i, ""),
        sourceFile: p.filename as string,
        fields: cols.map((c) => ({
          name: c,
          type: "text",
          sample: [],
          nullable: true,
        })),
        inferredRules: [],
        relationships: [],
      };
    }),
    observedConstraints: [],
    gaps:
      csvFiles.length === 0
        ? ["No CSV data attached; analysis is empty"]
        : [],
  };
}
