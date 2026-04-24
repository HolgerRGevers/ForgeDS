# ForgeDS Widgets Phase 2C — Build / Scaffold / Deploy Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use `- [ ]` for progress tracking.

**Goal:** Ship the widget build pipeline — `forgeds-scaffold-widget`, `forgeds-bundle-widget`, `forgeds-deploy-widget`, and `forgeds-build-app` — plus the shared `widget-spec.yaml` grammar, a Draft-07 schema + loader, a ZET shim, a publish client, and a lifted OAuth helper. All diagnostics emit through the Phase 2A envelope. Deploy `--confirm` is gated behind the §7.5 research spike; full-run `forgeds-build-app` is gated behind the Node Orchestrator Service landing (Phase 2 orchestration spec).

**Reference spec:** `docs/superpowers/specs/2026-04-23-forgeds-widgets-phase2c-build-design.md`
**Depends on:** Phase 1 (widget lint toolchain) + Phase 2A (envelope + CFG config diags) + Phase 2B (runtime harness — consumed by `build_app` conceptually only).

---

## Defaults applied (fast-path: user invoked `/forgeplan` option (a))

The spec's §15 open questions + three integration gaps are resolved as follows. Downstream edits may revisit any of these.

| # | Question / gap | Default chosen | Rationale |
|---|---|---|---|
| D1 | Orchestrator POST (§8, integration gap) | Ship `forgeds-build-app` as thin entry per spec. `--plan-only` fully works. Without `--plan-only`, POST to orchestrator; exit **3** with pointer to `2026-04-23-forgeds-widgets-phase2-orchestration-design.md` when unreachable. | Spec §8.1-§8.4 explicit. Orchestrator is designed but not implemented; a temporary in-process fallback would need ripping out when the orchestrator lands. |
| D2 | Deploy `--confirm` mode (§7.5) | `--dry-run` first-class. `--confirm` returns exit **3** with pointer to §7.5 until the research spike confirms the publish endpoint. | Matches spec §7.5 explicit instruction. |
| D3 | Rule prefixes (contradiction with spec §4.5) | Allocate **WSP### / SCF### / BND### / DPY### / BLD###** prefixes. `Diagnostic.rule` is non-optional in `_shared/diagnostics.py`, so the spec's `source="widget-spec"` guidance cannot be applied literally. | Keeps the CLAUDE.md rule-registry pattern intact and lets each CLI's tests assert on rule codes. |
| D4 | ZET invocation tests | `--no-zet` has full fixtures + tests. `zet pack` path uses a pytest skip-marker when `npx zet --version` fails, plus a mocked-subprocess unit test that asserts the argv+env. | ZET is runtime-optional per spec §11.1. ZET not installed in this dev env. |
| D5 | Widget lifecycle API in `index.js` stub (§15.3) | TODO-tagged placeholder block in scaffolder template. | Matches spec §5.4. |
| D6 | Version bump policy (§15.4) | No auto-bump; author controls `plugin-manifest.json` version. | Matches spec §14 non-goals. |
| D7 | `build-report.json` retention (§15.5) | Single file at `dist/build-report.json`; overwrite on each run. | Out of v1 scope per §15. |
| D8 | Deploy side-effect on `widget-spec.yaml` (§7.4) | Code path implemented, unit-tested against mocked publish-client response. No integration coverage until spike. | Consistent with D2. |
| D9 | YAML write-back for `deployment:` block | Minimal serializer in `spec_loader.py`, round-trips only the `deployment:` sub-dict; preserves author ordering by rewriting just that block, not the full file. | YAML fidelity is out of scope; `_load_yaml_simple` is lossy. |
| D10 | `scaffold --force` warning on deploy-in-progress (§9.4) | Not in v1 — would require `forgeds-build-app` to annotate widget tree with "deploy pending" marker. Tracked as follow-up. | Spec §9.4 marks this "warn loudly" without specifying mechanism; we'd rather underbuild than misbuild. |

---

## Rule code allocation (CLAUDE.md registry update)

Introduce five new rule-code owners. Fixture-less structural errors (missing file, malformed JSON) reuse existing WG/CFG codes where the concept already has one.

| Prefix | Owner module | Range | Meaning |
|---|---|---|---|
| `WSP###` | `forgeds.widgets.spec_loader` | 001-099 | `widget-spec.yaml` schema / cross-ref violations |
| `SCF###` | `forgeds.widgets.scaffold_widget` | 001-099 | Scaffolder diagnostics (collision, missing template, unknown enum) |
| `BND###` | `forgeds.widgets.bundle_widget` | 001-099 | Bundler diagnostics (manifest/spec mismatch, zet stderr, size limits) |
| `DPY###` | `forgeds.widgets.deploy_widget` | 001-099 | Deployer diagnostics (OAuth-source failure, spike gate, conflicting flags) |
| `BLD###` | `forgeds.widgets.build_app` | 001-099 | Orchestrator-entry diagnostics (config validation, orchestrator unreachable, stage flag parsing) |

Initial rule assignments used by tasks below (all later tasks may extend):

| Code | Severity | Meaning |
|---|---|---|
| `WSP001` | ERROR | `widget-spec.yaml` missing or unparseable |
| `WSP002` | ERROR | `widget-spec.yaml` schema violation (missing required / wrong type / bad enum) |
| `WSP003` | ERROR | `widget-spec.name` ≠ `plugin-manifest.name` or directory name |
| `WSP004` | WARNING | `consumes_apis[i]` not in `forgeds.yaml custom_apis` (config-time duplicate of WG003/CFG012; emitted by spec-loader when invoked outside hybrid lint) |
| `WSP005` | WARNING | Decorative field has unexpected type (warn, proceed) |
| `SCF001` | ERROR | Output collision without `--force` |
| `SCF002` | WARNING | `--force` overwrote an existing file (one per file) |
| `SCF003` | ERROR | Output directory unwritable / cannot create |
| `SCF004` | WARNING | Idempotency drift — on-disk file differs from re-scaffold |
| `BND001` | ERROR | Bundle pre-flight: schema/manifest/cross-ref failed (aggregate; details from WSP/WG) |
| `BND002` | ERROR | `zet pack` returned non-zero |
| `BND003` | WARNING | `zet pack` emitted stderr warnings |
| `BND004` | WARNING | File-size sanity check exceeded (manifest > 64 KB, any JS > 2 MB — UNVERIFIED limits) |
| `BND005` | WARNING | `TODO` token present in `index.js` at bundle time |
| `BND006` | ERROR | Output collision without `--force` |
| `DPY001` | ERROR | `--confirm` without `--target` |
| `DPY002` | ERROR | Conflicting flags (`--dry-run --confirm`) |
| `DPY003` | ERROR | No OAuth source resolved (lists each attempted source) |
| `DPY004` | INFO | OAuth source resolved (source name only, never token) |
| `DPY005` | ERROR | Publish endpoint returned non-3000 code (UNVERIFIED shape) |
| `BLD001` | ERROR | `--target` required when `deploy` in `--stages` |
| `BLD002` | ERROR | Orchestrator unreachable; use `--plan-only` to preview dispatch |
| `BLD003` | ERROR | Invalid `--stages` token |
| `BLD004` | WARNING | `forgeds.yaml` validation surfaced CFG diagnostics; not halting (propagated) |
| `BLD005` | ERROR | `forgeds.yaml` missing or unparseable (sim finding F4) |

