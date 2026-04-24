# forgeds-apply-playbook — simulation report (2026-04-24)

Phase-6 simulation output for the `forgeds-apply-playbook` feature.

## Inputs

- Spec: `docs/superpowers/specs/2026-04-24-forgeds-apply-playbook-design.md` (post-rebuttal revision)
- Plan: `docs/superpowers/plans/2026-04-24-forgeds-apply-playbook.md`

## Methodology

- **Role-play stub review (§6 step 2):** compressed into a single aggregate reviewer dispatch in the planning phase (the planner implicitly validated task-level dependencies, file-surface conflicts, and tool-availability by writing the plan's "Depends on" / "Files to create / modify" / "Acceptance criteria" structure). No per-task stub workers dispatched separately.
- **Math simulation (§6 step 3):** opus verifier ran 5 invariants. Findings below.

## Invariant findings

### Invariant 1 — Round-trip identity on empty input: COUNTEREXAMPLE

**Issue:** §8.2 rule 2 says "If no `workflow { }` block exists: synthesise a new `workflow { <entry> }` block." This triggers unconditionally on a .ds without a workflow block, even when the `EmitResult` list is empty.

**Input that breaks it:** `.ds` with no `workflow { }` block + playbook MD with H1/H2 headings only (no action code fences) → mutator synthesises an empty `workflow { }` block + DS064 WARNING fires → output ≠ input by a few bytes.

**Fix (for Phase 7 implementer):** In `mutator.py` entry point, short-circuit when `EmitResult` list is empty — return `source_text` unchanged and emit no DS064. Add test `test_empty_ir_roundtrip_identity` that asserts bytes-equal I/O on empty IR. Make this part of **Task 8 (Mutator)** acceptance criteria.

### Invariant 2 — Brace-depth state machine termination: COUNTEREXAMPLE (conditional on §7.4)

**Issue:** §7.4 is explicitly TODO and defaults to `\"` as escape. If Deluge's real escape convention is `""` (doubled-quote, SQL/VBA-style), `\"` in a string toggles `in_string` incorrectly; a desynced run that still ends with even `"` count will exit `depth==0, in_string==False` and emit NO diagnostic — silent corruption.

**Status:** Already acknowledged in spec Risk 2 (HIGH, ship-blocker). Plan Task 5 (Landmarks) has empirical-study obligation before code lands.

**Reinforcement (for Task 5 implementer):** when performing the §7.4 study, explicitly test BOTH candidate escape conventions against a known .ds string. If the empirical finding is inconclusive, add a strict fixture that would fail under the wrong convention. Do NOT rely solely on DS062/DS063 safety nets — they do not catch all desync cases.

### Invariant 3 — Atomic-or-nothing mutation: PROOF SKETCH

**Verdict:** The two-phase discipline (validate all offsets + guardrails, then splice) is sound as specified. In-memory assembly means no intermediate disk state.

**Minor gap:** §4.2 does not mandate a temp-file + `os.replace` pattern for the final write. A crash *during* write could truncate the original (especially in `--out == --ds` in-place mode).

**Fix (for Phase 7 implementer):** In `cli.py` / orchestrator file-write step: write to `<out>.tmp.<pid>`, fsync, then `os.replace(tmp, out)`. Make this part of **Task 10 (CLI)** acceptance criteria.

### Invariant 4 — Idempotency under sentinel check: UNVERIFIED

**Issue:** Spec §8.4 assumes Creator strips `/* ... */` comments on re-import, so sentinels added by `apply-playbook` won't survive a re-export → re-apply cycle. This assumption is not empirically validated.

**Status:** Remains UNVERIFIED. Document as "Risk 6 — Creator comment preservation behaviour" in spec §14 during Phase 7.

**Mitigation (for Phase 7 implementer):** In Task 10 (docs), add a CLAUDE.md note: "First real re-export after applying the tool should be sanity-checked for sentinel survival. If Creator preserves sentinels, `--allow-reapply` may be needed on legitimate re-applies after Creator round-trip."

### Invariant 5 — Rule-code namespace integrity: COUNTEREXAMPLE (minor)

**Issue:** DS005, DS006 are labelled "Parser/Validator" (dual-owner) and DS043 is labelled "Emitter/CLI" in the §10 registry. §10's own text says "Rule codes are component-exclusive; cross-component reuse is a spec bug."

**Fix (for Phase 7 Task 10 / docs):** Update §10 registry to clarify: **meaning is single; emission site may be multiple.** Replace dual-owner rows with a "Primary component (also fired by):" notation. OR split codes (DS005 parser + DS005V validator). Recommended: first option — it's a documentation fix only, no code impact.

## Aggregate simulation verdict

| Invariant | Verdict | Blocking for Phase 7? |
|---|---|---|
| 1. Empty-IR round-trip | COUNTEREXAMPLE | No — addressed in Task 8 acceptance |
| 2. Brace state machine | COUNTEREXAMPLE (TODO-gated) | No — Task 5 pre-implementation study |
| 3. Atomic mutation | PROOF SKETCH (minor write-gap) | No — Task 10 acceptance |
| 4. Sentinel survival | UNVERIFIED | No — documentation risk |
| 5. Rule-code namespace | COUNTEREXAMPLE (minor) | No — Task 10 documentation fix |

**Phase 7 entry authorised.** All 5 invariant findings have assigned owners in the existing plan tasks (no new tasks required). The spec can ship with the findings above recorded as Phase-7 implementation notes. Overall confidence: MODERATE → HIGH once Task 5's §7.4 empirical study lands.

## Plan-conflict check (role-play aggregate)

The 11 tasks in `docs/superpowers/plans/2026-04-24-forgeds-apply-playbook.md` were checked for:

- **File conflicts:** None. Each task's "Files to create / modify" set is disjoint from its concurrent siblings. Shared touchpoints (CLAUDE.md, pyproject.toml) are owned exclusively by Task 1 (pyproject) and Task 10 (CLAUDE.md).
- **Dangling dependencies:** None. Every "Depends on" reference resolves to a prior numbered task.
- **Impossible sequencing:** None. The critical path (T0 → T1/T2 → T3 → T5 → T6 → T8 → T9 → T10) is acyclic and respects the bisimulated build-sequence contract.
- **Missing tools/permissions:** None. All tasks use stdlib Python, pytest, Edit/Write/Read tools. No optional deps. No network.

## Phase 7 dispatch guidance

Per plan parallelism map:

- Kickoff wave (can dispatch concurrently): T0 (prereq fix), T1 (scaffold), T2 (fixtures).
- Wave 2 (on T1+T2 done): T3 (IR), T4 (parser).
- Wave 3 (on T1+T2 done, parallel with Wave 2): T5 (landmarks — blocks on §7.4 study).
- Wave 4: T6 (validator — blocks on T0+T1+T3+T5), T7 (emitter — blocks on T3).
- Wave 5: T8 (mutator — blocks on T5+T7).
- Wave 6: T9 (orchestrator+E2E — blocks on everything), then T10 (CLI+docs — blocks on T9).

Per-task model tier (from `references/model-tiers.md` defaults + plan judgement):
- T0 prereq: haiku (3-line mechanical fix)
- T1 scaffold: haiku (package setup, pyproject entry)
- T2 fixtures: haiku (file authoring)
- T3 IR: sonnet (dataclass design decisions)
- T4 parser: sonnet (regex + edge cases)
- T5 landmarks: sonnet (state machine + §7.4 study — judgement-heavy)
- T6 validator: sonnet (cross-checks)
- T7 emitter: sonnet (template + three modes)
- T8 mutator: sonnet (two-phase + atomicity)
- T9 orchestrator+E2E: sonnet (integration)
- T10 CLI+docs: haiku (mechanical wiring + registry update)

Escalate to opus only if per-task rebuttal critic flags major issues twice on the same task.
