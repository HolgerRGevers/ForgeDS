# ForgeDS Widgets Phase 2 — Multi-Agent Orchestration Design (DRAFT for user review)

**Date:** 2026-04-23
**Status:** Draft — produced by architect-agent blueprint pass, awaits user approval before a plan is written.
**Relationship:** Master orchestration contract. Phases 2A (contract), 2C (build), and 2D (IDE) reference this doc. Phase 2B (runtime) is consumed by the `worker/runtime-verifier` role but otherwise unchanged.
**Depends on:** Phase 1, Phase 2A, 2B, 2C, 2D (see `docs/superpowers/specs/`).
**JS SDK reference:** `@anthropic-ai/claude-agent-sdk` (TypeScript).

---

## 1. Problem statement

Phase 2D wires a single agent into the IDE through a tool-use loop. That model works for
bounded prompts ("lint this file", "scaffold this form") but collapses under realistic
end-to-end requests such as *"build me an expense-tracking app with approval workflow"*.
A single-agent loop has three structural failures for that class of work:

1. **Context saturation.** One agent holding the full intent plus every file read,
   lint result, scaffolder output, and runtime trace blows past useful context windows
   long before the task finishes. The agent starts dropping early constraints.
2. **No planning/execution split.** The agent makes plan and edit decisions in the
   same turn. If the plan is wrong, the user sees it only after files have moved.
3. **No cost tiering.** Every turn uses the same model tier. Cheap mechanical
   work (running a linter, verifying a widget, scaffolding from a template) is
   billed at the same rate as architectural reasoning.

This spec replaces the single-agent loop from 2D with an **architect → orchestrator →
workers** system powered by the Claude Agent SDK. The architect produces a BuildPlan,
the orchestrator dispatches workers according to the plan's dependency graph, and each
worker runs at the lowest model tier that fits its role. The user sees the plan before
any file is written and keeps a hard budget cap across the whole session.

Non-goal in this phase: multi-user/shared orchestration, cross-session mid-worker resume,
a third-party worker plugin system. See §19.

## 2. Architecture overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  USER  ──────────  prompt: "build expense-tracking app"                      │
│                                                                              │
│  [natural language intent]                                                   │
└─────────────────────────┬────────────────────────────────────────────────────┘
                          │  HTTP POST /api/agent — { prompt, sessionId }
                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  IDE (React SPA, port 5173)                                                 │
│  BuildPlanPreview panel ────── shows architect output before dispatch       │
│  AgentRun panel ─────────────  tree view: architect + workers, live status  │
│  ConsolePanel AI Build Log ──  tool-call trace per worker                   │
│  aiOrchestrationStore ──────── BuildSession, WorkerStatus[], BuildPlan      │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │  ws://localhost:9876
                                   │  msg type: orchestrator:plan:submit
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Bridge backend (Python / WS router)                                        │
│  Forwards orchestrator:* messages to Node Orchestrator Service              │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │  HTTP POST http://127.0.0.1:9878/orchestrate
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  NODE ORCHESTRATOR SERVICE  (port 9878)                                     │
│  Step 1 — spawn Architect agent via SDK query()                             │
│  Step 2 — await user approval (or auto-proceed on fast-path)                │
│  Step 3 — WorkerDispatch loop (topologically sorted tasks)                  │
│  Step 4 — emit orchestrator:session:done  { summary }                       │
└───────────────────┬──────────────┬──────────────────────────────────────────┘
                    │              │  SDK subagent spawns
                    │              │  (see Agent Roster)
                    ▼              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  FORGEDS MCP SERVER  (Node, stdio)  — createSdkMcpServer()                  │
