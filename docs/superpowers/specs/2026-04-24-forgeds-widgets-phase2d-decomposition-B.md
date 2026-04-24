# ForgeDS Widgets Phase 2D — Decomposition (Twin B)

**Date:** 2026-04-24
**Author:** architect twin B (parallel-dispatched `feature-dev:code-architect`, opus)
**Status:** Draft — bisimulation input
**Source spec:** `docs/superpowers/specs/2026-04-23-forgeds-widgets-phase2d-ide-design.md`
**Orchestration contract:** `docs/superpowers/specs/2026-04-23-forgeds-widgets-phase2-orchestration-design.md`

---

## 1. Why 2D needs decomposition

Phase 2D as specified bundles four disjoint bodies of work — the dockable-panel surface for ForgeDS CLIs, a brand-new local HTTP sidecar and bridge-routing layer, a Node Orchestrator Service with SDK / MCP plumbing, and a multi-agent runtime with live streaming panels and credential wiring — into one "phase." Each body has its own failure modes (React StrictMode, chunked HTTP, MCP allowlist enforcement, OS keyring, Claude-SDK costing), its own rule-code prefix demand, and its own natural seam. Prior phases (1, 2A, 2B, 2C) each shipped exactly one such body, and that is the pattern we must match here. Shipping 2D as a monolith would either deliver a non-functional mid-state (panels without sidecar, orchestrator without IDE) or block a six-month critical path behind a single merge. The decomposition below keeps each sub-phase stopping-coherent (the product is usable after any sub-phase lands), isolates blast radii, and preserves the WS-message-type and rule-prefix discipline already in the registry.

---

## 2. Sub-phase table

| # | Slug | One-line deliverable | Rule prefix (own/extend) | WS-message-type range owned |
|---|---|---|---|---|
| 2D.0 | `ide-shell-finish` | Close out IDE shell-overhaul tasks 7–20 (Dockview persistence, ActivityBar wiring, DevTools categories) — prerequisite substrate for any new panel. | — (extends existing IDE-side code; no ForgeDS rule-code) | none (reuses existing bridge types) |
| 2D.1 | `sidecar-bridge-route` | Local HTTP sidecar (`forgeds.sidecar`, port 9877) + Python-bridge `forgeds:*` routing + port-file discovery + health/shutdown/restart lifecycle. | **owns** `SDC###` (new — sidecar/bridge transport diagnostics) | owns `forgeds:cli:*`, `forgeds:fs:*`, `forgeds:diagnostics:broadcast` |
| 2D.2 | `readonly-panels` | WidgetExplorer + ApiPlayground panels + `widgetStore` + `apiPlaygroundStore` + DiagnosticsRenderer shared component + inert `AiBuildLogTab` stub in ConsolePanel. | **owns** `IDE###` (new — IDE-side panel/store diagnostics, surfaced via bridge) | owns `forgeds:widgets:list`, `forgeds:api:invoke` |
| 2D.3 | `widget-runner-streaming` | WidgetRunner panel + `widgetRunStore` + chunked-transfer streaming contract on bridge + sidecar `/forgeds/verify` NDJSON endpoint wiring + AbortController hygiene. | **extends** `IDE###` (adds IDE-side streaming diagnostics) and **extends** `WGR###` (passes through from Phase 2B) | owns `forgeds:widgets:run` (stream + stream_end) |
| 2D.4 | `orchestrator-skeleton+spec-approval` | Rebuttal/approval pass on orchestration spec **plus** the Node Orchestrator Service skeleton (port 9878, `POST /orchestrate`, `GET /health`, `GET /status/:id`, `POST /abort/:id`) with an in-memory BuildPlan executor, MCP server shell (no real tool bodies), empty agent roster. `forgeds-build-app` flips from `--plan-only` to live POST. | **owns** `ORC###` (new — orchestrator service diagnostics) | owns `orchestrator:plan:submit`, `orchestrator:plan:ready`, `orchestrator:plan:approve`, `orchestrator:session:abort` |
| 2D.5 | `mcp-tools-wired` | Full MCP tool catalog (9 tools per orchestration spec §8.1) wired end-to-end to the sidecar's Python CLIs through the Node service; `PreToolUse` allowlist enforcement + `canUseTool` scoping; `postToolUse` diagnostic aggregator with `agent:` provenance. | **owns** `MCP###` (new — MCP tool dispatch / allowlist / scope diagnostics) | none new (tool calls ride orchestrator streams from 2D.4) |
| 2D.6 | `build-plan-preview+dispatch` | BuildPlanPreview panel + `aiOrchestrationStore` + architect-agent spawn + fast-path classifier + user-approval UI + fast-path auto-proceed toggle + dependency-graph SVG. First sub-phase where a single-worker build is user-visible end-to-end. | **extends** `ORC###` (plan-validation + dispatch) | none new (plan messages owned by 2D.4) |
| 2D.7 | `agent-run-streaming+diagnostics-provenance` | AgentRun panel + live worker tree from `orchestrator:worker:stream` + ConsolePanel AiBuildLogTab becomes live filterable table + `orchestrator:diagnostics:batch` aggregation + editor-gutter integration for orchestrator-annotated diagnostics + escalation modal. | **extends** `ORC###` + **extends** `MCP###` | owns `orchestrator:worker:stream`, `orchestrator:worker:status`, `orchestrator:diagnostics:batch`, `orchestrator:escalate:human`, `orchestrator:session:done` |
| 2D.8 | `full-roster+keyring+prod-polish` | Full 9-worker roster in `worker-definitions.ts` + per-worker system prompts + session persistence + **OS-keyring credential wiring for Zoho OAuth** + WSS-in-prod enforcement + `no-zoho-secrets` ESLint rule + pre-warming + model-tier escalation + 80-call budget enforcement + e2e test. | **extends** `ORC###` + **extends** `MCP###` | none new (final polish on existing types) |

