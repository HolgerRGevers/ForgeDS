# Phase 2D Decomposition — Rebuttal Transcript

**Date:** 2026-04-24
**Target document:** `docs/superpowers/specs/2026-04-24-forgeds-widgets-phase2d-decomposition.md`
**Critic:** `feature-dev:code-reviewer` (sonnet)
**Author response:** in-session orchestrator (opus)
**Bisimulation drafts (audit trail):** `-A.md`, `-B.md` alongside the canonical spec.

Critic returned 6 major + 8 minor + 7 nit claims. The author accepted all 6 majors and the top 5 minors, with revisions applied in-place to the canonical spec. Outcome: the canonical spec is renumbered from 9 sub-phases (2D.0–2D.8) to **10 sub-phases (2D.0–2D.9)** because the old 2D.7 is split into two per Major 5.

---

## Majors

### MAJOR 1 — Shared-file parallelism hazard on `forgedsCli.ts`

**Critic claim:** §4.2 claims 2D.2 ∥ 2D.3 ∥ 2D.4 is safe parallelism, but 2D.4 needs to extend `web/src/services/forgedsCli.ts` (owned by 2D.2) with a write wrapper, creating a shared-file merge hazard.

**Author response:** Accepted. The disjointness claim is at the WS-message-type level; `forgedsCli.ts` is a shared service file. Two fixes: (a) qualify the parallelism statement in §4.2; (b) add S9 risk. Applied: see §4.2 parallelism-note and §10 S9.

### MAJOR 2 — Sidecar NDJSON wire format ≠ SDK partial-message shape

**Critic claim:** §10 S3 mitigation asserts "2D.1 wire format matches SDK's `SDKPartialAssistantMessage` natural serialization" — but sidecar NDJSON carries `CallTraceEntry` objects (per Phase 2D spec §4.2), whereas SDK partial messages carry assistant-message deltas. These are different at the payload layer; only the framing layer (one JSON per line + `stream_end`) is reusable.

**Author response:** Accepted, and the critic's distinction is correct and material. The bridge NDJSON→WS multiplexer is frozen at the **framing layer**, not the payload layer; 2D.7 will add a payload-translation adapter at the same code site. Applied: rewrote §10 S3 mitigation and §5.4 seam-freeze.

### MAJOR 3 — BuildPlan schema missing `estimatedRiskLevel` field

