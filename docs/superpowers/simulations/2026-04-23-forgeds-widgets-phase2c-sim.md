# ForgeDS Widgets Phase 2C — Plan Simulation Report

**Date:** 2026-04-23
**Plan:** `docs/superpowers/plans/2026-04-23-forgeds-widgets-phase2c.md`
**Spec:** `docs/superpowers/specs/2026-04-23-forgeds-widgets-phase2c-build-design.md`
**Simulator:** inline controller pass (Opus). No per-task subagents dispatched — the plan's task set is small enough and self-consistent enough that a combined walk-through is equivalent.

---

## Aggregate findings

- **File conflicts:** NONE. Every task's write-set is disjoint from the others (verified below).
- **Dangling dependencies:** NONE. Every cross-task dependency points from a later task to an earlier task that produces the required symbol / file.
- **Impossible sequencing:** NONE. Task ordering (T1 → T2 → T3 → … → T11) satisfies all dependencies.
- **Missing tools / permissions:** NONE. All tasks use stdlib, `subprocess`, `urllib`, `pytest`, `zipfile`, `json`. Node/ZET is runtime-optional and its absence is tested via mocks.
- **UNVERIFIED items:** 4 acknowledged (publish endpoint §7.5, ZIP parity §6.4, widget lifecycle API §5.4, BND004 size limits §6.2). All are labeled in rule docstrings or comments — none are hidden gaps.

**Conclusion:** plan is executable as written, with five plan-refinement findings (F1-F5 below) that should be addressed before Task 3 begins. All findings are minor — they tighten contracts rather than reveal structural gaps.

---

## Per-task simulation walk-through

### T1 — Config `deploy:` block

- **Files touched:** `src/forgeds/_shared/config.py` (one-line default dict extension), `tests/test_config_deploy_block.py` (new).
- **Tools:** `pytest`, file read/write.
- **Depends on:** nothing.
- **Gaps:** none.

### T2 — Shared OAuth lift

- **Files touched:** `src/forgeds/_shared/oauth.py` (new), `src/forgeds/hybrid/upload_to_creator.py` (delete 2 classes, add import), `tests/test_shared_oauth.py` (new).
- **Tools:** `pytest`, `urllib.request` (mocked).
- **Depends on:** nothing (T1 not strictly required).
- **Gaps:** ensure `upload_to_creator.py` tests (if any) still pass. Grep found none at `tests/test_upload*`, so regression surface is limited to smoke `--help`.

### T3 — Spec schema + loader

- **Files touched:** `src/forgeds/widgets/configs/widget-spec.schema.json`, `src/forgeds/widgets/spec_loader.py`, `tests/test_spec_loader.py`, `tests/fixtures/widgets_phase2c/spec_*/widget-spec.yaml`.
- **Tools:** `pytest`, `json`, `yaml-subset-loader`.
- **Depends on:** Phase 2A `_shared.diagnostics`, `_shared.config._load_yaml_simple` (both exist).
- **Gaps:** **F1 — atomicity of `write_deployment_block`.** See findings.

### T4 — Scaffolder + templates

- **Files touched:** `src/forgeds/widgets/scaffold_widget.py`, `src/forgeds/widgets/templates/*.tmpl`, `tests/test_scaffold_widget.py`, `tests/fixtures/widgets_phase2c/scaffold_existing_tree/…`.
- **Tools:** `pytest`, file I/O, `str.format_map`.
- **Depends on:** T3 `load_spec`.
- **Gaps:** none directly; F3 applies partially.

### T5 — ZET shim

- **Files touched:** `src/forgeds/widgets/zet_shim.py`, `tests/test_zet_shim.py`.
- **Tools:** `pytest`, `subprocess.run` (mocked).
- **Depends on:** nothing.
- **Gaps:** none.

### T6 — Bundler

- **Files touched:** `src/forgeds/widgets/bundle_widget.py`, `tests/test_bundle_widget.py`, `tests/fixtures/widgets_phase2c/bundle_*/…`.
- **Tools:** `pytest`, `subprocess.run` (via shim, mocked), `zipfile` (real).
- **Depends on:** T3 `load_spec`, T5 `run_zet_pack`, Phase 1 `validate_manifest.validate_manifest_file`, Phase 1 `forgeds-lint-widgets` CLI.
- **Gaps:** **F2 — `--skip-lint` invocation mode.** See findings.

### T7 — Publish client

- **Files touched:** `src/forgeds/widgets/publish_client.py`, `tests/test_publish_client.py`.
- **Tools:** `pytest`, `urllib.request` (mocked).
- **Depends on:** nothing (takes `access_token` as arg; does not resolve OAuth itself).
- **Gaps:** none.

### T8 — Deployer

- **Files touched:** `src/forgeds/widgets/deploy_widget.py`, `tests/test_deploy_widget.py`, `tests/fixtures/widgets_phase2c/deploy_*/…`.
- **Tools:** `pytest`, `urllib.request` (mocked via T7), env-var manipulation.
- **Depends on:** T2 `resolve_access_token`, T3 `load_spec` + `write_deployment_block`, T7 `upload_widget_zip`.
- **Gaps:** **F3 — env-bypass semantics for spike gate.** See findings.

### T9 — Build-app thin entry

- **Files touched:** `src/forgeds/widgets/build_app.py`, `tests/test_build_app.py`, `tests/fixtures/widgets_phase2c/build_app_full_happy/forgeds.yaml`.
- **Tools:** `pytest`, `urllib.request` (mocked for orchestrator POST).
- **Depends on:** `_shared.config.load_config_with_diagnostics` (exists).
- **Gaps:** **F4 — missing-forgeds.yaml rule code.** See findings.