**Total: 9 sub-phases (2D.0 through 2D.8).**

---

## 3. Dependency DAG

```
                        2D.0  (ide-shell-finish)
                           │
                           ▼
                        2D.1  (sidecar-bridge-route)
                        │        │
         ┌──────────────┘        └──────────────┐
         ▼                                      ▼
      2D.2                                   2D.4
 (readonly-panels)             (orchestrator-skeleton+spec-approval)
         │                                      │
         ▼                                      ▼
      2D.3                                   2D.5
(widget-runner-streaming)                (mcp-tools-wired)
                                              │
                                              ▼
                                          2D.6
                              (build-plan-preview+dispatch)
                                              │
                                              ▼
                                          2D.7
                      (agent-run-streaming+diagnostics-provenance)
                                              │
                                              ▼
                                          2D.8
                           (full-roster+keyring+prod-polish)
```

### Parallelizable pairs (after 2D.1 lands)

| Pair | Why safe |
|---|---|
| 2D.2 ∥ 2D.4 | Disjoint surface: 2D.2 is renderer + bridge passthrough of existing Phase 1/2A CLIs; 2D.4 is a greenfield Node service. Neither touches the other's stores. |
| 2D.3 ∥ 2D.5 | 2D.3 extends bridge-transport streaming for `forgeds:widgets:run`; 2D.5 extends orchestrator-transport streaming for MCP tool dispatch. Different ports, different message namespaces. |

Everything from 2D.6 onward serializes, because BuildPlanPreview → AgentRun → Full-roster each depends on the prior sub-phase's user-observable surface.

---

## 4. Per-slice detail

### 2D.0 — ide-shell-finish

**Scope:** Finish tasks 7–20 of `docs/superpowers/plans/2026-04-22-ide-shell-overhaul.md`. Hard prerequisite — no new panel registers cleanly until Dockview persistence, ActivityBar, and ConsolePanel two-level tabs are stable.

**Acceptance:** tasks 7–20 all checked; `npm run build` green; `npx vitest run` green; `test_ide_strictmode_clean` passes against the unmodified shell.

**Seams frozen:** `PanelRegistry` interface on `DockviewHost`; `ideStore.diagnostics` first-class array shape; ConsolePanel category/sub-tab abstraction.

---

### 2D.1 — sidecar-bridge-route

**File-level deliverables:**
- `src/forgeds/sidecar/server.py` — stdlib `http.server` + `threading.Thread`; endpoints `/health`, `/shutdown`, `/forgeds/lint`, `/forgeds/scaffold`, `/forgeds/bundle`, `/forgeds/verify`, `/forgeds/fs/read`, `/forgeds/fs/write`. Streaming endpoints use chunked-transfer NDJSON.
- `src/forgeds/sidecar/__main__.py` — `python -m forgeds.sidecar` entry.
- `src/forgeds/sidecar/port_file.py` — read/write `<project-root>/.forgeds-sidecar.port` with bridge PID.
- Bridge side: new router module + `forgeds:*` handler that resolves port file, lazy-spawns sidecar, round-trips HTTP, and relays diagnostics.
- `pyproject.toml` — new console-script `forgeds-sidecar`.
- Tests: `tests/test_sidecar_lifecycle.py`, `tests/test_sidecar_port_file.py`, `test_bridge_forgeds_router.py`.

