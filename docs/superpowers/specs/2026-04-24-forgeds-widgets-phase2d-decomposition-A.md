# ForgeDS Widgets — Phase 2D Decomposition (Draft A)

**Date:** 2026-04-24
**Author:** architect twin A (in-session orchestrator)
**Status:** Draft — bisimulation input
**Supersedes planning scope of:** `2026-04-23-forgeds-widgets-phase2d-ide-design.md` (that spec stays as the reference design; this doc governs the *ordering + boundaries* of implementation).

---

## 1. Why this exists

Phase 2D as originally specced bundles five independent concerns behind one milestone:

1. Finishing the pre-existing IDE shell-overhaul (tasks 7–20).
2. Exposing the already-shipped Phase 2A/2B/2C Python CLIs through the IDE.
3. Designing & implementing a new Node-side agent runtime (orchestration spec).
4. Building AI-observability UI (plan preview, agent run tree).
5. Renderer-side security + credential boundary + prod-readiness polish.

Each concern has a different blast radius, verification cost, and dependency set. Following the pattern set by Phase 1 / 2A / 2B / 2C — one shipping layer per phase — we slice Phase 2D into 2D.0 … 2D.8. Each slice is independently shippable, owns a distinct rule-code prefix and WS-message-type range, and has explicit exit criteria. Each will get its own spec → plan → simulate → implement run through `/forgeplan`.

## 2. Decomposition principles (inherited from 2A/2B/2C)

1. **One new layer per phase.** Phase 2A = config contract; 2B = runtime verifier; 2C = build/deploy pipeline. 2D.N slices follow suit.
2. **Each phase ships user-observable value on its own.** Stopping after any 2D.N leaves the product in a coherent state.
3. **No phase depends on an un-built peer.** If a downstream system is merely designed, the current phase treats it as a stub and documents the seam.
4. **One rule-code prefix per phase.** Diagnostics from a given phase are localized to one namespace.
5. **One WS-message-type range per phase.** No cross-phase editing of message-type catalogs.
6. **Exit criteria are testable.** Each sub-phase has a green-gate checklist its plan must satisfy before the next phase's spec is authored.

## 3. Judgment-call resolutions (committed)

These were debated and settled before decomposition:

| Question | Resolution | Rationale |
|---|---|---|
| **Where does OS-keyring credential wiring live?** | 2D.8 | Zoho OAuth tokens only matter when deploy is live; deploy is IDE-user-initiated in 2D (not AI-driven). Dragging keyring into an earlier slice bloats that slice without adding observable value. |
| **Does the orchestration-spec rebuttal pass get its own phase?** | No — bundled into 2D.5 with the Node-service skeleton. | The skeleton is the first proof the spec is correct. Approving the spec without the skeleton gives us no new leverage. |
| **Is WidgetRunner isolated from the other read-only panels?** | Yes — 2D.3, separate from 2D.2. | Streaming has distinct failure modes (chunked-transfer, abort, backpressure). Isolating it means a runtime-verifier bug cannot block `WidgetExplorer` / `ApiPlayground`. |
| **Does `AiBuildLogTab` ship inert in 2D.2 or wait for 2D.7 data?** | Inert stub in 2D.2. | Avoids a second `ConsolePanel` render in 2D.7. The stub renders an empty table with filter controls wired to `aiOrchestrationStore` — which simply has nothing in it until 2D.6. |

## 4. Sub-phase overview

### 4.1 Table

