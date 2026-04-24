# ForgeDS Widgets Phase 2D — IDE Integration + AI Tool-Use Layer (DRAFT for user review)

**Date:** 2026-04-23
**Status:** Draft — produced by parallel-agent brainstorming pass, awaits user approval before a plan is written.
**Depends on:** Phase 1, Phase 2A (contract), 2B (runtime), 2C (build/deploy).
**IDE shell prerequisite:** Shell-overhaul branch (`claude/ide-shell-overhaul`) tasks 1–6 complete; 7–20 remain. See `RESUME-IDE-SHELL-OVERHAUL.md`.
**Parallel siblings:** Phase 2A, 2B, 2C.

> **Multi-agent note:** The single-agent AI-tool-use model originally proposed in this spec has been superseded by a three-tier architect + orchestrator + worker architecture defined in `docs/superpowers/specs/2026-04-23-forgeds-widgets-phase2-orchestration-design.md`. This spec retains ownership of the IDE shell, panels, bridge WS protocol, and MCP tool catalog; the orchestration spec defines the agent layer that consumes them.

---

## 1. Problem statement

The ForgeDS_IDE (React SPA at `web/`) is the visual shell where a user prompts Claude to build a Zoho Creator app. Today it owns six panels (EditorPanel, RepoExplorer, AppTreeExplorer, InspectorPanel, SourceControlPanel, ConsolePanel), a two-level console (Scripts + Dev Tools), a Dockview host with persistence, and a WebSocket bridge at `ws://localhost:9876`. What the IDE does **not** have:

- Any surface for the widget ecosystem Phase 1 introduced (`widgets:` / `custom_apis:` in `forgeds.yaml`, `zoho_widget_sdk.db`, `forgeds-lint-widgets`, manifest validator).
- A way to invoke Phase 2A/2B/2C Python CLIs from the IDE — the bridge today speaks to a generic backend, not to ForgeDS tools.
- A Claude tool-use layer that turns a natural-language prompt ("build me an expense app") into a deterministic sequence of ForgeDS CLI calls with diagnostic-driven error recovery.
- First-class IDE UX for diagnostics, error-loops, and the AI's own reasoning trail.

Phase 2D fills these four gaps. It does **not** change the contract (2A), runtime (2B), or build/deploy (2C) layers — it exposes them. The deliverable is an IDE in which a user can type "build me an expense reimbursement app" and watch Claude scaffold, lint, fix, and verify the app, with every CLI call streaming into visible panels and every diagnostic addressable in the editor.

### Why now

Phase 1 shipped the widget-lint plumbing. Phases 2A/2B/2C land the contract, runtime verifier, and deploy pipeline in parallel. Without 2D, those CLIs are invokable only from a terminal. The IDE is the product surface users see — Phase 2D is the thing that makes ForgeDS visibly "an AI-driven Zoho Creator builder" rather than "a set of Python tools with a separate IDE."

---

## 2. Scope

**In scope**

| Area | Deliverable |
|---|---|
| Panels | `WidgetExplorer`, `WidgetRunner`, `CustomAPI Playground`, `BuildPlanPreview`, `AgentRun` — five new dockable panels |
| Stores | `widgetStore`, `widgetRunStore`, `apiPlaygroundStore`, `aiOrchestrationStore` |
| Bridge | New message types wrapping Phase 2A/2B CLIs + `orchestrator:*` family; local HTTP sidecar (Option B) |
| AI layer | MCP tool catalog (7–9 tools, shared by all workers), three-layer system prompts (architect + per-worker), error-loop UX driven by orchestrator |
| Diagnostics | App-global diagnostics channel surfaced in ConsolePanel + editor gutter; orchestrator diagnostics carry agent provenance |
| Credentials | Zoho OAuth trust boundary: tokens live in bridge, never in renderer |

**Out of scope (deferred or explicitly non-goal)**

| Item | Reason |
|---|---|
| Offline mode | Bridge is assumed reachable; offline UX is Phase 3+ |
| Mobile/touch layout | Dockview is desktop-first; responsive pass is Phase 3+ |
| Third-party IDE plugins | No plugin API surface in v1 |
| AI model choice UI | Claude-only for 2D; multi-model switcher is Phase 3+ |
| Phase 2C deploy called by AI | IDE-only invocation in 2D; AI-driven deploy requires separate approval gate |
| Custom AI agent personas | Per-worker prompts are fixed (architect + roster of workers defined in orchestration spec); user-authored personas are Phase 3+. Brainstorm's `multi-agent.ts` fanout is unrelated and stays. |
| Widget scaffolder UI | `forgeds:scaffold:widget` tool exists, but no dedicated panel — uses WidgetExplorer actions |

---

## 3. Architecture

### 3.1 New files in `web/src/`

```
web/src/
├── components/ide/
│   ├── WidgetExplorer.tsx              # §4.1 — left dock, tabbed with repo-explorer
│   ├── WidgetRunner.tsx                # §4.2 — right dock, above inspector
│   ├── ApiPlayground.tsx               # §4.3 — bottom dock, separate panel
│   ├── BuildPlanPreview.tsx            # §4.4 — center modal on plan receipt, then docks bottom
│   ├── AgentRun.tsx                    # §4.5 — right dock, replaces earlier AiBuildLogTab
│   ├── AiBuildLogTab.tsx               # ConsolePanel tab under Dev Tools (filterable by worker_id)
│   └── DiagnosticsRenderer.tsx         # shared UI for Diagnostic[] (used by ConsolePanel + panel footers)
├── stores/
│   ├── widgetStore.ts                  # widget registry state
│   ├── widgetRunStore.ts               # streamed run results
│   ├── apiPlaygroundStore.ts           # last request/response
│   └── aiOrchestrationStore.ts         # BuildPlan, worker registry, diagnostics aggregate, session budget
├── services/
│   ├── forgedsCli.ts                   # typed wrappers over new bridge messages
│   └── orchestratorClient.ts           # typed wrapper over orchestrator:* WS family (plan submit/approve, stream subscribe, abort)
└── types/
    └── forgeds-cli.ts                  # shared request/response interfaces
```

### 3.2 Modified files

- `stores/ideStore.ts` — add `diagnostics` shape promoted to first-class (already present at line 155–161, extend to support per-source filtering).
- `components/ide/IdeShell.tsx` — register five new panels in the `PanelRegistry` passed to `DockviewHost` (WidgetExplorer, WidgetRunner, ApiPlayground, BuildPlanPreview, AgentRun).
- `components/ide/ConsolePanel.tsx` — add "AI Build Log" tab under Dev Tools category.
- `services/bridge.ts` — no API change; new message `type` strings added via type union.
- `claude-api.ts` — `buildProject()` is replaced by a call to the Node orchestrator HTTP endpoint (`POST http://127.0.0.1:9878/orchestrate`) rather than direct Claude API invocation from the SPA. The orchestrator (see orchestration spec §5 and §6) owns the architect + worker agent lifecycle; the SPA only submits prompts, renders WS events, and surfaces approval/abort controls.

### 3.3 Flow diagram

