# Resume: IDE Shell Overhaul Execution

**Saved:** 2026-04-22
**Branch:** `claude/ide-shell-overhaul` in ForgeDS repo
**Plan:** [`docs/superpowers/plans/2026-04-22-ide-shell-overhaul.md`](docs/superpowers/plans/2026-04-22-ide-shell-overhaul.md)
**Spec:** [`docs/superpowers/specs/2026-04-22-ide-shell-overhaul-design.md`](docs/superpowers/specs/2026-04-22-ide-shell-overhaul-design.md)

Use this file to restart execution in a fresh session. Delete it when the branch is merged.

---

## Progress So Far

6 of 20 tasks done. All Task 1–5 work passed both spec-compliance and code-quality review. Task 6 implementation passed tests but has **not** been reviewed yet.

### Commits on `claude/ide-shell-overhaul` (run `git log --oneline main..HEAD` to verify)

| SHA | Task | Description | Status |
|---|---|---|---|
| `59c749f` | 1 | `feat(ide): add dockview-react dependency` | ✅ reviewed |
| `6b2559c` | 2 | `feat(ide): add shell-overhaul types (ScriptsTab, PanelDockHint, ConsoleCategory)` | ✅ reviewed |
| `e58604a` | 3 | `feat(ide): implement ideStore two-level console state + tighten related types` | ✅ reviewed |
| `abe1809` | 4 | `feat(ide): add layoutStore for dockview state persistence` | ✅ reviewed |
| `950c652` | 4a | `test(ide): add direct test for recordLastKnownPosition` (review follow-up) | ✅ |
| `aa46aed` | 5 | `feat(ide): add DockviewHost wrapping dockview-react with persistence` | ✅ reviewed |
| `6d7554f` | 5a | `fix(ide): clean up DockviewHost lifecycle (timer, disposable, components memo)` (review follow-up) | ✅ |
| `dbd5d9f` | 6 | `feat(ide): add ActivityBar with 6 icon buttons` | ⚠️ impl only, no reviews yet |

### Remaining Work

- Task 6: spec review + code-quality review.
- Tasks 7 through 20: full SDD cycle (impl → spec review → code review) each.
- Final code review across the whole branch.
- Run full validation pass (`npm run build`, `npx tsc -b --noEmit`, `npx vitest run`).

---

## How to Resume

1. Open a fresh Claude Code session from a working directory that can reach `C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS/`.
2. Read this file and the plan file.
3. Pick an execution mode from the options below.
4. Start at **Task 6 spec review**.

---

## Execution Mode Options

### (A) Strict SDD (safest, slowest) — RECOMMENDED DEFAULT