│  Tools: forgeds_lint_app, forgeds_lint_file, forgeds_scaffold_form,         │
│         forgeds_scaffold_widget, forgeds_verify_runtime, forgeds_bundle_app,│
│         forgeds_read_file, forgeds_write_file, forgeds_status               │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │  Diagnostic[]
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  DIAGNOSTIC AGGREGATOR  (inside Orchestrator Service)                       │
│  Merges envelopes, adds agent: { id, role, model }, broadcasts to IDE       │
└─────────────────────────────────────────────────────────────────────────────┘
```

Four-tier architecture:

- **IDE (React)** owns user-facing state and the two new panels.
- **Python bridge** remains the single WebSocket endpoint the IDE talks to; it
  forwards `orchestrator:*` messages to the Node service over loopback HTTP.
- **Node Orchestrator Service** owns the SDK, hosts the MCP server, runs the
  dispatch loop, and aggregates diagnostics.
- **Python ForgeDS CLIs** (`forgeds-lint`, `forgeds-scaffold-*`,
  `forgeds-verify-runtime`, `forgeds-bundle-app`) are invoked by the MCP server
  as subprocesses and are otherwise unchanged.

The Node service is a new deliverable; the Python CLIs and bridge already exist.

## 3. Agent roster

Nine agents. Only the architect runs at capable tier; all workers are cheap
or standard. This is the primary cost lever.

| Agent ID | Role | Model Tier | Tool Allowlist | System-Prompt Theme |
|---|---|---|---|---|
| `architect/build-plan` | Produces BuildPlan from user intent + repo snapshot | capable | `forgeds_status`, `forgeds_read_file`, `forgeds_lint_app` | You produce a BuildPlan JSON; you never implement. |
| `worker/deluge-author` | Writes `.dg` Deluge scripts and edits `.ds` forms | standard | `forgeds_read_file`, `forgeds_write_file`, `forgeds_scaffold_form`, `forgeds_lint_file` | Write idiomatic Deluge, honor `.ds` gotchas, exact link-names. |
| `worker/widget-author` | Writes `index.js`/`.html`/`.css` widget implementation | standard | `forgeds_read_file`, `forgeds_write_file`, `forgeds_lint_file`, `forgeds_verify_runtime` | Write minimal widget JS; never embed credentials; use generated stubs. |
| `worker/linter` | Runs aggregate lint; interprets findings; produces remediation instructions | cheap | `forgeds_lint_app`, `forgeds_lint_file`, `forgeds_status`, `forgeds_read_file` | Produce explicit, file-attributed remediation instructions. |
| `worker/runtime-verifier` | Executes runtime verification, interprets WGR diagnostics | cheap | `forgeds_verify_runtime`, `forgeds_read_file` | Run every widget; return verdict with full context. |
| `worker/scaffold-gen` | Generates `widget-spec.yaml`; calls scaffold CLI | cheap | `forgeds_scaffold_widget`, `forgeds_write_file`, `forgeds_read_file` | Produce valid `widget-spec.yaml` + invoke scaffolder. |
| `worker/bundler` | Calls bundle CLI; interprets ZET output | cheap | `forgeds_bundle_app`, `forgeds_read_file` | Execute bundle; surface ZET errors as diagnostics; never proceed to deploy. |
| `worker/typegen` | Refreshes `_generated/` stubs from custom_apis | cheap | `forgeds_read_file`, `forgeds_write_file` (scoped to `_generated/`), `forgeds_lint_file` | Keep generated stubs in sync; never touch hand-authored code. |
| `worker/ds-reader` | Read-only inspection of `.ds` — form names, field link names | cheap | `forgeds_read_file`, `forgeds_lint_app` (scope=deluge) | Extract authoritative field link names; do not write. |

Notes:
- `worker/ds-reader` exists because the `.ds` file-format gotchas in `CLAUDE.md`
  (case-sensitive link names, `action_1` vs `Action`, etc.) burn cycles when
  every author agent has to re-derive them. One cheap read pass produces a
  canonical field-map that downstream workers consume as `inputs`.
- `worker/typegen` never touches hand-authored code. It's scoped by `canUseTool`
  to writes under `_generated/` only (see §8.3).
- Deploy is not a worker role. Deploy remains IDE-user-initiated (§13).

## 4. BuildPlan schema

### 4.1 TypeScript interfaces

```typescript
interface BuildPlan {
  version: "1";
  prompt: string;
  created_at: string;
  session_id: string;
  tasks: BuildTask[];
  edges: DependencyEdge[];
  estimated_tool_calls: number;
}

interface BuildTask {
  id: string;
  description: string;
  worker: string;  // Agent ID
  inputs: Record<string, unknown>;
  pass_criteria: PassCriteria;
  fallback: FallbackAction;
  estimated_turns: number;
}

interface DependencyEdge { from: string; to: string; }

interface PassCriteria {
  lint_clean?: boolean;
  runtime_passed?: boolean;
  files_written?: string[];
  no_new_errors?: boolean;
}