**Rule prefix owned:** `SDC###`:
- `SDC001` ERROR sidecar unreachable on health check
- `SDC002` ERROR port-file stale (PID dead)
- `SDC003` WARNING sidecar restart (within 3-per-5-min budget)
- `SDC004` ERROR sidecar restart budget exceeded
- `SDC005` WARNING heartbeat timeout (3 missed)

**Acceptance:**
- `forgeds-sidecar` console script boots and responds to `GET /health`.
- Port collision: occupy 9877 → sidecar probes 9878..9885 → writes chosen port to `.forgeds-sidecar.port`.
- `test_sidecar_port_file_rewrite` green.
- `test_bridge_strips_auth_headers` green (hook exists even though auth lands later).
- `forgeds:cli:lint` round-trips against a fixture widget.

**Open risks:**
- Two IDE windows racing for the same port — mitigated by PID-bearing port file.
- Windows/POSIX atomic-replace differences on port file — `os.replace` covers both.

**Seams frozen:** NDJSON streaming wire format (one JSON object per line, terminated by `{"type":"stream_end", ...}`); bridge `forgeds:*` routing pattern becomes the template for `orchestrator:*` routing.

---

### 2D.2 — readonly-panels

**File-level deliverables:**
- `web/src/components/ide/WidgetExplorer.tsx`
- `web/src/components/ide/ApiPlayground.tsx`
- `web/src/components/ide/DiagnosticsRenderer.tsx`
- `web/src/components/ide/AiBuildLogTab.tsx` — **inert stub**; subscribes to placeholder module `web/src/stores/aiOrchestrationStorePlaceholder.ts` that 2D.6 will delete.
- `web/src/stores/widgetStore.ts`, `web/src/stores/apiPlaygroundStore.ts`.
- `web/src/services/forgedsCli.ts` — typed wrappers over `forgeds:widgets:list` and `forgeds:api:invoke`.
- `web/src/types/forgeds-cli.ts` — shared request/response interfaces.
- `IdeShell.tsx` updated to register the two new panels + AiBuildLogTab sub-tab.
- Tests: `test_widget_explorer_panel_registers`, `test_api_playground_panel_registers`, `test_widget_store_refresh_sets_status`, `test_api_playground_store_history_bounded`, `test_diagnostics_renderer_groups_by_source`.

**Rule prefix owned:** `IDE###`:
- `IDE001` WARNING orphan widget directory on disk not registered in `forgeds.yaml`
- `IDE002` WARNING widget lint never run (lastLintAt null)
- `IDE003` ERROR ApiPlayground: request exceeded 30s timeout
- `IDE004` WARNING ApiPlayground: history truncated (>10 entries)

**Acceptance:**
- Three integration tests for panel registration pass.
- WidgetExplorer refresh button round-trips `forgeds:widgets:list` via the 2D.1 bridge and renders rows with lint status.
- Right-click context menu invokes `forgeds:cli:lint` on a single widget.
- ApiPlayground can POST against a declared Custom API and render response body in read-only Monaco.
- StrictMode: no duplicate fetches, two Monaco editors disposed, context-menu listener cleaned up.
- AiBuildLogTab renders its inert empty-state text under ConsolePanel → Dev Tools.

**Open risks:**
- AiBuildLogTab's placeholder must not create a circular dep with the not-yet-existing `aiOrchestrationStore`; solved by a dedicated placeholder module path.
- WidgetExplorer polling interval vs. StrictMode double-invoke — follow spec §10.1 Rule 1.

**Seams frozen:** `DiagnosticsRenderer` prop shape `(diagnostics: DiagnosticWithAgent[], filter?: Filter)`; placeholder store export path.

---

### 2D.3 — widget-runner-streaming

**File-level deliverables:**
- `web/src/components/ide/WidgetRunner.tsx`
- `web/src/stores/widgetRunStore.ts`
- Extension of `web/src/services/forgedsCli.ts` with `runWidget(widgetId, payload, onChunk, signal)`.
- Bridge-side streaming glue: `forgeds:widgets:run` WS message multiplexed through a single `request.id`; bridge forwards NDJSON lines from sidecar's `/forgeds/verify` as stream chunks.
- Sidecar `/forgeds/verify` hooked to existing `forgeds.widgets.run_widget` Phase 2B entrypoint.
- Tests: `test_widget_runner_panel_registers`, `test_widget_run_store_appends_calls_in_order`, `test_bridge_streams_widget_run`, plus new streaming-specific tests: `test_widget_run_abort_mid_stream`, `test_widget_run_backpressure`.