```
 ┌─────────────────────────────────┐
 │ IDE (React SPA, port 5173)      │
 │                                 │
 │ ┌─ Panels ──────┐               │
 │ │ WidgetExp     │               │
 │ │ WidgetRunner  │               │
 │ │ ApiPlayground │               │
 │ │ ConsolePanel  │               │
 │ └───────────────┘               │
 │         │                       │
 │         ▼                       │
 │ ┌─ Stores ──────┐               │
 │ │ widgetStore   │               │
 │ │ widgetRunStore│               │
 │ │ apiPlayStore  │               │
 │ │ aiOrchestrationStore│               │
 │ │ ideStore      │               │
 │ └───────────────┘               │
 │         │                       │
 │         ▼                       │
 │ ┌─ bridge.ts (WS) ─┐            │
 │ └──────────────────┘            │
 └───────────│─────────────────────┘
             │ ws://localhost:9876
             ▼
 ┌──────────────────────────────────┐
 │ Bridge backend (existing, Python)│
 │                                  │
 │  ┌─ WS router ─┐                 │
 │  │ forgeds:*   │──► HTTP client ─┼──► http://127.0.0.1:9877/forgeds/<op>
 │  │ (other)     │                 │              │
 │  └─────────────┘                 │              ▼
 │                                  │    ┌──────────────────────────┐
 │  ┌─ Zoho OAuth store ─┐          │    │ ForgeDS CLI sidecar      │
 │  │ tokens, refresh    │          │    │ (local HTTP, Python)     │
 │  └────────────────────┘          │    │                          │
 └──────────────────────────────────┘    │  /forgeds/lint   → lint_*│
                                         │  /forgeds/scaffold → ... │
                                         │  /forgeds/bundle → ...   │
                                         │  /forgeds/verify → ...   │
                                         │  /forgeds/deploy → ...   │
                                         │  /forgeds/read   → fs    │
                                         │  /forgeds/write  → fs    │
                                         └──────────────────────────┘
```

The sidecar is the new component. The bridge is unchanged in shape — it gains new message `type` strings and an HTTP client pointed at the sidecar.

### 3.4 Store additions

| Store | State shape (abbreviated) | Primary actions |
|---|---|---|
| `widgetStore` | `{widgets: WidgetRow[], loading: boolean, lastRefresh: number}` | `refresh()`, `runLint(id)`, `runTest(id)` |
| `widgetRunStore` | `{activeRunId: string \| null, calls: CallTraceEntry[], summary: RunSummary \| null, status: "idle"\|"running"\|"done"\|"error"}` | `start(widgetId, payload)`, `appendCall(entry)`, `finish(summary)` |
| `apiPlaygroundStore` | `{lastRequest: ApiRequest \| null, lastResponse: ApiResponse \| null, history: ApiExchange[]}` | `send(req)`, `clear()` |
| `aiOrchestrationStore` | `{activeBuildPlan, activeBuildSession, workerRegistry, diagnosticsAggregate, totalToolCalls, sessionId, workerSessionIds}` (see typed interface below) | `setPlan()`, `approvePlan()`, `upsertWorker()`, `recordToolCall()`, `resetSession()` |

All stores follow existing Zustand patterns (see `ideStore.ts:14-199`). No message bus is introduced — stores remain the bus, consistent with Phase 1 of the shell overhaul.

**`aiOrchestrationStore` typed interface:**

```typescript
interface AiOrchestrationStore {
  activeBuildPlan: BuildPlan | null;           // Architect's output; shown in BuildPlanPreview
  activeBuildSession: BuildSession | null;
  workerRegistry: Map<string, WorkerState>;    // workerId → state
  diagnosticsAggregate: DiagnosticWithAgent[];
  totalToolCalls: number;                       // Against 80-call budget
  sessionId: string | null;                     // Orchestrator session ID (for resume)
  workerSessionIds: Map<string, string>;        // workerId → SDK session_id (for resume)
}

interface WorkerState {
  workerId: string;
  status: "WAITING" | "RUNNING" | "DONE" | "DONE_WITH_CONCERNS" | "NEEDS_CONTEXT" | "BLOCKED" | "ABANDONED";
  toolCallCount: number;
  startedAt: number | null;
  finishedAt: number | null;
  sdkSessionId: string | null;
  transcript: ToolCallRecord[];
}
```

---

## 4. New panels

Five new dockable panels: the original three (WidgetExplorer, WidgetRunner, CustomAPI Playground — §4.1–4.3) plus two orchestration panels (BuildPlanPreview, AgentRun — §4.4–4.5). §4.6 covers integration with existing panels.

### 4.1 WidgetExplorer

| Field | Value |
|---|---|
| Panel id | `widget-explorer` |
| Default dock zone | Left, tabbed with `repo-explorer` |
| Backing store | `widgetStore` |
| Refresh trigger | On mount + on `forgeds.yaml` change + manual refresh button |

**Bridge message**

```ts
// Request
interface GetWidgetsRequest {
  type: "forgeds:widgets:list";
  data: { app?: string };   // optional: scoped to an app; else all
}

// Response
interface GetWidgetsResponse {
  type: "response";
  data: {
    widgets: Array<{
      id: string;
      name: string;               // from forgeds.yaml key
      displayName: string;        // from manifest.json .name
      root: string;               // absolute path
      manifestValid: boolean;
      lintStatus: "clean" | "warnings" | "errors" | "unknown";
      lastLintAt: number | null;  // epoch ms
      consumesApis: string[];
    }>;
  };
}
```

**UI layout**

```
┌──────────────────────────────────────────────────┐
│ Widgets (N registered)            [↻] [+ New]    │  ← header
├──────────────────────────────────────────────────┤
│ Name                       Status                │
├──────────────────────────────────────────────────┤
│ ▸ expense_dashboard        ● clean               │  ← row (click → open manifest)
│ ▸ approval_queue           ⚠ warnings (3)        │
│ ▸ audit_trail              ✖ errors (1)          │
│                                                  │
│ (orphan: src/widgets/foo/ — not registered)      │  ← WG-meta row
└──────────────────────────────────────────────────┘
```

- Row click → opens `<root>/plugin-manifest.json` in EditorPanel.
- Right-click context menu: `Lint`, `Validate manifest`, `Run in WidgetRunner`, `Reveal in RepoExplorer`.
- `+ New` button → prompts for widget name, calls `forgeds:scaffold:widget`.

**StrictMode hygiene**

- Refresh polling uses `setInterval` — ref must be cleared in unmount cleanup.
- Context menu listener on `document` must be added via `useEffect` with a removal cleanup.
- Row array passed to a virtualized list must be memoized on `widgets` identity.

### 4.2 WidgetRunner

| Field | Value |
|---|---|
| Panel id | `widget-runner` |
| Default dock zone | Right, above `inspector` (stacked in same group) |
| Backing store | `widgetRunStore` |
| Streaming | Yes — `stream` + `stream_end` messages from bridge |

**Bridge message**

```ts
// Request
interface RunWidgetRequest {
  type: "forgeds:widgets:run";
  data: {
    widget_id: string;
    payload: unknown;          // test input handed to widget entry fn
    timeout_ms?: number;       // default 30000
  };
}

// Stream chunks (multiple)
interface RunWidgetChunk {
  type: "stream";
  data: {
    call_id: string;
    fn_name: string;           // e.g. "ZOHO.CREATOR.API.getRecords"
    args: unknown[];
    result: unknown | { error: string };
    duration_ms: number;
    depth: number;             // for nested call tree rendering
  };
}

// Terminal
interface RunWidgetEnd {
  type: "stream_end";
  data: {
    total_calls: number;
    errors: number;
    duration_ms: number;
    diagnostics: Diagnostic[];
  };
}
```

**UI layout**

```
┌──────────────────────────────────────────────────┐
│ Widget: [expense_dashboard ▾]        [▶ Run]     │
├──────────────────────────────────────────────────┤
│ Test payload (Monaco):                           │
│ { "user_id": "12345" }                           │
├──────────────────────────────────────────────────┤
│ Call trace:                                      │
│ ▸ ZOHO.CREATOR.init()                  12ms  OK  │
│ ▸ ZOHO.CREATOR.API.getRecords(...)    141ms  OK  │
│   ▸ invokeCustomApi("get_pending...")  98ms  OK  │
│ ✖ addRecords(...)                      23ms  ERR │  ← highlighted
├──────────────────────────────────────────────────┤
│ Summary: 4 calls, 1 error, 174ms total           │
│ Diagnostics: 1 error (click to jump)             │
└──────────────────────────────────────────────────┘
```