Tasks emitting new codes document intent in function-level docstring.

---

## File Structure

### Files to create

```
src/forgeds/_shared/
└── oauth.py                                    # Task 2 — lifted TokenManager + source-order resolver

src/forgeds/widgets/
├── spec_loader.py                              # Task 3 — widget-spec.yaml load + validate + write-back
├── scaffold_widget.py                          # Task 4 — forgeds-scaffold-widget
├── zet_shim.py                                 # Task 5 — zet pack subprocess wrapper
├── bundle_widget.py                            # Task 6 — forgeds-bundle-widget
├── publish_client.py                           # Task 7 — HTTP client (UNVERIFIED endpoint)
├── deploy_widget.py                            # Task 8 — forgeds-deploy-widget
├── build_app.py                                # Task 9 — forgeds-build-app thin entry
├── configs/
│   └── widget-spec.schema.json                 # Task 3 — Draft-07 widget-spec schema
└── templates/
    ├── plugin-manifest.json.tmpl               # Task 4
    ├── index.js.tmpl                           # Task 4
    ├── index.html.tmpl                         # Task 4
    └── styles.css.tmpl                         # Task 4

tests/
├── test_shared_oauth.py                        # Task 2
├── test_spec_loader.py                         # Task 3
├── test_scaffold_widget.py                     # Task 4
├── test_zet_shim.py                            # Task 5
├── test_bundle_widget.py                       # Task 6
├── test_publish_client.py                      # Task 7
├── test_deploy_widget.py                       # Task 8
├── test_build_app.py                           # Task 9
└── fixtures/widgets_phase2c/
    ├── spec_minimal/widget-spec.yaml           # Task 3
    ├── spec_full/widget-spec.yaml              # Task 3 — every optional field
    ├── spec_missing_name/widget-spec.yaml      # Task 3
    ├── spec_bad_location/widget-spec.yaml      # Task 3
    ├── scaffold_existing_tree/…                # Task 4
    ├── bundle_happy_path/…                     # Task 6
    ├── bundle_missing_manifest/…               # Task 6
    ├── bundle_stale_widget_spec/…              # Task 6
    ├── bundle_oversized_manifest/…             # Task 6
    ├── deploy_dry_run/…                        # Task 8
    ├── deploy_config/zoho-api.yaml             # Task 8
    └── build_app_full_happy/forgeds.yaml       # Task 9
```

### Files to modify

```
src/forgeds/_shared/config.py                   # Task 1 — accept optional `deploy:` block
src/forgeds/hybrid/upload_to_creator.py         # Task 2 — import TokenManager from _shared.oauth
pyproject.toml                                  # Task 10 — register 4 new console scripts
templates/forgeds.yaml.example                  # Task 10 — document `deploy:` block
templates/gitignore.example (new if missing)    # Task 10 — add config/zoho-api.yaml + build-report.json
CLAUDE.md                                       # Task 11 — register WSP/SCF/BND/DPY/BLD + Phase 2C section
docs/superpowers/specs/2026-04-22-forgeds-widgets-phase1-design.md  # Task 11 — G8 pointer-back (cosmetic)
docs/TOOLCHAIN.md (new)                         # Task 11 — pin ZET version + install hint
docs/ROLLBACK.md (new, under docs/superpowers/) # Task 11 — manual rollback procedure
```

---

## Commit conventions

Repo uses `feat(scope):`, `test(scope):`, `fix(scope):`, `docs(scope):`. Scope for this work: **`widgets`** (consistent with Phase 1 / 2A / 2B).

---

## Orchestration (controller-driven, fast-path)

Executed by the orchestrating session directly, same pattern as Phase 2A / 2B. Each task: failing test → implementation → tests green → commit. Tasks are not dispatched as subagents; the controller does it all. Rationale: spec is detailed at contract-level, 12 defaults already pre-resolve the open questions, and per-task rebuttal is cheaper to do inline than to spawn critic agents for each.

Per-task rebuttal (phase 7 forgeplan integrity): after the final commit of each task, re-read the diff and check:
- Does it match the spec section listed under "Spec refs"?
- Any obvious bugs vs the test assertions?
- Any CLAUDE.md domain gotcha violated? (YAML key link-name casing, forms/reports block placement — not applicable to this phase since no `.ds` work, but still check.)
- Any unintended scope creep?
Report findings inline; commit a fixup if needed before moving to next task.