**Rule prefix:** extends `IDE###`:
- `IDE010` ERROR stream terminated without `stream_end` chunk
- `IDE011` ERROR stream chunk decode failure (non-JSON line)
- `IDE012` WARNING run aborted by user

**Acceptance:**
- Chunks arrive in order; `stream_end` terminates cleanly; diagnostics array is non-null.
- Abort test: unmounting mid-stream does not leave sidecar write-blocked and does not update store after unmount.
- Call-trace nested rendering works via CSS `padding-left: depth * 1rem`.
- "Jump to source" opens widget JS file at stack-trace line.
- StrictMode: Monaco disposed, AbortController fires on unmount.

**Open risks:**
- Node absent → `WGR-meta` surfaces as `IDE010` via `stream_end`-that-isn't path.
- Large trace trees (>1000 calls) — flat-list with depth indent, cheapest render.

**Seams frozen:** NDJSON-chunk → WS-stream-message multiplexing code path in bridge — 2D.7 reuses verbatim for `orchestrator:worker:stream`.

---

### 2D.4 — orchestrator-skeleton + spec-approval

**Rebuttal pass deliverables:**
- `docs/superpowers/rebuttals/2026-04-24-orchestration-spec-rebuttal.md` — point-by-point reply against the orchestration spec's 20 sections.
- User sign-off commit on the rebuttal doc **before** any Node code lands.

**Skeleton deliverables:**
- `tools/orchestrator/package.json` — new package; depends on `@anthropic-ai/claude-agent-sdk`.
- `tools/orchestrator/src/index.ts` — HTTP server on 9878, routes `/orchestrate`, `/health`, `/status/:id`, `/abort/:id`.
- `tools/orchestrator/src/orchestrator.ts` — deterministic dispatch loop; stub architect returning a hardcoded single-task BuildPlan.
- `tools/orchestrator/src/build-plan-executor.ts` — topological sort, Kahn, parallel-batch dispatch; `SDK.query()` stubbed with `Promise.resolve(stubWorker(task))`.
- `tools/orchestrator/src/worker-registry.ts` — full state machine.
- `tools/orchestrator/src/persistence/session-store.ts` — writes `.forgeds/orchestration-session.json` on every transition.
- `tools/orchestrator/src/mcp/forgeds-mcp-server.ts` — **empty shell** `createSdkMcpServer({ name: "forgeds", version: "1", tools: [] })`.
- Python bridge `orchestrator:*` router mirroring 2D.1 pattern, POST to `http://127.0.0.1:9878/orchestrate`.
- `forgeds-build-app` flips from `--plan-only` to live POST path.
- Tests: `worker-registry.test.ts`, `build-plan-executor.test.ts`, `topological-sort.test.ts`, `test_forgeds_build_app_live_post`, `session-resume.test.ts`.

**Rule prefix owned:** `ORC###`:
- `ORC001` ERROR BuildPlan schema validation failed
- `ORC002` ERROR BuildPlan contains dependency cycle
- `ORC003` WARNING BuildPlan missing `edges` (flat plan)
- `ORC004` ERROR orchestrator session aborted (user-initiated)
- `ORC005` ERROR session-budget exceeded (80-call cap)
- `ORC006` WARNING >25% of tasks ABANDONED — replan offered

**Acceptance:**
- Rebuttal doc merged first; commit referenced in Node-service PR.
- `POST /orchestrate` with a fixture prompt returns `sessionId` + `orchestrator:plan:ready` with stub BuildPlan.
- User can approve via `orchestrator:plan:approve`; executor dispatches stub workers; `orchestrator:session:done` fires.
- `forgeds-build-app` without `--plan-only` completes end-to-end against the skeleton.
- Session persistence: kill Node service mid-session → restart → `/status/:sessionId` reflects persisted state.

**Open risks:**
- Without real agents, skeleton could drift from final SDK surface. Mitigated by using real `@anthropic-ai/claude-agent-sdk` types even at stubbed call sites.
- `forgeds-build-app` BLD002 semantics change subtly — update plan-of-record.

**Seams frozen:** BuildPlan JSON schema; `WorkerState` TypeScript interface; orchestrator HTTP surface.

---

### 2D.5 — mcp-tools-wired