| # | Slug | Deliverable (one-line) | Rule-prefix | WS-msg range |
|---|---|---|---|---|
| 2D.0 | `shell-overhaul-tail` | Finish shell-overhaul tasks 7–20 from the existing plan | *(uses existing)* | *(none added)* |
| 2D.1 | `sidecar-bridge` | Python HTTP sidecar + bridge router + sidecar spawn/health/shutdown + req/res + NDJSON streaming | `SC###`, `BR###` | `forgeds:cli:*`, `forgeds:fs:read` (read-only), `forgeds:diagnostics:broadcast` |
| 2D.2 | `cli-panels-readonly` | `WidgetExplorer` + `ApiPlayground` + `AiBuildLogTab` (inert) + `DiagnosticsRenderer` + stores | `IDE###` | `forgeds:widgets:list`, `forgeds:api:invoke` |
| 2D.3 | `widget-runner-streaming` | `WidgetRunner` panel + `widgetRunStore` + streamed run events | *(reuses IDE/SC)* | `forgeds:widgets:run` (stream) |
| 2D.4 | `fs-security` | `forgeds:fs:write`, atomic-write semantics, `no-zoho-secrets` ESLint rule, bridge header stripping | `SEC###` | `forgeds:fs:write` |
| 2D.5 | `orchestration-skeleton` | Orchestration spec rebuttal + Node Orchestrator Service skeleton + MCP server (8 tools proxy to sidecar) | `ORC###` | `orchestrator:plan:submit`, `orchestrator:plan:ready` (stub architect) |
| 2D.6 | `architect-agent` | Architect system prompt + BuildPlan schema + `BuildPlanPreview` panel + `aiOrchestrationStore` foundations | *(extends `ORC`)* | `orchestrator:plan:approve` |
| 2D.7 | `first-worker-linter` | Dispatch loop + state machine + retry/budget + `AgentRun` panel + single worker role (linter) | *(extends `ORC`)* | `orchestrator:worker:stream`, `:worker:status`, `:diagnostics:batch`, `:escalate:human`, `:session:*` |
| 2D.8 | `full-roster-prod` | Six more worker roles + OS keyring + preamble-sync test + pause/resume + WSS + sidecar log rotation + `StrictMode` integration test | *(extends `ORC`, `SEC`)* | *(none new — polish on existing)* |

### 4.2 Dependency DAG

```
                           ┌──────────► 2D.2  (readonly panels)
                           │
2D.0 ─► 2D.1 ──────────────┼──────────► 2D.3  (streaming panel)
                           │
                           └─► 2D.4 ─► 2D.5 ─► 2D.6 ─► 2D.7 ─► 2D.8
```

**Parallelizable lanes** (different humans or sessions):
- Lane α: 2D.0 → 2D.1
- Lane β after 2D.1: 2D.2, 2D.3, 2D.4 can proceed in any order / in parallel (independent test surfaces)
- Lane γ after 2D.4: 2D.5 → 2D.6 → 2D.7 → 2D.8 is strictly sequential

## 5. Per-slice detail

Each slice below lists: scope, files touched, acceptance criteria, open risks, seams.

### 5.1 Phase 2D.0 — Shell-overhaul tail

**Scope.** Execute tasks 7–20 from `docs/superpowers/plans/2026-04-22-ide-shell-overhaul.md`. No new design.

**Acceptance criteria.**
- All tasks 7–20 marked `[x]` in the plan doc.
- `npx tsc -b --noEmit` clean in `web/`.
- `npx vitest run` green in `web/`.
- `IdePage.tsx` renders only `<IdeShell />`; `DevConsole.tsx` deleted; layout persists to localStorage and restores on reload.

**Note.** This is already-designed work — no new spec. The entry into `/forgeplan` is phase-7 only (`--from-phase 7 --plan docs/superpowers/plans/2026-04-22-ide-shell-overhaul.md`). Treating it as 2D.0 recognizes its prerequisite status without inventing new artifacts.

**Seam going forward.** Once 2D.0 is done, the `PanelRegistry` in `IdeShell.tsx` is the single registration point used by every 2D.N panel.

---

### 5.2 Phase 2D.1 — Sidecar + bridge foundations

