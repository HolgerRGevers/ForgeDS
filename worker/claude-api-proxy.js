/**
 * Cloudflare Worker — Claude API proxy for ForgeDS IDE.
 *
 * Proxies prompt refinement and code generation requests to the
 * Anthropic Claude API. Keeps the API key server-side.
 *
 * Environment variables (set via `npx wrangler secret put`):
 *   ANTHROPIC_API_KEY — Anthropic API key
 *
 * Endpoints:
 *   POST /api/refine  — Analyze prompt, return structured sections
 *   POST /api/build   — Generate code files (SSE stream)
 */

const ANTHROPIC_API = "https://api.anthropic.com/v1/messages";
const MODEL = "claude-sonnet-4-20250514";
const MAX_TOKENS_REFINE = 4096;
const MAX_TOKENS_BUILD = 16384;

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

// ── System Prompts ───────────────────────────────────────────────────────

const REFINE_SYSTEM = `You are a Zoho Creator application architect. Your job is to analyze a user's natural-language request and break it down into a structured specification for a Zoho Creator application.

Return ONLY valid JSON (no markdown fences, no explanation) matching this schema:

{
  "sections": [
    {
      "id": "string",
      "title": "string",
      "icon": "emoji",
      "content": "Description of this section",
      "items": ["Specific item 1", "Specific item 2"],
      "isEditable": true
    }
  ],
  "planSteps": ["Step 1 description", "Step 2 description"]
}

Always include these section categories (skip if not applicable):
1. **Forms & Fields** (id: "forms") — Creator forms with their fields, field types, and validation rules
2. **Deluge Workflows** (id: "workflows") — On-submit, on-edit, scheduled, and custom function scripts
3. **Reports & Views** (id: "reports") — List reports, calendar views, pivot tables, dashboards
4. **Integrations** (id: "integrations") — API calls, Zoho CRM/Books/Invoice connections, webhooks
5. **Configuration** (id: "config") — Roles, permissions, email notifications, page layouts

For planSteps, provide 4-6 high-level implementation steps.

The items in each section should be specific, actionable deliverables — not vague descriptions. Use Zoho Creator terminology (forms, fields, Deluge functions, reports, connections).`;

const BUILD_SYSTEM = `You are a Zoho Creator / Deluge code generator. Given a structured specification of a Zoho Creator application, generate production-ready code files.

You MUST return ONLY valid JSON (no markdown fences, no explanation) matching this schema:

{
  "files": [
    {
      "name": "filename.dg",
      "path": "src/deluge/filename.dg",
      "content": "// Full file content here",
      "language": "deluge"
    }
  ]
}

File types to generate:
- **.dg** files for Deluge scripts (workflows, custom functions, validations)
- **.yaml** files for form/field definitions
- **.json** files for report configurations and connections
- **.ds** files for ForgeDS schema definitions

Deluge code guidelines:
- Use proper Zoho Creator Deluge syntax (v2)
- Include error handling with try/catch
- Use info statements for debugging
- Follow naming conventions: snake_case for variables, PascalCase for form names
- Add comments explaining business logic
- Use zoho.crm.*, zoho.books.*, zoho.invoice.* APIs where appropriate
- Include input validation on form submissions
- Use proper data types (text, number, date, datetime, email, etc.)

Generate complete, runnable files — not stubs or placeholders.`;

// ── Auth ──────────────────────────────────────────────────────────────────

async function validateGitHubToken(token) {
  try {
    const res = await fetch("https://api.github.com/user", {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "ForgeDS-Worker",
      },
    });
    return res.ok;
  } catch {
    return false;
  }
}

// ── Handlers ─────────────────────────────────────────────────────────────