**File-level deliverables:**
- `tools/orchestrator/src/mcp/forgeds-mcp-server.ts` — 9 `tool()` definitions: `forgeds_lint_app`, `forgeds_lint_file`, `forgeds_scaffold_form`, `forgeds_scaffold_widget`, `forgeds_verify_runtime`, `forgeds_bundle_app`, `forgeds_read_file`, `forgeds_write_file`, `forgeds_status`. Each body makes HTTP call to 2D.1 sidecar.
- `tools/orchestrator/src/hooks/pre-tool-use.ts` — consults `workerId → allowedToolSet` map; denies foreign tools.
- `tools/orchestrator/src/hooks/post-tool-use.ts` — parses tool-result `diagnostics:` and invokes aggregator.
- `tools/orchestrator/src/diagnostic-aggregator.ts` — annotates with `agent: {id, role, model, session_id}`.
- `canUseTool` implementations: typegen-scoped writes under `_generated/`, scaffold-gen force-overwrite guard, widget-author blocked from `_generated/`, deluge-author scope check.
- Tests: `mcp-tool-routing.test.ts`, `pre-tool-use-allowlist.test.ts`, `can-use-tool-scopes.test.ts`; extend `test_bridge_roundtrip_lint_widgets` to assert `agent:` provenance.

**Rule prefix owned:** `MCP###`:
- `MCP001` ERROR tool not in worker's allowlist
- `MCP002` ERROR `canUseTool` denial (path/scope)
- `MCP003` ERROR sidecar unreachable mid-tool-call
- `MCP004` WARNING tool response missing `diagnostics:` field (envelope drift)
- `MCP005` ERROR MCP schema version mismatch

**Acceptance:**
- All nine tools invocable via SDK `query()` with stub system prompt; each produces diagnostics array with provenance.
- `test_mcp_server_rejects_deploy_from_worker` passes — no deploy tool registered.
- `agent.session_id` carries SDK session_id from first `system:init` message.

**Open risks:**
- MCP tool schemas could drift from Python CLI envelopes — mitigated by consuming existing v1 envelope serializer directly.

**Seams frozen:** Tool schemas (SCHEMA_VERSION = "1"); `agent:` diagnostic provenance field.

---

### 2D.6 — build-plan-preview + dispatch

**File-level deliverables:**
- `web/src/components/ide/BuildPlanPreview.tsx` — modal-on-first-receipt, dock-to-bottom after approval.
- `web/src/stores/aiOrchestrationStore.ts` — full typed interface; replaces the 2D.2 placeholder module.
- `web/src/services/orchestratorClient.ts` — typed wrapper over `orchestrator:plan:*` WS family.
- Orchestrator side: real architect via SDK `query()`; `tools/orchestrator/src/agents/architect.ts`; prompt in `tools/orchestrator/src/agents/system-prompts/architect.md`.
- `tools/orchestrator/src/fast-path-classifier.ts` — keyword matcher per orchestration spec §12.
- BuildPlanPreview dependency-graph SVG rendered via memoized `useMemo` on plan identity.
- **Single worker role** (`worker/linter` — cheapest, read-only, no write path) wired as real-SDK first mover. Others remain stubs.
- Fast-path auto-proceed checkbox.
- Tests: `test_build_plan_preview_panel_registers`, `test_ai_orchestration_store_worker_lifecycle`, `test_orchestrator_client_submits_plan`, `test_orchestrator_error_loop_deterministic` (seeded).

**Rule prefix:** extends `ORC###`:
- `ORC010` INFO fast-path classifier matched — architect skipped
- `ORC011` ERROR architect output not valid BuildPlan JSON
- `ORC012` WARNING architect used > estimated_tool_calls

**Acceptance:**
- User prompt "lint this project" → fast-path → `worker/linter` runs → diagnostics render.
- User prompt "build me something bigger" → architect runs → BuildPlanPreview opens → user approves → plan dispatches (other workers stubs) → session completes.
- `test_preamble_in_sync` green.
- Pre-warming via `startup()` gated behind `forgeds.yaml: orchestrator.prewarm: true`.

**Open risks:**
- Architect cold-start 3-8s without pre-warming — visible latency; mitigated by pre-warming default-on.
- Token cost on architect runs during development — capped at 10 turns per §14.

**Seams frozen:** `aiOrchestrationStore` typed interface; `buildArchitectPrompt(intent, snapshot)` signature.

---

### 2D.7 — agent-run-streaming + diagnostics-provenance

**File-level deliverables:**
- `web/src/components/ide/AgentRun.tsx` — live tree with status badges; selected-worker transcript.
- `AiBuildLogTab.tsx` body filled in — filterable table with `worker_id` column.
- `ConsolePanel.tsx` — Dev Tools > Lint tab adds `source` filter including `worker_id`.
- Editor gutter integration — `EditorPanel` listens to `ideStore.diagnostics` for active file.
- Escalation modal `EscalateModal.tsx` — actions `[view-transcript, amend-plan, skip-task, abort]`.
- Bridge-side `orchestrator:worker:stream` multiplexing reusing 2D.3 NDJSON pattern.
- `includePartialMessages: true` in SDK `query()` options for real workers.
- Bridge debounces `orchestrator:worker:stream` at 50ms.
- Tests: `test_agent_run_panel_registers`, `test_ai_build_log_renders_tool_calls`, `test_orchestrator_diagnostics_batch_has_agent`, `test_escalate_modal_renders_on_blocked_worker`.