**Scope.**
- New Python module `forgeds.sidecar` (or `forgeds._shared.sidecar`) implementing `http.server`-based local service with endpoints `POST /forgeds/lint`, `/forgeds/scaffold`, `/forgeds/bundle`, `/forgeds/verify`, `/forgeds/fs/read`, `/forgeds/shutdown`, `GET /health`. Streaming endpoints use chunked transfer + NDJSON.
- Port discovery: default 9877, probe up to 9885, write chosen port to `<project-root>/.forgeds-sidecar.port`.
- New console-script `forgeds-sidecar` for explicit start (default behaviour: spawned by bridge).
- Bridge backend gains `forgeds:*` WS message router + sidecar spawn-on-first-request + `/health` polling + `POST /shutdown` on bridge graceful shutdown + heartbeat (30 s / 3 misses).
- `forgeds:diagnostics:broadcast` event type (bridge → renderer) — hooks into `ideStore.diagnostics` (stubbed consumer; real rendering lands in 2D.2).
- Crash recovery: max 3 sidecar restarts per 5 min; beyond that → `forgeds:diagnostics:broadcast` error surfaced via a new "sidecar unhealthy" banner.
- No renderer UI beyond a stub `DiagnosticsRenderer.tsx` that renders diagnostic arrays as a list (no filtering yet).

**Rule prefix allocations.**
- `SC001` — sidecar failed to bind any port in probe range.
- `SC002` — sidecar crashed ≥ 3 times in 5 min.
- `SC003` — sidecar subprocess exited non-zero for non-CLI reasons.
- `SC004` — NDJSON stream malformed (invalid UTF-8 / missing newline).
- `BR001` — bridge failed to locate sidecar port file and spawn failed.
- `BR002` — bridge WS client requested unknown `forgeds:*` type.
- `BR003` — bridge stripped header on outbound (info).

**Acceptance criteria.**
- `pytest tests/sidecar/` green: covers port-probe, NDJSON streaming, graceful shutdown.
- Integration test: WS roundtrip `forgeds:cli:lint` → sidecar → `forgeds-lint` exec → response includes diagnostics envelope.
- Integration test: streaming `forgeds:cli:bundle` over a fixture widget emits ≥ 2 stream chunks then `stream_end`.
- Manual smoke: kill sidecar mid-request; bridge surfaces `SC002` warning; subsequent request auto-respawns.

**Seams.**
- WS message-type catalog is published (see §6) and frozen for downstream phases.
- Sidecar endpoint contracts are versioned via `X-Forgeds-Sidecar-Version: 1` response header.
- Diagnostics envelope (see envelope policy in CLAUDE.md) is the only thing leaving the sidecar.

**Open risks.**
- Windows + Python `http.server` NDJSON flush semantics. Sidecar must explicitly `flush()` after each NDJSON line to avoid OS-level buffering on Windows pipes.
- Port-file race when multiple IDE windows open. Second instance must detect healthy sidecar (via PID file lock) and reuse.

---

### 5.3 Phase 2D.2 — Read-only CLI panels

**Scope.**
- New React components in `web/src/components/ide/`: `WidgetExplorer.tsx`, `ApiPlayground.tsx`, `AiBuildLogTab.tsx` (inert stub), `DiagnosticsRenderer.tsx` (shared).
- New Zustand stores: `widgetStore` (list state, loading, refresh), `apiPlaygroundStore` (last req/res, bounded history=10). `aiOrchestrationStore` shell with empty `workerRegistry` (used by `AiBuildLogTab` stub).
- WS message types `forgeds:widgets:list` (req/res) and `forgeds:api:invoke` (req/res) in both sidecar and bridge router.
- Panel registration in `IdeShell.tsx` (wired via Task-14 `PanelRegistry` from 2D.0).

**Rule prefix allocations.**
- `IDE001` — panel registered with a panel-id collision.
- `IDE002` — store action triggered before bridge connected.
- `IDE003` — `forgeds:widgets:list` returned a widget whose manifest fails schema (surfaces WG004).