interface FallbackAction {
  on_blocked: "replan" | "escalate" | "skip";
  message: string;
}
```

`PassCriteria` fields are ANDed together; any declared criterion that is not
satisfied by the worker's terminal state fails the task. `no_new_errors` is
defined relative to the baseline snapshot captured by `task/baseline-lint`
(or an empty baseline if no such task exists).

### 4.2 Example: expense-tracking app

This is a realistic architect output for the user prompt *"build an
expense-tracking app with approval workflow"*. Note the two `scaffold-*-form`
tasks dispatch in parallel (both depend only on `baseline-lint`), exercising
the bulk `dispatch-all` path from Phase 1 plan line 143.

```json
{
  "version": "1",
  "prompt": "build an expense-tracking app with approval workflow",
  "created_at": "2026-04-23T18:00:00Z",
  "session_id": "sess_architect_01abc",
  "estimated_tool_calls": 34,
  "tasks": [
    { "id": "task/baseline-lint", "description": "Run baseline lint", "worker": "worker/linter", "inputs": { "scope": "all" }, "pass_criteria": { "no_new_errors": true }, "fallback": { "on_blocked": "escalate", "message": "Repo has pre-existing lint errors." }, "estimated_turns": 2 },
    { "id": "task/scaffold-claim-form", "description": "Scaffold expense_claim form", "worker": "worker/deluge-author", "inputs": { "form_name": "expense_claim", "fields": ["merchant_account","amount","category","receipt_file","status"] }, "pass_criteria": { "files_written": ["app.ds"], "lint_clean": true }, "fallback": { "on_blocked": "replan", "message": "Form scaffold blocked." }, "estimated_turns": 5 },
    { "id": "task/scaffold-approval-form", "description": "Scaffold expense_approval form", "worker": "worker/deluge-author", "inputs": { "form_name": "expense_approval", "fields": ["claim_ref","approver_notes","decision"] }, "pass_criteria": { "files_written": ["app.ds"], "lint_clean": true }, "fallback": { "on_blocked": "replan", "message": "Approval form blocked." }, "estimated_turns": 5 },
    { "id": "task/lint-after-forms", "description": "Lint after both forms", "worker": "worker/linter", "inputs": { "scope": "all" }, "pass_criteria": { "lint_clean": true }, "fallback": { "on_blocked": "escalate", "message": "Lint errors remain." }, "estimated_turns": 3 },
    { "id": "task/scaffold-dashboard-widget", "description": "Generate widget-spec.yaml + scaffold", "worker": "worker/scaffold-gen", "inputs": { "widget_name": "expense_dashboard", "consumes_apis": ["get_pending_claims","approve_claim"], "location": "standalone", "state_model": ["pendingList","selectedClaim"] }, "pass_criteria": { "files_written": ["src/widgets/expense_dashboard/index.js"] }, "fallback": { "on_blocked": "escalate", "message": "Widget scaffold blocked." }, "estimated_turns": 3 },
    { "id": "task/implement-dashboard-widget", "description": "Implement widget JS", "worker": "worker/widget-author", "inputs": { "widget": "expense_dashboard" }, "pass_criteria": { "lint_clean": true, "runtime_passed": true }, "fallback": { "on_blocked": "replan", "message": "Widget implementation blocked." }, "estimated_turns": 8 },
    { "id": "task/runtime-verify-dashboard", "description": "Runtime-verify dashboard", "worker": "worker/runtime-verifier", "inputs": { "widget_id": "expense_dashboard" }, "pass_criteria": { "runtime_passed": true }, "fallback": { "on_blocked": "escalate", "message": "Widget runtime verification failed." }, "estimated_turns": 2 },
    { "id": "task/bundle", "description": "Bundle widgets to dist/", "worker": "worker/bundler", "inputs": { "widget": "expense_dashboard" }, "pass_criteria": { "files_written": ["dist/widgets/expense_dashboard-0.0.1.zip"] }, "fallback": { "on_blocked": "escalate", "message": "Bundle failed." }, "estimated_turns": 2 }
  ],
  "edges": [
    { "from": "task/baseline-lint", "to": "task/scaffold-claim-form" },
    { "from": "task/baseline-lint", "to": "task/scaffold-approval-form" },
    { "from": "task/scaffold-claim-form", "to": "task/lint-after-forms" },
    { "from": "task/scaffold-approval-form", "to": "task/lint-after-forms" },
    { "from": "task/lint-after-forms", "to": "task/scaffold-dashboard-widget" },
    { "from": "task/scaffold-dashboard-widget", "to": "task/implement-dashboard-widget" },
    { "from": "task/implement-dashboard-widget", "to": "task/runtime-verify-dashboard" },
    { "from": "task/runtime-verify-dashboard", "to": "task/bundle" }
  ]
}
```

`estimated_tool_calls: 34` against a session budget of 80 (§14) leaves headroom
for a single replan cycle.

## 5. Orchestrator service specification

### 5.1 Node service file layout

```
tools/orchestrator/
├── src/
│   ├── index.ts                 # HTTP server entry (port 9878)
│   ├── orchestrator.ts          # Main dispatch loop
│   ├── worker-registry.ts       # workerId ↔ session_id state
│   ├── build-plan-executor.ts   # Topological sort + batch dispatch
│   ├── diagnostic-aggregator.ts # Merge + annotate with agent:
│   ├── hooks/
│   │   ├── pre-tool-use.ts      # Allowlist enforcement
│   │   └── post-tool-use.ts     # Diagnostic ingestion
│   ├── agents/
│   │   ├── architect.ts         # Architect agent prompt + options
│   │   ├── worker-definitions.ts # AgentDefinition per worker role
│   │   └── system-prompts/      # .md files, one per role
│   ├── mcp/
│   │   └── forgeds-mcp-server.ts # createSdkMcpServer + all tools
│   └── persistence/
│       └── session-store.ts     # .forgeds/orchestration-session.json
└── package.json                 # depends on @anthropic-ai/claude-agent-sdk
```

The service is a single Node process. It speaks HTTP to the Python bridge
(loopback only, port 9878) and stdio to its child MCP server. It is started
and stopped by the bridge under the same lifecycle as the IDE.

### 5.2 HTTP API surface

| Method | Path | Purpose |
|---|---|---|
| POST | `/orchestrate` | Start a new session. Body: `{ prompt, repoRoot, sessionId? }`. Returns `{ sessionId }` and begins streaming events back via the bridge's WS. |
| GET | `/status/:sessionId` | Snapshot of `{ activeBuildPlan, workerStates, diagnosticsAggregate, totalToolCalls }`. |
| POST | `/abort/:sessionId` | Terminate the session; cascade-abort all in-flight workers. |
| GET | `/health` | Liveness check; returns SDK and MCP-server readiness. |

All streaming goes through the existing WS bridge; the HTTP surface is request/response
only. This keeps the IDE's WS protocol as the one place the client cares about.

### 5.3 Worker dispatch loop (pseudocode)

```
function runSession(plan):
    registry = new WorkerRegistry(plan)
    batch   = topologicalRoots(plan)          // tasks whose deps are all DONE
    while batch is not empty:
        results = await dispatchAll(batch)     // SDK query() per task, parallel
        for r in results:
            registry.update(r.workerId, r.status)
            aggregator.ingest(r.diagnostics, r.agent)
            broadcast("orchestrator:worker:status", r)
        if registry.anyAbandonedOverThreshold(0.25):
            return replanRequest()
        batch = registry.readyTasks()          // deps satisfied, not WAITING
        if registry.allDone():
            break
    broadcast("orchestrator:session:done", summary(registry))