**Rule prefix:** extends `ORC###` and `MCP###`:
- `ORC020` ERROR worker transitioned to BLOCKED (after retry budget)
- `ORC021` INFO worker transitioned to DONE_WITH_CONCERNS
- `ORC022` INFO worker ABANDONED (after 3 redispatches)
- `MCP010` WARNING partial-message throughput rate-limited at bridge (50ms debounce saturated)

**Acceptance:**
- AgentRun tree updates live as stub workers transition.
- Clicking a worker row opens transcript.
- Diagnostics from orchestrator carry `agent.*`; direct CLI diagnostics do not — DiagnosticsRenderer handles both shapes.
- Editor gutter fires on real diagnostic after a real orchestrator run through one real worker.
- Escalation modal renders on synthetic BLOCKED, offers all four actions.

**Open risks:**
- Partial-message volume × worker count could exceed WS throughput — 50ms debounce is mitigation; `test_agent_run_renders_under_10_concurrent_workers` as soft gate.
- Transcript memory footprint for long sessions — lazy-mount transcript for only selected worker.

**Seams frozen:** `orchestrator:worker:stream` payload shape; `orchestrator:escalate:human` payload shape.

---

### 2D.8 — full-roster + keyring + prod-polish

**File-level deliverables:**
- `tools/orchestrator/src/agents/worker-definitions.ts` — full 9 AgentDefinitions.
- `tools/orchestrator/src/agents/system-prompts/*.md` — one prompt per role; generated from `CLAUDE.md` gotchas via build step so `test_preamble_in_sync` passes with all roles.
- Bridge-side OS-keyring integration:
  - `src/forgeds/bridge/credentials/keyring_store.py` — Windows via `win32cred`, macOS via `security` CLI subprocess, Linux via `secret-tool` subprocess. Fallback: encrypted file at `.forgeds/credentials.enc` with PBKDF2 + AES (one new optional dep).
  - Passphrase prompt on bridge start if fallback path.
- Bridge injects `Authorization: Zoho-oauthtoken <token>` per-request to sidecar when deploy is called.
- Session persistence expanded: `.forgeds/orchestration-session.json` rotation — keep last 3.
- Pre-warming finalization — SDK `startup()` invoked on bridge boot per `forgeds.yaml` setting.
- Model-tier escalation — cheap → standard → capable, scoped to one redispatch.
- 80-call session budget enforcement + session progress bar in AgentRun header.
- `web/` ESLint rule `no-zoho-secrets`: any `.ts/.tsx` containing `zoho_refresh_token | ZOHO_CLIENT_SECRET | zoho_access_token` fails lint.
- Bridge refuses `ws://` when `NODE_ENV=production`.
- Token-refresh flow 5min-before-expiry, silent to renderer.
- E2E test: `tools/orchestrator/tests/e2e/e2e-expense-tracking-build.test.ts` running §4.2 architect plan against fixture repo; all 8 tasks reach DONE/DONE_WITH_CONCERNS under 80-call budget.
- `session-resume.test.ts` — kills Node service mid-session, restarts, confirms executor skips DONE tasks.
- CLAUDE.md registry update for `SDC###`, `IDE###`, `ORC###`, `MCP###`.

**Rule prefix:** extends all existing ORC/MCP; no new prefix:
- `ORC030` ERROR OS-keyring unavailable and passphrase prompt failed
- `ORC031` WARNING Zoho token refresh succeeded (debug-level only)
- `ORC032` ERROR Zoho token refresh failed — reconnect required
- `MCP020` ERROR deploy tool invocation attempted (third-defense check)

**Acceptance:**
- E2E expense-tracking build runs green under 80-call cap.
- Session-resume test green.
- `no-zoho-secrets` rule fires on fixture containing forbidden substring; passes on every real `.tsx`.
- Bridge refuses `ws://` in production.
- `test_bridge_strips_auth_headers` — real assertion.
- Token refresh test: mock Zoho refresh response; bridge updates token silently.
- Keyring write/read round-trip on current platform passes.

