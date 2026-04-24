# ForgeDS Widgets — Phase 2D Decomposition (Converged Meta-Spec, Post-Rebuttal)

**Date:** 2026-04-24
**Status:** Post-rebuttal revision — bisimulation converged, critic claims applied. Awaiting user approval.
**Bisimulation artifacts:** `2026-04-24-forgeds-widgets-phase2d-decomposition-A.md`, `-B.md` (both kept as audit trail).
**Rebuttal transcript:** `docs/superpowers/rebuttals/2026-04-24-phase2d-decomposition-rebuttals.md`.
**Source spec:** `docs/superpowers/specs/2026-04-23-forgeds-widgets-phase2d-ide-design.md`
**Orchestration contract:** `docs/superpowers/specs/2026-04-23-forgeds-widgets-phase2-orchestration-design.md`
**Sibling pattern references:** Phase 1, Phase 2A, Phase 2B, Phase 2C plans.

---

## 1. Why this exists

Phase 2D as originally specced bundles five independent concerns behind one milestone: (1) finishing the pre-existing IDE shell-overhaul (tasks 7–20); (2) exposing the already-shipped Phase 2A/2B/2C Python CLIs through the IDE; (3) a new streaming transport contract; (4) designing & implementing a new Node-side agent runtime; (5) building AI-observability UI plus renderer-side security and credential boundary. Each concern has a different blast radius, verification cost, and dependency set.

Following the pattern set by Phase 1 / 2A / 2B / 2C — one shipping layer per phase — we slice Phase 2D into **ten sub-phases, 2D.0 through 2D.9**. Each slice is independently shippable (stopping after any 2D.N leaves the product in a coherent state), owns a distinct rule-code prefix, claims a disjoint WS-message-type range, and has testable exit criteria. Each sub-phase will receive its own `/forgeplan` invocation producing its own sub-spec → plan → simulate → implement cycle.

## 2. Decomposition principles (inherited from 2A/2B/2C)

1. **One new layer per phase.** Phase 2A = config contract; 2B = runtime verifier; 2C = build/deploy pipeline. 2D.N slices follow suit.
2. **Each phase ships user-observable value on its own.** Stopping after any 2D.N leaves the product in a coherent state.
3. **No phase depends on an un-built peer.** Design-only deps are OK if the current phase uses a stub and documents the seam.
4. **One rule-code prefix per phase** (new or extended). Diagnostics from a given phase live in one namespace.
5. **One WS-message-type range per phase.** No cross-phase editing of the catalog.
6. **Exit criteria are testable.** Each sub-phase's plan must satisfy a green-gate checklist before the next phase's spec is authored.
7. **Schema evolution is additive-open.** Shared schemas (BuildPlan, v1 envelope) may gain optional fields without a version bump, provided they are documented as optional and existing consumers are unaffected — consistent with the CLAUDE.md envelope policy.

## 3. Committed judgment calls

These were settled before decomposition; both architects independently validated them:

| Question | Resolution | Rationale |
|---|---|---|
| **OS-keyring credential wiring placement** | 2D.9 (final phase) | Zoho OAuth tokens only matter once deploy hits the wire; deploy in 2D is IDE-user-initiated, not AI-driven. Keyring platform fragmentation (Windows Credential Manager / macOS Keychain / libsecret) would bloat earlier phases with branchy install surface. |
| **Orchestration-spec rebuttal pass** | Bundled with Node-service skeleton in 2D.5 | Rebuttal without a reference implementation is theatre; skeleton without rebuttal risks building a subtly-wrong spec. Ordering inside 2D.5: rebuttal commit lands before skeleton commit; user sign-off gates. |
| **WidgetRunner (streaming panel) vs read-only panels** | Isolated in 2D.3, separate from 2D.2 | Streaming failure modes deserve their own test surface. `test_widget_run_abort_mid_stream` and `test_widget_run_backpressure` are uniquely justified there. |
| **AiBuildLogTab timing** | Inert stub in 2D.2, body filled in 2D.8 | Adding a ConsolePanel sub-tab is a tree-shape change; re-laying out twice would destabilize the Scripts category that shell-overhaul just landed. Placeholder store module `web/src/stores/aiOrchestrationStorePlaceholder.ts` is the mechanism; 2D.7 replaces its body with the real store at the same import path; 2D.8 swaps the `AiBuildLogTab` body. |
| **Architect + BuildPlanPreview vs dispatch + AgentRun** | **Split** — 2D.7 ships the plan-approval UI with a stub executor; 2D.8 ships the dispatch loop and AgentRun | *(Applied post-rebuttal.)* Original convergence merged them; critic correctly identified two distinct user-observable stopping states and flagged retroactive-split as empty mitigation. Splitting now keeps each phase under reviewable size. |

## 4. Sub-phase overview

### 4.1 Table (10 sub-phases)

| # | Slug | One-line deliverable | Rule-prefix (own/extend) | WS-msg range owned |
|---|---|---|---|---|
| **2D.0** | `shell-overhaul-tail` | Finish shell-overhaul tasks 7–20 from existing plan | *(none — uses existing IDE code)* | *(none added)* |
| **2D.1** | `sidecar-bridge-route` | Python HTTP sidecar (port 9877 w/ probe) + `forgeds:*` bridge router + lazy-spawn lifecycle + req/res and chunked-NDJSON streaming + `fs:read` + deploy-intent-token issuance | **owns** `SDC###` | owns `forgeds:cli:*`, `forgeds:fs:read`, `forgeds:diagnostics:broadcast` |
| **2D.2** | `readonly-panels` | `WidgetExplorer` + `ApiPlayground` + `AiBuildLogTab` (inert stub) + `DiagnosticsRenderer` + stores | **owns** `IDE###` | owns `forgeds:widgets:list`, `forgeds:api:invoke` |
| **2D.3** | `widget-runner-streaming` | `WidgetRunner` + `widgetRunStore` + end-to-end NDJSON streaming contract exercise | **extends** `IDE###` (streaming codes) | owns `forgeds:widgets:run` (stream + stream_end) |
| **2D.4** | `fs-security` | `forgeds:fs:write` (atomic + path-scoped + if_match) + `no-zoho-secrets` ESLint rule (with pre-commit hook) + bridge header stripping + deploy-intent-token verification | **owns** `SEC###` | owns `forgeds:fs:write` |
| **2D.5** | `orchestrator-skeleton+spec-approval` | Rebuttal pass on orchestration spec + Node Orchestrator Service skeleton + empty MCP shell + BuildPlan schema (with `estimatedRiskLevel`) + `forgeds-build-app` live POST | **owns** `ORC###` | owns `orchestrator:plan:submit`, `:plan:ready`, `:plan:approve`, `:session:abort` |
| **2D.6** | `mcp-tools-wired` | Full MCP tool catalog (9 tools) proxying to sidecar + `PreToolUse` allowlist + `canUseTool` scoping + `agent:` diagnostic provenance | **owns** `MCP###` | *(none new)* |
| **2D.7** | `architect+buildplan-preview` *(split from original 2D.7)* | Architect agent (real SDK) + `BuildPlanPreview` panel + `aiOrchestrationStore` real (replaces 2D.2 placeholder) + fast-path classifier + **stub dispatch executor** (no real worker runs) | **extends** `ORC###` | *(none new)* |
| **2D.8** | `dispatch+agentrun+first-linter` *(split from original 2D.7)* | Real dispatch loop + worker state machine + `AgentRun` panel + `AiBuildLogTab` body fill + `EscalateModal` + first worker role (linter) — first complete user-visible AI build | **extends** `ORC###`, **extends** `MCP###` | owns `orchestrator:worker:stream`, `:worker:status`, `:diagnostics:batch`, `:escalate:human`, `:session:done` |
| **2D.9** | `full-roster+keyring+prod-polish` | Six more worker roles + OS keyring (with `cryptography` as documented second optional dep) + WSS-in-prod + session resume + preamble-sync test + 80-call budget enforcement + `StrictMode` integration test + E2E "build small app" | **extends** `ORC###`, **extends** `MCP###`, **extends** `SEC###` | *(none new)* |