- Monaco editor for payload — debounced sync to store.
- Call tree is a flat list with `depth`-based indentation; nested rendering via CSS `padding-left: depth * 1rem`.
- Error rows show a "Jump to source" link → opens the widget's JS file at the line extracted from the stack trace (when available).

**StrictMode hygiene**

- Stream subscription (via `bridge.sendStream(onChunk)`) returns no disposable directly but writes to the store; abort via an `AbortController` whose `abort()` fires on unmount.
- The run button's pending state must be gated on `status === "running"` read from the store, not a local `useState` (avoids StrictMode double-invoke duplicating runs).
- Monaco editor instance disposed on unmount.

### 4.3 CustomAPI Playground

| Field | Value |
|---|---|
| Panel id | `api-playground` |
| Default dock zone | Bottom, separate panel from Console (not tabbed within it) |
| Backing store | `apiPlaygroundStore` |
| Streaming | No — single request/response |

**Bridge message**

```ts
// Request
interface InvokeCustomApiRequest {
  type: "forgeds:api:invoke";
  data: {
    api_name: string;           // must be in config.custom_apis
    method: "GET" | "POST" | "PUT" | "DELETE";
    payload?: unknown;
    headers?: Record<string, string>;
  };
}

// Response
interface InvokeCustomApiResponse {
  type: "response";
  data: {
    status: number;
    headers: Record<string, string>;
    body: unknown;
    duration_ms: number;
    error?: string;             // present when status >= 400 or transport failed
  };
}
```

**UI layout**

```
┌──────────────────────────────────────────────────┐
│ API: [get_pending_claims ▾]  Method: [POST ▾]    │
│                                        [▶ Send]  │
├──────────────────────────────────────────────────┤
│ Payload (Monaco):                                │
│ { "status": "pending" }                          │
├──────────────────────────────────────────────────┤
│ Response:                                        │
│ Status: 200 OK · 142ms · 1.2KB                   │
│ ┌────────────────────────────────────────┐       │
│ │ {                                      │       │
│ │   "claims": [...],                     │       │
│ │   "total": 47                          │       │
│ │ }                                      │       │
│ └────────────────────────────────────────┘       │
└──────────────────────────────────────────────────┘
```

- Status badge color-coded (2xx green, 4xx amber, 5xx red).
- Response body in read-only Monaco instance with JSON syntax highlighting.
- "History" dropdown shows last 10 exchanges (resettable via `clear()` action).

**StrictMode hygiene**

- Two Monaco editors (request + response) — both disposed on unmount.
- `send()` uses `bridge.send()` which returns a Promise; wrap in `AbortController` for cleanup on unmount mid-request.

### 4.4 BuildPlanPreview

| Field | Value |
|---|---|
| Panel id | `build-plan-preview` |
| Default dock zone | Center, modal-style overlay on first plan receipt — docks to bottom after approval |
| Backing store | `aiOrchestrationStore.activeBuildPlan` |
| Trigger | Shown automatically when `orchestrator:plan:ready` WS message arrives |

**Purpose:** Display the architect's BuildPlan in a human-readable tree before any worker is dispatched. User can Approve / Edit / Cancel.

**Fast-path toggle:** "Build without reviewing plan" skips the preview and auto-proceeds for trivial prompts (single-task plans with low estimated risk).

**UI layout**

```
┌──────────────────────────────────────────────────────────┐
│ Build Plan   (architect: opus-4.7, 8 tasks, est. 6 min)  │
│                              [Approve] [Edit] [Cancel]   │
├──────────────────────────────────────────────────────────┤
│ ▸ T1  scaffolder       create app.ds skeleton            │
│ ▸ T2  scaffolder       scaffold form: submit_claim       │  depends on T1
│ ▸ T3  deluge-author    add validation workflow           │  depends on T2
│ ▸ T4  scaffolder       scaffold form: approve_claim      │  depends on T1
│ ▸ T5  widget-author    create expense_dashboard widget   │  depends on T2,T4
│ ▸ T6  linter           lint full app                     │  depends on T3,T5
│ ▸ T7  fixer            apply diagnostics (conditional)   │  depends on T6
│ ▸ T8  verifier         runtime verify widgets            │  depends on T5,T7
├──────────────────────────────────────────────────────────┤
│ Dependency graph:                                        │
│                                                          │
│   T1 ──► T2 ──► T3 ──┐                                   │
│    └───► T4 ──┐      ├──► T6 ──► T7 ──► T8               │
│               └► T5 ─┘                                   │
└──────────────────────────────────────────────────────────┘
```

**StrictMode hygiene**

- Tree expansion state held in local `useState` — no global store coupling needed.
- Approve/Cancel buttons use AbortController to cancel in-flight WS request on unmount.
- Dependency graph rendered via memoized SVG; re-computed only when `activeBuildPlan` identity changes.

### 4.5 AgentRun

| Field | Value |
|---|---|
| Panel id | `agent-run` |
| Default dock zone | Right dock, replacing the single `AiBuildLogTab` in the earlier 2D draft |
| Backing store | `aiOrchestrationStore` |
| Streaming | Yes — updates on every `orchestrator:worker:stream` WS message |

**Purpose:** Tree view showing architect + all workers, each with live status, model tier indicator, elapsed time, tool-call count. Click a worker row to open its transcript.

**Status badges:** ✓ DONE (green), ● RUNNING (amber pulse), ○ WAITING (grey), ✖ BLOCKED (red), ⚠ DONE_WITH_CONCERNS (yellow), ⊘ ABANDONED (grey-strikethrough).

**UI layout**

```
┌──────────────────────────────────────────────────────────┐
│ Agent Run — session s-42   budget: 34/80   [Pause][Abort]│
├──────────────────────────────────────────────────────────┤
│ ✓ architect            opus-4.7     1.2s    4 calls      │
│ ├─ ✓ T1 scaffolder     sonnet-4.7   0.8s    3 calls      │
│ ├─ ✓ T2 scaffolder     sonnet-4.7   1.4s    5 calls      │
│ ├─ ● T3 deluge-author  sonnet-4.7   6.1s    7 calls  ⏵   │  ← click to open transcript
│ ├─ ○ T4 scaffolder     —            —       —            │
│ ├─ ○ T5 widget-author  —            —       —            │
│ ├─ ✖ T6 linter         sonnet-4.7   2.0s    4 calls  ⚠   │  ← BLOCKED
│ ├─ ⚠ T7 fixer          sonnet-4.7   3.1s    6 calls      │  ← DONE_WITH_CONCERNS
│ └─ ⊘ T8 verifier       —            —       —            │  ← ABANDONED
├──────────────────────────────────────────────────────────┤
│ Transcript (T3): expand below                            │
│   → forgeds_read_file: forms/submit_claim.dg             │
│   ← { content: "...", size: 1240 }                       │
│   → forgeds_write_file: forms/submit_claim.dg            │
│   ← { bytes_written: 1312, sha: "9ab3..." }              │
└──────────────────────────────────────────────────────────┘
```

**StrictMode hygiene**

- WS subscription for `orchestrator:worker:stream` events registered via `useEffect` with cleanup that unsubscribes on unmount.
- Worker row array derived from `aiOrchestrationStore.workerRegistry` via memoized selector; identity stable across renders when the Map's keys/values don't change.
- Transcript panel lazy-mounts only for the currently-selected worker (avoids rendering hundreds of tool-call rows for background workers).

### 4.6 Integration with existing panels