**Open risks:**
- Keyring cross-platform fragility (especially Linux `secret-tool` absence in headless CI) — mitigated by fallback + pytest skip marker.
- Claude API billable test cost on e2e — gate behind `RUN_E2E_LIVE=1`; CI runs against recorded-response VCR cassette.

**Seams frozen for Phase 3+:** OS-keyring adapter interface; roster file is the ONE place a new worker gets added.

---

## 5. WS-message-type ownership matrix

| Message type | Owner | Direction | Mode | Consumed by |
|---|---|---|---|---|
| `forgeds:cli:lint` | 2D.1 | IDE → bridge | req/res | 2D.2 (ctx menu), 2D.6 fast-path |
| `forgeds:cli:scaffold` | 2D.1 | IDE → bridge | req/res | 2D.2 (`+ New`) |
| `forgeds:cli:bundle` | 2D.1 | IDE → bridge | stream | 2D.8 deploy prep |
| `forgeds:cli:verify` | 2D.1 | IDE → bridge | stream | 2D.3 |
| `forgeds:cli:deploy` | 2D.1 | IDE → bridge | stream | 2D.8 (user-initiated) |
| `forgeds:fs:read` | 2D.1 | IDE → bridge | req/res | 2D.2, 2D.3, 2D.7 |
| `forgeds:fs:write` | 2D.1 | IDE → bridge | req/res | 2D.2 |
| `forgeds:diagnostics:broadcast` | 2D.1 | bridge → IDE | event | 2D.2 DiagnosticsRenderer |
| `forgeds:widgets:list` | 2D.2 | IDE → bridge | req/res | WidgetExplorer |
| `forgeds:api:invoke` | 2D.2 | IDE → bridge | req/res | ApiPlayground |
| `forgeds:widgets:run` + `stream` + `stream_end` | 2D.3 | IDE → bridge | stream | WidgetRunner |
| `orchestrator:plan:submit` | 2D.4 | IDE → orchestrator | req/res | 2D.6 |
| `orchestrator:plan:ready` | 2D.4 | orchestrator → IDE | event | 2D.6 |
| `orchestrator:plan:approve` | 2D.4 | IDE → orchestrator | req/res | 2D.6 |
| `orchestrator:session:abort` | 2D.4 | IDE → orchestrator | req/res | 2D.6 + 2D.7 |
| `orchestrator:worker:stream` | 2D.7 | orchestrator → IDE | event | AgentRun transcript |
| `orchestrator:worker:status` | 2D.7 | orchestrator → IDE | event | AgentRun tree |
| `orchestrator:diagnostics:batch` | 2D.7 | orchestrator → IDE | event | ConsolePanel + gutter |
| `orchestrator:escalate:human` | 2D.7 | orchestrator → IDE | event | EscalateModal |
| `orchestrator:session:done` | 2D.7 | orchestrator → IDE | event | AgentRun summary |

---

## 6. Rule-prefix reservations

| Prefix | Owner | Range | Meaning |
|---|---|---|---|
| `SDC###` | 2D.1 | 001-099 | Sidecar / bridge transport lifecycle |
| `IDE###` | 2D.2 (own), 2D.3 (extend) | 001-099 | IDE-side renderer / panel / stream-transport |
| `ORC###` | 2D.4 (own), 2D.6/2D.7/2D.8 (extend) | 001-099 | Node Orchestrator Service (plan, session, worker state, budget) |
| `MCP###` | 2D.5 (own), 2D.7/2D.8 (extend) | 001-099 | MCP tool dispatch / allowlist / `canUseTool` |

Envelope `version` remains `"1"`. `agent:` field is optional per spec §9.

---

## 7. Fixed-input restatement and defense

1. **Keyring in 2D.8.** Zoho OAuth only matters when deploy is live; deploy in 2D is always IDE-user-initiated, so no sub-phase before 2D.8 ships a credential-consuming code path. Keyring backends are platform-fragmented and would bloat earlier sub-phases. The `no-zoho-secrets` ESLint rule is itself a polish item.

2. **Spec-rebuttal bundled with skeleton in 2D.4.** Rebuttal without a reference implementation is theatre; skeleton without rebuttal risks building a spec that's subtly wrong. Bundling forces the rebuttal to be tested against stub-level code. Required ordering: rebuttal commit lands before Node code commit inside 2D.4.

3. **WidgetRunner isolated in 2D.3.** Streaming failure modes (chunked-transfer partial reads, AbortController mid-run, backpressure, Node-toolchain-absent `WGR-meta`, stack-trace line extraction) have their own test surface. Bundling would either delay the non-streaming panels or force streaming tests to wedge into non-streaming test files. `test_widget_run_abort_mid_stream` and `test_widget_run_backpressure` are uniquely justified here.