### T10 — pyproject + templates

- **Files touched:** `pyproject.toml`, `templates/forgeds.yaml.example`, `templates/gitignore.example` (new).
- **Tools:** `pip install -e .`, entry-point smoke.
- **Depends on:** T2, T4, T6, T8, T9 (all entry-point targets must exist).
- **Gaps:** none.

### T11 — Documentation

- **Files touched:** `CLAUDE.md`, `docs/superpowers/specs/2026-04-22-forgeds-widgets-phase1-design.md`, `docs/TOOLCHAIN.md` (new), `docs/superpowers/ROLLBACK.md` (new).
- **Tools:** grep, markdown lint.
- **Depends on:** T3, T4, T6, T8, T9 (rule codes must exist to register).
- **Gaps:** none.

### T12 — Optional branch review

- **Files touched:** none (review only) unless fixups.
- **Depends on:** T1-T11 complete.
- **Gaps:** none.

---

## Plan refinements to apply before execution

The simulation surfaced five minor contract-tightening gaps. None require re-spinning the plan — they're inline edits that clarify behavior. I'll apply them as an in-place plan edit before Task 3 begins (Tasks 1 & 2 are unaffected).

### F1 — `write_deployment_block` atomicity

**Gap:** plan's Task 3 says "rewrites only the `deployment:` sub-block" but doesn't specify atomic write. Partial-write failure mid-rename would leave the file corrupted.

**Fix:** write to `<path>.forgeds-tmp` in the same directory, then `os.replace()` (atomic on POSIX and Windows ≥ Vista for same-volume renames). Add assertion in tests.

**Plan edit:** Task 3 §3.2 write_deployment_block bullet — append "atomic: writes to sibling tmp file then `os.replace`." Task 3 §3.1 — add `test_write_deployment_block_atomic_on_write_failure` (simulate mid-write failure via a patched `open`, assert original file intact).

### F2 — `--skip-lint` implementation mode

**Gap:** plan says "invoke via subprocess OR import and call" — leaving the choice unpinned creates two divergent implementation paths.

**Fix:** pin to subprocess invocation. Matches Phase 1 ESLint pattern (always a separate process). Keeps bundler decoupled from lint internals.

**Plan edit:** Task 6 §6.2 step on `--skip-lint` — change "invoke via subprocess or import and call" to "invoke via subprocess (`subprocess.run([sys.executable, '-m', 'forgeds.widgets.lint_widgets', …])`); capture stdout/stderr; parse the JSON-v1 envelope; map lint ERRORs to halting BND001 and WARNINGs to BND003."

### F3 — `FORGEDS_DEPLOY_BYPASS_SPIKE` env var scoping

**Gap:** plan has the env-bypass for tests, but a motivated attacker or a confused CI config could set it in production. We should scope it more tightly.

**Fix:** rename env var to include a clear test-only marker and gate on pytest env indicators. Use `FORGEDS_DEPLOY_SPIKE_OVERRIDE_TESTONLY` and additionally require that `PYTEST_CURRENT_TEST` be set OR `sys.argv[0]` contains `pytest`. Document in CLAUDE.md that setting this env var outside of a pytest run is undefined behavior.

**Plan edit:** Task 8 §8.2 spike-gate bullet — replace env var name to `FORGEDS_DEPLOY_SPIKE_OVERRIDE_TESTONLY`; add requirement that `PYTEST_CURRENT_TEST` also be set. Task 8 §8.4 rebuttal bullet — update env var name. Task 11 §11.1 — update CLAUDE.md documentation to match.

### F4 — Missing-forgeds.yaml rule code in Task 9

**Gap:** plan test `test_build_app_forgeds_yaml_missing_exits_2` emits STA001, but STA is owned by `forgeds.status`. Cross-module rule emission violates the CLAUDE.md registry ownership rule.

**Fix:** allocate `BLD005 — forgeds.yaml missing or unparseable` in the BLD registry. Use it when `find_project_root()` returns a path without forgeds.yaml.

**Plan edit:** add `BLD005` to the rule table at top of plan; Task 9 §9.1 test uses BLD005 instead of STA001; Task 11 §11.1 registers BLD005.

### F5 — Phase 1 `lint_widgets` JSON-v1 envelope consumption (tightens F2)

**Gap:** F2's subprocess invocation of lint_widgets needs to parse the envelope. If lint_widgets doesn't emit JSON-v1 when invoked with `--format json-v1`, bundler's propagation logic fails.

**Check:** `src/forgeds/widgets/lint_widgets.py` already has `--format json-v1` support (Phase 2A: `c81dd54 feat(widgets): promote --format json-v1 to every linter via shared envelope`). ✓ No change needed — this is a satisfied dep, logged here for audit trail.

---

## Math-sim (conditional invariants)

The spec has three invariants worth noting:

1. **Token-never-in-logs.** Verified by per-CLI unit tests in T7 + T8. No formal proof needed — the tests span every code path that touches the token.
2. **Scaffolder idempotency.** `output_bytes(N+1) == output_bytes(N)` on unchanged spec without `--force`. Verified by `test_scaffold_is_idempotent_on_unchanged_spec`. Mathematical invariant satisfied by construction: `str.format_map` is deterministic, template files are stable.
3. **Spike gate unbypassability in production.** After F3 applied, bypass requires BOTH env var AND pytest context marker. A production run has neither → exit 3 always fires. Deductive verification sufficient.

No counterexamples found. No UNVERIFIED invariants.

---

## Go / no-go

**Go, after applying F1-F4 plan refinements** (F5 is a no-op). Proceed to Phase 6 gate.