### 4.2 Dependency DAG

```
                        2D.0  (shell-overhaul-tail)
                           │
                           ▼
                        2D.1  (sidecar-bridge-route)
                ┌──────────┼──────────┐
                ▼          ▼          ▼
             2D.2       2D.3        2D.4
     (readonly-panels) (runner)  (fs-security)
                │          │          │
                │          │          ▼
                │          │       2D.5  (orchestrator-skeleton + spec-approval)
                │          │          │
                │          │          ▼
                │          │       2D.6  (mcp-tools-wired)
                │          │          │
                │          │          ▼
                └──────────┼───────►2D.7  (architect + BuildPlanPreview, stub executor)
                           │          │
                           │          ▼
                           └───────►2D.8  (dispatch + AgentRun + linter)
                                      │
                                      ▼
                                   2D.9  (full roster + keyring + prod-polish)
```

**Edges explained:**
- 2D.2 → 2D.7: the `aiOrchestrationStorePlaceholder` module (shipped by 2D.2) is replaced in 2D.7 at the same import path.
- 2D.2 → 2D.8: the `AiBuildLogTab.tsx` body (inert stub in 2D.2) is filled in 2D.8; `DiagnosticsRenderer` gains optional `worker_id` filtering in 2D.8.
- 2D.3 → 2D.8: the bridge-side NDJSON → WS multiplexer (frozen at the **framing layer** in 2D.3) is reused in 2D.8 with an added payload-translation adapter for `orchestrator:worker:stream` events.

**Parallelizable after 2D.1:** 2D.2, 2D.3, 2D.4 can proceed in any order / in parallel. **Caveat:** at the *file* level, 2D.2 and 2D.4 both touch `web/src/services/forgedsCli.ts` (owned by 2D.2; extended by 2D.4 with the `fs:write` wrapper). If different implementers take the parallel lanes, coordinate merges to avoid conflict — prefer sequencing 2D.2 before 2D.4 when a single implementer holds both. The WS-message-type map in §6 is disjoint at the protocol level; the service wrapper file is not. Recorded as S9 in §10.

Everything from 2D.5 onward serializes strictly; 2D.8 additionally depends on 2D.2 and 2D.3 via the edges above.

## 5. Per-slice detail

### 5.1 Phase 2D.0 — `shell-overhaul-tail`

**Scope.** Execute tasks 7–20 from `docs/superpowers/plans/2026-04-22-ide-shell-overhaul.md`. No new design.

**Entry into `/forgeplan`.** Phase-7 only: `/forgeplan --from-phase 7 --plan docs/superpowers/plans/2026-04-22-ide-shell-overhaul.md`. The plan is already written and approved; this is pure execution.

**Acceptance criteria.**
- All tasks 7–20 marked `[x]` in the plan doc.
- `npx tsc -b --noEmit` clean in `web/`.
- `npx vitest run` green in `web/`.
- `IdePage.tsx` renders only `<IdeShell />`; `DevConsole.tsx` deleted; layout persists to `localStorage` and restores on reload.
- `test_ide_strictmode_clean` (if present from Task 19) green against the unmodified shell.

**Seams frozen for downstream.**
- `PanelRegistry` interface on `DockviewHost.tsx`.
- `ideStore.diagnostics` first-class array shape (current lines 155–161).
- `ConsolePanel.tsx` category / sub-tab abstraction.

---

### 5.2 Phase 2D.1 — `sidecar-bridge-route`

**Scope.**
- New Python module `src/forgeds/sidecar/` (`server.py`, `__main__.py`, `port_file.py`) implementing stdlib `http.server` + `threading.Thread`.
- Endpoints: `GET /health`, `POST /shutdown`, `POST /forgeds/lint`, `POST /forgeds/scaffold`, `POST /forgeds/bundle`, `POST /forgeds/verify`, `POST /forgeds/fs/read`. Streaming endpoints use chunked transfer + NDJSON (one JSON object per line; terminator `{"type":"stream_end", ...}`).
- Port discovery: default 9877, probe 9878–9885, chosen port written to `<project-root>/.forgeds-sidecar.port` (PID-bearing file for multi-window detection).
- New console-script `forgeds-sidecar` in `pyproject.toml`.
- Bridge backend: new `forgeds:*` WS message router + sidecar lazy-spawn on first `forgeds:*` request + health polling + `POST /shutdown` on bridge graceful close + heartbeat every 30 s (3 missed = exit).
- `forgeds:diagnostics:broadcast` event type (bridge → renderer) — consumed by a stub `DiagnosticsRenderer.tsx` (filtering added in 2D.2).
- Crash recovery: max 3 sidecar restarts per 5 min; beyond that → `SDC004` surfaced via `forgeds:diagnostics:broadcast`.
- `forgeds:fs:read` endpoint: 100 KB cap, binary refusal, summary object when truncated. Write path deferred to 2D.4.
- **Deploy-intent-token issuance:** the bridge's `forgeds:cli:deploy` WS handler requires a one-time token. The token is issued by the renderer (generated via `crypto.randomUUID`) ONLY when the user clicks the Deploy button in the IDE, bound to a specific `request.id`, and rejected on any other invocation path. Token mint + verify skeleton ships in 2D.1; final credential-injection wiring in 2D.9.

**Rule prefix owned: `SDC###`.** Allocation (001-099 range):
- `SDC001` ERROR — sidecar unreachable on health check
- `SDC002` ERROR — port-file stale (recorded PID dead)
- `SDC003` WARNING — sidecar restart within 3-per-5-min budget
- `SDC004` ERROR — sidecar restart budget exceeded
- `SDC005` WARNING — heartbeat timeout (3 missed)
- `SDC006` ERROR — NDJSON chunk decoded as non-JSON / missing newline
- `SDC010` WARNING — bridge WS client requested unknown `forgeds:*` type
- `SDC020` ERROR — `forgeds:cli:deploy` invoked without a valid intent-token