```

`dispatchAll` fans out one SDK `query()` per task and awaits all iterators.
`registry.readyTasks()` returns only tasks whose dependencies are DONE or
DONE_WITH_CONCERNS (the latter proceed by default unless `fallback.on_blocked`
is `replan`).

### 5.4 Session registry and persistence model

The worker registry holds, per worker ID:

- `status` — one of the state-machine values in §6
- `sdk_session_id` — from the first `system:init` message of the SDK query
- `tool_call_count` — incremented on every `PostToolUse`
- `transcript` — tool-call records the IDE renders
- `redispatch_count` — for retry/escalation decisions

After every status transition the registry writes to
`<project-root>/.forgeds/orchestration-session.json`. See §11 for what is and
isn't recoverable across IDE reloads.

### 5.5 Dependency graph execution

Tasks form a DAG. Execution is Kahn-style topological: the executor maintains
an in-degree map, starts with all zero-in-degree tasks, and after each task
completes decrements the in-degree of its successors. The zero-in-degree
frontier is dispatched in parallel as a single batch.

Parallel batch semantics:

- All tasks in a batch start simultaneously via `Promise.all([...query(...)])`.
- A BLOCKED task does not cancel its siblings in the same batch; siblings
  finish, then the executor decides BLOCKED-task next action via §6.
- A BLOCKED task *does* mark all downstream tasks WAITING; they are not
  dispatched until the blockage is resolved.
- If more than 25% of total tasks reach ABANDONED, the executor stops,
  emits `orchestrator:escalate:human`, and offers replan.

Cycles in the DAG are a plan-validation error and rejected before dispatch;
the architect is redispatched with the cycle report.

## 6. Orchestrator lifecycle protocol

### 6.1 Verbs

| Verb | Semantics |
|---|---|
| `dispatch(workerId, taskPayload)` | Spawn a worker via SDK `query()` with the worker's AgentDefinition. |
| `await(workerId)` | Block on the SDK iterator until a terminal SDK result. |
| `redispatch(workerId, updatedContext)` | Terminate current session and re-spawn the same worker role with enriched context. |
| `abort(workerId)` | Terminate immediately; mark ABANDONED. |
| `list()` | Return `{workerId → WorkerStatus}` snapshot. |
| `status(workerId)` | Return one worker's current state. |
| `dispatch-all(batch)` | Bulk dispatch a parallel batch; returns when all iterators resolve. |

### 6.2 Worker-status state machine

Maps 1:1 to the Phase 1 plan status table with one new terminal state:

- **DONE** — criteria met; advance. Aggregate diagnostics.
- **DONE_WITH_CONCERNS** — criteria met, but the worker flagged concerns.
  Orchestrator reads concern log and either redispatches with fix context
  or proceeds with a flag on the WorkerStatus.
- **NEEDS_CONTEXT** — worker returned identifying the missing context.
  Orchestrator supplies it (usually from `worker/ds-reader` or the
  aggregator) and redispatches the same workerId.
- **BLOCKED** — worker cannot make progress. Orchestrator diagnoses:
  - context gap → redispatch with supplied context
  - reasoning gap → upgrade model tier (cheap → standard → capable)
  - task too big → split into subtasks, insert into plan
  - plan wrong → `orchestrator:escalate:human`
- **ABANDONED** (new terminal) — after 3 failed redispatches. IDE shows a
  modal with transcript access.

### 6.3 Retry and escalation policy

| Knob | Value |
|---|---|
| Per-worker retry limit | 3 redispatches before ABANDONED |
| Per-session call budget | 80 total tool calls (2× the single-agent 40 from 2D §7) |
| BLOCKED mid-chain dependents | Marked WAITING; independent branches continue |
| Replan trigger | >25% of tasks ABANDONED → full replan request |
| Model tier escalation | cheap → standard → capable before human escalation |

Model tier escalation is scoped to the single worker and single redispatch;
it does not mutate the worker's declared tier for future dispatches.

## 7. JS SDK integration

All primitives come from `@anthropic-ai/claude-agent-sdk` (npm ≥ 0.2.117).

### 7.1 Spawning via `query()`

Every agent — architect and worker — is spawned as a single `query()` call.
Example:

```typescript
const architectSession = query({
  prompt: buildArchitectPrompt(userIntent, repoSnapshot),
  options: {
    allowedTools: ["forgeds_status", "forgeds_read_file", "forgeds_lint_app"],
    permissionMode: "acceptEdits",
    mcpServers: {
      "forgeds": { type: "stdio", command: "node", args: ["dist/forgeds-mcp-server.js"] }
    },
    maxTurns: 10,
    systemPrompt: ARCHITECT_SYSTEM_PROMPT
  }
});
for await (const message of architectSession) {
  if (message.type === "system" && message.subtype === "init") {
    sessionRegistry.set("architect/build-plan", message.session_id);
  }
  if ("result" in message) {
    buildPlan = JSON.parse(message.result);
  }
}
```

### 7.2 Pre-warming

`startup()` from the SDK is called when the IDE loads a project, before the
user types anything. This cuts architect cold-start latency from 3–8 s to
1–3 s on the first real prompt. Pre-warming runs the MCP server stdio
handshake and warms an empty agent context; no user data is sent.

### 7.3 Tool definitions via `createSdkMcpServer()` + `tool()`

Each ForgeDS CLI becomes an MCP tool in `forgeds-mcp-server.ts`. Workers
reference the server by its string name (`"forgeds"`) in their
`AgentDefinition.mcpServers`. Full tool catalog:

| Tool | readOnlyHint | destructiveHint |
|---|---|---|
| `forgeds_lint_app` | true | — |
| `forgeds_lint_file` | true | — |
| `forgeds_scaffold_form` | — | true |
| `forgeds_scaffold_widget` | — | true |
| `forgeds_verify_runtime` | true | — |
| `forgeds_bundle_app` | true | — (produces artifact, doesn't mutate source) |
| `forgeds_read_file` | true | — |
| `forgeds_write_file` | — | true |
| `forgeds_status` | true | — |

### 7.4 `PreToolUse` and `PostToolUse` hooks

`PreToolUse` enforces per-worker allowlist beyond the SDK's `allowedTools`
(second defense). A read-only worker attempting a write tool receives
`permissionDecision: "deny"` with a message identifying the worker role.

`PostToolUse` feeds the diagnostic aggregator. Every tool result with a
`diagnostics:` field is parsed, annotated with `agent: { id, role, model, session_id }`,
and broadcast on `orchestrator:diagnostics:batch`.

### 7.5 Partial-message streaming

`includePartialMessages: true` surfaces `SDKPartialAssistantMessage` events.
These are forwarded as `orchestrator:worker:stream` WS events so the AgentRun
panel can render live tool-call traces without waiting for worker completion.

### 7.6 Permission modes per worker

| Worker | `permissionMode` |
|---|---|
| architect/build-plan | `acceptEdits` (read-only by allowlist) |
| worker/deluge-author | `default` (`canUseTool` gates `.ds` writes) |
| worker/widget-author | `default` (`canUseTool` blocks `_generated/`) |
| worker/linter | `acceptEdits` |
| worker/runtime-verifier | `acceptEdits` |
| worker/scaffold-gen | `default` (`canUseTool` blocks overwrite without `--force`) |
| worker/bundler | `acceptEdits` |
| worker/typegen | `default` (`canUseTool` restricts to `_generated/`) |
| worker/ds-reader | `acceptEdits` |

`acceptEdits` means the worker's declared tool allowlist is trusted without
per-call prompts; `default` routes the tool call through `canUseTool` for
path/scope validation.

### 7.7 What the SDK does NOT provide

The orchestrator implements these itself:

1. Deterministic stable worker ID tracking (SDK provides `session_id`;
   orchestrator maintains `workerId → session_id` registry).
2. Cross-agent diagnostic aggregation with `agent:` annotation.
3. BuildPlan dependency graph execution (topological sort, parallel batch,
   WAITING states, replan triggers).
4. Session persistence across IDE reload (SDK `resume: sessionId` works
   only within a single Node process).
5. Per-worker tool allowlist enforcement via `PreToolUse` hook.

## 8. MCP server specification

### 8.1 `forgeds-mcp-server.ts` tool definitions

One `createSdkMcpServer()` instance named `"forgeds"` over stdio. Nine tools,
each a thin wrapper over the corresponding Python CLI:

| Tool | Description (summary) | Input schema (summary) |
|---|---|---|
| `forgeds_lint_app` | Run project-wide lint across `.ds`/`.dg`/widgets/SQL. | `{ scope?: "all"\|"deluge"\|"widgets"\|"access" }` |
| `forgeds_lint_file` | Lint a single file by path. | `{ path: string }` |
| `forgeds_scaffold_form` | Scaffold a new `.ds` form + stub Deluge scripts. | `{ form_name: string, fields: string[], section?: string }` |
| `forgeds_scaffold_widget` | Run `forgeds-scaffold-widget` from a spec. | `{ spec_path: string, force?: boolean }` |
| `forgeds_verify_runtime` | Execute Phase 2B runtime verification for one widget. | `{ widget_id: string }` |
| `forgeds_bundle_app` | Produce `dist/widgets/<name>-<version>.zip`. | `{ widget: string }` |
| `forgeds_read_file` | Read a file from the project root. | `{ path: string }` |
| `forgeds_write_file` | Write a file under the project root. | `{ path: string, content: string, overwrite?: boolean }` |
| `forgeds_status` | Return repo snapshot: forms, widgets, custom APIs, last lint summary. | `{}` |

All tool outputs conform to the Phase 2A v1 envelope plus the `agent` field
from §9 (injected by the orchestrator's `PostToolUse` hook, not by the tool
itself).

Deploy-class tools (`forgeds_deploy_zoho`, any `*deploy*`) are **not** in this
MCP server. See §13.

### 8.2 Per-worker tool allowlists

The allowlist column in §3 is the authoritative list. Summarised:

| Worker | Allowlist |
|---|---|
| architect/build-plan | `forgeds_status`, `forgeds_read_file`, `forgeds_lint_app` |
| worker/deluge-author | `forgeds_read_file`, `forgeds_write_file`, `forgeds_scaffold_form`, `forgeds_lint_file` |
| worker/widget-author | `forgeds_read_file`, `forgeds_write_file`, `forgeds_lint_file`, `forgeds_verify_runtime` |
| worker/linter | `forgeds_lint_app`, `forgeds_lint_file`, `forgeds_status`, `forgeds_read_file` |
| worker/runtime-verifier | `forgeds_verify_runtime`, `forgeds_read_file` |
| worker/scaffold-gen | `forgeds_scaffold_widget`, `forgeds_write_file`, `forgeds_read_file` |
| worker/bundler | `forgeds_bundle_app`, `forgeds_read_file` |
| worker/typegen | `forgeds_read_file`, `forgeds_write_file` (scoped), `forgeds_lint_file` |
| worker/ds-reader | `forgeds_read_file`, `forgeds_lint_app` |

### 8.3 `canUseTool` and `PreToolUse` hook implementations

`canUseTool` fires on every tool invocation when `permissionMode` is
`default`. It performs path- and scope-level checks that the SDK's
`allowedTools` cannot express:

- `worker/widget-author` attempting to write under `src/_generated/` → deny.
- `worker/typegen` attempting to write outside `src/_generated/` → deny.
- `worker/scaffold-gen` invoking `forgeds_scaffold_widget` on an existing
  widget without `force: true` → deny.
- `worker/deluge-author` writing to a file outside `app.ds`, `.dg`, or a
  `_generated/` stub it owns → deny.

`PreToolUse` is a second defense layer, run for all workers regardless of
`permissionMode`. It consults an orchestrator-owned
`workerId → allowedToolSet` map and denies any tool not in that set. This
guards against a worker being spawned with a misconfigured
`AgentDefinition.tools`.

## 9. Diagnostic provenance

The Phase 2A v1 envelope gains an optional `agent` field per diagnostic.
The envelope version does not bump; direct CLI invocations omit the field
and existing IDE renderers continue to work.

Before (Phase 2A direct CLI):

```json
{
  "file": "src/forms/expense_claim.dg",
  "line": 84,
  "rule": "DG014",
  "severity": "error",
  "message": "undefined field 'amount_usdd'"
}
```

After (orchestrator-annotated):

```json
{
  "file": "src/forms/expense_claim.dg",
  "line": 84,
  "rule": "DG014",
  "severity": "error",
  "message": "undefined field 'amount_usdd'",
  "agent": {
    "id": "worker/linter",
    "role": "linter",
    "model": "claude-haiku-4",
    "session_id": "sess_01abc..."
  }
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `agent.id` | string | yes if `agent` present | Stable worker ID |
| `agent.role` | string | yes if `agent` present | Human-readable role |
| `agent.model` | string | yes if `agent` present | Model ID from SDK `ResultMessage` |
| `agent.session_id` | string | no | For cross-referencing transcripts; omit for non-agent CLI invocations |

Backward-compatible: `agent` is optional. The Python `_shared/envelope.py`
serializer is unchanged — provenance is injected by the Node-side aggregator
after the Python CLI returns. This keeps the CLI an independent integration
point for users running ForgeDS outside the IDE.

## 10. Orchestrator ↔ IDE bridge protocol

New WS message family. All flow through the existing Python bridge on
`ws://localhost:9876`; the bridge forwards `orchestrator:*` messages to the
Node service over loopback HTTP and streams responses back.

| Type | Direction | Mode | Purpose |
|---|---|---|---|
| `orchestrator:plan:submit` | IDE → orchestrator | req/res | Submit prompt + repo snapshot. |
| `orchestrator:plan:ready` | orchestrator → IDE | event | BuildPlan is ready for user approval. |
| `orchestrator:plan:approve` | IDE → orchestrator | req/res | User approves; trigger dispatch. |
| `orchestrator:worker:stream` | orchestrator → IDE | event | Live tool-call trace. |
| `orchestrator:worker:status` | orchestrator → IDE | event | Status-machine transition. |
| `orchestrator:diagnostics:batch` | orchestrator → IDE | event | Batch diagnostics with provenance. |
| `orchestrator:escalate:human` | orchestrator → IDE | event | BLOCKED — user input needed. |
| `orchestrator:session:done` | orchestrator → IDE | event | Session complete + summary. |
| `orchestrator:session:abort` | IDE → orchestrator | req/res | User-initiated abort. |

`orchestrator:plan:ready` carries the BuildPlan JSON defined in §4.1.
`orchestrator:escalate:human` carries `{ workerId, reason, transcriptRef,
offeredActions: ["view-transcript","amend-plan","skip-task","abort"] }`.

## 11. Session persistence and resume

`<project-root>/.forgeds/orchestration-session.json` persists per session:

- the approved BuildPlan
- the `workerSessionIds` map (`workerId → sdk_session_id`)
- aggregate diagnostics
- the last WorkerStatus per task
- `totalToolCalls` against the budget

On IDE reload:

- BuildPlanPreview panel reopens showing partial completion, with per-task
  status badges from the persisted record.
- The user may re-dispatch from the last DONE task. The orchestrator
  re-spawns only WAITING and downstream tasks; completed tasks are
  skipped.
- Mid-worker resume (continuing a BLOCKED or mid-turn worker exactly where
  it left off) is **not** supported in v1. The worker is re-spawned from
  the top of the task with the same inputs; the prior transcript is kept
  for reference only. Full mid-worker resume is deferred to Phase 3.

What's lost across reload:
- Live `orchestrator:worker:stream` partial messages prior to reload.
- SDK-internal cache state.
- Any model reasoning scratchpad not surfaced in tool calls.

## 12. Fast-path for trivial prompts

A pure-Node keyword classifier (no LLM, no SDK call) sits in front of the
architect dispatch. Prompts matching `lint|validate|check status|run widget`
bypass the architect and dispatch a single worker directly:

| Keyword pattern | Direct worker |
|---|---|
| `lint` / `validate` | `worker/linter` |
| `check status` | `worker/linter` with `scope=all, dry` |
| `run widget <name>` | `worker/runtime-verifier` |
| `scaffold form <name>` | `worker/scaffold-gen` after short user-prompt form |

This reduces latency from 3–8 s (architect cold-start) to ≈200 ms for the
most common prompts.

Toggle semantics: the BuildPlanPreview panel exposes a **"Build without
reviewing plan"** checkbox. When set, non-trivial prompts still run the
architect but auto-approve its plan. This is orthogonal to the fast-path
classifier, which applies before the architect is considered at all.

Classifier failure mode: if the classifier is uncertain, it defaults to
the architect path. False positives (a prompt matches a keyword but means
something else) are bounded by each fast-path worker's tool allowlist and
by `maxTurns` on the worker session.

## 13. Security model

Deploy-class tools (anything that pushes bits to a live Zoho Creator tenant)
are prohibited from the agent system through three independent layers:

1. **`AgentDefinition.tools`.** Deploy tools are not in any worker's
   allowlist. A misconfiguration at this layer fails closed at the SDK's
   `allowedTools` check.
2. **`PreToolUse` hook.** Orchestrator-owned `workerId → allowedToolSet`
   map re-validates every tool call. A worker spawned with a drifted
   `AgentDefinition.tools` is still denied.
3. **MCP server omission.** `forgeds-mcp-server.ts` does not register any
   deploy tool at all. Even if an attacker bypassed layers 1 and 2, the
   tool name does not resolve at the server.

Deploy remains IDE-user-initiated via a non-agent WS message
`forgeds:cli:deploy`. That message path is unchanged from pre-orchestration
IDE behavior and is authenticated against the user's own credentials as it
was before.

Secondary protections:
- All worker subprocesses run as the same OS user as the IDE; there is no
  privilege boundary below the MCP server. Filesystem writes are bounded
  by `canUseTool` path checks.
- The architect has no write tools. It cannot scaffold or overwrite files
  even transiently.
- Network egress from workers goes through the Anthropic API; there is no
  worker-side HTTP fetch tool in the MCP server.

## 14. Cost model and token-budget guidance

Per-role caps:

| Role | Tier | Max turns | Output token cap | Expected per session |
|---|---|---|---|---|
| `architect/build-plan` | capable | 10 | ~2000 | 1 |
| `worker/linter` | cheap | 5 | ~1500 | 2–4 |
| `worker/runtime-verifier` | cheap | 5 | ~1500 | 1–N (N = widget count) |
| `worker/bundler` | cheap | 5 | ~1000 | 1 per widget |
| `worker/ds-reader` | cheap | 5 | ~1000 | 0–1 |
| `worker/scaffold-gen` | cheap | 5 | ~1500 | 1 per widget |
| `worker/typegen` | cheap | 5 | ~1500 | 0–1 |
| `worker/deluge-author` | standard | 20 | ~4000 | 1 per form |
| `worker/widget-author` | standard | 20 | ~5000 | 1 per widget |

Session-level caps:

- **80 tool calls** total across all workers (2× the single-agent 40 from
  Phase 2D §7). This is the hard budget; hitting it emits
  `orchestrator:escalate:human`.
- Capable tier is only for the architect. If a worker reasoning gap
  triggers a temporary tier upgrade (§6.3), that upgrade is scoped to one
  redispatch of one worker.
- Pre-warming (§7.2) is tracked separately and not billed against the
  session budget, because it runs against an empty context.

Token cost is dominated in practice by `worker/deluge-author` and
`worker/widget-author` (standard tier, 20-turn cap). Keeping those two as
standard rather than capable is the single biggest cost lever; the
BuildPlan dependency graph is designed so upstream cheap workers produce
the exact context those two need, minimising their turn count.

## 15. Testing

Test file names only; implementation in the plan.

- **Orchestrator unit** — `tools/orchestrator/tests/unit/`
  - `worker-registry.test.ts`
  - `build-plan-executor.test.ts`
  - `diagnostic-aggregator.test.ts`
  - `topological-sort.test.ts`
- **MCP integration** — `tools/orchestrator/tests/integration/`
  - `mcp-tool-routing.test.ts`
  - `pre-tool-use-allowlist.test.ts`
  - `can-use-tool-scopes.test.ts`
- **End-to-end** — `tools/orchestrator/tests/e2e/`
  - `e2e-expense-tracking-build.test.ts` — runs the §4.2 plan against a
    fixture repo; asserts all 8 tasks reach DONE or DONE_WITH_CONCERNS
    without exceeding the 80-call budget.
- **Session resume** — `tools/orchestrator/tests/e2e/`
  - `session-resume.test.ts` — kills the Node service mid-session, restarts,
    confirms the executor skips DONE tasks and re-spawns WAITING tasks only.

## 16. Deltas to Phase 2A

Three deltas, documented in `2026-04-23-forgeds-widgets-phase2a-contract-design.md`:

- **Delta 2A-1** — Add optional `agent` field to v1 diagnostic envelope. Injected
  by orchestrator aggregator, not by Python CLIs. Serializer unchanged. §9.
- **Delta 2A-2** — Document that direct CLI invocations omit `agent` and that
  IDE renderers must handle both shapes.
- **Delta 2A-3** — `agent.session_id` is optional and is used only for
  transcript cross-reference; it carries no authority.

## 17. Deltas to Phase 2C

Three deltas, documented in `2026-04-23-forgeds-widgets-phase2c-build-design.md`:

- **Delta 2C-1** — `forgeds-bundle-app` output must be usable as an MCP tool
  result; the `bundle` subcommand's JSON mode is the MCP contract.
- **Delta 2C-2** — Bundle CLI must never initiate deploy. Deploy is a separate
  user-only CLI, not an MCP tool.
- **Delta 2C-3** — ZET-format error output surfaces through the bundler's
  tool result to `worker/bundler`'s diagnostics stream.

## 18. Deltas to Phase 2D

Five deltas, documented in `2026-04-23-forgeds-widgets-phase2d-ide-design.md`:

- **Delta 2D-1** — `aiToolUseStore` is replaced by `aiOrchestrationStore`
  (§19 of 2D). Interface in §7 of this doc.
- **Delta 2D-2** — `AiBuildLogTab` is subsumed by the new AgentRun panel.
- **Delta 2D-3** — New BuildPlanPreview panel (id `build-plan-preview`).
- **Delta 2D-4** — ConsolePanel AI Build Log becomes a filterable table with
  a `worker_id` column.
- **Delta 2D-5** — WS message family expands per §10; all new messages are
  `orchestrator:*`-namespaced so pre-existing IDE messages are untouched.

## 19. Non-goals

- **No auto-approve deploy.** Deploy is never initiated by the orchestrator
  or by any worker, regardless of plan content. The `forgeds:cli:deploy`
  WS message is user-initiated only.
- **No cross-session mid-worker resume in v1.** Workers are re-spawned from
  task entry on reload; in-flight SDK turns are discarded. Full resume is
  a Phase 3 concern.
- **No third-party worker plugin system.** The 9-agent roster is fixed in
  v1. Adding a worker requires a code change to `worker-definitions.ts`
  and a spec-level review of its tool allowlist and tier.
- **No multi-user / shared-session orchestration.** A BuildSession is
  scoped to one user's IDE on one project root.
- **No model selection override in the IDE.** Per-worker tier is declared
  in `worker-definitions.ts` and not user-editable through the IDE. A CLI
  flag for diagnostic runs is out of scope for this phase.

## 20. Open questions

1. **Replan cost-accounting.** Does a replan reset `totalToolCalls` to zero
   (fresh budget) or carry it over (the user has now paid twice to reach
   the same outcome)? Default proposal: carry over; replan is a real cost
   signal.
2. **Architect-visible lint scope.** The architect's allowlist includes
   `forgeds_lint_app` so it can assess the repo before planning. Should
   `forgeds_lint_app` from the architect be restricted to `scope=summary`
   to bound architect-turn token consumption?
3. **`worker/ds-reader` as implicit preamble.** Should every plan that
   touches `.ds` be rewritten to auto-insert a `worker/ds-reader` task at
   the root, or should the architect be trained to insert it explicitly?
   Current default: architect-explicit; insertion rewriting deferred.
4. **Concurrency cap inside a parallel batch.** Should there be a hard
   cap (e.g. at most 4 concurrent workers) to bound memory and API
   concurrency? Current default: no cap, rely on the session-level
   80-call budget as the backpressure.
5. **Transcript retention.** How long are per-worker transcripts kept in
   `.forgeds/orchestration-session.json`? Unbounded retention grows the
   file over a long project; truncating risks breaking
   `orchestrator:escalate:human` "view transcript" on older sessions.
   Default proposal: keep last 3 sessions, rotate older into
   `.forgeds/archive/`.
6. **Partial-message throughput.** `includePartialMessages: true`
   multiplies WS traffic by the number of active workers. Should the
   bridge coalesce `orchestrator:worker:stream` events on a short
   debounce (e.g. 50 ms) before forwarding to the IDE? Default proposal:
   yes, 50 ms; revisit if UI feels laggy.
7. **Pre-warm credential surface.** `startup()` on project load means the
   SDK is initialised whether or not the user ever invokes the agent.
   Should pre-warming be gated on a user setting for privacy-conscious
   setups? Default proposal: gate behind
   `forgeds.yaml: orchestrator.prewarm: true` (default `true`).