- **WidgetRunner:** Unchanged. Invoked BY `worker/widget-author` via `forgeds:verify:runtime` tool, not directly triggered by the orchestrator. Worker streaming still surfaces in the panel when the widget-author invokes it.
- **ConsolePanel AI Build Log tab:** Becomes a filterable table with a `worker_id` column. Default filter: "all workers." Clicking a worker name filters to that worker's tool calls.
- **CustomAPI Playground, AppTreeExplorer, RepoExplorer:** Unchanged.

---

## 5. Bridge protocol additions

### 5.1 New message type catalog

| Type | Direction | Mode | Purpose |
|---|---|---|---|
| `forgeds:widgets:list` | → bridge | req/res | List registered widgets |
| `forgeds:widgets:run` | → bridge | stream | Run widget against mocked SDK |
| `forgeds:api:invoke` | → bridge | req/res | Invoke Custom API via Phase 2A typed client |
| `forgeds:cli:lint` | → bridge | req/res (or stream for large) | Run any lint CLI |
| `forgeds:cli:scaffold` | → bridge | req/res | Run scaffolder |
| `forgeds:cli:bundle` | → bridge | stream | Run Phase 2C bundle (streams progress) |
| `forgeds:cli:verify` | → bridge | stream | Run Phase 2B runtime verifier |
| `forgeds:cli:deploy` | → bridge | stream | Run Phase 2C deploy (IDE-only; not AI-callable) |
| `forgeds:fs:read` | → bridge | req/res | Read file content |
| `forgeds:fs:write` | → bridge | req/res | Write file content (project-root-scoped) |
| `forgeds:diagnostics:broadcast` | bridge → | event | Push async diagnostics into `ideStore.diagnostics` |
| `orchestrator:plan:submit` | IDE → bridge → orchestrator | req/res | Submit user prompt + project snapshot; triggers architect run |
| `orchestrator:plan:ready` | orchestrator → IDE | event | BuildPlan ready for user approval |
| `orchestrator:plan:approve` | IDE → bridge → orchestrator | req/res | User approves plan; triggers dispatch |
| `orchestrator:worker:stream` | orchestrator → IDE | event | Live tool-call trace from a running worker |
| `orchestrator:worker:status` | orchestrator → IDE | event | Worker status change (e.g., RUNNING → DONE) |
| `orchestrator:diagnostics:batch` | orchestrator → IDE | event | Batch of diagnostics with agent provenance |
| `orchestrator:escalate:human` | orchestrator → IDE | event | Worker BLOCKED; needs human input; payload includes context |
| `orchestrator:session:done` | orchestrator → IDE | event | All tasks DONE; final build-report.json summary |
| `orchestrator:session:abort` | IDE → bridge → orchestrator | req/res | User abort |

> The existing `forgeds:diagnostics:broadcast` message type remains for async diagnostics from the Python sidecar (direct CLI invocations). The `orchestrator:diagnostics:batch` type carries batch diagnostics annotated with agent provenance from the orchestrator. Both coexist; UI consumers ideally subscribe to the orchestrator stream during an active build session and fall back to the sidecar stream when no orchestration is running.

**Streaming vs req/res decision rule:** operations with bounded, predictable duration (< 2s p95) use req/res. Operations that emit progressive output (call traces, bundle steps, deploy phases) use stream. Lint defaults to req/res; switches to stream when invoked over `app:*` scope (many files).

### 5.2 Streaming example

```ts
// Request
{
  "id": "req-42",
  "type": "forgeds:widgets:run",
  "data": { "widget_id": "expense_dashboard", "payload": { "user_id": "12345" } }
}

// Stream chunk 1
{
  "id": "req-42",
  "type": "stream",
  "data": {
    "call_id": "c-001",
    "fn_name": "ZOHO.CREATOR.init",
    "args": [],
    "result": { "ok": true },
    "duration_ms": 12,
    "depth": 0
  }
}

// Stream chunk 2
{
  "id": "req-42",
  "type": "stream",
  "data": {
    "call_id": "c-002",
    "fn_name": "ZOHO.CREATOR.API.getRecords",
    "args": ["expense_claims", "status == \"pending\"", 1, 50],
    "result": { "data": [/* ... */], "code": 3000 },
    "duration_ms": 141,
    "depth": 0
  }
}

// Terminal
{
  "id": "req-42",
  "type": "stream_end",
  "data": {
    "total_calls": 4,
    "errors": 1,
    "duration_ms": 174,
    "diagnostics": [
      {
        "file": "src/widgets/expense_dashboard/index.js",
        "line": 87,
        "rule": "RT001",
        "severity": "error",
        "message": "addRecords called without required permission ZOHO.CREATOR.API.write"
      }
    ]
  }
}
```

### 5.3 Local HTTP sidecar (Option B)

**Decision:** adopt Option B (local HTTP server spawned alongside IDE). Rationale: Phase 2A CLIs are natural REST endpoints; MCP (Option A) adds a translation hop for agent-centric benefit the IDE doesn't need; subprocess exec (Option C) pays 200ms startup per call and loses streaming.

**Port allocation:** fixed port **9877** (bridge is 9876; sidecar sits adjacent). If busy, sidecar probes 9878, 9879, up to 9885, and writes the chosen port to `<project-root>/.forgeds-sidecar.port`. Bridge reads this file on startup.

**Process lifecycle**

- **Spawner:** the bridge backend, on first ForgeDS CLI request (lazy start). Avoids cost when the user only uses non-ForgeDS features.
- **Discovery:** bridge reads `.forgeds-sidecar.port`; if file missing, spawns and waits for health check (`GET /health` returning `{"status": "ok"}`).
- **Shutdown:** bridge sends `POST /shutdown` on its own graceful shutdown; sidecar also exits if bridge closes WS (heartbeat every 30s, 3 missed = exit).
- **Crash recovery:** bridge re-spawns on first failed request after health check fails. Max 3 restarts per 5 min; beyond that, emits `forgeds:diagnostics:broadcast` with severity error and the IDE's `DockviewErrorBoundary`-style surface shows "ForgeDS backend unreachable — check sidecar logs at `<path>`".

**Sidecar implementation:** Python stdlib `http.server` + `threading.Thread`, ~300 LOC. Zero new dependencies. Each endpoint dispatches to the corresponding `forgeds.*` module's `main()` entry. Stream endpoints use chunked transfer encoding.

**Protocol between bridge and sidecar:**

```
POST /forgeds/lint               # req/res
  body: { "tool": "widgets", "paths": [...], "format": "json" }
  response 200: { "diagnostics": [...], "exit_code": 0 }

POST /forgeds/verify             # streamed (chunked)
  body: { "widget_id": "expense_dashboard", "payload": {...} }
  response 200 chunked: one JSON object per line (NDJSON)

POST /forgeds/fs/read            # req/res, project-root-scoped
  body: { "path": "src/widgets/.../index.js" }
  response 200: { "content": "...", "size": 4837, "truncated": false }

POST /forgeds/shutdown           # graceful exit
  body: {}
  response 204
```

---

## 6. AI tool-use schema

> See `docs/superpowers/specs/2026-04-23-forgeds-widgets-phase2-orchestration-design.md` for the architect, orchestrator, and worker definitions. This section defines the TOOL surface shared by all agents; the orchestration spec defines WHO calls WHICH tools.

The user prompt is handled by a three-tier system — (1) an **architect** agent produces a BuildPlan, (2) a **Node-side orchestrator** dispatches **worker agents** per the plan, (3) workers call ForgeDS tools within their per-worker allowlist. The tool catalog below becomes the definition of the MCP server (`forgeds-mcp-server.ts`) that all workers reference; per-worker allowlists are defined in the orchestration spec §8.2. The single-agent 40-call budget becomes an 80-call session-global budget across all workers.

The tool schemas defined in §6.2 are unchanged in shape — they are now MCP tool definitions (rather than a monolithic single-agent tool registry). The renderer's `services/aiToolRegistry.ts` is superseded by the MCP server; the renderer no longer dispatches tool calls, only renders WS events describing calls made by workers against the MCP server.