**Acceptance criteria.**
- `pytest tests/sidecar/` green: `test_sidecar_lifecycle`, `test_sidecar_port_file_rewrite` (port-file rewritten when 9877 occupied), NDJSON streaming round-trip.
- **Integration: `test_sidecar_restart_budget_exceeded`** — kill sidecar 3 times within a 5-minute window; fourth request triggers `SDC004` (not `SDC003`); bridge emits sidecar-unhealthy banner via `forgeds:diagnostics:broadcast`; no further restart attempted.
- Integration: `forgeds:cli:lint` WS roundtrip returns v1 envelope diagnostics.
- Integration: streaming `forgeds:cli:bundle` over a fixture widget emits ≥ 2 stream chunks then `stream_end`.
- Integration: `test_deploy_intent_token_required` — `forgeds:cli:deploy` invoked without a valid token returns `SDC020`; with a valid token bound to the same `request.id`, succeeds (end-to-end deploy wiring finalized in 2D.9).
- `test_bridge_strips_auth_headers` placeholder test lands (real assertion in 2D.4).

**Seams frozen.**
- **NDJSON streaming wire format (framing layer):** one JSON object per line + `stream_end` terminator. Frozen for 2D.3 and 2D.8. **Payload shapes are NOT frozen** — they differ by endpoint (sidecar emits `CallTraceEntry` objects for widget runs; SDK emits `SDKPartialAssistantMessage` deltas in 2D.8; the framing multiplexer is reused with a payload-translation adapter).
- **Sidecar endpoint contract** versioned via `X-Forgeds-Sidecar-Version: 1` response header.
- **Bridge `forgeds:*` routing pattern** — 2D.5 reuses the same router shape for `orchestrator:*`.
- **v1 diagnostic envelope** is the only shape leaving the sidecar (per CLAUDE.md envelope policy).
- **Deploy-intent-token protocol** (mint → bind to `request.id` → single-use verify).

**Open risks.**
- Windows + Python `http.server` NDJSON flush semantics. Sidecar must `flush()` after each line.
- Two IDE windows racing for the port file. Second instance must detect healthy sidecar via PID file lock and reuse.

---

### 5.3 Phase 2D.2 — `readonly-panels`