**Acceptance criteria.**
- Unit: `widgetStore` transitions `loading → idle` on fetch complete; history bounded at 10 in `apiPlaygroundStore`.
- Integration: `test_widget_explorer_panel_registers`, `test_api_playground_panel_registers` — panels appear in `PanelRegistry` on `IdeShell` mount.
- StrictMode: no duplicate fetches, no leaked intervals — verified by component-level React Testing Library mount under `<StrictMode>`.
- Manual smoke: with a sample `forgeds.yaml`, opening the IDE shows `WidgetExplorer` populated; clicking a row opens `plugin-manifest.json` in the EditorPanel; `ApiPlayground` can invoke a Custom API and render response.

**Seams.**
- `DiagnosticsRenderer` is the ONLY component consuming `ideStore.diagnostics`. 2D.3 through 2D.8 extend diagnostics sources but not the renderer.
- `AiBuildLogTab` filter controls query `aiOrchestrationStore` — they render empty until 2D.6 populates the store.

**Open risks.**
- Virtualization (`react-window`) import cost; if not already a transitive dep, skip virtualization until 2D.7 when volumes rise.

---

### 5.4 Phase 2D.3 — WidgetRunner (streaming panel)

**Scope.**
- New component `web/src/components/ide/WidgetRunner.tsx`.
- New store `widgetRunStore` with `start`, `appendCall`, `finish` actions; streaming subscription via `AbortController`.
- WS message type `forgeds:widgets:run` with stream chunks + `stream_end`.
- Monaco editor payload input (reuse existing Monaco setup from shell overhaul).

**Acceptance criteria.**
- Unit: `widgetRunStore` preserves call-order under out-of-order stream chunks.
- Integration: `test_bridge_streams_widget_run` — chunks arrive in order, `stream_end` fires with `diagnostics` + `total_calls`.
- Manual smoke: run `expense_dashboard` fixture widget; call trace renders with depth-indented tree; error rows red-highlighted.
- StrictMode: aborting mid-stream does not double-emit; Monaco instance disposed on unmount.

**Seams.**
- `widgetRunStore` does not talk to `aiOrchestrationStore`. Orchestrator-driven widget runs (2D.7+) flow through `aiOrchestrationStore.workerRegistry` instead.

**Open risks.**
- Large call-traces (> 1000 calls) blow store-subscriber reflow. Mitigation: throttle `appendCall` updates to 16 ms frames.

---

### 5.5 Phase 2D.4 — File I/O + renderer-side security

**Scope.**
- Sidecar endpoints `POST /forgeds/fs/write` + the existing `/forgeds/fs/read` extended with 100 KB cap, binary refusal, summary object when truncated.
- Atomic write: temp file + `os.replace()`; `if_match` SHA check.
- Path validation: every request rejected if resolved path falls outside `<project-root>`.
- Bridge strips `Authorization`, `Cookie`, `X-*-Token` headers from any response metadata it forwards.
- New ESLint rule `no-zoho-secrets` (ForgeDS plugin, reused from `src/forgeds/widgets/configs/.eslintrc.zoho.json` plugin package) banning `zoho_access_token`, `ZOHO_CLIENT_SECRET`, `zoho_refresh_token` literals in `web/src/**/*.{ts,tsx}`.
- WS message type `forgeds:fs:write` in bridge + sidecar.

**Rule prefix allocations.**
- `SEC001` — `forgeds:fs:write` path outside project root.
- `SEC002` — `forgeds:fs:write` if-match mismatch.
- `SEC003` — `forgeds:fs:write` post-write .ds parser failure (re-emits `DG`/structural).
- `SEC004` — `forgeds:fs:read` binary file detected.
- `SEC005` — bridge stripped a forbidden header (info — counted for audit).
- `SEC006` — `no-zoho-secrets` ESLint rule match.