### 6.1 Tool list (8 tools — Goldilocks)

Naming convention: `forgeds:<verb>:<object>` mirrors the CLI surface. Each tool returns a rich result object (never boolean). The "AI-callable" column below indicates whether the tool appears in ANY worker's allowlist; the specific mapping of tool → worker role is in the orchestration spec §8.2.

| Tool | Purpose | AI-callable | IDE-callable |
|---|---|---|---|
| `forgeds:lint:app` | Lint an entire app (Deluge + widgets + hybrid) | ✓ | ✓ |
| `forgeds:lint:file` | Lint a single file | ✓ | ✓ |
| `forgeds:scaffold:form` | Create a new form in .ds | ✓ | ✓ |
| `forgeds:scaffold:widget` | Create a new widget directory + manifest | ✓ | ✓ |
| `forgeds:bundle:app` | Phase 2C bundle for deploy prep | ✓ | ✓ |
| `forgeds:verify:runtime` | Phase 2B runtime verify a widget | ✓ | ✓ |
| `forgeds:read:file` | Read a project file (100KB cap; truncate + summary if larger) | ✓ | ✓ |
| `forgeds:write:file` | Write a project file (.ds, .dg, widget JS, manifest) | ✓ | ✓ |

**Explicitly not AI-callable** (IDE-only in Phase 2D):

- `forgeds:deploy:zoho` — pushing to Zoho Creator. Requires user-initiated click in the IDE; user must confirm the diff. Rationale: deploy is irreversible against production resources.
- `forgeds:fs:delete` — destructive; never AI-driven in v1.

### 6.2 Tool schemas (abbreviated — full JSON Schema lives in the MCP server `forgeds-mcp-server.ts`; see orchestration spec)

**`forgeds:lint:app`**

```ts
// Input
{
  app_name: string;
  scope?: "widgets" | "deluge" | "all";   // default "all"
  fix?: boolean;                            // auto-apply safe fixes; default false
}

// Output
{
  status: "clean" | "warnings" | "errors";
  diagnostics: Diagnostic[];                // always present; empty array when clean
  summary: { error_count: number; warning_count: number; file_count: number };
}

// Error cases
// - E_APP_NOT_FOUND: app_name missing from forgeds.yaml
// - E_TOOLCHAIN_MISSING: Node/ESLint absent (exit code 3 from forgeds-lint-widgets)
// - E_CONFIG_INVALID: forgeds.yaml fails schema validation
```

**`forgeds:scaffold:widget`**

```ts
// Input
{
  app_name: string;
  widget_name: string;                      // snake_case, must not collide
  consumes_apis?: string[];                 // must be in custom_apis
  template?: "blank" | "dashboard" | "form_embed";  // default "blank"
}

// Output
{
  status: "created";
  root: string;                             // absolute path
  files_written: string[];
  forgeds_yaml_updated: boolean;
}

// Error cases
// - E_NAME_COLLISION: widget already registered
// - E_UNKNOWN_API: consumes_apis[i] not in custom_apis
// - E_PATH_CONFLICT: root directory already exists non-empty
```

**`forgeds:verify:runtime`**

```ts
// Input
{
  widget_id: string;
  payload: unknown;
  timeout_ms?: number;                      // default 30000
}

// Output
{
  status: "passed" | "failed" | "errored";
  calls: Array<{ call_id: string; fn_name: string; duration_ms: number; result_ok: boolean }>;
  total_calls: number;
  errors: number;
  duration_ms: number;
  diagnostics: Diagnostic[];
}

// Error cases
// - E_WIDGET_NOT_FOUND
// - E_SDK_METHOD_UNKNOWN: widget called SDK fn not in zoho_widget_sdk.db
// - E_TIMEOUT
// - E_PERMISSION_MISSING: fn invoked without declared permission
```

**`forgeds:read:file`**

```ts
// Input
{
  path: string;                             // project-root-relative
  max_bytes?: number;                       // default 102400 (100KB)
}

// Output
{
  path: string;
  content: string;                          // may be truncated
  size: number;                             // actual file size
  truncated: boolean;
  summary?: {                               // present only when truncated
    line_count: number;
    forms?: string[];                       // for .ds
    functions?: string[];                   // for .dg
    tree_shape?: string;                    // for widgets
  };
}

// Error cases
// - E_PATH_OUTSIDE_PROJECT
// - E_NOT_FOUND
// - E_BINARY_FILE
```

**`forgeds:write:file`**

```ts
// Input
{
  path: string;
  content: string;
  if_match?: string;                        // optional SHA of current content for optimistic concurrency
}

// Output
{
  path: string;
  bytes_written: number;
  sha: string;
}

// Error cases
// - E_PATH_OUTSIDE_PROJECT
// - E_IF_MATCH_MISMATCH
// - E_DS_SYNTAX_INVALID: post-write .ds parser fails
// - E_READ_ONLY_PATH: attempt to write zoho_widget_sdk.db or other protected files
```

### 6.3 Call/response example

```json
// Worker agent (e.g., worker/linter) emits via Claude Agent SDK
{
  "type": "tool_use",
  "id": "toolu_01abc",
  "name": "forgeds:lint:app",
  "input": { "app_name": "expense_reimbursement", "scope": "all" }
}

// Orchestrator dispatches via MCP server → sidecar → back; IDE observes via orchestrator:worker:stream WS event
// Worker receives
{
  "type": "tool_result",
  "tool_use_id": "toolu_01abc",
  "content": [
    {
      "type": "text",
      "text": "{\"status\":\"errors\",\"diagnostics\":[{\"file\":\"forms/submit_claim.dg\",\"line\":42,\"rule\":\"DG014\",\"severity\":\"error\",\"message\":\"undefined field 'Merchant_Account'; did you mean 'merchant_account'?\"}],\"summary\":{\"error_count\":1,\"warning_count\":0,\"file_count\":17}}"
    }
  ]
}
```

### 6.4 Granularity rationale

- **8 tools, not 3 or 20.** Three would conflate operations (one super-tool `forgeds:do`), losing AI's ability to diagnose where a build failed. Twenty would fragment the space so that the AI spends cycles choosing which lint variant to invoke.
- **Every tool emits diagnostics array.** Even when clean (empty array). No boolean returns. Forces consistent error-handling code path.
- **No tool blocks on user confirmation.** Confirmation is a layer above (the error-loop UX in §8). Tools are synchronous-semantics.

---

## 7. System prompt preamble

The single monolithic "ForgeDS Build Assistant" preamble is replaced by three layers: an architect prompt, deterministic orchestrator code (no prompt), and per-worker prompts. Each agent sees only the prompt for its role. The multi-step workflow that used to live in a single preamble now lives in the architect's planning logic — workers execute ONE task each.

### 7.1 Layer 1 — Architect system prompt

Prepended to every architect run. The architect receives a user intent and a project snapshot, and returns a BuildPlan JSON.

> You are the ForgeDS Architect. You receive a user intent and a project snapshot. You produce a BuildPlan JSON (schema in orchestration spec §4). You DO NOT implement. You DO NOT call `forgeds_write_file`. You read project state using `forgeds_status` and `forgeds_read_file` to understand the current state, then plan incremental tasks. Each task must be assigned to exactly one worker role from the roster. Your output is a single JSON object matching the BuildPlan schema — nothing else. Never prose around the JSON. Never markdown-fence the JSON in your final `result`.

### 7.2 Layer 2 — Orchestrator (not an agent prompt)

> The orchestrator is deterministic Node-side logic that consumes the BuildPlan, dispatches workers, manages their lifecycle, aggregates diagnostics, and emits WS events to the IDE. It has no prompt — it is code. See orchestration spec §5 and §6.