async function handleRefine(body, apiKey) {
  const { prompt, files, repoContext, mode } = body;

  let userMessage = `User request: ${prompt}`;
  if (files && files.length > 0) {
    userMessage += `\n\nAttached files: ${files.join(", ")}`;
  }
  if (repoContext && repoContext.length > 0) {
    userMessage += "\n\nRepository context:";
    for (const ctx of repoContext) {
      userMessage += `\n--- ${ctx.path} (from ${ctx.source}) ---\n${ctx.content}\n`;
    }
  }
  if (mode) {
    userMessage += `\n\nMode: ${mode}`;
  }

  const res = await fetch(ANTHROPIC_API, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: MAX_TOKENS_REFINE,
      system: REFINE_SYSTEM,
      messages: [{ role: "user", content: userMessage }],
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Anthropic API ${res.status}: ${err}`);
  }

  const data = await res.json();
  const text = data.content?.[0]?.text ?? "{}";

  // Parse JSON from response (handle potential markdown fences)
  const cleaned = text.replace(/^```json?\n?/, "").replace(/\n?```$/, "").trim();
  return JSON.parse(cleaned);
}

async function handleBuild(body, apiKey) {
  const { sections, prompt } = body;

  let userMessage = `Generate all code files for this Zoho Creator application:\n\n`;
  if (prompt) {
    userMessage += `Original prompt: ${prompt}\n\n`;
  }
  userMessage += `Specification:\n${JSON.stringify(sections, null, 2)}`;

  // Use streaming to prevent Cloudflare 524 timeout on long generations.
  // We accumulate the full text server-side, then send the parsed JSON
  // as one final SSE event once Claude finishes.
  const res = await fetch(ANTHROPIC_API, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: MAX_TOKENS_BUILD,
      stream: true,
      system: BUILD_SYSTEM,
      messages: [{ role: "user", content: userMessage }],
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Anthropic API ${res.status}: ${err}`);
  }

  const encoder = new TextEncoder();

  // Read the entire stream, accumulate text, send keepalive pings
  const { readable, writable } = new TransformStream();
  const writer = writable.getWriter();

  // Process stream in background
  (async () => {
    try {
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = "";
      let buffer = "";
      let chunkCount = 0;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6).trim();
          if (!payload || payload === "[DONE]") continue;

          try {
            const event = JSON.parse(payload);

            if (event.type === "content_block_delta" && event.delta?.text) {
              accumulated += event.delta.text;
              chunkCount++;

              // Send keepalive progress every 30 chunks (~every few seconds)
              if (chunkCount % 30 === 0) {
                const msg = chunkCount < 60
                  ? "Generating form definitions..."
                  : chunkCount < 120
                    ? "Writing Deluge workflows..."
                    : chunkCount < 180
                      ? "Creating report configurations..."
                      : "Finalizing code generation...";
                await writer.write(
                  encoder.encode(`data: ${JSON.stringify({ message: msg, type: "info" })}\n\n`),
                );
              }
            }
          } catch {
            // skip unparseable
          }
        }
      }

      // Done — parse the accumulated text
      const cleaned = accumulated
        .replace(/^[\s\S]*?```json\s*\n?/, "")
        .replace(/\n?\s*```[\s\S]*$/, "")
        .trim();

      let result;
      try {
        result = JSON.parse(cleaned || accumulated);
      } catch {
        try {
          result = JSON.parse(accumulated);
        } catch {
          result = {
            files: [{
              name: "generated_code.dg",
              path: "src/deluge/generated_code.dg",
              content: accumulated,
              language: "deluge",
            }],
          };
        }
      }

      if (!result.files || !Array.isArray(result.files)) {
        result = {
          files: [{
            name: "generated_code.dg",
            path: "src/deluge/generated_code.dg",
            content: accumulated,
            language: "deluge",
          }],
        };
      }

      // Send final result
      await writer.write(
        encoder.encode(`data: ${JSON.stringify({ done: true, ...result })}\n\n`),
      );
    } catch (err) {
      await writer.write(
        encoder.encode(`data: ${JSON.stringify({ error: err.message || "Build failed" })}\n\n`),
      );
    } finally {
      await writer.close();
    }
  })();

  return new Response(readable, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      ...CORS_HEADERS,
    },
  });
}

// ── Main ─────────────────────────────────────────────────────────────────

export default {
  async fetch(request, env) {
    // CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method !== "POST") {
      return new Response("Method not allowed", {
        status: 405,
        headers: CORS_HEADERS,
      });
    }

    // Validate paths
    if (path !== "/api/refine" && path !== "/api/build") {
      return new Response("Not found", {
        status: 404,
        headers: CORS_HEADERS,
      });
    }

    // Auth: require valid GitHub token
    const authHeader = request.headers.get("Authorization") ?? "";
    const ghToken = authHeader.replace("Bearer ", "");
    if (!ghToken) {
      return new Response(
        JSON.stringify({ error: "Authorization required" }),
        { status: 401, headers: { "Content-Type": "application/json", ...CORS_HEADERS } },
      );
    }

    const isValid = await validateGitHubToken(ghToken);
    if (!isValid) {
      return new Response(
        JSON.stringify({ error: "Invalid or expired GitHub token" }),
        { status: 401, headers: { "Content-Type": "application/json", ...CORS_HEADERS } },
      );
    }

    // Parse body
    let body;
    try {
      body = await request.json();
    } catch {
      return new Response(
        JSON.stringify({ error: "Invalid JSON body" }),
        { status: 400, headers: { "Content-Type": "application/json", ...CORS_HEADERS } },
      );
    }

    try {
      if (path === "/api/refine") {
        const result = await handleRefine(body, env.ANTHROPIC_API_KEY);
        return new Response(JSON.stringify(result), {
          headers: { "Content-Type": "application/json", ...CORS_HEADERS },
        });
      }

      if (path === "/api/build") {
        return await handleBuild(body, env.ANTHROPIC_API_KEY);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Internal error";
      const status = message.includes("401") ? 401 : message.includes("429") ? 429 : 500;
      return new Response(
        JSON.stringify({ error: message }),
        { status, headers: { "Content-Type": "application/json", ...CORS_HEADERS } },
      );
    }
  },
};