**Acceptance criteria.**
- Unit: sidecar rejects `../../../etc/passwd` path; atomic write leaves no partial file on disk-full simulation; `if_match` mismatch returns 409.
- Unit: bridge response-forwarder drops `Authorization` header; assert via fixture.
- Unit: ESLint rule catches a fixture that embeds `zoho_access_token = "abc"`.
- Integration: `test_bridge_strips_auth_headers`, `test_fs_write_atomic_temp_replace`.
- Manual smoke: `write_file` to a protected path (`zoho_widget_sdk.db`) returns `E_READ_ONLY_PATH`.

**Seams.**
- The `fs:write` endpoint is the only path through which IDE-side code (or AI workers in 2D.7+) mutates repo files. Bundler / scaffolder / deployer continue to use their own Python CLI paths — the sidecar is the IDE-facing façade.

**Open risks.**
- Atomic rename across Windows volumes can fail. Mitigation: detect cross-volume paths and fall back to write-then-rename-within-same-dir.

---

### 5.6 Phase 2D.5 — Orchestration-spec approval + Node-service skeleton + MCP server

**Scope.**
- **Spec approval pass.** Run a rebuttal cycle on `docs/superpowers/specs/2026-04-23-forgeds-widgets-phase2-orchestration-design.md`. Critic + author cycle; revised spec commits. This is a hard prerequisite — the skeleton implements that spec.
- **Node Orchestrator Service** (new directory `orchestrator/`). Node + TypeScript. Express or `http.createServer` listening on port 9878 (per spec). Endpoints: `POST /orchestrate` accepting `{ prompt, projectSnapshot, sessionId }` and returning a BuildPlan JSON. In this phase, architect returns a **stub BuildPlan** — enough to prove the transport round-trips — not a real one.
- **MCP server** (`orchestrator/mcp/forgeds-mcp-server.ts`): implements the 8-tool catalog from Phase 2D spec §6.1, each tool proxying to the sidecar's matching endpoint. No AI-specific logic yet.
- **Bridge routing** forwards `orchestrator:*` messages to the Node service over loopback HTTP.
- `forgeds-build-app --plan-only` already emits a BuildPlan-shaped JSON; this phase wires `--plan-only` so it can (optionally) POST to the live service and receive the stub-architect response, confirming the wire format.

**Rule prefix allocations.**
- `ORC001` — Node service failed to bind port 9878 (or probe range).
- `ORC002` — MCP tool proxy failed (sidecar unreachable, downstream `SC002` surfaced).
- `ORC003` — BuildPlan schema validation failure (from architect or stub).
- `ORC004` — orchestrator session ID conflict.

**Acceptance criteria.**
- Orchestration spec has a committed rebuttal transcript and revised sections; user explicitly approves the revised spec before implementation begins.
- Unit: Node service `/orchestrate` with a synthetic prompt returns a well-formed stub BuildPlan.
- Unit: MCP server `forgeds_read_file` tool invocation proxies through sidecar correctly.
- Integration: `forgeds-build-app --plan-only --post http://127.0.0.1:9878/orchestrate` round-trips and the returned stub plan passes schema validation.
- No architect or workers yet — verified by: `/orchestrate` never emits `orchestrator:worker:*` events in this phase.

**Seams.**
- BuildPlan JSON schema is frozen at end of 2D.5; 2D.6 consumes it verbatim.
- MCP tool allowlist shape frozen; 2D.7 per-worker allowlists select subsets.
- `orchestrator:*` WS message shapes frozen; 2D.6/2D.7 only extend payloads, not envelopes.

**Open risks.**
- Node + TypeScript adds a new build pipeline to the repo. Mitigation: single `orchestrator/package.json` with `tsc` invocation, no bundler. Re-use MCP SDK types where available.
- `@anthropic-ai/claude-agent-sdk` import only lands in 2D.6. 2D.5 stub does not yet call Anthropic.

---

### 5.7 Phase 2D.6 — Architect agent + BuildPlanPreview