### 7.3 Layer 3 — Per-worker system prompts

Each worker role has its own preamble, narrowly scoped to the tools on its allowlist and the rules relevant to its slice of the problem. Three examples follow; the full roster (linter, deluge-author, widget-author, scaffolder, verifier, fixer, packager) is in the orchestration spec §8.

**Worker / linter:**

> You are the ForgeDS Linter worker. You call `forgeds_lint_app` and `forgeds_lint_file`. You return structured remediation instructions listing each diagnostic with: rule code, file, line, one-sentence fix description, and the worker role that should handle the fix. You do not write files. You do not call scaffold tools. Your output is a JSON object `{ remediations: RemediationItem[], summary: string }`.

**Worker / deluge-author:**

> You are the ForgeDS Deluge Author. You write `.dg` scripts and edit `.ds` forms. Follow these rules:
>
> 1. **Design in Python, build in JS** — server-side logic (Deluge, workflows, forms, reports) is your domain. Client-side widget code is NOT.
> 2. **Incremental scaffolding** — build one form or one workflow per task. Do not batch.
> 3. **Field names are case-sensitive.** Zoho Creator treats `merchant_account` and `Merchant_Account` as different. Always check the .ds before writing Deluge that references a field.
> 4. **Forms go inside `forms { }`, reports inside `reports { }`.** The `.ds` parser silently rejects misplaced blocks with a generic error. Use `forgeds_scaffold_form` — do not hand-assemble `.ds` via `forgeds_write_file` unless necessary.
>
> Use exact link-names from .ds files; never guess. When done, return `{ files_written: string[], summary: string }`.

**Worker / widget-author:**

> You are the ForgeDS Widget Author. You write `index.js`, `index.html`, `styles.css`. Follow these rules:
>
> 1. **Design in Python, build in JS** — client-side widget code is your domain. Server-side Deluge is NOT.
> 2. **Respect the typed schema.** Every tool input must conform to its declared shape. Do not invent fields. If you need data that isn't exposed, use `forgeds_read_file` first.
> 3. **No secrets in generated code.** Never embed OAuth tokens, API keys, or user credentials. If a Custom API needs auth, reference the runtime-provided identity — not a literal.
> 4. **Never call deploy tools.** Deploy is IDE-user-initiated only. Your job ends at a locally-verified, runtime-verified widget.
>
> Use Phase 2A's generated API stubs from `_generated/`; never call Zoho APIs directly without the typed client. When done, return `{ files_written: string[], summary: string }`.

### 7.4 Preamble tuning notes

- The numbered rules in each worker preamble are copied near-verbatim from `CLAUDE.md`'s `.ds file format gotchas` section and from the deprecated monolithic prompt. Keeping each preamble close to the authoritative project docs ensures rules stay in sync; CLAUDE.md edits propagate via a generator step in Phase 2D's build (see §11 testing — `test_preamble_in_sync`).
- The 80-call session budget is heuristic. Observable in `aiOrchestrationStore.totalToolCalls`. Exceeding it triggers a session-wide halt at the orchestrator level, even if no individual worker signals failure.
- The per-worker workflow (parse → fix → re-lint) is a worker's own internal loop, counted against its turn budget (`maxTurns: 20` per worker). Multi-step sequences across workers are the architect's job to plan.

---

## 8. Error-loop UX flow

### 8.1 End-to-end

1. **User:** types "build me an expense reimbursement app" into the ConsolePanel Dev Tools > AI Chat tab (existing stub, now wired to `orchestrator:plan:submit`).
2. **Renderer:** sends `orchestrator:plan:submit` over bridge; orchestrator invokes the **architect** agent.
3. **Architect:** emits BuildPlan JSON → orchestrator forwards `orchestrator:plan:ready` event to IDE.
4. **Renderer:** `BuildPlanPreview` panel opens automatically; user reviews tree + dependency graph, clicks Approve → `orchestrator:plan:approve`.
5. **Orchestrator:** dispatches first wave of workers (T1, T4 — no dependencies). Each worker's tool calls stream via `orchestrator:worker:stream`; worker status changes stream via `orchestrator:worker:status`.
6. **Worker / scaffolder (T1):** calls `forgeds:scaffold:form` (submit_claim). Orchestrator batches the diagnostic `status: clean` and emits `orchestrator:diagnostics:batch`. Renderer appends to `ideStore.diagnostics` (source: `"orchestrator"`, annotated with `worker_id: "T1"`).
7. **Renderer:** AppTreeExplorer refreshes on the write notification; AgentRun panel shows T1 → DONE, T4 → DONE.
8. **Orchestrator:** next wave — dispatches T2 (depends on T1). Worker / deluge-author writes validation workflow, calls `forgeds:lint:file` on its output.
9. **Worker / linter (T6, later in the plan):** calls `forgeds:lint:app` across the assembled app; sidecar returns diagnostics = `[DG014 undefined field 'Merchant_Account' at submit_claim.dg:42]`.
10. **Orchestrator:**
    - Emits `orchestrator:diagnostics:batch` to IDE.
    - ConsolePanel shows the diagnostic in the Dev Tools > Lint tab.
    - EditorPanel (if submit_claim.dg is open) shows a red gutter mark at line 42.
    - AgentRun panel shows T6 → DONE_WITH_CONCERNS; AiBuildLogTab renders a row annotated with `worker_id: "T6"`: `✖ DG014 submit_claim.dg:42 — undefined field 'Merchant_Account'`. Row has a "Jump to Error" chip.
11. **Orchestrator:** dispatches T7 (fixer) per the architect's plan. Worker / fixer reads diagnostic → reads offending file → determines case-sensitivity mismatch → writes corrected `merchant_account`.
12. **Worker / fixer:** returns `{ files_written: [...], summary: "1 fix applied" }`; orchestrator re-dispatches linter as a retry (retryCount = 1).
13. **Worker / linter (retry 1):** `status: "clean"`.
14. **Renderer:** AgentRun updates T6 → DONE; AiBuildLogTab row: `✓ DG014 resolved after 1 retry (by worker T7)`.
15. **Orchestrator:** dispatches T8 (verifier) — runtime-verifies widgets.
16. **On final session completion:** orchestrator emits `orchestrator:session:done` with build-report.json summary; AgentRun shows summary card; ConsolePanel shows "Build complete" toast; user sees the fully-built app in AppTreeExplorer.

### 8.2 What each actor does at each step

| Actor | Responsibility |
|---|---|
| **Architect (agent)** | Parse user intent + project snapshot, emit BuildPlan JSON listing tasks and per-task worker assignments. Never implements. |
| **Orchestrator (code)** | Consume BuildPlan, dispatch workers respecting dependencies, manage retries/abandonment, aggregate diagnostics, emit WS events, enforce 80-call session budget. |
| **Worker (agent)** | Execute one task within the worker's allowlist; return structured result `{ files_written | remediations | ... }`. Read → fix → re-lint loops happen inside a worker within its `maxTurns: 20` budget. |
| **Renderer** | Render BuildPlanPreview on `orchestrator:plan:ready`, submit approval, render AgentRun tree from streaming events, broadcast orchestrator diagnostics to stores, highlight editor, surface `orchestrator:escalate:human` as a modal. |
| **User** | Review + approve the BuildPlan, read diagnostics as they flow, optionally click "Jump to Error" to inspect, click "Pause" to halt orchestrator dispatch, click "Retry worker" on escalation, click "Abort" to terminate session. |

### 8.3 Retry policy