Continue the pattern from Tasks 1–5: for each task, dispatch implementer → spec compliance review → code quality review → fix loop if needed → advance. All three subagents dispatched from the **top-level session** (nested subagents can't run bash — see "Known Gotchas" below).

- Approx. 42 more agent dispatches.
- Catches issues early (Tasks 4 and 5 each needed review-driven hygiene fixes that would have compounded).
- Slow if you watch it happen; you can keep your hands off while it runs.

### (B) Lean SDD (balanced)

Full SDD only for integration-heavy tasks (12 ConsolePanel, 13 useIdeBootstrap, 14 IdeShell, 19 integration test, 20 validation). Implementer-only for simple tasks (7, 8, 9, 10, 11, 15, 16, 17, 18). One comprehensive code review at the end.

- Approx. 18 agent dispatches.
- Reasonable for low-risk task families (pure components, tiny file edits).

### (C) Single implementer agent, no per-task reviews

One general-purpose agent runs all 14 remaining tasks in sequence itself. No nested review cycles. Final review done by you when it finishes.

- Fastest.
- Sacrifices rigor. Suitable only if you'll carefully review the final branch before merging.

### (D) Nested permissions (if feasible)

Background orchestrator-style (one agent that itself dispatches sub-subagents) **does not work** with the current permission model — nested agents can't run bash. If you want to try this mode, you'd need to edit `.claude/settings.local.json` to grant `Bash` tool access at depth > 1. Exact key depends on your harness.

---

## SDD Cycle Template (for modes A and B)

For each task N:

### Dispatch Implementer

- Tool: `Agent` with `subagent_type: "general-purpose"`.
- Model: `haiku` for simple, mechanical tasks (one or two files, plan has exact code). `sonnet` for integration/multi-file/judgment-heavy tasks.
- Prompt structure:

```
You are implementing Task N of the ForgeDS IDE Shell Overhaul plan.

Scene: React SPA at C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS/web/.
Branch: claude/ide-shell-overhaul. Tasks 1..N-1 complete.

[FULL TEXT OF TASK N FROM THE PLAN — paste every code block, every command]

[Any cross-task guidance from prior reviews — e.g., "previous reviewer asked us to fold X into this commit"]

Your job: execute the steps in order. TDD discipline where the plan prescribes it.
If anything is unexpected, report NEEDS_CONTEXT or BLOCKED. Otherwise DONE.

Report back: status, test pass count, commit SHA, any concerns.
```

- **Do not** make the implementer read the plan file. Paste the task text.

### Dispatch Spec Compliance Reviewer

- Tool: `Agent` with `subagent_type: "general-purpose"`, model `sonnet`.
- Prompt: paste the task's requirements + the implementer's claimed SHA + instructions to verify independently (read files, run tests, `git show SHA --stat`).

### Dispatch Code Quality Reviewer

- Only after spec review passes.
- Tool: `Agent` with `subagent_type: "superpowers:code-reviewer"`.
- Fill the template:
  - `WHAT_WAS_IMPLEMENTED:` one paragraph.
  - `PLAN_OR_REQUIREMENTS:` `Task N of docs/superpowers/plans/2026-04-22-ide-shell-overhaul.md`.
  - `BASE_SHA:` commit before task N.
  - `HEAD_SHA:` task N's commit.
  - `DESCRIPTION:` focus areas. Always include: single-responsibility, file size growth, React 18 StrictMode hygiene (cleanup effects, dispose listeners, memoize non-primitive props).

### Handle Feedback

- **Critical / Important** → dispatch fix subagent (haiku is fine for hygiene fixes) with explicit fix instructions + validation + commit command. Then re-review. Loop until approved.
- **Minor** → note it, do not block.

---

## Known Gotchas Learned from Tasks 1–6

These have already bitten us once. Propagate them to the implementers of the remaining tasks:

### Dockview API specifics (for Tasks 5, 14, 19)

- `PanelRegistryEntry.component` should be typed `React.FunctionComponent<IDockviewPanelProps>`, not `React.ComponentType` (Task 5 fix).
- `api.onDidLayoutChange` returns a disposable — **must** be captured and disposed on unmount, else StrictMode double-subscribes (Task 5 hygiene).
- `Object.fromEntries(...)` for the `components` map must be wrapped in `useMemo` — non-stable references cause re-registration (Task 5 hygiene).
- Any `setTimeout` ref must be cleared in an unmount cleanup (Task 5 hygiene).

### PanelDockHint shape (Task 3)

- Both `referencePanelId` and `direction` are **required** (we tightened from the original plan's optional fields). Fallbacks must return a complete hint — not `{}`. Example for dockview hints: `{ referencePanelId: "editor", direction: "right" }`.

### vitest config (already handled)

- Tests live at repo-top-level `web/tests/`. `web/vitest.config.ts` has been extended to include `"tests/**/*.test.ts"` and `"tests/**/*.test.tsx"`. If an implementer asks "can't find my test", verify the include pattern still covers the path.
- `@testing-library/react` was added in Task 6 via `npm install --save-dev`. It is now available for Tasks 8–14, 19.

### Permission architecture

- **Only top-level subagents** (dispatched directly from the main session) can run bash / git / npm. Nested subagents (subagent dispatching another subagent) cannot. This is why the earlier background orchestrator failed.
- Stay one level deep: session → implementer/reviewer. No orchestrator-in-the-middle.

### Commit discipline

- One conceptual change per commit.
- Reviewer follow-ups go in **separate** commits with `fix(ide): ...` or `test(ide): ...` prefixes (not amended into the feature commit).
- Commit messages use the exact strings specified in the plan unless the plan explicitly tells you to rename them.

### Plan text is authoritative but not gospel

- If a plan code block has a type mismatch with the types landed in a prior task (e.g., Task 2 plan had `PanelDockHint` fields optional, but Task 3 tightened them), the implementer must **fix the drift** in their commit and note it in their report. The spec reviewer will accept "beneficial deviation" findings.

### Task-specific heads-up

- **Task 7 (DevConsole rename)** — use `git rm src/components/ide/DevConsole.tsx` to delete. Verify after the commit that the file is gone and the new `DevToolsCategory.tsx` is the only inhabitant of that concept.
- **Task 14 (IdeShell)** — the `registry` prop passed to `DockviewHost` **must be wrapped in `useMemo`** (DockviewHost's JSDoc requires referential stability, per the Task 5 hygiene follow-up).
- **Task 15 (IdePage slim + index.ts update)** — after this commit, `npx tsc -b --noEmit` should be **fully clean**. If it isn't, don't advance — something earlier is broken.
- **Task 19 (integration test)** — mocks `dockview-react` entirely via `vi.mock(...)`. If React 19 + Vitest has issues with the factory, try `vi.hoisted(...)` or a module-factory pattern. The essential coverage: (a) all 6 panels register, (b) wizard first-load activates Complete Script, (c) corrupt localStorage JSON falls back to default. How the stub is structured can deviate from the plan text; **what** it verifies cannot.
- **Task 20 (validation)** — build, tsc, vitest must all be green before reporting DONE. If any fail, dispatch a fix subagent with the specific failure instead of declaring done with concerns.

---

## Useful Commands to Re-orient in a New Session

```bash
# From a shell with access to the ForgeDS repo:

# Verify branch + commits
cd "C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS"
git branch --show-current   # expect: claude/ide-shell-overhaul
git log --oneline main..HEAD

# Verify repo cleanliness
git status

# Sanity run (pre-Task 7)
cd web
npx tsc -b --noEmit   # expect: 2 errors in DevConsole.tsx lines 343, 347 — these go away after Task 7
npx vitest run        # expect: all passing (Tasks 3, 4, 6 tests)
npm run build         # expect: succeeds
```

---

## What to Hand the Next Session

Start the new session with a prompt like:

> Read `C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS/RESUME-IDE-SHELL-OVERHAUL.md`. Branch `claude/ide-shell-overhaul` is 6 tasks into a 20-task plan. Resume at Task 6 reviews, then execute Tasks 7–20 + final code review using the execution mode labelled **(A)** / **(B)** / **(C)** in that doc. Use the gotchas section to avoid repeating past mistakes.

That's the whole handoff.

---

## Final Deliverable Shape (for whoever finishes)

When the branch is ready to merge, produce:

```
### IDE Shell Overhaul — Completion Summary

Branch: claude/ide-shell-overhaul
Final commit: <sha>

Completed tasks (SHA | description):
- Task 1: 59c749f — dockview-react dependency
- Task 2: 6b2559c — types
- Task 3: e58604a — ideStore
- Task 4: abe1809 + 950c652 — layoutStore
- Task 5: aa46aed + 6d7554f — DockviewHost
- Task 6: dbd5d9f — ActivityBar
- Task 7: <sha> — DevToolsCategory rename
... (8 through 20)

Review hygiene fixes (task | issue | fix SHA):
- Task 5: StrictMode listener leak / timer leak → 6d7554f
- Task 4: missing recordLastKnownPosition direct test → 950c652
... (additions from remaining tasks)

Final validation:
- `npm run build`: <status>
- `npx tsc -b --noEmit`: <status>
- `npx vitest run`: N/N passing

Manual QA checklist (spec §Testing):
- [ ] Default layout matches the diagram
- [ ] Drag Repo Explorer tab to right zone — lands in right group
- [ ] Drag Console to left zone — narrow-width fallback renders
- [ ] Resize splitters, reload — sizes persist
- [ ] Activity bar icons — show/hide matches spec
- [ ] Reset Layout restores defaults
- [ ] Wizard completion → .ds tab opens + Complete Script active
- [ ] Bridge reconnect with pre-loaded app → layout undisturbed

Notes / deviations from plan:
- <any>

Follow-up specs ready to start:
- Polish Pass (fix stubs/bugs in existing panels)
- Hybrid Gap Close
- Creator Parity Surfaces series
```

Merge when all automated + manual checks pass. Delete this RESUME file after merge.