**Scope.**
- Architect agent dispatched by Node service on `POST /orchestrate`. Architect system prompt per Phase 2D spec §7.1. Uses Claude Agent SDK `query()`. Returns a validated BuildPlan JSON.
- `BuildPlanPreview.tsx` panel — receives `orchestrator:plan:ready` event, renders task tree + dependency graph, exposes Approve/Edit/Cancel actions via `orchestrator:plan:approve` / `:session:abort`.
- `aiOrchestrationStore` extended with `activeBuildPlan`, `sessionId`.
- Fast-path toggle ("Build without reviewing") — honored only for BuildPlans where `tasks.length ≤ 1` AND architect's `estimatedRiskLevel` is "low" (per orchestration spec — must be present in the BuildPlan schema after 2D.5).
- Approval flow ends the session (no worker dispatch yet) — user sees "Plan approved; worker dispatch pending Phase 2D.7" toast.

**Acceptance criteria.**
- Unit: architect-stub returns deterministic plan for a fixed prompt seed.
- Unit: BuildPlan schema validation rejects malformed architect output and sidecar surfaces `ORC003`.
- Integration: `test_build_plan_preview_panel_registers`; `test_orchestrator_client_submits_plan`.
- Manual smoke: user types "build me an expense app", sees plan panel, clicks Approve, toast confirms end-of-session.

**Seams.**
- Worker dispatch machinery is stubbed: orchestrator acknowledges approval but does not dispatch. `orchestrator:session:done` fires immediately with `summary: "approved, no dispatch"`.

**Open risks.**
- Architect system-prompt preamble drifts from CLAUDE.md gotchas. Mitigation: preamble lives in an extracted file that CLAUDE.md references by include, and a test asserts equality (full `test_preamble_in_sync` lands in 2D.8).

---

### 5.8 Phase 2D.7 — Worker dispatch + AgentRun + first worker (linter)

**Scope.**
- Orchestrator dispatch loop: topologically sort BuildPlan tasks, dispatch workers, honor task dependencies.
- Worker state machine: `WAITING → RUNNING → DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED | ABANDONED`.
- Retry policy: per-worker retry = 3, per-session budget = 80 tool calls.
- `orchestrator:worker:stream`, `:worker:status`, `:diagnostics:batch`, `:escalate:human`, `:session:done`, `:session:abort` events.
- `AgentRun.tsx` panel: tree of architect + workers with live status, model-tier, elapsed, tool-call count, transcript on click.
- `aiOrchestrationStore` `workerRegistry` Map populated; selectors for panel rendering; pause/resume actions.
- One worker role: **linter**. Allowlist: `forgeds:lint:app`, `forgeds:lint:file`, `forgeds:read:file`. Returns `{ remediations: [...], summary: string }`.
- `AiBuildLogTab` wired to real data (filter by `worker_id`).

**Acceptance criteria.**
- Unit: `aiOrchestrationStore` worker transitions `WAITING → RUNNING → DONE` on matching events; `workerRegistry.retryCount` increments on redispatch.
- Integration: `test_orchestrator_error_loop_deterministic` with a seeded linter worker and a fixture app.
- Integration: `test_agent_run_panel_registers`; `test_ai_build_log_renders_tool_calls`.
- Manual smoke: prompt "lint my app" → architect plans one task → linter worker runs → diagnostics surface → AgentRun shows ✓ DONE.

**Seams.**
- Other worker roles defined but un-implemented; architect's BuildPlan-schema rejects tasks that name a role not in the current roster (`{linter}` only).
- 80-call budget surfaces as a `SessionBudgetBanner` once ≥ 60 calls consumed.

**Open risks.**
- Deterministic replay test depends on Claude SDK's seed support. If seed isn't exposed, fall back to snapshotting the dispatch sequence + tool-call names (not payloads).
- Pause/resume semantics for long-running tool calls: an in-flight call completes before suspension. Document in spec §8.3.

---

### 5.9 Phase 2D.8 — Full worker roster + production polish + credentials