Task order respects dependencies:
1. Config extension (foundational, no dependencies)
2. OAuth lift (unlocks deploy later; refactor only)
3. Spec schema + loader (unlocks scaffold/bundle/deploy)
4. Scaffolder + templates (uses Task 3)
5. ZET shim (unlocks bundle)
6. Bundler (uses Tasks 3 + 5)
7. Publish client (unlocks deploy)
8. Deployer (uses Tasks 2 + 3 + 7)
9. Build-app thin entry (uses forgeds.yaml validation only; no hard dep on 4/6/8 since it doesn't call them directly under the thin-entry design)
10. pyproject.toml + template updates
11. Documentation (CLAUDE.md registry + TOOLCHAIN.md + ROLLBACK.md + Phase 1 pointer-back)
12. Whole-branch review (optional, via `feature-dev:code-reviewer`)

---

## Task 1 — Config: extend `load_config()` for optional `deploy:` block

**Spec refs:** §3.2 (Modified files), §10.1, §10.2.

### 1.1 Failing tests

Add `tests/test_config_deploy_block.py`:

- [ ] `test_load_config_without_deploy_block_ok` — fixture has no `deploy:` key; `load_config()` returns dict where `cfg.get("deploy", {}) == {}`.
- [ ] `test_load_config_with_deploy_block_parsed` — fixture has `deploy: { oauth_env_prefix: ZOHO }`; `cfg["deploy"]["oauth_env_prefix"] == "ZOHO"`.
- [ ] `test_load_config_deploy_block_unknown_keys_preserved` — unknown keys under `deploy:` pass through (no schema enforcement in v1).

### 1.2 Implementation

- [ ] In `src/forgeds/_shared/config.py`, extend the defaults dict to include `"deploy": {}`.
- [ ] No parser changes — `_load_yaml_simple` already handles nested dicts.
- [ ] Do NOT add validation rules yet; `deploy:` is a hint block, not structured-contract.

### 1.3 Tests green

- [ ] `pytest tests/test_config_deploy_block.py -xvs` all green.
- [ ] Existing `pytest tests/` passes (no regression).

### 1.4 Commit

```
feat(widgets): config accepts optional deploy: block

Adds `deploy:` to the default cfg dict (empty by default). Consumer
projects may populate it with OAuth env-var names, auth base overrides,
etc. Parser unchanged — existing nested-dict support handles it. No
validation rules introduced in this phase; the block is a free-form
hint surfaced by forgeds-deploy-widget.
```

---

## Task 2 — Shared OAuth helper (lift from `upload_to_creator.py`)

**Spec refs:** §3.2 (Modified files), §10.1, §10.2, §10.4.

### 2.1 Failing tests

Add `tests/test_shared_oauth.py`:

- [ ] `test_token_resolver_env_wins_over_config` — `ZOHO_ACCESS_TOKEN=abc` env + config file with `access_token: xyz` → resolver returns `("abc", "env:ZOHO_ACCESS_TOKEN")`.
- [ ] `test_token_resolver_config_fallback` — no env, config has `access_token: xyz` → returns `("xyz", "config:zoho-api.yaml")`.
- [ ] `test_token_resolver_refresh_flow_invoked` — no direct token, refresh creds present → mocked `urlopen` returns `{"access_token": "fresh", "expires_in": 3600}`; resolver returns `("fresh", "refresh:<auth_base>")`. Assert URL, body, Content-Type.
- [ ] `test_token_resolver_all_sources_fail` — no env, no config, no creds → resolver raises `OAuthResolutionError` with message listing each attempted source.
- [ ] `test_token_resolver_arg_wins_over_all` — `token="explicit"` passed → returns `("explicit", "arg:--token")`.
- [ ] `test_token_never_logged` — call resolver with `capsys`; assert token value does not appear in captured stdout/stderr; source name does appear.

### 2.2 Implementation

Create `src/forgeds/_shared/oauth.py`:

- [ ] `class TokenManager` — moved from `upload_to_creator.py`, API preserved (`get_access_token()`, `validate()`).
- [ ] `class OAuthResolutionError(Exception)` — includes `.attempted_sources: list[tuple[str, str]]` (source_name, reason).
- [ ] `def resolve_access_token(*, explicit_token: str | None, config_path: str | None) -> tuple[str, str]` — implements the 4-step order from spec §7.2; returns `(token, source_name)`. Uses env vars `ZOHO_ACCESS_TOKEN`, `ZOHO_REFRESH_TOKEN`, `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_AUTH_BASE`.
- [ ] `def parse_flat_yaml(path: str) -> dict[str, str]` — lifted from `upload_to_creator.parse_yaml` (flat-only yaml loader for `config/zoho-api.yaml`).

Modify `src/forgeds/hybrid/upload_to_creator.py`:

- [ ] Import `TokenManager` and `parse_flat_yaml` from `forgeds._shared.oauth`.
- [ ] Remove in-file `class TokenManager` and `def parse_yaml`.
- [ ] Keep everything else unchanged; module's public behaviour is identical.

### 2.3 Tests green

- [ ] `pytest tests/test_shared_oauth.py -xvs` all green.
- [ ] `pytest tests/` — any existing upload_to_creator tests still pass.
- [ ] Smoke-run `forgeds-upload --help` (entry point still resolves).

### 2.4 Commit

```
feat(widgets): lift TokenManager + YAML loader into _shared.oauth

Introduces src/forgeds/_shared/oauth.py with:
- TokenManager (moved from hybrid/upload_to_creator.py, API preserved)
- OAuthResolutionError
- resolve_access_token() implementing the spec §7.2 source-order
  resolution (arg → env → config → refresh flow)
- parse_flat_yaml()

hybrid/upload_to_creator.py now imports from the shared module; its
public surface is unchanged.

Prepares forgeds-deploy-widget to reuse the same auth plumbing without
either re-implementing it or importing from `hybrid/` (which would
create a dependency cycle once deploy ships).
```

---

## Task 3 — `widget-spec.yaml` schema + loader (`spec_loader.py`)

**Spec refs:** §4.3, §4.4, §4.5.

### 3.1 Failing tests

Create `tests/fixtures/widgets_phase2c/spec_minimal/widget-spec.yaml` with only required fields per §4.3. Create `spec_full/widget-spec.yaml` with every optional field populated. Create `spec_missing_name/`, `spec_bad_location/` negative fixtures.

Add `tests/test_spec_loader.py`:

- [ ] `test_load_spec_minimal_valid` — returns spec dict; no diagnostics.
- [ ] `test_load_spec_full_valid` — returns spec dict with all optional fields populated; no diagnostics.
- [ ] `test_load_spec_missing_file_WSP001` — non-existent path → single WSP001 ERROR diagnostic.
- [ ] `test_load_spec_missing_name_WSP002` — fixture missing `name:` → WSP002 ERROR with path `name`.
- [ ] `test_load_spec_bad_location_WSP002` — `location: weird_value` → WSP002 ERROR with enum message.
- [ ] `test_load_spec_decorative_wrong_type_WSP005` — `ui_primitives: "card"` (string instead of list) → WSP005 WARNING; load still returns spec (decorative fields don't block).
- [ ] `test_write_deployment_block_roundtrip` — load spec, call `write_deployment(spec_path, {"last_uploaded_at": "...", "last_uploaded_version": "0.0.1", "last_uploaded_target": "..."})`; re-load → deployment block matches; author-written fields unchanged byte-for-byte.
- [ ] `test_write_deployment_block_atomic_on_write_failure` — monkeypatch `open` to raise mid-write; original file byte-for-byte intact; no `.forgeds-tmp` leftover.
- [ ] `test_cross_ref_name_mismatch_WSP003` — spec name "a", manifest name "b", directory name "a" → WSP003 ERROR. (Cross-ref function takes explicit manifest dict + dir name, so this can be unit-tested without full scaffold.)

### 3.2 Implementation

Create `src/forgeds/widgets/configs/widget-spec.schema.json` — Draft-07, mirrors §4.3 grammar. Required: `name`, `location`, `description`, `consumes_apis`. Enum for `location`: `["form_view", "report_view", "standalone"]`. Optional: `ui_primitives`, `state_model`, `events_bound` (all arrays of strings). `deployment` is an object with `last_uploaded_at | last_uploaded_version | last_uploaded_target` all nullable strings.

Create `src/forgeds/widgets/spec_loader.py`:

- [ ] `def load_spec(path: str) -> tuple[dict, list[Diagnostic]]` — reads YAML, validates against schema, returns `(spec_dict, diagnostics)`.
- [ ] Reuse the `_validate` recursive function pattern from `validate_manifest.py` — copy + adapt for the WSP rule namespace (do not import the private `_validate` from validate_manifest; duplicate it with the WSP rule string). This is a pragmatic duplication to avoid tight coupling between two validators. Note in a comment: "mirror of validate_manifest._validate; divergence intentional".
- [ ] `def check_cross_refs(spec: dict, manifest: dict | None, directory_name: str, config: dict) -> list[Diagnostic]` — emits WSP003 on name mismatch, WSP004 on missing consumes_apis entry.
- [ ] `def write_deployment_block(path: str, deployment: dict) -> None` — rewrites only the `deployment:` sub-block in `widget-spec.yaml`. Strategy: read file as lines, find `deployment:` line, replace the block up to next top-level key (by indent = 0) or EOF, preserve prefix exactly. If absent, append `deployment:\n  ...\n` at EOF. **Atomic write:** write to `<path>.forgeds-tmp` in the same directory, then `os.replace()` (atomic on POSIX and Windows for same-volume renames). Unit-test with a fixture containing comments and unusual spacing.

### 3.3 Tests green

- [ ] `pytest tests/test_spec_loader.py -xvs` all green.
- [ ] `pytest tests/` — full suite green.

### 3.4 Per-task rebuttal checklist

- [ ] Rule codes used: WSP001-005 match the registry table in this plan's defaults.
- [ ] No silent fallbacks — every parser error surfaces as a Diagnostic.
- [ ] `write_deployment_block` does NOT rewrite the whole file (risk of losing YAML comments / author formatting).

### 3.5 Commit

```
feat(widgets): add widget-spec.yaml schema + spec_loader

Introduces:
- src/forgeds/widgets/configs/widget-spec.schema.json (Draft-07 subset)
- src/forgeds/widgets/spec_loader.py with load_spec, check_cross_refs,
  write_deployment_block
- WSP001-005 rule codes (schema / missing / cross-ref / decorative-type)

write_deployment_block surgically rewrites only the `deployment:` sub-
block to preserve author-written comments and formatting in the rest
of the file. The schema validator intentionally duplicates the small
recursive walk from validate_manifest.py rather than sharing internals
(to decouple WG vs WSP evolution).

Spec §4.3-§4.5.
```

---

## Task 4 — Scaffolder templates + `scaffold_widget.py`

**Spec refs:** §5.1-§5.6.

### 4.1 Failing tests

Populate `tests/fixtures/widgets_phase2c/scaffold_existing_tree/` with: a pre-existing `expense_dashboard/index.js` containing hand-edits.

Add `tests/test_scaffold_widget.py`:

- [ ] `test_scaffold_emits_full_tree_from_minimal_spec` — `--spec spec_minimal/widget-spec.yaml --output <tmp>` → all 5 files created at `<tmp>/<name>/`. Content of `index.js` contains the spec description in a comment; each `consumes_apis` entry produces a `// TODO: implement` stub.
- [ ] `test_scaffold_emits_full_tree_from_full_spec` — includes `state_model`, `events_bound` fields expanded in `index.js`.
- [ ] `test_scaffold_emits_diagnostics_for_malformed_spec` — WSP002 from loader is surfaced, exit 2 before any file written.
- [ ] `test_scaffold_errors_on_collision_without_force` — SCF001 emitted for each conflicting file; exit 2; no files written.
- [ ] `test_scaffold_overwrites_with_force_and_warns` — SCF002 per overwritten file; files match template output.
- [ ] `test_scaffold_dry_run_touches_no_files` — `--dry-run` + collision scenario; stdout lists files-that-would-be-written; `os.listdir(output)` unchanged.
- [ ] `test_scaffold_is_idempotent_on_unchanged_spec` — second run with no `--force` after first successful run → exit 0, no SCF001.
- [ ] `test_scaffold_idempotency_drift_SCF004` — after first run, hand-edit `index.js`, second run detects drift → SCF004 WARNING, exit 1.
- [ ] `test_scaffold_output_json_envelope` — `--format json-v1` emits a well-formed envelope with `tool: "scaffold_widget"` and the expected diagnostics.

### 4.2 Implementation

Create `src/forgeds/widgets/templates/` with 4 `.tmpl` files. Templates use `str.format_map()` with a defaultdict(str)-style missing-key fallback, so absent optional fields render as empty string. The `index.js.tmpl` template receives formatted fragments (consumes_apis stubs, state_model stubs, events_bound stubs) assembled by scaffold_widget.py before format_map. Placeholder tokens use `{name}`, `{description}`, `{location}`, `{consumes_apis_block}`, `{state_block}`, `{events_block}`.

`plugin-manifest.json.tmpl` produces a minimal valid Phase 1 manifest:

```json
{
  "name": "{name}",
  "widget_location": "{location}",
  "entry": "index.html",
  "version": "0.0.1",
  "permissions": [],
  "roles": []
}
```

`index.js.tmpl` top:
```js
// {description}
// Widget: {name}  |  location: {location}
// Generated by forgeds-scaffold-widget — safe to edit.
// TODO(phase-2a): replace with generated client once typegen lands.
import {{ api }} from "./_generated/client.js";  // TODO(phase-2a)

{state_block}

{consumes_apis_block}

{events_block}

// TODO(zoho-lifecycle): widget registration — exact shape UNVERIFIED.
// Research spike §7.5 / §15.3 will confirm.
```

Create `src/forgeds/widgets/scaffold_widget.py`:

- [ ] `def main(argv=None) -> int` — argparse for `--spec`, `--output`, `--dry-run`, `--force`, `--verbose`, `--format`.
- [ ] Search cwd for a lone `widget-spec.yaml` if `--spec` omitted; error if 0 or >1 candidates.
- [ ] Load spec via `spec_loader.load_spec`; surface any WSP diagnostics; exit 2 if any ERROR.
- [ ] Assemble template fragments:
  - `consumes_apis_block` — one stub per API (`async function {api}(...args) { /* TODO: implement {api} */ }`).
  - `state_block` — `const state = { {field}: null, /* TODO: type */ ... };` or empty if no fields.
  - `events_block` — one `function on{Event}(...) { /* TODO: handle {Event} */ }` per event.
- [ ] Compute target paths; check collisions; emit SCF001 without `--force` / SCF002 per overwrite with `--force`.
- [ ] Canonicalise the input spec and write as `<output>/<name>/widget-spec.yaml` (pretty-print: sort top-level keys per a fixed order, 2-space indent).
- [ ] Dry-run: emit file list to stdout (paths + file sizes) without writing.
- [ ] Idempotency check: before writing, compare would-be content against existing; emit SCF004 per drifted file (when not `--force`); when `--force` ignore drift.
- [ ] Exit 0 clean / 1 warnings / 2 errors.
- [ ] JSON-v1 envelope when `--format json-v1` using the shared serializer.

### 4.3 Tests green

- [ ] `pytest tests/test_scaffold_widget.py -xvs` all green.
- [ ] Full suite green.

### 4.4 Per-task rebuttal

- [ ] Spec §5.2: templates use `str.format_map()` — no Jinja. Confirm no Jinja import sneaked in.
- [ ] Spec §5.6: idempotency is byte-for-byte on generated files — verify the test actually compares bytes not high-level diffs.
- [ ] Spec §5.4: every `// TODO` tag includes the phase/topic (e.g., `TODO(phase-2a)`, `TODO(zoho-lifecycle)`) so downstream grep can target them.
- [ ] `--dry-run` is observation-only; double-check no `mkdir` / `touch` can leak before the write-guard.

### 4.5 Commit

```
feat(widgets): add forgeds-scaffold-widget + templates

- src/forgeds/widgets/scaffold_widget.py entry point
- src/forgeds/widgets/templates/{plugin-manifest.json,index.js,index.html,styles.css}.tmpl
- SCF001-004 rule codes

Templates use str.format_map() with assembled fragment blocks for
consumes_apis / state_model / events_bound — no Jinja, zero deps.
Idempotent: re-running against an unchanged spec is a no-op; drift
emits SCF004 warnings. Dry-run is observation-only.

Spec §5.1-§5.6.
```

---

## Task 5 — `zet_shim.py`

**Spec refs:** §6.3, §11.1.

### 5.1 Failing tests

Add `tests/test_zet_shim.py`:

- [ ] `test_zet_shim_success_returns_stdout_stderr` — mock `subprocess.run` to return `(stdout="ok", stderr="", returncode=0)`; shim returns the dataclass with `returncode=0`.
- [ ] `test_zet_shim_absent_returns_exit3_sentinel` — mock `shutil.which("npx")` returning None → shim returns `(returncode=3, stderr="<install hint>")`.
- [ ] `test_zet_shim_timeout` — mock subprocess.run to raise `subprocess.TimeoutExpired` → shim returns `(returncode=2, stderr="<timeout msg>")`.
- [ ] `test_zet_shim_nonzero_exit` — subprocess returns `(returncode=1, stderr="bad manifest")` → shim passes through.
- [ ] `test_zet_shim_argv_shape` — assert `subprocess.run` called with `["npx", "zet", "pack", "--source", <src>, "--dist", <dst>]` + timeout=120.
- [ ] `test_zet_shim_skipped_when_zet_unreachable` — integration skip-marker test: `@pytest.mark.skipif(shutil.which('npx') is None, reason='node unavailable')`; actually runs `npx zet --version`; skipped in CI envs that don't have zet.

### 5.2 Implementation

Create `src/forgeds/widgets/zet_shim.py`:

- [ ] `@dataclass class ZetResult: returncode: int; stdout: str; stderr: str`.
- [ ] `def run_zet_pack(source_dir: str, dist_dir: str, verbose: bool = False, timeout_s: int = 120) -> ZetResult`.
- [ ] If `shutil.which("npx")` is None → return `ZetResult(3, "", <install hint>)`.
- [ ] Use `subprocess.run([...], capture_output=True, text=True, timeout=timeout_s)`.
- [ ] On TimeoutExpired → `ZetResult(2, "", "zet pack timed out after Ns")`.
- [ ] Include `-v` in argv when verbose=True.

### 5.3 Tests green

- [ ] `pytest tests/test_zet_shim.py -xvs` — passes (skip marker fires if npx unreachable).

### 5.4 Commit

```
feat(widgets): add zet_shim for zet pack subprocess invocation

Thin wrapper over `npx zet pack` matching the Phase 1 ESLint pattern:
runtime-optional posture (exit 3 if npx unavailable), 120s timeout,
captured stdout/stderr. Bundle stage (Task 6) consumes this.

Spec §6.3.
```

---

## Task 6 — `bundle_widget.py`

**Spec refs:** §6.1-§6.6.

### 6.1 Failing tests

Fixture prep:
- `bundle_happy_path/` — valid scaffolded tree of `good_bundle_widget` (minimal valid spec + manifest + index files).
- `bundle_missing_manifest/` — tree without `plugin-manifest.json`.
- `bundle_stale_widget_spec/` — spec says `name: a`, manifest says `name: b`.
- `bundle_oversized_manifest/` — manifest file > 64 KB.

Add `tests/test_bundle_widget.py`:

- [ ] `test_bundle_happy_path_no_zet` — `--no-zet` path on valid tree → zip at `<output>/<name>-0.0.1.zip`; zip contains all 4 files; exit 0.
- [ ] `test_bundle_exits_3_when_zet_missing` — no `--no-zet`, mock `shutil.which` None → exit 3 (toolchain-missing).
- [ ] `test_bundle_succeeds_with_no_zet_flag` — explicit flag, exit 0 even if ZET absent.
- [ ] `test_bundle_rejects_spec_manifest_mismatch_BND001` — stale-spec fixture → BND001 ERROR, exit 2, no zip written.
- [ ] `test_bundle_surfaces_zet_stderr_as_BND003` — mock zet_shim to return `(returncode=0, stderr="warning: xyz")` → BND003 WARNING, exit 1, zip still produced.
- [ ] `test_bundle_zet_failure_BND002` — mock zet_shim to return `(returncode=1, stderr="error")` → BND002 ERROR, exit 2.
- [ ] `test_bundle_oversized_manifest_BND004` — BND004 WARNING, exit 1.
- [ ] `test_bundle_todo_tokens_BND005` — index.js with `TODO: implement` → BND005 WARNING, exit 1, zip still produced (warn, not fail).
- [ ] `test_bundle_output_collision_BND006` — existing zip at target path without `--force` → BND006 ERROR, exit 2.
- [ ] `test_bundle_widget_selection_single_auto` — project has one widget → no `--widget` flag required.
- [ ] `test_bundle_widget_selection_multiple_requires_flag` — multi-widget project + no flag → BND001 ERROR "multiple widgets declared, pass --widget".

### 6.2 Implementation

Create `src/forgeds/widgets/bundle_widget.py`:

- [ ] argparse: `--widget`, `--output`, `--no-zet`, `--skip-lint`, `--force`, `--verbose`, `--format`.
- [ ] Resolve target widget from `forgeds.yaml` widgets block.
- [ ] Run validation phases in order, halting on error (§6.2):
  1. `spec_loader.load_spec()` — surface WSP diagnostics; any ERROR → BND001 aggregate + exit 2.
  2. `validate_manifest.validate_manifest_file()` — any WG004 → BND001 aggregate + exit 2.
  3. Cross-ref: spec.name == manifest.name == directory name → BND001 (WSP003 re-emit) on mismatch.
  4. Structural: `index.html`, `index.js` present; manifest `entry` file exists → BND001 if missing.
  5. Ready-for-upload: grep `index.js` for `TODO` (BND005 WARNING, non-fatal); check file sizes (BND004 WARNING, non-fatal). Limits: manifest < 64 KB, any JS file < 2 MB.
- [ ] If `--skip-lint` not set: invoke `subprocess.run([sys.executable, "-m", "forgeds.widgets.lint_widgets", "--format", "json-v1", <widget-root>])`; capture stdout; parse the JSON-v1 envelope; any lint ERROR → halt with BND001 aggregate; WARNINGs → propagate as BND003. (Sim F2: subprocess pinned, not in-process import, to stay decoupled from lint internals and mirror Phase 1 ESLint pattern.)
- [ ] Bundle: either `zet_shim.run_zet_pack(...)` or pure-Python `_zip_fallback(source, dest)` when `--no-zet`.
- [ ] Pure-Python fallback: `zipfile.ZipFile` with `ZIP_DEFLATED`, walks widget root, excludes `widget-spec.yaml` (Zoho doesn't need it) and dot-files.
- [ ] Output path: `<--output>/<widget_name>-<manifest.version>.zip`. `--force` overrides collision; else BND006.
- [ ] `--format json-v1` envelope support.

### 6.3 Tests green

- [ ] `pytest tests/test_bundle_widget.py -xvs` all green.
- [ ] Full suite green.

### 6.4 Per-task rebuttal

- [ ] ZIP fallback MUST exclude `widget-spec.yaml` — it's authoring-only, not runtime. Tests assert this.
- [ ] BND004 size thresholds sourced from spec §6.2 — document the UNVERIFIED tag in the rule docstring so future readers don't think these are official.
- [ ] `--skip-lint` interacts safely with `--no-zet` (two independent optionals).

### 6.5 Commit

```
feat(widgets): add forgeds-bundle-widget + pure-Python ZIP fallback

- src/forgeds/widgets/bundle_widget.py
- BND001-006 rule codes
- Validation chain: spec → manifest → cross-ref → structural → ready-
  for-upload, halting on ERROR at each stage
- --no-zet path uses stdlib zipfile with ZIP_DEFLATED; excludes
  widget-spec.yaml from the bundle (authoring-only)
- BND004 size thresholds flagged UNVERIFIED per spec §6.2

Spec §6.1-§6.6.
```

---

## Task 7 — `publish_client.py`

**Spec refs:** §7.3, §10.4.

### 7.1 Failing tests

Add `tests/test_publish_client.py`:

- [ ] `test_publish_client_request_shape_UNVERIFIED` — mock `urllib.request.urlopen`; invoke client with `(zip_bytes, name="w", version="0.0.1", access_token="T", target="creator:app-id=abc")`. Assert:
  - URL = `https://creator.zoho.com/api/v2.1/applications/abc/plugins/upload`
  - Authorization header = `Zoho-oauthtoken T`
  - Content-Type = `multipart/form-data; boundary=...`
  - Body contains the ZIP bytes + a metadata JSON part with name + version.
- [ ] `test_publish_client_response_success` — mocked 200 with `{"code": 3000, "plugin": {...}}` → returns parsed response dict; no DPY005.
- [ ] `test_publish_client_response_error` — mocked 200 with `{"code": 4099, "message": "bad"}` → returns response + DPY005 diagnostic.
- [ ] `test_publish_client_token_never_in_repr_or_logs` — capsys-capture; token value never appears in any output; source/URL does appear.
- [ ] `test_publish_client_network_error` — mock `urllib.error.URLError` → DPY005 ERROR with generic error text.

### 7.2 Implementation

Create `src/forgeds/widgets/publish_client.py`:

- [ ] `@dataclass class PublishResult: ok: bool; response: dict; diagnostics: list[Diagnostic]`.
- [ ] `def upload_widget_zip(*, zip_path: str, widget_name: str, version: str, access_token: str, target: str) -> PublishResult`.
- [ ] Parse `target` format `creator:app-id=<ID>`; accept other shapes gracefully (fallback: treat the value after `=` as app_id).
- [ ] Build multipart body via stdlib (`email.mime.multipart` or manual `--boundary` bytes). Prefer manual to keep deps zero + avoid weirdness.
- [ ] Headers: `Authorization: Zoho-oauthtoken <token>`, `Content-Type: multipart/form-data; boundary=<b>`.
- [ ] Call `urllib.request.urlopen(req, timeout=60)`. On HTTPError / URLError → wrap in DPY005 diagnostic.
- [ ] `__repr__` on the client class (if any) redacts `access_token`.
- [ ] All UNVERIFIED assumptions annotated with `# UNVERIFIED (§7.5 spike)`.

### 7.3 Tests green

- [ ] `pytest tests/test_publish_client.py -xvs` — all green.

### 7.4 Commit

```
feat(widgets): add publish_client (UNVERIFIED endpoint, spike-gated)

HTTP client for widget upload against the speculative Creator v2.1
plugin-upload endpoint. All request/response fields annotated
UNVERIFIED per spec §7.5 — shipped so the deploy CLI has something to
call, but NOT invoked end-to-end until the research spike confirms the
endpoint. The deploy CLI (Task 8) gates --confirm mode on the same
spike.

Tokens never appear in __repr__ or log output; asserted by unit tests.

Spec §7.3, §10.4.
```

---

## Task 8 — `deploy_widget.py`

**Spec refs:** §7.1-§7.5, §9.1-§9.4, §10.4.

### 8.1 Failing tests

Fixture: `tests/fixtures/widgets_phase2c/deploy_dry_run/` — valid bundled zip + manifest + spec.
Fixture: `tests/fixtures/widgets_phase2c/deploy_config/zoho-api.yaml` — full OAuth config.

Add `tests/test_deploy_widget.py`:

- [ ] `test_deploy_dry_run_is_default_DPY004` — no `--confirm` → DPY004 INFO "would post to <URL>"; no `urlopen` call (mock asserts 0 calls); exit 0.
- [ ] `test_deploy_confirm_without_target_DPY001` — `--confirm` alone → DPY001 ERROR, exit 2.
- [ ] `test_deploy_confirm_and_dry_run_DPY002` — both flags → DPY002 ERROR, exit 2.
- [ ] `test_deploy_confirm_returns_exit3_until_spike` — `--confirm --target x --non-interactive` → exit 3 with message pointing at §7.5; no `urlopen` call. **D2 gate.**
- [ ] `test_deploy_resolves_env_token_DPY004` — env `ZOHO_ACCESS_TOKEN=abc` + `--dry-run` → DPY004 INFO lists source `env:ZOHO_ACCESS_TOKEN`; token value absent from output.
- [ ] `test_deploy_resolves_config_token_DPY004` — no env + config → DPY004 with source `config:zoho-api.yaml`.
- [ ] `test_deploy_no_oauth_source_DPY003` — no env, no config, no args → DPY003 ERROR listing each attempted source; exit 2.
- [ ] `test_deploy_redacts_token_in_all_logs` — run with `--verbose --dry-run` + real-looking token; assert token string never appears in captured stdout/stderr/log-file.
- [ ] `test_deploy_writes_deployment_block_on_mocked_success` — override `--confirm` gate by setting both `FORGEDS_DEPLOY_SPIKE_OVERRIDE_TESTONLY=1` and `PYTEST_CURRENT_TEST` (pytest sets the latter automatically); mock `publish_client.upload_widget_zip` to return success; assert `widget-spec.yaml`'s deployment block updated with ISO timestamp + version + target.
- [ ] `test_deploy_spike_gate_env_alone_not_sufficient` — set `FORGEDS_DEPLOY_SPIKE_OVERRIDE_TESTONLY=1` but simulate running outside pytest (monkeypatch `PYTEST_CURRENT_TEST` to be absent) → exit 3 still fires. Guards against the env-alone bypass attack.

### 8.2 Implementation

Create `src/forgeds/widgets/deploy_widget.py`:

- [ ] argparse: `--widget`, `--zip`, `--target`, `--token`, `--dry-run` (default: True), `--confirm`, `--non-interactive`, `--verbose`, `--format`.
- [ ] Flag-conflict checks first: `--dry-run --confirm` → DPY002; `--confirm` without `--target` → DPY001.
- [ ] **Spike gate (sim F3, double-locked):** if `--confirm` AND NOT (env `FORGEDS_DEPLOY_SPIKE_OVERRIDE_TESTONLY == "1"` AND env `PYTEST_CURRENT_TEST` is set) → print: `"forgeds-deploy-widget --confirm is gated on the §7.5 research spike. Use --dry-run to preview the request."`; exit 3. Both locks must be satisfied to bypass: the test-only env var AND the pytest context marker. A misconfigured CI setting the env var outside a pytest run cannot bypass. Production runs have neither → always exit 3.
- [ ] Locate zip (via `--zip` explicit or via `--widget` name → derive from forgeds.yaml widgets config + default dist dir).
- [ ] Load widget-spec to grab version + name; confirm they match the zip filename.
- [ ] Resolve OAuth: `shared.oauth.resolve_access_token(explicit_token=args.token, config_path=<default path>)`.
- [ ] If `--dry-run` (default): emit DPY004 with resolved source + URL that would be hit (via `publish_client._compose_url(target)`); exit 0.
- [ ] If bypassing spike + `--confirm`: confirmation prompt (unless `--non-interactive`) — print summary table + prompt for literal `deploy`; on any other input → abort with exit 1.
- [ ] Call `publish_client.upload_widget_zip(...)`. On success: `spec_loader.write_deployment_block(...)`. On failure: surface DPY005.
- [ ] `--format json-v1` support.

### 8.3 Tests green

- [ ] `pytest tests/test_deploy_widget.py -xvs` all green.
- [ ] Full suite green.

### 8.4 Per-task rebuttal

- [ ] Spec §7.5: the spike gate is user-facing, not just a comment. Confirm exit 3 actually fires.
- [ ] Spec §10.4: token never in logs — the test explicitly asserts this with a real-looking value.
- [ ] Spec §9.2: the confirmation prompt's text is the redacted summary (resolved OAuth source by NAME, not value).
- [ ] Env-bypass name `FORGEDS_DEPLOY_SPIKE_OVERRIDE_TESTONLY` is documented in a CLAUDE.md warning + docstring so it doesn't become a stealth backdoor.

### 8.5 Commit

```
feat(widgets): add forgeds-deploy-widget (dry-run default, spike-gated)

- src/forgeds/widgets/deploy_widget.py
- DPY001-005 rule codes
- --dry-run as default; --confirm exits 3 with a pointer to spec §7.5
  until the publish-endpoint research spike confirms the Creator v2.1
  plugin-upload shape.
- FORGEDS_DEPLOY_SPIKE_OVERRIDE_TESTONLY=1 gate for test-only bypass; documented
  in CLAUDE.md.
- OAuth resolution via _shared.oauth.resolve_access_token (source
  order: --token → env → config → refresh); source name logged,
  token value never.
- On mocked successful publish, writes back the deployment: block to
  widget-spec.yaml via spec_loader.write_deployment_block.

Spec §7.1-§7.5, §9.1-§9.4, §10.4.
```

---

## Task 9 — `build_app.py` thin entry

**Spec refs:** §8.1-§8.6.

### 9.1 Failing tests

Fixture: `tests/fixtures/widgets_phase2c/build_app_full_happy/forgeds.yaml` — declares forms, widgets, custom_apis.

Add `tests/test_build_app.py`:

- [ ] `test_build_app_plan_only_emits_request_payload` — `--plan-only` writes `build-plan-request.json` shaped as §8.4 to stdout; exit 0.
- [ ] `test_build_app_plan_payload_snapshot` — snapshot against a canonical shape; assert `config_path` is absolute, `forms`/`widgets`/`custom_apis` lists are sorted.
- [ ] `test_build_app_stage_flags_parsing_BLD003` — `--stages foo,lint` → BLD003 ERROR "unknown stage 'foo'", exit 2. Valid subset returns OK.
- [ ] `test_build_app_deploy_without_target_BLD001` — `--stages lint,deploy` no `--target` → BLD001 ERROR, exit 2.
- [ ] `test_build_app_forgeds_yaml_missing_BLD005` — no forgeds.yaml in cwd → BLD005 ERROR (sim F4: use BLD-owned code, do not cross into `forgeds.status` STA namespace); exit 2.
- [ ] `test_build_app_config_validation_BLD004` — CFG012 violation in the config (widget consumes_apis not in custom_apis) → BLD004 WARNING propagated + exit 1, NOT halting (warning-class).
- [ ] `test_build_app_orchestrator_unreachable_BLD002` — without `--plan-only`, POST attempt fails ConnectionRefused → BLD002 ERROR, exit 3; message includes `--plan-only` hint.
- [ ] `test_build_app_report_path_default` — successful `--plan-only` run writes NO `build-report.json` (no orchestrator response); with mocked orchestrator, report written at `<project-root>/dist/build-report.json`; schema matches §8.5.
- [ ] `test_build_app_report_custom_path` — `--report /tmp/out.json` honored.

### 9.2 Implementation

Create `src/forgeds/widgets/build_app.py`:

- [ ] argparse: `--stages`, `--plan-only`, `--orchestrator-url` (default `http://127.0.0.1:9878`), `--dry-run`, `--force`, `--collect-all`, `--fail-fast`, `--target`, `--report`, `--format`.
- [ ] Load + validate forgeds.yaml (via `load_config_with_diagnostics`); propagate CFG diagnostics as BLD004 WARNINGs (non-halting).
- [ ] Parse `--stages` against the allowed set `{lint, verify, scaffold, bundle, deploy}`; unknown tokens → BLD003.
- [ ] If `deploy` in stages but no `--target` → BLD001, exit 2.
- [ ] Build snapshot dict per §8.4 (config_path absolute, sorted forms/widgets/custom_apis).
- [ ] If `--plan-only`: write plan-request JSON to stdout; exit 0.
- [ ] Else: POST to `<orchestrator_url>/orchestrate` with a 10s connect timeout via `urllib.request`. On `URLError` / `ConnectionRefused` / any 5xx → BLD002, exit 3 with "Node Orchestrator Service not running; use --plan-only to preview."
- [ ] On successful POST: parse NDJSON stream from response; each line is a stage event; assemble `build-report.json` from events (last event is `orchestrator:session:done` with summary).
- [ ] Write `--report` path (default `<project-root>/dist/build-report.json`); compute overall exit code per §8.6.

### 9.3 Tests green

- [ ] `pytest tests/test_build_app.py -xvs` all green.
- [ ] Full suite green.

### 9.4 Per-task rebuttal

- [ ] Spec §8.1 item 3: `--plan-only` must emit to stdout, not a file.
- [ ] Spec §8.5 schema backward-compatibility: `diagnostics[i].agent` is OPTIONAL — we don't produce it here, but the assembler must not drop it if the orchestrator emits it.
- [ ] BLD002 is exit 3 (toolchain missing), not exit 2 (validation error). Double-check.

### 9.5 Commit

```
feat(widgets): add forgeds-build-app thin entry

- src/forgeds/widgets/build_app.py
- BLD001-004 rule codes
- Validates forgeds.yaml, builds a project snapshot, and either
  emits the build-plan-request JSON to stdout (--plan-only) or POSTs
  to the Node Orchestrator Service per the Phase 2 orchestration spec.
- Orchestrator unreachable → BLD002 ERROR + exit 3 with pointer to
  --plan-only (the orchestrator is designed but not implemented; see
  2026-04-23-forgeds-widgets-phase2-orchestration-design.md).
- Assembles build-report.json from streamed NDJSON per §8.5. Schema
  backward-compatible; optional diagnostics[i].agent preserved.

Spec §8.1-§8.6.
```

---

## Task 10 — pyproject.toml + template updates

**Spec refs:** §3.2 (Modified files).

### 10.1 Changes

- [ ] pyproject.toml: add 4 console scripts:
  ```
  forgeds-scaffold-widget = "forgeds.widgets.scaffold_widget:main"
  forgeds-bundle-widget   = "forgeds.widgets.bundle_widget:main"
  forgeds-deploy-widget   = "forgeds.widgets.deploy_widget:main"
  forgeds-build-app       = "forgeds.widgets.build_app:main"
  ```
- [ ] templates/forgeds.yaml.example: add a commented-out `deploy:` block documenting `oauth_env_prefix`, `auth_base`.
- [ ] templates/gitignore.example: add `config/zoho-api.yaml` and `dist/build-report.json`. Create the file if it doesn't exist yet.

### 10.2 Tests green

- [ ] `pip install -e .` succeeds — entry points resolve (smoke).
- [ ] `forgeds-scaffold-widget --help`, `forgeds-bundle-widget --help`, `forgeds-deploy-widget --help`, `forgeds-build-app --help` all run without import errors.

### 10.3 Commit

```
feat(widgets): register Phase 2C console scripts + template updates

- pyproject.toml: forgeds-scaffold-widget, forgeds-bundle-widget,
  forgeds-deploy-widget, forgeds-build-app
- templates/forgeds.yaml.example: document the new deploy: block
- templates/gitignore.example: add config/zoho-api.yaml + build-
  report.json
```

---

## Task 11 — Documentation (CLAUDE.md + pointer-back + TOOLCHAIN.md + ROLLBACK.md)

**Spec refs:** §3.2 (Modified files), §11.2, §9.3.

### 11.1 Changes

- [ ] CLAUDE.md — extend the rule-code registry table with WSP / SCF / BND / DPY / BLD owners + range 001-099.
- [ ] CLAUDE.md — add a new "Widget build pipeline (Phase 2C)" section analogous to the existing "Widget runtime toolchain (Phase 2B)" section. Cover:
  - The 4 CLI entry points and their one-sentence purpose.
  - ZET as runtime-optional (mirrors Phase 1 ESLint posture): `npx zet --version`, exit 3 hint, `npm i -g zoho-extension-toolkit`.
  - Dry-run posture asymmetry (§9.1) — scaffold/bundle write files; deploy is dry-run-by-default.
  - FORGEDS_DEPLOY_SPIKE_OVERRIDE_TESTONLY env var: test-only, documented, not a production bypass.
  - §7.5 research spike blocking `--confirm`.
  - `forgeds-build-app` is a thin entry to the Node Orchestrator Service; `--plan-only` works today, full-run pending orchestrator.
- [ ] docs/superpowers/specs/2026-04-22-forgeds-widgets-phase1-design.md — add a one-paragraph pointer to 2C at the spot where G8 was deferred. Cosmetic only.
- [ ] docs/TOOLCHAIN.md (new) — pin known-good ZET version, install hint, CI recipe stub.
- [ ] docs/superpowers/ROLLBACK.md (new) — manual rollback procedure from §9.3.

### 11.2 Tests green

- [ ] grep CLAUDE.md for WSP/SCF/BND/DPY/BLD — all prefixes present in the registry.
- [ ] Markdown lints cleanly (no broken links).

### 11.3 Commit

```
docs(widgets): register Phase 2C rule prefixes + toolchain + rollback

- CLAUDE.md: add WSP/SCF/BND/DPY/BLD to the rule-code registry + new
  "Widget build pipeline (Phase 2C)" section covering ZET posture,
  dry-run asymmetry, FORGEDS_DEPLOY_SPIKE_OVERRIDE_TESTONLY env var, §7.5 spike
  gate, and orchestrator thin-entry status
- docs/superpowers/specs/2026-04-22-forgeds-widgets-phase1-design.md:
  G8 pointer-back to Phase 2C (cosmetic)
- docs/TOOLCHAIN.md (new): pinned ZET version + install hint
- docs/superpowers/ROLLBACK.md (new): manual rollback procedure
```

---

## Task 12 — (Optional) whole-branch review via `feature-dev:code-reviewer`

Run the existing `code-review` skill (or `superpowers:requesting-code-review`) against the full Phase 2C branch diff. Surface findings; apply fixups in follow-up commits as needed.

- [ ] Review focus areas: token redaction (Task 7+8), idempotency correctness (Task 4), cross-ref semantics (Task 3), orchestrator error handling (Task 9), spike-gate unbypassability (Task 8).
- [ ] If the review finds substantive issues, create a `fix(widgets): address Phase 2C review findings` commit.

---

## Rollback / abort

- Branch `claude/ide-shell-overhaul` — DO NOT delete on abort; user will decide.
- Any task may be reverted with `git revert <sha>`; tasks are designed to be individually revertable (they introduce new files except for Task 1 and Task 2 which touch config.py / upload_to_creator.py).
- If a task can't be completed due to spec-gap: emit a NEEDS_CONTEXT-style note, leave its WIP work in a separate branch, and report back to the user.