**Scope.**
- New panels in `web/src/components/ide/`: `WidgetExplorer.tsx`, `ApiPlayground.tsx`, `AiBuildLogTab.tsx` (**inert stub — no WS listener registered, no store subscription beyond the placeholder**), `DiagnosticsRenderer.tsx` (shared; extends 2D.1's stub with filtering by `source`; `worker_id` filter added in 2D.8).
- New Zustand stores: `widgetStore.ts`, `apiPlaygroundStore.ts` (bounded history = 10).
- Placeholder store: `web/src/stores/aiOrchestrationStorePlaceholder.ts` — empty module subscribed-to by the `AiBuildLogTab` stub. 2D.7 replaces its body with the real `aiOrchestrationStore` at the same import path.
- New service `web/src/services/forgedsCli.ts` — typed WS wrappers. **Note:** this file will be extended by 2D.4 with the `fs:write` wrapper. When 2D.2 and 2D.4 proceed in parallel, coordinate merge order (see §4.2).
- New types file `web/src/types/forgeds-cli.ts`.
- `IdeShell.tsx` updated to register the three new panels / tabs.

**Rule prefix owned: `IDE###`.** Allocation (001-099 range):
- `IDE001` WARNING — orphan widget directory on disk not registered in `forgeds.yaml`
- `IDE002` WARNING — widget lint never run (`lastLintAt` null)
- `IDE003` ERROR — `ApiPlayground` request exceeded 30 s timeout
- `IDE004` WARNING — `ApiPlayground` history truncated (> 10 entries)
- `IDE005` ERROR — panel registered with a panel-id collision
- *(`IDE006`–`IDE009` reserved for future 2D.3 extensions.)*

**Acceptance criteria.**
- Unit: `widgetStore` transitions `loading → idle`; history bounded at 10 in `apiPlaygroundStore`; `DiagnosticsRenderer` groups by `source`.
- Integration: `test_widget_explorer_panel_registers`, `test_api_playground_panel_registers`.
- Integration: `WidgetExplorer` refresh round-trips `forgeds:widgets:list` via 2D.1 bridge; right-click context menu invokes `forgeds:cli:lint`.
- StrictMode: no duplicate fetches; two Monaco editors disposed; context-menu listener cleaned up. `AiBuildLogTab` stub must NOT register any WS listener (lifecycle-leak prevention).
- Manual smoke: `ApiPlayground` POST against a declared Custom API renders response in read-only Monaco.

**Seams frozen.**
- `DiagnosticsRenderer` prop shape `(diagnostics: DiagnosticWithAgent[], filter?: Filter)` — 2D.8 adds the `worker_id` filter key optionally.
- Placeholder store export path — 2D.7 replaces body at same path.

---

### 5.4 Phase 2D.3 — `widget-runner-streaming`

**Scope.**
- New `WidgetRunner.tsx` + `widgetRunStore.ts` (actions `start`, `appendCall`, `finish`).
- Extend `forgedsCli.ts` with `runWidget(widgetId, payload, onChunk, signal)`.
- Bridge-side streaming glue: `forgeds:widgets:run` WS message multiplexed through a single `request.id`; bridge forwards NDJSON lines from sidecar's `/forgeds/verify` as WS `stream` chunks.
- Sidecar `/forgeds/verify` hooked to existing `forgeds.widgets.run_widget` Phase 2B entry.
- Monaco payload editor; `AbortController` lifecycle bound to unmount.

**Rule prefix: extends `IDE###`.**
- `IDE010` ERROR — stream terminated without `stream_end` chunk
- `IDE011` ERROR — stream chunk decode failure
- `IDE012` WARNING — run aborted by user

**Acceptance criteria.**
- Unit: `widgetRunStore` preserves call-order under out-of-order stream chunks.
- Integration: `test_bridge_streams_widget_run`, `test_widget_run_abort_mid_stream`, `test_widget_run_backpressure`.
- Manual smoke: run `expense_dashboard` fixture; call trace renders with depth-indented tree; "Jump to source" opens widget JS at stack-trace line.
- StrictMode: Monaco disposed; run-pending state gated on store `status === "running"` (not local `useState`).

**Seams frozen (framing layer only).**
- Bridge-side NDJSON → WS stream-message **multiplexing infrastructure** (not payload shape) — 2D.8 reuses with a payload-translation adapter for orchestrator partial messages.

**Open risks.**
- Node absent → `WGR-meta` bubbles as `IDE010` via `stream_end`-that-isn't path.
- Large call-traces throttled to 16 ms frame updates.

---

### 5.5 Phase 2D.4 — `fs-security`

**Scope.**
- Sidecar endpoint `POST /forgeds/fs/write`: atomic write (`os.replace`), project-root enforcement, `if_match` SHA, protected-path list, post-write .ds parser validation.
- Bridge strips `Authorization` / `Cookie` / `X-*-Token` headers from forwarded response metadata.
- **Deploy-intent-token verification** (token protocol minted in 2D.1): bridge's `forgeds:cli:deploy` handler validates the token is (a) present, (b) bound to the incoming `request.id`, (c) single-use — rejects with `SEC008` otherwise.
- New ESLint rule `no-zoho-secrets` in the ForgeDS plugin, banning `zoho_access_token`, `ZOHO_CLIENT_SECRET`, `zoho_refresh_token` literals in `web/src/**/*.{ts,tsx}`.
- **Pre-commit hook** wired at the repo root running `no-zoho-secrets` against staged `.ts/.tsx` files — catches violations from any parallel branch before merge, including 2D.2/2D.3 panels developed concurrently.
- WS message type `forgeds:fs:write`.

**Rule prefix owned: `SEC###`.** Allocation:
- `SEC001` ERROR — `forgeds:fs:write` path outside project root
- `SEC002` ERROR — `if_match` mismatch
- `SEC003` ERROR — post-write .ds parser failure (re-emits `DG`/structural)
- `SEC004` ERROR — `forgeds:fs:read` binary file detected
- `SEC005` INFO — bridge stripped a forbidden header (audit counter)
- `SEC006` ERROR — `no-zoho-secrets` ESLint rule match
- `SEC007` ERROR — attempt to write protected / read-only path
- `SEC008` ERROR — `forgeds:cli:deploy` intent-token invalid (wraps `SDC020`)

**Acceptance criteria.**
- Unit: sidecar rejects `../../../etc/passwd`; atomic write leaves no partial file on simulated disk-full; `if_match` mismatch returns 409.
- Unit: bridge drops `Authorization` header (real assertion; previous placeholder replaced).
- Unit: ESLint rule catches fixture with `zoho_access_token = "abc"`; does not fire on any `.tsx` file in `web/` at merge commit, including all 2D.2/2D.3 panels if merged before or at the 2D.4 gate.
- Integration: `test_fs_write_atomic_temp_replace`, `test_fs_write_if_match_mismatch`.
- Integration: `test_deploy_intent_token_verification` — mismatched `request.id` returns `SEC008`; replay (second use of same token) returns `SEC008`.
- Pre-commit hook: test fixture in `tests/fixtures/no_zoho_secrets_violations.tsx` fails `git commit` via the hook.
- Manual smoke: write to protected path returns `E_READ_ONLY_PATH` (`SEC007`); Windows cross-volume fallback works.

**Seams frozen.**
- The `fs:write` endpoint is the **only path** through which IDE-side code and AI workers mutate repo files.
- Header-stripping allowlist is the audit surface for 2D.9 credential routing.
- Deploy-intent-token **verification semantics** frozen; 2D.9 adds the OS-keyring credential injection that happens *after* a verified-token request arrives.

**Open risks.**
- Windows cross-volume atomic rename can fail. Mitigation: detect + fall back to write-then-rename-within-same-dir.

---

### 5.6 Phase 2D.5 — `orchestrator-skeleton` + spec-approval

**Scope (bundled per committed judgment call 2).**

**Spec-approval deliverables (must land first in this phase):**
- `docs/superpowers/rebuttals/2026-04-24-orchestration-spec-rebuttal.md` — point-by-point reply; revised sections land in the orchestration spec itself.
- **User sign-off commit** on the revised orchestration spec before any Node code lands. If rebuttal surfaces a contract break, 2D.5 stops and the skeleton work becomes 2D.5b.

**Skeleton deliverables:**
- `tools/orchestrator/` with `package.json`, TypeScript, `tsc` only (no bundler). Depends on `@anthropic-ai/claude-agent-sdk`.
- `tools/orchestrator/src/index.ts` — `http.createServer` on port 9878; endpoints `/orchestrate`, `/health`, `/status/:id`, `/abort/:id`.
- `tools/orchestrator/src/orchestrator.ts` — deterministic dispatch loop; **stub architect** returns a hardcoded single-task BuildPlan.
- `tools/orchestrator/src/build-plan-executor.ts` — topological sort (Kahn), parallel-batch dispatch; `SDK.query()` stubbed with `Promise.resolve(stubWorker(task))`.
- `tools/orchestrator/src/worker-registry.ts` — full state machine.
- `tools/orchestrator/src/persistence/session-store.ts` — writes `.forgeds/orchestration-session.json` on every transition.
- `tools/orchestrator/src/mcp/forgeds-mcp-server.ts` — **empty shell** (`tools: []`). 2D.6 fills.
- Bridge gains `orchestrator:*` router POSTing to `http://127.0.0.1:9878/orchestrate`.
- `forgeds-build-app` flips from `--plan-only` to live POST path.

**BuildPlan JSON schema (frozen, additive-open) — lands here:**
```
{
  version: "1",
  session_id: string,
  prompt: string,
  created_at: string,          // ISO-8601
  tasks: BuildTask[],
  edges: TaskEdge[],
  estimated_tool_calls: number,
  estimatedRiskLevel: "low" | "medium" | "high"   // consumed by 2D.7 fast-path classifier
}
```
Additive-open policy: optional fields may be added by later phases without a `version` bump, provided existing consumers are unaffected.

**Rule prefix owned: `ORC###`.** Allocation:
- `ORC001` ERROR — BuildPlan schema validation failed
- `ORC002` ERROR — dependency cycle in BuildPlan
- `ORC003` WARNING — BuildPlan missing `edges` (flat plan)
- `ORC004` ERROR — orchestrator session aborted (user-initiated)
- `ORC005` ERROR — session-budget exceeded (wiring here; enforcement in 2D.9)
- `ORC006` WARNING — > 25 % of tasks ABANDONED
- `ORC007` ERROR — orchestrator failed to bind port 9878
- `ORC008` ERROR — MCP server SCHEMA_VERSION mismatch at session-init handshake *(was MCP005 in first draft; moved here per rebuttal — schema-version checks happen at session-init, not per-tool-call)*

**Acceptance criteria.**
- Orchestration spec: rebuttal transcript + revised sections committed; user approval before implementation.
- Unit: `worker-registry.test.ts`, `build-plan-executor.test.ts`, `topological-sort.test.ts`.
- Integration: `POST /orchestrate` returns `sessionId` + `orchestrator:plan:ready` stub BuildPlan; approve → executor dispatches stub workers → `orchestrator:session:done`.
- Integration: `test_forgeds_build_app_live_post` — `forgeds-build-app` without `--plan-only` completes.
- **Integration: `test_skeleton_emits_no_worker_events`** — asserts `/orchestrate` in this phase never emits `orchestrator:worker:*` events (negative assertion, explicit test).
- Session persistence: `session-resume.test.ts` — kill mid-session → restart → `/status/:sessionId` reflects persisted state.

**Seams frozen.**
- BuildPlan JSON schema (additive-open; 2D.7 consumes `estimatedRiskLevel`).
- `WorkerState` TypeScript interface.
- Orchestrator HTTP surface.
- `orchestrator:*` WS envelope shapes.

**Open risks.**
- Skeleton drifts from final SDK surface. Mitigation: use real `@anthropic-ai/claude-agent-sdk` types at stub call sites.
- Node + TypeScript build pipeline is new. Mitigation: minimal `package.json`, `tsc`-only.
- `forgeds-build-app` BLD002 semantics change. Mitigation: record as a delta note in `docs/superpowers/specs/2026-04-24-phase2c-delta-from-2d5.md` (mirroring orchestration spec §17 pattern) — do NOT retroactively edit the Phase 2C plan.

---

### 5.7 Phase 2D.6 — `mcp-tools-wired`

**Scope.**
- `tools/orchestrator/src/mcp/forgeds-mcp-server.ts` populated with 9 tool definitions (per orchestration spec §8.1): `forgeds_lint_app`, `forgeds_lint_file`, `forgeds_scaffold_form`, `forgeds_scaffold_widget`, `forgeds_verify_runtime`, `forgeds_bundle_app`, `forgeds_read_file`, `forgeds_write_file`, `forgeds_status`. Each body proxies to the corresponding 2D.1 sidecar endpoint.
- `PreToolUse` hook — consults `workerId → allowedToolSet` map per orchestration spec §8.2.
- `postToolUse` + `diagnostic-aggregator.ts` — annotates diagnostics with `agent: {id, role, model, session_id}` (additive-optional, no envelope bump).
- `canUseTool` implementations per spec §8.3.
- Deploy tool (`forgeds_cli_deploy`) is **not registered** (fourth-line defense; first three: WS-handler intent-token from 2D.1, ESLint rule from 2D.4, token-verification from 2D.4).

**Rule prefix owned: `MCP###`.** Allocation:
- `MCP001` ERROR — tool not in worker's allowlist
- `MCP002` ERROR — `canUseTool` denial (path/scope)
- `MCP003` ERROR — sidecar unreachable mid-tool-call
- `MCP004` WARNING — tool response missing `diagnostics:` field (envelope drift)
- *(MCP005 moved to `ORC008` per rebuttal — session-init schema version is an orchestrator-layer concern.)*

**Acceptance criteria.**
- All 9 tools invocable via SDK `query()` with stub system prompt; each produces a diagnostics array with `agent.*`.
- Unit: `mcp-tool-routing.test.ts`, `pre-tool-use-allowlist.test.ts`, `can-use-tool-scopes.test.ts`.
- Integration: `test_mcp_server_rejects_deploy_from_worker` — no `forgeds_cli_deploy` tool at server; worker-initiated invocation returns tool-not-found.
- `agent.session_id` carries SDK `session_id` from first `system:init` message.

**Seams frozen.**
- MCP tool schemas at `SCHEMA_VERSION = "1"` (spec §13).
- `agent:` diagnostic provenance (additive-optional).

**Open risks.**
- Tool schemas drift from Python envelopes — mitigated by using `forgeds._shared.envelope` serializer directly.

---

### 5.8 Phase 2D.7 — `architect+buildplan-preview` *(NEW — split from original 2D.7)*

**Scope.** The architect agent runs for real, produces BuildPlans, user sees and approves them. **No real worker dispatch yet** — the executor remains stubbed (inherited from 2D.5). Stopping state: user can type a prompt, watch architecture happen, approve or cancel, and session ends without file writes.

**Deliverables:**
- `web/src/components/ide/BuildPlanPreview.tsx` — modal-on-first-receipt; docks bottom after approval; memoized SVG dependency graph.
- `web/src/stores/aiOrchestrationStore.ts` — full typed interface per Phase 2D spec §3.4. **Replaces** the 2D.2 placeholder at the same import path; `web/src/stores/aiOrchestrationStorePlaceholder.ts` deleted (pre-commit grep guard).
- `web/src/services/orchestratorClient.ts` — typed wrapper over `orchestrator:plan:*` WS family.
- Orchestrator: real architect via SDK `query()`; `tools/orchestrator/src/agents/architect.ts`; prompt generated from `CLAUDE.md` gotchas.
- `tools/orchestrator/src/fast-path-classifier.ts` — keyword matcher per orchestration spec §12.
- `BuildPlanPreview` "Build without reviewing plan" auto-proceed: fires when `tasks.length ≤ 1` AND `estimatedRiskLevel === "low"`.
- Stub executor (inherited from 2D.5) still in place — approval → executor "runs" stub workers synchronously → `orchestrator:session:done` with "approved, stub dispatch complete" summary.

**Rule prefix: extends `ORC###` and `MCP###`.**
- `ORC010` INFO — fast-path classifier matched; architect skipped
- `ORC011` ERROR — architect output not valid BuildPlan JSON (wraps `ORC001`)
- `MCP012` WARNING — architect agent per-invocation tool-call budget warning (`architect used > estimated_tool_calls`). *(Was ORC012 in first draft; moved to MCP per rebuttal — per-invocation concern.)*

**Acceptance criteria.**
- Unit: architect-stub returns deterministic plan for a fixed seeded prompt; BuildPlan schema validation rejects malformed output → `ORC011`.
- Unit: fast-path classifier matches keyword fixtures correctly.
- Integration: `test_build_plan_preview_panel_registers`, `test_orchestrator_client_submits_plan`.
- Integration: **`test_orchestrator_dispatch_loop_stub_architect_deterministic`** *(renamed from prior `test_orchestrator_error_loop_deterministic` — always uses a pre-recorded stub architect; live SDK path is covered only by manual smoke and 2D.9 E2E)*.
- Manual smoke: type "build me an app" → architect runs live → `BuildPlanPreview` opens → approve → stub executor "completes" → toast "Plan approved — worker dispatch lands in 2D.8".
- `test_preamble_in_sync` (preliminary — full version lands in 2D.9) green for architect prompt.

**Seams frozen.**
- `aiOrchestrationStore` final typed interface (2D.8 extends `workerRegistry` consumption, not shape).
- `buildArchitectPrompt(intent, snapshot)` signature.
- `fast-path-classifier` keyword-matcher shape.

**Open risks.**
- Architect cold-start 3–8 s without pre-warming. 2D.9 adds pre-warming; 2D.7 accepts the latency.

---

### 5.9 Phase 2D.8 — `dispatch+agentrun+first-linter` *(NEW — split from original 2D.7)*

**Scope.** Replace the stub executor with the real dispatch loop. Ship `AgentRun`, the first real worker (linter), and the live `AiBuildLogTab`. Stopping state: a user can prompt "lint my app", watch a linter worker run, and see diagnostics flow into the editor and ConsolePanel.

**Deliverables:**
- Real dispatch loop in `tools/orchestrator/src/orchestrator.ts` (replaces stub): topologically sorts BuildPlan, dispatches workers honoring deps, emits events.
- `orchestrator:worker:stream`, `:worker:status`, `:diagnostics:batch`, `:escalate:human`, `:session:done` events.
- `aiOrchestrationStore.workerRegistry` populated; selectors for panel rendering.
- `web/src/components/ide/AgentRun.tsx` — live tree with status badges, model-tier, elapsed, tool-call count, transcript-on-click.
- `web/src/components/ide/EscalateModal.tsx` — on `orchestrator:escalate:human`, offers `[view-transcript, amend-plan, skip-task, abort]`.
- **`AiBuildLogTab.tsx` body filled** (was inert stub in 2D.2; same file path, body swap; inert stub had no WS subscription per 2D.2 acceptance criteria, so this is additive).
- `ConsolePanel.tsx` Lint tab gains `source` filter including `worker_id`.
- `EditorPanel` renders orchestrator-annotated diagnostics on the active file's gutter.
- Bridge-side `orchestrator:worker:stream` multiplexer: reuses 2D.3's NDJSON→WS framing infrastructure with an **added payload-translation adapter** mapping SDK `SDKPartialAssistantMessage` deltas into the UI-ready tool-call event shape.
- Bridge debounces `orchestrator:worker:stream` at 50 ms (**default subject to orchestration spec rebuttal open question #6; 50 ms is the committed default unless rebuttal changes it**).
- `includePartialMessages: true` in SDK `query()` for the first real worker.
- **First real worker — linter:** allowlist `forgeds_lint_app`, `forgeds_lint_file`, `forgeds_read_file`. Returns `{ remediations: RemediationItem[], summary: string }`.
- Other worker roles stubbed; architect's BuildPlan validation rejects tasks naming non-ready roles with `ORC001`.
- Retry policy wired: per-worker retry = 3; session budget = 80 tool calls (enforcement finalizes in 2D.9).

**Rule prefix: extends `ORC###` and `MCP###`.**
- `ORC020` ERROR — worker transitioned to BLOCKED after retry budget
- `ORC021` INFO — worker transitioned to DONE_WITH_CONCERNS
- `ORC022` INFO — worker ABANDONED after 3 redispatches
- `MCP010` WARNING — partial-message throughput rate-limited at bridge (50 ms debounce saturated)

**Acceptance criteria.**
- Unit: `aiOrchestrationStore` worker transitions `WAITING → RUNNING → DONE`; `retryCount` increments on redispatch.
- Integration: `test_agent_run_panel_registers`, `test_ai_build_log_renders_tool_calls`, `test_escalate_modal_renders_on_blocked_worker`.
- Integration: `test_orchestrator_diagnostics_batch_has_agent` — orchestrator diagnostics carry `agent.*`; direct CLI diagnostics don't; `DiagnosticsRenderer` handles both.
- Integration: `test_payload_translation_adapter_maps_sdk_delta_to_tool_call_event` — adapter correctly translates `SDKPartialAssistantMessage` content into the UI tool-call shape.
- Manual smoke (the phase's demo): "lint my app" → architect plans one linter task → linter executes → diagnostics surface in `ConsolePanel` Lint tab + gutter in `EditorPanel` → `AgentRun` shows `✓ DONE`. Fast-path variant: "lint this file" → classifier matches → skip architect → same result.

**Seams frozen.**
- `orchestrator:worker:stream` **payload** shape.
- `orchestrator:escalate:human` payload shape.
- Bridge-side payload-translation adapter interface (swappable if SDK partial-message shape evolves).

**Open risks.**
- Partial-message volume × worker count may exceed WS throughput. 50 ms debounce is the mitigation; `test_agent_run_renders_under_10_concurrent_workers` (2D.9) as the soft gate.
- SDK partial-message shape evolution would require adapter update, not protocol rewrite.

---

### 5.10 Phase 2D.9 — `full-roster` + keyring + prod-polish

**Scope.**

**Six more worker roles** (architect + linter already in place):
- `scaffolder`, `deluge-author`, `widget-author`, `fixer`, `verifier`, `packager`. Each with own system prompt in `tools/orchestrator/src/agents/system-prompts/*.md`, generated from `CLAUDE.md` gotchas via a build step.
- Per-worker MCP tool allowlists (per orchestration spec §8.2).
- **`test_preamble_in_sync`** (full) — every worker's numbered rules equal the matching `CLAUDE.md` gotchas section.

**OS-keyring integration (committed judgment call 1):**
- `src/forgeds/bridge/credentials/keyring_store.py`: Windows via `win32cred`, macOS via `security` CLI subprocess, Linux via `secret-tool` subprocess. Each platform branch import-guarded.
- **Fallback with `cryptography` dependency (stdlib does not provide AES):** encrypted file at `<project-root>/.forgeds/credentials.enc` using PBKDF2-HMAC-SHA256 + AES-GCM via the `cryptography` package. **`cryptography` is formally declared as a second documented optional dep in CLAUDE.md, with the same posture as `pyodbc` — import-guarded, feature skipped on absence.** If the user declines to install `cryptography` AND OS-keyring is unavailable, the fallback degrades to plaintext at `<project-root>/.forgeds/credentials.plain` with 0600 permissions and a conspicuous CLI warning (UI reconnect banner).
- Passphrase prompt on bridge start when using the encrypted-file fallback.
- Bridge injects `Authorization: Zoho-oauthtoken <token>` per-request when IDE-initiated deploy is called with a valid intent-token (verified in 2D.4).
- Token refresh (5 min before expiry) as bridge background task; silent unless refresh fails → renderer reconnect banner.

**Production polish:**
- WSS-in-prod: bridge refuses `ws://` when `NODE_ENV=production`.
- Sidecar log persistence at `<project-root>/.forgeds/sidecar.log`, 10 MB rotation.
- Session persistence: keep last 3 `.forgeds/orchestration-session.json`, archive older.
- Pre-warming: SDK `startup()` on bridge boot, gated by `forgeds.yaml: orchestrator.prewarm: true`.
- Model-tier escalation on BLOCKED: cheap → standard → capable, scoped to one redispatch.
- **80-call session-budget enforcement** (wiring landed in 2D.5; hard halt + progress bar finalize here).
- **CLAUDE.md rule-code registry updated** for `SDC###`, `IDE###`, `SEC###`, `ORC###`, `MCP###`.
- **CLAUDE.md dependency policy updated** to list `cryptography` as a second documented optional dep.

**E2E + regression:**
- `tools/orchestrator/tests/e2e/e2e-expense-tracking-build.test.ts` — runs §4.2 architect plan; all 8 tasks → `DONE`/`DONE_WITH_CONCERNS` under 80-call budget. **Gated behind `RUN_E2E_LIVE=1`; CI runs against VCR cassette playback** (never live API on CI).
- `test_ide_strictmode_clean` — full `IdeShell` under `<StrictMode>`, asserts no console warnings.
- `test_agent_run_renders_under_10_concurrent_workers` — synthetic soft gate for partial-message throughput.
- Manual E2E: "build me a simple todo app" completes within budget.

**Rule prefix: extends existing; no new prefix.**
- `ORC030` ERROR — OS-keyring unavailable and passphrase prompt failed
- `ORC031` WARNING — Zoho token refresh succeeded (debug-level only)
- `ORC032` ERROR — Zoho token refresh failed — reconnect required
- `MCP020` ERROR — deploy tool invocation attempted (third-defense audit; never expected to fire)

**Acceptance criteria.**
- All 7 worker roles present; each has ≥ 1 unit test on system-prompt-to-output fixture.
- `test_preamble_in_sync` green.
- Manual E2E completes ≤ 80 total calls.
- Keyring round-trip test on current platform.
- Encrypted-file fallback test when OS keyring artificially unavailable (with `cryptography` installed).
- Plaintext fallback test when `cryptography` also unavailable (CI matrix covers both).
- Unit: bridge refuses `ws://` in `NODE_ENV=production`.
- Session-resume: kill Node mid-build → restart → executor skips DONE tasks.
- `no-zoho-secrets` passes on all `web/src/**/*.{ts,tsx}` at phase gate (pre-commit hook already active from 2D.4).

**Seams frozen for Phase 3+.**
- OS-keyring adapter interface (swappable backends).
- Worker-definitions file is the ONE place a new worker gets added.
- Dependency policy extended (stdlib + documented optional: `pyodbc`, `cryptography`).

**Open risks.**
- Keyring cross-platform fragility (Linux `secret-tool` absent in headless CI). Mitigated by fallback + pytest skip marker.
- Claude API billable cost on E2E — VCR cassette in CI; `RUN_E2E_LIVE=1` local-only gate.
- Inter-worker file-write conflicts — `if_match` SHA (from 2D.4) forces serialization.

## 6. WS message-type ownership map (canonical)

| Message type | Owner phase | Direction | Mode | Consumed by |
|---|---|---|---|---|
| `forgeds:cli:lint` | 2D.1 | IDE → bridge | req/res | 2D.2 (ctx menu), 2D.7 fast-path |
| `forgeds:cli:scaffold` | 2D.1 | IDE → bridge | req/res | 2D.2 |
| `forgeds:cli:bundle` | 2D.1 | IDE → bridge | stream | 2D.9 deploy prep |
| `forgeds:cli:verify` | 2D.1 | IDE → bridge | stream | 2D.3 |
| `forgeds:cli:deploy` | 2D.1 *(handler + intent-token)*, 2D.4 *(token verification)*, 2D.9 *(OS-keyring credential injection)* | IDE → bridge | stream | 2D.9 (IDE-only, user-initiated) |
| `forgeds:fs:read` | 2D.1 | IDE → bridge | req/res | 2D.2, 2D.3, 2D.8 |
| `forgeds:fs:write` | 2D.4 | IDE → bridge | req/res | 2D.8 workers |
| `forgeds:diagnostics:broadcast` | 2D.1 | bridge → IDE | event | 2D.2 `DiagnosticsRenderer` |
| `forgeds:widgets:list` | 2D.2 | IDE → bridge | req/res | `WidgetExplorer` |
| `forgeds:api:invoke` | 2D.2 | IDE → bridge | req/res | `ApiPlayground` |
| `forgeds:widgets:run` + stream chunks + `stream_end` | 2D.3 | IDE → bridge | stream | `WidgetRunner` |
| `orchestrator:plan:submit` | 2D.5 | IDE → bridge → orchestrator | req/res | 2D.7 |
| `orchestrator:plan:ready` | 2D.5 | orchestrator → IDE | event | 2D.7 |
| `orchestrator:plan:approve` | 2D.5 | IDE → orchestrator | req/res | 2D.7 |
| `orchestrator:session:abort` | 2D.5 | IDE → orchestrator | req/res | 2D.7 + 2D.8 |
| `orchestrator:worker:stream` | 2D.8 | orchestrator → IDE | event | `AgentRun` transcript |
| `orchestrator:worker:status` | 2D.8 | orchestrator → IDE | event | `AgentRun` tree |
| `orchestrator:diagnostics:batch` | 2D.8 | orchestrator → IDE | event | `ConsolePanel` + gutter |
| `orchestrator:escalate:human` | 2D.8 | orchestrator → IDE | event | `EscalateModal` |
| `orchestrator:session:done` | 2D.8 | orchestrator → IDE | event | `AgentRun` summary |

## 7. Rule-prefix reservations

| Prefix | Owner | Range | Meaning |
|---|---|---|---|
| `SDC###` | 2D.1 | 001-099 | Sidecar + bridge transport lifecycle; includes deploy-intent-token mint |
| `IDE###` | 2D.2 (own), 2D.3 (extend) | 001-099 | IDE-side renderer / panel / stream-transport |
| `SEC###` | 2D.4 (own), 2D.9 (extend) | 001-099 | Renderer-side security boundary: fs:write safety, credential stripping, no-zoho-secrets, deploy-intent-token verification |
| `ORC###` | 2D.5 (own), 2D.7 / 2D.8 / 2D.9 (extend) | 001-099 | Orchestrator session lifecycle, state machine, budget, schema-version init handshake |
| `MCP###` | 2D.6 (own), 2D.7 / 2D.8 / 2D.9 (extend) | 001-099 | MCP tool dispatch, per-invocation budgets, allowlist, canUseTool |

Envelope `version` remains `"1"` throughout Phase 2D. Optional-additive fields (`agent:` on diagnostics, `estimatedRiskLevel` on BuildPlan) do not bump.

## 8. Cross-cutting testing strategy

| Layer | 2D.1 | 2D.2 | 2D.3 | 2D.4 | 2D.5 | 2D.6 | 2D.7 | 2D.8 | 2D.9 |
|---|---|---|---|---|---|---|---|---|---|
| **Python unit** | sidecar lifecycle; port-file; intent-token mint | — | — | fs-write atomic+if_match; header-strip; intent-token verify | bridge `orchestrator:*` router | — | — | — | keyring (native+encrypted+plaintext); WSS-in-prod; token refresh |
| **TS/JS unit** | — | store transitions; `DiagnosticsRenderer` | store order preservation | — | `worker-registry`; topo-sort | MCP tool routing; allowlist; `canUseTool` scopes | architect stub determinism; plan validator; fast-path classifier; `BuildPlanPreview` memoization | `AgentRun` memoized selector; payload-translation adapter | roster; model-tier escalation |
| **Integration** | `forgeds:cli:lint` round-trip; **restart-budget exhausted**; deploy-intent-token rejection | panel-registers × 2; `forgeds:widgets:list` round-trip | `WidgetRunner` stream round-trip; abort; backpressure | `test_bridge_strips_auth_headers`; `test_fs_write_*`; `test_deploy_intent_token_verification` | `orchestrator:plan:*` round-trip; `forgeds-build-app` live; **`test_skeleton_emits_no_worker_events`** | `test_mcp_server_rejects_deploy_from_worker` | `test_build_plan_preview_panel_registers`; `test_orchestrator_dispatch_loop_stub_architect_deterministic` | `test_agent_run_panel_registers`; `test_ai_build_log_renders_tool_calls`; `test_escalate_modal_renders_on_blocked_worker`; adapter-translation test | session-resume; e2e-expense-tracking; concurrent-workers throughput |
| **StrictMode hygiene** | — | `WidgetExplorer` + `ApiPlayground` | `WidgetRunner` | — | — | — | `BuildPlanPreview` | `AgentRun` + `AiBuildLogTab` | full-shell `test_ide_strictmode_clean` |
| **Manual E2E / smoke** | `forgeds-lint-widgets` via bridge | ctx-menu lint smoke | run fixture widget | protected-path write | `forgeds-build-app` live post | SDK query vs stub architect | "build me an app" → approve → stub "complete" | "lint my app" → real linter → green demo | "build small todo app" + pause/resume/abort |

Global gates at every phase boundary: `npx tsc -b --noEmit` clean; `npx vitest run` green; `pytest tests/` green.

## 9. Triggering downstream `/forgeplan` runs

For each 2D.N, the next sub-phase's spec is authored **only after** the current phase's exit criteria are green and user approval has passed. Workflow:

1. User invokes `/forgeplan` citing this decomposition + the sub-phase (e.g., "implement 2D.1").
2. `/forgeplan` enters phase 1 (scope) acknowledging the sub-phase is already scoped by this doc — scope gate passes immediately.
3. Brainstorming (phase 2) is brief.
4. Research (phase 3) targets repo-specific patterns for that slice.
5. Architect (phase 4) + spec (phase 5) produce a sub-spec at `docs/superpowers/specs/<YYYY-MM-DD>-forgeds-widgets-phase2d-<slug>-design.md`.
6. Plan (phase 6) + simulate + implement (phase 7) proceed normally.

No sub-phase is authored before its predecessor ships.

## 10. Risks to the decomposition itself

| # | Risk | Likelihood | Mitigation |
|---|---|---|---|
| S1 | **2D.5 bundles spec-rebuttal + skeleton.** If rebuttal breaks the spec, skeleton is wasted. | Medium | Rebuttal commit lands BEFORE skeleton within 2D.5; user sign-off gates. If rebuttal breaks spec, stop 2D.5 early, open 2D.5b. |
| S2 | **2D.2's placeholder must be deleted in 2D.7.** | Low | Conspicuous module name (`aiOrchestrationStorePlaceholder`); pre-commit grep; `test_ai_orchestration_store_is_real` fires after 2D.7. |
| S3 | **2D.1 NDJSON framing reused in 2D.8, but payload shapes differ** (sidecar emits `CallTraceEntry` objects; SDK emits `SDKPartialAssistantMessage` deltas). The framing layer is reusable; the payload layer is not. | Medium | Seam-freeze §5.4 restricts the freeze to **framing-layer infrastructure**. 2D.8 adds a payload-translation adapter at the same bridge code site, tested in `test_payload_translation_adapter_maps_sdk_delta_to_tool_call_event`. Adapter is swappable if SDK shape evolves. |
| S4 | **ORC / MCP split at margins.** A `PreToolUse` diagnostic could belong to either. | Low | Rule: dispatch/tool-body/allowlist → `MCP`; session/state-machine/budget/schema-version → `ORC`. Rebuttal already moved `MCP005` → `ORC008` and `ORC012` → `MCP012` to apply this consistently. |
| S5 | **2D.8 is heavy** (dispatch + AgentRun + `AiBuildLogTab` body + adapter + linter). May not fit one reviewable PR. | Medium | Acknowledged. Single sub-phase boundary, not single PR; plan may have ≥ 10 tasks. Previous over-bundled-with-architect version was split per rebuttal; further split not anticipated. |
| S6 | **2D.9 is heavy** (6 worker prompts × keyring × 3 platforms × session-resume × E2E × WSS). | High | Acknowledged. Concrete trigger for retroactive split 2D.9a/2D.9b: if 2D.9 task count during plan-writing exceeds 30, split per simulator's recommendation. Authority: user, informed by simulation report. This is a real trigger, not empty text. |
| S7 | **Parallel lanes 2D.2 ∥ 2D.3 ∥ 2D.4** may diverge if coordination fails. | Low | §6 matrix is single source of truth; cross-phase edits require a new decomposition revision. |
| S8 | **2D.8 linter-first choice.** If architect can't reliably produce linter-only plans, the demo degrades to fast-path only. | Medium | Belt (fast-path classifier) + suspenders (seeded `test_orchestrator_dispatch_loop_stub_architect_deterministic`). Demo reliability is evaluation-bound, not Claude-latency-bound. |
| **S9** | **Shared-file hazard: `web/src/services/forgedsCli.ts`.** 2D.2 owns it; 2D.4 must extend with `fs:write` wrapper. Parallel lanes produce merge conflicts. | Medium | §4.2 parallelism note; prefer sequencing 2D.2 before 2D.4 when a single implementer; if two implementers, coordinate via shared PR convention (2D.2 merges first). Not a protocol-level conflict (WS types are disjoint), only a file-level one. |
| **S10** | **Deploy WS handler trust boundary.** Even with MCP deploy-tool omission (fourth defense) and ESLint rule (second), the bridge-side `forgeds:cli:deploy` handler is WS-accessible. A compromised renderer or confused worker could theoretically send the WS frame. | Medium-Low | **Deploy-intent-token** protocol lands in 2D.1 (mint, bound to `request.id`, single-use); verification lands in 2D.4. Token is generated by renderer ONLY on user Deploy-button click. Invocation without a valid token returns `SDC020` + `SEC008`. Defense-in-depth layers: (1) intent-token mint/verify; (2) `no-zoho-secrets` ESLint; (3) token-verification in bridge; (4) MCP omission from worker allowlists. |

## 11. What this decomposition does NOT do

- Does not re-derive the Phase 2D design. Original spec is authoritative for component shapes, prompts, interfaces.
- Does not implement any code. Deliverable is this document and the per-sub-phase specs it spawns.
- Does not gate downstream phases on each other's code quality — only on testable exit criteria.
- Does not change rule-prefix ownership of shipped phases (Phase 1 / 2A / 2B / 2C untouched).

## 12. Sign-off gates

Before any 2D.N implementation begins, this document itself needs:
1. **Bisimulation convergence:** merged output of drafts A + B — §5 incorporates both positions where consistent, resolves divergences per §3 judgment calls. ✓ Complete.
2. **Rebuttal pass:** critic claims applied (6 majors + 5 minors + 7 nits); transcript at `docs/superpowers/rebuttals/2026-04-24-phase2d-decomposition-rebuttals.md`. ✓ Complete.
3. **User approval:** human review of this revised spec. *(Gate before 2D.0 / 2D.1 implementation kick-off.)*

Each 2D.N sub-phase additionally requires its own spec to pass a local rebuttal + approval gate before plan-writing, per the standard `/forgeplan` pipeline.

### Bisimulation divergence notes

For audit-trail completeness:
- Twin A used separate `SC###` (sidecar) + `BR###` (bridge) prefixes for 2D.1. Twin B merged them into `SDC###`. Convergence adopts B's merged prefix to avoid fragmented namespace.
- Both twins independently proposed 9 sub-phases; rebuttal grew to 10 via splitting the original 2D.7.
- Both twins agreed on the four committed judgment calls in §3 (keyring placement, spec-approval bundling, streaming-panel isolation, `AiBuildLogTab` inert stub). A fifth judgment call (architect + dispatch split) was added post-rebuttal as Major 5's resolution.