**Scope.**
- Six additional worker roles: `scaffolder`, `deluge-author`, `widget-author`, `fixer`, `verifier`, `packager`. Each with its own system prompt (per Phase 2D spec §7.3) and a narrow MCP allowlist (per orchestration spec §8.2).
- `test_preamble_in_sync` — every worker's numbered rules equal the matching CLAUDE.md gotchas section.
- OS-keyring integration (`keyring` Python package, guarded by ImportError; fall back to encrypted-file-with-passphrase). Used exclusively for Zoho OAuth tokens held by the bridge. Never accessed by Node service directly.
- Token refresh (5 min before expiry) as a bridge-side background task.
- WSS in `NODE_ENV=production`; bridge refuses `ws://` when prod-mode env var set.
- Sidecar log persistence at `<project-root>/.forgeds/sidecar.log`, rotated at 10 MB.
- `test_ide_strictmode_clean` — mount `IdeShell` under `<StrictMode>`, assert no console warnings.
- Manual E2E: user types "build me a simple todo app", sees full flow, assembled app lints clean + runtime-verifies + `< 80` tool calls consumed.
- Session-budget soft cap at 60 (warning toast), hard cap at 80 (halt + escalate).

**Acceptance criteria.**
- All worker roles present, each with at least one dedicated unit test of its system-prompt-to-output shape on a fixture input.
- `test_preamble_in_sync` green.
- Manual E2E above completes with total-calls ≤ 80.
- Keyring: first-run prompts for Zoho OAuth, stores via keyring, subsequent runs auto-refresh; on refresh failure, renderer shows reconnect banner.

**Seams.**
- Phase 2D is considered "complete" when this phase exits.

**Open risks.**
- Inter-worker file-write conflicts (scaffolder T4 and deluge-author T3 touching adjacent .ds regions). Mitigation: `if_match` SHA check in `forgeds:fs:write` (already in 2D.4) forces serialization.
- Deluge-author preamble length and CLAUDE.md gotchas section growth. Mitigation: keep preamble as an include rather than a copy.

## 6. WS message-type ownership map

This matrix is the canonical allocation. No phase may introduce a type claimed by another phase. Types not listed are not yet planned.

| Message type | Owner phase | Mode |
|---|---|---|
| `forgeds:widgets:list` | 2D.2 | req/res |
| `forgeds:widgets:run` | 2D.3 | stream |
| `forgeds:api:invoke` | 2D.2 | req/res |
| `forgeds:cli:lint` | 2D.1 | req/res or stream |
| `forgeds:cli:scaffold` | 2D.1 | req/res |
| `forgeds:cli:bundle` | 2D.1 | stream |
| `forgeds:cli:verify` | 2D.1 | stream |
| `forgeds:cli:deploy` | 2D.1 (wiring) / 2D.8 (creds) | stream |
| `forgeds:fs:read` | 2D.1 | req/res |
| `forgeds:fs:write` | 2D.4 | req/res |
| `forgeds:diagnostics:broadcast` | 2D.1 | event |
| `orchestrator:plan:submit` | 2D.5 (skeleton) / 2D.6 (real) | req/res |
| `orchestrator:plan:ready` | 2D.5 / 2D.6 | event |
| `orchestrator:plan:approve` | 2D.6 | req/res |
| `orchestrator:worker:stream` | 2D.7 | event |
| `orchestrator:worker:status` | 2D.7 | event |
| `orchestrator:diagnostics:batch` | 2D.7 | event |
| `orchestrator:escalate:human` | 2D.7 | event |
| `orchestrator:session:done` | 2D.6 (stub) / 2D.7 (real) | event |
| `orchestrator:session:abort` | 2D.6 | req/res |

## 7. Rule-prefix reservations