- **Per-worker retry limit:** 3 redispatches before ABANDONED (tracked in `aiOrchestrationStore.workerRegistry[workerId].retryCount`).
- **Per-session call budget:** 80 tool calls across all workers (2× the single-agent 40), rendered as a session progress bar.
- **Worker-level BLOCKED** surfaces in the Agent Run panel with full context (transcript, attempted tools, last diagnostics). The orchestrator emits `orchestrator:escalate:human`; renderer shows a modal: "Worker blocked — needs your input. [View context] [Retry worker] [Abort session]".
- **Diagnostic-level retry** (read → fix → re-lint) is a worker's own internal loop, counted against its turn budget (`maxTurns: 20` per worker). The orchestrator does not manage diagnostic-level retries.
- **User-initiated pause:** "Pause" button halts dispatch at the orchestrator (no new workers spawn); in-flight workers complete their current tool call then suspend. Resumption replays the suspended workers' last tool_result.

### 8.4 Visual hierarchy of diagnostics

| Surface | Content shown | When |
|---|---|---|
| Editor gutter | Severity icon on offending line | File open + diagnostic present |
| Editor hover | Full message, rule, "Jump to next" | Hover on gutter icon |
| ConsolePanel Dev Tools > Lint | Full diagnostic table (file, line, rule, severity, message) | Always, filterable by source |
| ConsolePanel Dev Tools > AI Build Log | Orchestrator-initiated diagnostics, filterable by worker_id, with attempt history | Always during build |
| AgentRun panel | Live tree of architect + workers with status, elapsed, tool-call counts; transcript panel per worker | During build session |
| WidgetRunner footer | Diagnostics from latest run only | After run completes |
| ApiPlayground footer | Request/response errors only | After API call |

All surfaces read from the same `ideStore.diagnostics` array; filtering is display-only.

---

## 9. Credential handling

### 9.1 Trust boundary

```
┌─────────────────────────┐
│ Renderer (browser)      │
│                         │
│ NO OAuth tokens         │
│ NO Zoho credentials     │
│ NO API keys             │
│                         │
│ Auth to bridge: short-  │
│ lived session token     │
│ from GitHub OAuth flow  │
└──────────┬──────────────┘
           │ WS (wss:// in prod)
           ▼
┌─────────────────────────────────────────┐
│ Bridge backend (Python)                 │
│                                         │
│ Holds: Zoho OAuth tokens (refresh +     │
│        access), user GitHub session,    │
│        Claude API key (for /api/agent   │
│        passthrough, if self-hosted)     │
│                                         │
│ Storage: OS keyring (Windows Credential │
│ Manager / macOS Keychain / libsecret).  │
│ Fallback: encrypted file with user      │
│ passphrase prompt on bridge start.      │
└──────────┬──────────────────────────────┘
           │ HTTP to sidecar
           ▼
┌─────────────────────────────────────────┐
│ Sidecar — does NOT hold tokens.         │
│ Bridge injects Zoho creds per-request   │
│ via Authorization header when sidecar   │
│ hits Zoho APIs (deploy / invoke).       │
└─────────────────────────────────────────┘
```

### 9.2 Explicit rules

- **Frontend code must never import or handle Zoho OAuth tokens.** Any `.ts`/`.tsx` file containing the substring `zoho_refresh_token`, `ZOHO_CLIENT_SECRET`, `zoho_access_token` fails lint (new ESLint rule `no-zoho-secrets`).
- **Frontend logs must never contain tokens.** Bridge strips `Authorization` / `Cookie` / `X-*-Token` headers before streaming response metadata back to renderer.
- **Claude API key** (if self-hosted proxy) lives in bridge; renderer authenticates to bridge via GitHub OAuth session, bridge authenticates to Anthropic via its own key.
- **Deploy flow** (`forgeds:cli:deploy`, IDE-only): renderer sends WS message; bridge looks up user's Zoho OAuth; bridge invokes sidecar with `Authorization: Zoho-oauthtoken <redacted>` header; sidecar forwards to Zoho Creator Publish API. Sidecar never sees the raw token until the HTTP hop.
- **WSS in production.** Dev uses `ws://localhost`. Prod-hosted mode uses `wss://` + TLS. Bridge refuses `ws://` if `NODE_ENV=production`.

### 9.3 Token refresh