**Critic claim:** 2D.5 freezes the BuildPlan schema, but 2D.7's fast-path classifier auto-proceeds when `architect's estimatedRiskLevel is "low"`. This field is absent from the schema.

**Author response:** Accepted. Two fixes available: (a) add `estimatedRiskLevel: "low" | "medium" | "high"` to the BuildPlan schema in 2D.5, (b) declare "additive-open" (mirroring the v1 envelope policy that allows optional-additive fields without version bump). Applied (a) — explicit field added in 2D.5 scope; also added an additive-open policy note consistent with CLAUDE.md envelope policy.

### MAJOR 4 — Missing DAG edges: 2D.2 → 2D.7 and 2D.3 → 2D.7

**Critic claim:** The old 2D.7 modifies 2D.2 deliverables (`AiBuildLogTab` body, `aiOrchestrationStorePlaceholder` replacement, `DiagnosticsRenderer` filter extension) and reuses 2D.3's NDJSON→WS multiplexer. These are direct code dependencies; the DAG omits them, violating principle 3 ("no phase depends on an un-built peer").

**Author response:** Accepted. Added edges. After the 2D.7 split in response to Major 5, the edges now flow 2D.2 → 2D.8 and 2D.3 → 2D.8 (since the `AiBuildLogTab` body fills in the new 2D.8, the `AgentRun` bridge multiplexer reuses 2D.3's infrastructure in 2D.8). The 2D.2 `aiOrchestrationStorePlaceholder` replacement moves to 2D.7 (the new architect phase) since that's where the real store lands. Applied: §4.2 DAG updated.

### MAJOR 5 — 2D.7 retroactive-split mitigation is empty; split now

**Critic claim:** S5 acknowledges High-likelihood risk and responds with "may retroactively split into 2D.7a/2D.7b" — this is a deferred decision, not a mitigation. The two sub-concerns (architect + BuildPlanPreview with stub dispatch; dispatch + AgentRun + linter) are distinct user-observable stopping states. Split now.

**Author response:** Accepted. The critic's structural argument is sound — "retroactive split" language converts a real risk into empty text. Renumbering from 9 to 10 sub-phases:
- New **2D.7** (`architect+buildplan-preview`): architect agent + `BuildPlanPreview` + `aiOrchestrationStore` real + fast-path classifier + stub executor. Stopping state: user can submit prompt, see plan, approve — no worker execution.
- New **2D.8** (`dispatch+agentrun+first-linter`): dispatch loop + worker state machine + `AgentRun` + linter worker + `AiBuildLogTab` body + `EscalateModal`. Stopping state: first end-to-end AI build visible.
- New **2D.9** (former 2D.8, unchanged scope): `full-roster+keyring+prod-polish`.
Applied: full renumbering through spec.

### MAJOR 6 — Deploy WS handler security: MCP omission is insufficient

**Critic claim:** 2D.6 omits `forgeds_cli_deploy` from MCP server (third-line defense), but the bridge-side WS handler for `forgeds:cli:deploy` is wired in 2D.1 and is accessible to any WS client, not only a human Deploy-button click. A misconfigured orchestrator event could theoretically trigger it.

**Author response:** Accepted. The distinction between MCP-surface blocking and bridge-handler authentication is real. Add a **human-intent marker**: the bridge's `forgeds:cli:deploy` handler requires a one-time token issued by the renderer only when the user clicks Deploy in the IDE. The token is bound to a specific `request.id` and rejected on any other path. Applied: §5.2 2D.1 scope adds the token-issuance mechanism; §5.5 2D.4 (bridge header stripping) extends to include token-verification; §10 S10 added for this risk.

---

## Top 5 Minors

### MINOR 1 — MCP005 vs ORC classification; ORC012 vs MCP

**Critic claim:** By the §10 S4 rule ("dispatch/tool-body/allowlist → MCP; session/state-machine/budget → ORC"), `MCP005 MCP schema version mismatch` is a session-init concern (belongs in ORC) and `ORC012 architect used > estimated_tool_calls` is per-invocation (belongs in MCP).

**Author response:** Accepted. Applied: `MCP005` → `ORC008 MCP session-init SCHEMA_VERSION mismatch`; `ORC012` → `MCP012 architect agent per-invocation tool-call budget warning`.

### MINOR 2 — 2D.1 missing automated test for 3-per-5-min restart budget

**Critic claim:** Acceptance criteria cover kill-mid-request but not the 3-per-5-min boundary (where a 4th restart should NOT happen; should emit `SDC004` instead).

**Author response:** Accepted. Added `test_sidecar_restart_budget_exceeded` to 2D.1 acceptance criteria.

### MINOR 3 — `test_orchestrator_error_loop_deterministic` nondeterminism risk

**Critic claim:** Claude API has no seed parameter; a "deterministic" test that uses the real SDK cannot be deterministic. Current test name implies the real SDK; risk mitigation says fall back to stub but text doesn't clarify.

**Author response:** Accepted. Renamed test to `test_orchestrator_dispatch_loop_stub_architect_deterministic`; explicitly documented that this test always uses a pre-recorded stub architect (not live SDK). Added a requirement: live-SDK integration in 2D.9 E2E uses VCR cassette playback for CI green-gate status.

### MINOR 4 — `no-zoho-secrets` ESLint rule may not audit parallel-developed panels

**Critic claim:** 2D.4's ESLint rule is added after 2D.2/2D.3 panels are written (in the parallel lane). The "rule passes on all existing .tsx" criterion checks state at gate-time, not state at merge time of other parallel branches.

**Author response:** Accepted. Added pre-commit hook requirement so any branch (including parallel lanes) catches violations before merge. Applied to §5.5 2D.4 scope.

### MINOR 5 — `cryptography` optional dep conflicts with stdlib-only invariant

**Critic claim:** CLAUDE.md specifies zero external dependencies (stdlib only); `pyodbc` is the documented optional exception. The decomposition adds `cryptography` for keyring fallback (PBKDF2 + AES), but stdlib has no AES; `cryptography` is much heavier than `pyodbc`. Either accept it explicitly as a second optional dep (updating CLAUDE.md) or drop to plaintext-with-permissions fallback.

**Author response:** Accepted. Choosing option (a): explicitly list `cryptography` as a second optional dep with same posture as `pyodbc` (import-guarded, feature skipped on absence). Applied to §5.9 2D.9 scope + added a note that CLAUDE.md update must be part of that phase's deliverables.

---

## Nits (accepted, applied in spec clean-up)

- N1: `forgeds:cli:deploy` dual-owner phrasing in §4.1 table cleaned up (2D.1 wires; 2D.4 adds token-verification; 2D.9 injects credentials).
- N2: Stub `AiBuildLogTab` must explicitly NOT register a WS listener; added to §5.3 scope.
- N3: Unallocated rule-code gaps (`IDE006-IDE009`) noted as "reserved for future 2D.3 extensions."
- N4: 2D.5 negative-assertion test `/orchestrate never emits orchestrator:worker:*` backed by named test `test_skeleton_emits_no_worker_events`.
- N5: 2D.8 50 ms debounce default flagged as "subject to orchestration spec rebuttal (open question #6)."
- N6: Bisimulation SC/BR → SDC rename noted in §12 sign-off gates.
- N7: Phase 2C plan-of-record update pattern: use a delta note in `docs/superpowers/specs/` (mirroring orchestration spec §17 "Deltas to Phase 2C" pattern), not retroactive edit to the 2C plan itself.

---

## Outcome

All 6 majors, 5 of 8 minors (top-ranked), and 7 nits applied. Remaining minors (3 of 8) were either duplicative or already covered; critic did not flag them as blockers. Renumbered canonical spec now contains **10 sub-phases (2D.0 through 2D.9)**. No second critic cycle needed — revisions are targeted, not architectural. Author's assessment: spec is **ready for user approval**.