| Prefix | Owner phase | Range | Notes |
|---|---|---|---|
| `SC###` | 2D.1 | 001-099 | Sidecar process + transport |
| `BR###` | 2D.1 | 001-099 | Bridge routing + WS protocol |
| `IDE###` | 2D.2 | 001-099 | Panel registration + store invariants |
| `SEC###` | 2D.4 | 001-099 | FS-write + credential boundary |
| `ORC###` | 2D.5+ | 001-099 | Orchestrator / MCP / Node service |

Widget rule prefixes (`WG`, `WGR`, `WSP`, `SCF`, `BND`, `DPY`, `BLD`) are **unchanged** by Phase 2D. Every new diagnostic from 2D lives in the five prefixes above.

## 8. Cross-cutting testing strategy

- **Every phase ships both Python-side and TypeScript-side tests** where applicable. Phases with no Python delta (2D.2, 2D.3, 2D.6, 2D.7, 2D.8 UI parts) get only TypeScript tests; phases with no TS delta (none in this slicing) would get only Python tests.
- **Integration tests that span the WS transport** live in `tests/integration/` and spin up the sidecar as a subprocess in the fixture.
- **Manual E2E** for each phase is documented in the phase's spec under a "Manual verification" heading; automated E2E against a live Zoho Creator project is out of scope until 2D.8.
- **StrictMode hygiene** is tested at the component level in 2D.2 / 2D.3 / 2D.6 / 2D.7 (for the new panels introduced there) and at the full-shell level in 2D.8 (`test_ide_strictmode_clean`).

## 9. Triggering downstream `/forgeplan` runs

For each 2D.N, the next sub-phase's spec is authored **only after** the current phase's exit criteria are green and a user approval gate is passed. The workflow per sub-phase:

1. User invokes `/forgeplan` citing this decomposition + the sub-phase (e.g., "implement 2D.1").
2. `/forgeplan` enters phase 1 (scope) acknowledging the sub-phase is already scoped by this doc.
3. Brainstorming (phase 2) is brief — high-level design is already fixed; what varies is implementation detail.
4. Research (phase 3) targets repo-specific patterns for that slice (e.g., for 2D.1, Python `http.server` idioms, NDJSON chunked-transfer on Windows).
5. Architect (phase 4) + spec (phase 5) produce a sub-spec at `docs/superpowers/specs/2026-04-??-forgeds-widgets-phase2d-<slug>-design.md`.
6. Plan (phase 6) + simulate + implement (phase 7) execute normally.

No sub-phase is authored before its predecessor ships.

## 10. Risks to the decomposition itself

| Risk | Mitigation |
|---|---|
| 2D.5 bundles spec approval + implementation; if the rebuttal pass requires major spec revisions, the implementation deliverable for 2D.5 shrinks or slips. | Separate the spec-approval artifact (commit before implementation begins). If revisions are large, 2D.5 splits into 2D.5a (spec) + 2D.5b (skeleton) retroactively. |
| Parallel lanes (2D.2 / 2D.3 / 2D.4) after 2D.1 may diverge if not coordinated. | WS-message-type map in §6 is the coordination artifact; no cross-phase edits to it without a new decomposition doc. |
| Worker-role count in 2D.8 is seven total; each prompt + allowlist is non-trivial. 2D.8 may expand. | If 2D.8's plan exceeds a reasonable cap (say 30 tasks), split into 2D.8a (scaffolder + deluge-author + widget-author) and 2D.8b (fixer + verifier + packager + creds + polish). |
| Orchestrator Node-service introduces a new build toolchain to the repo. | `orchestrator/package.json` kept minimal; no bundler; TypeScript compiled via `tsc`. New `forgeds-orchestrator` console-script bridges to the existing Python ecosystem only where needed. |

## 11. What this decomposition does NOT do

- Does not re-derive the Phase 2D design from scratch. The original spec is authoritative for component shapes, prompts, and interfaces.
- Does not implement any code. The deliverable is this document and its approved successor.
- Does not gate downstream sub-phases on each other's code quality — only on their exit criteria being testably green.

---

*(Draft A complete. Awaiting draft B from the twin architect for bisimulation.)*