4. **AiBuildLogTab inert stub in 2D.2.** Adding a new ConsolePanel sub-tab is a ConsolePanel re-layout event. Re-laying out twice would destabilize the just-landed Scripts category. Shipping the tab inert in 2D.2 and swapping its body in 2D.7 freezes ConsolePanel tree-shape at the 2D.2 boundary. `aiOrchestrationStorePlaceholder.ts` is the exact mechanism.

---

## 8. Testing strategy cross-cut

| Layer | 2D.1 | 2D.2 | 2D.3 | 2D.4 | 2D.5 | 2D.6 | 2D.7 | 2D.8 |
|---|---|---|---|---|---|---|---|---|
| **Python unit** | sidecar lifecycle, port-file | — | — | bridge `orchestrator:*` router | — | — | — | keyring, WSS-in-prod |
| **TS/JS unit** | — | store transitions, DiagnosticsRenderer | store order preservation | worker-registry, topo-sort | MCP tool routing | architect-client, plan-validator, fast-path | AgentRun selector memoization | roster, model-tier escalation |
| **Integration** | `forgeds:cli:lint` end-to-end | panel-register × 2, `forgeds:widgets:list` round-trip | WidgetRunner stream round-trip, abort | `orchestrator:plan:*` round-trip, `forgeds-build-app` live | `test_mcp_server_rejects_deploy_from_worker`, scopes, allowlist | `test_build_plan_preview_panel_registers` + fast-path linter | `test_agent_run_panel_registers`, log renders, escalation | session-resume, token-refresh silent |
| **StrictMode** | — | WidgetExplorer + ApiPlayground | WidgetRunner | — | — | BuildPlanPreview | AgentRun + AiBuildLogTab | full shell `test_ide_strictmode_clean` |
| **E2E** | `forgeds-lint-widgets` via bridge | ctx-menu lint smoke | real widget run | `forgeds-build-app` no `--plan-only` | SDK `query()` against stub architect | "lint this project" → fast-path | "build small widget" → approve → single real worker | `e2e-expense-tracking-build` + pause/resume/abort |

Global gates at every boundary: `npx tsc -b --noEmit` clean; `npx vitest run` green; `pytest tests/` green.

---

## 9. Risks to the decomposition itself

| # | Risk | Likelihood | Mitigation |
|---|---|---|---|
| S1 | 2D.4 bundles two concerns (spec-rebuttal + skeleton). If rebuttal surfaces contract-break after skeleton is written, skeleton is waste. | Medium | Rebuttal commit lands BEFORE skeleton within 2D.4; user sign-off gates. If rebuttal breaks spec, stop 2D.4 early and open 2D.4a. |
| S2 | 2D.2's inert AiBuildLogTab placeholder module must be deleted in 2D.6. If forgotten, ships to production. | Low | Conspicuous name; pre-commit grep; `test_ai_orchestration_store_is_real` assertion. |
| S3 | 2D.1's NDJSON contract frozen before orchestrator's partial-message shape known. 2D.7 might want different chunk boundary. | Medium-Low | 2D.1 defines wire format matching SDK's `SDKPartialAssistantMessage`. If 2D.7 disagrees, opens 2D.1a. |
| S4 | ORC/MCP split arbitrary at margins. A `PreToolUse` diagnostic could belong to either. | Medium | Rule: dispatch/tool-body/allowlist → MCP. Session/worker-state-machine/budget → ORC. Documented in 2D.5 commit. |
| S5 | 2D.6's `worker/linter` choice: if architect can't reliably produce linter-only plans for basic prompts, 2D.6 looks empty beyond fast-path. | Medium | Belt (fast-path) + suspenders (real-architect linter dispatch). `test_orchestrator_error_loop_deterministic` runs seeded, not Claude-latency-bound. |
| S6 | 2D.8 is heaviest by margin (8 workers × prompts, keyring × 3 platforms, session resume, e2e, ESLint rule). | High | Acknowledged. May need internal tasking akin to Phase 2C's 12-task controller. Single sub-phase boundary, not single PR. |
| S7 | 2D.3 depends on 2D.1 NDJSON shape; 2D.4 also needs it in parallel. If 2D.4 rejects the shape, 2D.3 may rewire. | Low | 2D.1 locks wire format; bridge-side multiplexer is one function. |
| S8 | "Parallelizable after 2D.1" assumes two streams. Single implementer collapses DAG to linear. | Low | Either ordering works (2D.2/2D.4 disjoint surfaces). Serial traversal valid. |

---

*(Draft B complete — ready for bisimulation diff against Draft A.)*