Bridge refreshes Zoho tokens via the `refresh_token` grant 5 minutes before expiry. Renderer is never notified of the refresh event (it's invisible). If refresh fails, bridge emits `forgeds:diagnostics:broadcast` with severity error: "Zoho authentication expired — please reconnect". Renderer shows a reconnect button in ActivityBar footer.

---

## 10. StrictMode hygiene playbook

React 18 StrictMode double-invokes effects in development to surface latent bugs. All shell-overhaul panels (Tasks 1–6) passed hygiene review; new panels must match.

### 10.1 The 3-rule set

**Rule 1 — Dispose all subscriptions.**
Any `on*` / `subscribe` / `addEventListener` / `setInterval` / `setTimeout` call must have a matching cleanup in the effect's return. If the API returns a disposable, capture it in a ref and call `.dispose()` in cleanup.

Canonical example: `web/src/components/ide/DockviewHost.tsx:102-150` — `api.onDidLayoutChange()` returns a disposable, captured in `layoutChangeDisposableRef`, disposed on unmount.

**Rule 2 — Memoize non-primitive props.**
Objects, arrays, and `Object.fromEntries()` results passed as props or dependencies must be wrapped in `useMemo` with stable dependencies. Otherwise every render creates a new reference, triggering unnecessary re-registration.

Canonical example: `web/src/components/ide/IdeShell.tsx:75-108` — the `PanelRegistry` map passed to `DockviewHost` is built with `useMemo([])`.

**Rule 3 — No async directly in `useEffect` body.**
Wrap in an IIFE or use an `AbortController`. The effect cleanup must abort in-flight work to prevent state updates on unmounted components.

```ts
useEffect(() => {
  const controller = new AbortController();
  (async () => {
    try {
      const result = await fetchThing({ signal: controller.signal });
      if (!controller.signal.aborted) setState(result);
    } catch (e) {
      if (e.name !== "AbortError") throw e;
    }
  })();
  return () => controller.abort();
}, [deps]);
```

### 10.2 Per-panel applicability

| Panel | Rule 1 site | Rule 2 site | Rule 3 site |
|---|---|---|---|
| WidgetExplorer | Refresh interval, context menu listener | `widgets` row array | Initial widget fetch |
| WidgetRunner | Stream subscription AbortController, Monaco dispose | Tree nodes derived from store | Payload debounce |
| ApiPlayground | Two Monaco instances dispose | Response body formatted JSON | Send request |
| BuildPlanPreview | Approve/cancel WS request AbortController | Dependency graph SVG memoized on plan identity | Plan submission |
| AgentRun | `orchestrator:worker:stream` subscription disposed on unmount | Worker row array derived via memoized selector from `workerRegistry` Map | Initial session fetch |
| AiBuildLogTab | Orchestrator WS subscription | ToolCall rows array (filterable by worker_id) | Build session start |

### 10.3 Verification gate

- `npx tsc -b --noEmit` must be clean.
- `npx vitest run` must be green.
- Manual check: mount each panel in StrictMode; verify no duplicate network calls, no duplicate console logs.
- Integration test `test_ide_strictmode_clean` mounts IdeShell under `<StrictMode>` and asserts no console warnings.

---

## 11. Testing

### 11.1 Unit tests

| Name | Subject |
|---|---|
| `test_widget_store_refresh_sets_status` | widgetStore transitions loading→idle on fetch complete |
| `test_widget_run_store_appends_calls_in_order` | widgetRunStore preserves call order even under out-of-order stream chunks |
| `test_api_playground_store_history_bounded` | apiPlaygroundStore caps history at 10 exchanges |
| `test_orchestrator_client_submits_plan` | orchestratorClient sends `orchestrator:plan:submit` with correct shape |
| `test_mcp_server_rejects_deploy_from_worker` | Worker-initiated `forgeds:cli:deploy` raises `E_FORBIDDEN_TOOL` (deploy is IDE-only) |
| `test_diagnostics_renderer_groups_by_source` | DiagnosticsRenderer groups by `source` field (including `worker_id` for orchestrator diagnostics) |
| `test_preamble_in_sync` | Architect + per-worker preambles' numbered rules match CLAUDE.md gotchas section |
| `test_ai_orchestration_store_worker_lifecycle` | workerRegistry transitions WAITING → RUNNING → DONE on matching events |
| `test_sidecar_port_file_rewrite` | Sidecar writes `.forgeds-sidecar.port` on alt-port startup |
| `test_bridge_strips_auth_headers` | Bridge does not forward `Authorization` header to renderer |

### 11.2 Integration tests

| Name | Coverage |
|---|---|
| `test_widget_explorer_panel_registers` | WidgetExplorer appears in Dockview PanelRegistry on IdeShell mount |
| `test_widget_runner_panel_registers` | WidgetRunner appears in PanelRegistry |
| `test_api_playground_panel_registers` | ApiPlayground appears in PanelRegistry |
| `test_bridge_roundtrip_lint_widgets` | `forgeds:cli:lint` WS request → sidecar → response with diagnostics |
| `test_bridge_streams_widget_run` | `forgeds:widgets:run` emits stream chunks + stream_end in order |
| `test_ide_strictmode_clean` | IdeShell mounts under StrictMode without warnings or duplicate effects |
| `test_build_plan_preview_panel_registers` | BuildPlanPreview panel registers and opens on `orchestrator:plan:ready` |
| `test_agent_run_panel_registers` | AgentRun panel registers and updates on `orchestrator:worker:status` events |
| `test_ai_build_log_renders_tool_calls` | AiBuildLogTab renders one row per tool_use in aiOrchestrationStore, grouped by worker_id |
| `test_orchestrator_error_loop_deterministic` | Seeded architect+worker pipeline produces identical task-dispatch sequence across runs |

### 11.3 End-to-end (manual)

- User types "build me a simple todo app" → expect: BuildPlanPreview opens with a small plan; after approval, scaffolded .ds with one form + one widget, all lint green, runtime verified, <80 tool calls session-global.
- User clicks "Pause" mid-build → orchestrator stops dispatching new workers; in-flight workers suspend; "Resume" continues from last tool_result.
- User disables the sidecar mid-build → renderer shows "ForgeDS backend unreachable"; orchestrator emits `orchestrator:escalate:human` for affected workers; user restarts bridge → build resumes (or fails gracefully if state lost).

---

## 12. Risks

| Risk | Mitigation |
|---|---|
| StrictMode violations compound (unhandled listeners, un-memoed props) | Enforce §10 playbook in code review; `test_ide_strictmode_clean` is a blocking gate. |
| Tool-use granularity drift (worker tries to compose scaffold from read+write instead of calling scaffold) | Per-worker system prompt + narrow allowlist removes unrelated tools from the worker's view; eval in `test_ai_build_simple_app` asserts `forgeds:scaffold:form` appears in the scaffolder worker's tool-call trace. |
| Sidecar port collision | 8-port probe range + persisted port file; bridge re-reads on spawn. |
| Token exfiltration via renderer logs | `no-zoho-secrets` ESLint rule; bridge header stripping; WSS in prod. |
| Large .ds files blow AI context budget | `forgeds:read:file` auto-truncates at 100KB and returns summary object; worker re-requests specific line ranges if needed. |
| Worker calls undefined Deluge function in widget | `forgeds:lint:app` (hybrid rules WG001–WG003 + Phase 2 extensions) catches before runtime; orchestrator dispatches fixer worker with the diagnostic as remediation input. |
| Error loop diverges (infinite lint→fix→lint within a worker) | Worker `maxTurns: 20` hard cap; orchestrator per-worker retry cap = 3; session 80-call budget; user "Abort" always available. |
| Sidecar crash during long build | Bridge re-spawns up to 3× per 5 min; beyond that, orchestrator emits `orchestrator:escalate:human` for affected workers and user must restart. |
| Multiple IDE windows open → two sidecars race | Sidecar's port file includes bridge PID; second instance detects existing healthy sidecar and reuses it. |
| Zoho API changes break widget runtime mock | Phase 2B's mocked SDK is versioned against `zoho_widget_sdk.db`; failing a mock update is a Phase 2B concern, not 2D's. |
| Diagnostic volume overwhelms ConsolePanel | Virtualized list (react-window already a transitive dep); filter by severity / source; collapse resolved diagnostics. |

---

## 13. Non-goals

Explicitly called out to prevent scope creep:

- No offline mode. Bridge reachability assumed.
- No mobile / touch layout.
- No third-party plugin / extension API for new tools or panels in v1.
- No multi-model AI switcher (Claude-only).
- No AI-driven deploy (`forgeds:deploy:zoho` is IDE-user-initiated only).
- No AI-driven file deletion or project-level structural rewrites (worker must emit a BLOCKED status with context, orchestrator emits `orchestrator:escalate:human` for user approval).
- No custom AI personas in build sessions (brainstorm wizard's `multi-agent.ts` fanout is unrelated and stays).
- No telemetry / analytics of tool-call patterns in v1 (Phase 3+).
- No in-IDE widget bundle inspection (use filesystem / external tools).
- No dedicated widget scaffolder panel (WidgetExplorer's `+ New` button is sufficient).
- No cross-session build resume (close the IDE = lose the build state; Phase 3+).
- No UI for editing `forgeds.yaml` directly — users edit via EditorPanel like any file.
- No single-agent self-directed tool-use loop for full app builds. The AI build flow is orchestrator-driven multi-agent. A minimal single-agent fallback exists only via the fast-path for trivial prompts (orchestration spec §12).

---

## 14. Open questions

| Q | Proposed resolution |
|---|---|
| Should the sidecar be shared across multiple IDE instances, or one-per-bridge? | One-per-bridge. Simpler lifecycle; bridge is the auth gate anyway. Revisit if multi-window UX demands it. |
| Is 80 tool calls the right session budget? | Start at 80 (2× the old single-agent 40). Emit telemetry (locally logged, not shipped) after 10 real build sessions; tune. |
| Should `forgeds:scaffold:widget` be worker-callable without user confirmation? | Yes for Phase 2D — after BuildPlan approval. Scaffolding is reversible (delete the directory). Deploy is the irreversible step we gate. |
| Should WidgetRunner live in the right dock or bottom dock? | Right, above Inspector. Bottom is reserved for Console + ApiPlayground; keeping run/inspect adjacent aids the debug flow. |
| Do we need a separate `AiBuildLogTab` panel, or is it a Console tab? | Console tab under Dev Tools (filterable by worker_id). The separate `AgentRun` panel (§4.5) owns the live tree + transcript; the Console tab is the flat diagnostic log. |
| Does `forgeds:read:file` read binary files or refuse? | Refuse. Return `E_BINARY_FILE`. Workers have no use case for binary content in Phase 2D. |
| Does the bridge persist sidecar logs, or only stream them? | Persist to `<project-root>/.forgeds/sidecar.log`, rotated at 10MB. Renderer streams tail-f view in a Dev Tools tab (future). |
| Should retry counters reset between builds? | Yes — `resetSession()` clears the `workerRegistry` (and its per-worker retryCount). Counters are per-session, not global. |
| How do we handle `forgeds:write:file` partial failures (e.g., disk full mid-write)? | Atomic write (temp file + rename). Partial state never observable. Surface `E_WRITE_FAILED` with OS error. |
| Do we version the MCP tool schema? | Yes, the MCP server exposes `SCHEMA_VERSION = "1"`. Breaking changes (tool rename, input shape change) require major bump + compat shim. See orchestration spec for MCP server versioning. |
