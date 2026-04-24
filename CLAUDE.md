# ForgeDS — Zoho Creator Development Engine

## What this repo is
Pip-installable Python package providing linting, scaffolding, .ds editing,
and import pipeline tools for Zoho Creator applications. Zero external
dependencies (stdlib only). Extracted from the ERM project.

## Tech stack
- **Language**: Python >= 3.10
- **Package format**: pip-installable via pyproject.toml
- **Target platform**: Zoho Creator / Deluge ecosystem
- **Dependencies**: None (stdlib only; pyodbc optional for Access tools)

## Architecture
- `src/forgeds/core/` — Zoho/Deluge tools (lint, build DB, scaffold, parse, edit .ds)
- `src/forgeds/access/` — Access/VBA migration tools (lint SQL, build DB, export CSV)
- `src/forgeds/hybrid/` — Cross-environment tools (hybrid lint, validate, upload)
- `src/forgeds/widgets/` — Widget lint tools (ESLint orchestrator, SDK DB, manifest validator)
- `src/forgeds/status/` — Aggregate project-health CLI (`forgeds-status`)
- `src/forgeds/knowledge/` — HRC knowledge base with Librarian token authority
- `src/forgeds/_shared/` — Shared internals (diagnostics, config loader)
- `templates/` — Starter configs for new consumer projects
- `tests/fixtures/` — Lint test fixtures

## Knowledge Base / HRC subsystem
- **Librarian** (`librarian.c` / `librarian_io.py`): sole authority for token creation, destruction, and weight mutation. Coded in C for I/O efficiency; Python fallback if no compiler.
- **RB** (Reality Database, `reality.db`): permanent source of truth — scraped docs, ingested apps, promoted shadow cases.
- **HB** (Holographic Database, `holographic.db`): ephemeral projections — hologram tokens destroyed after analysis + user confirmation.
- **Invariants**: SHA uniqueness across RB+HB; immutability after creation (only weight is mutable); closed-world output (only JSON analysis results leave the system).
- **Token lifecycle**: all INSERT/DELETE go through `LibrarianHandle.create()` / `.destroy()`. Never write tokens via direct SQL.

## Key design principles
1. **Config over hardcoding**: All project-specific values come from `forgeds.yaml` in the consumer project root. ForgeDS tools auto-discover this file by walking up from cwd.
2. **Shared diagnostics**: All linters use `forgeds._shared.diagnostics.Severity` and `Diagnostic` — never define local copies.
3. **DB path resolution**: Use `get_db_dir()` from `forgeds._shared.config` — never hardcode `Path(__file__).parent`.
4. **Generic framework**: `ds_editor.py` provides generic subcommands. Project-specific subcommands (apply-two-key, apply-esg) live in the consumer repo.
5. **Zero dependencies**: Every tool uses stdlib only. `pyodbc` is optional and guarded by ImportError.

## Development workflow
```bash
# Install in editable mode
pip install -e .

# Test linters against fixtures
forgeds-lint tests/fixtures/lint_test_bad.dg
forgeds-lint-access tests/fixtures/lint_test_access_bad.sql

# Build language databases
forgeds-build-db
forgeds-build-access-db
```

## .ds file format gotchas
1. **Forms must be inside `forms { }`**: When programmatically inserting new forms
   into an existing .ds file, they MUST go inside the `forms { }` block — before
   its closing `}`. The closing `}` of `forms` sits on the line before the
   `reports` keyword. Inserting between that `}` and `reports` places forms at
   the application level, which Zoho Creator silently rejects with a generic
   "A problem encountered while creating the application" error.
2. **Report filter syntax uses brackets**: Filtered reports use
   `show all rows from form_name  [filter_expr]`, NOT `where (filter)`.
   Example: `show all rows from incidents  [status == "Open"]`
3. **Deluge field references must match .ds field link names exactly**:
   Zoho Creator is case-sensitive. If the .ds defines `merchant_account`
   (lowercase), Deluge scripts must use `input.merchant_account`, NOT
   `input.Merchant_Account`. The audit_trail form's action field is
   `action_1` (not `Action`). Always check actual field link names in the
   .ds before writing Deluge scripts.
4. **New reports must be inside `reports { }`**: Same pattern as gotcha #1.
   Insert before the closing `}` of `reports`, not between `}` and `pages`.
5. **Widgets are not represented in `.ds` exports**: Creator widgets are
   packaged separately (plugin-manifest.json + JS/HTML/CSS bundled as a zip)
   and uploaded through the Creator portal, not serialized into `.ds`.
   `parse_ds_export.py` does not inspect widgets and does not need to.
   Widget declarations live in `forgeds.yaml` under the `widgets:` block,
   and on disk under the path configured as each widget's `root`.

## Rules for contributions
- Every tool must have `def main()` and `if __name__ == "__main__": main()`
- Import shared types: `from forgeds._shared.diagnostics import Severity, Diagnostic`
- Import config: `from forgeds._shared.config import load_config, get_db_dir`
- No project-specific constants — use `load_config()` with sensible defaults
- Exit codes: 0 = clean, 1 = warnings, 2 = errors

## Rule code registry

All linters emit `Diagnostic` objects with a `rule` field using these prefixes:

| Prefix | Owner | Meaning |
|---|---|---|
| `DG###` | `forgeds.core.lint_deluge` | Deluge lint rules |
| `AV###` / `AC###` | `forgeds.access.lint_access` | Access / VBA rules |
| `HY###` | `forgeds.hybrid.lint_hybrid` | Deluge↔Access cross-checks |
| `WG###` | `forgeds.hybrid.lint_hybrid` (WG001-003) and `forgeds.widgets.validate_manifest` (WG004) | Widget↔Deluge cross-checks + manifest-schema violations |
| `WGR###` | `forgeds.widgets.run_widget` | Widget runtime verification (mocked-SDK execution) |
| `JS:<rule>` | `forgeds.widgets.lint_widgets` | ESLint rule ID, foreign provenance (includes `JS:zoho-widget/...` from the local plugin) |
| `CFG###` | `forgeds._shared.config` | Config-schema diagnostics (custom_apis, widgets, types) |
| `STA###` | `forgeds.status.*` | `forgeds-status` aggregate-check diagnostics |
| `WSP###` | `forgeds.widgets.spec_loader` | `widget-spec.yaml` schema / cross-ref violations (Phase 2C) |
| `SCF###` | `forgeds.widgets.scaffold_widget` | Scaffolder diagnostics (collision, force-overwrite, drift) |
| `BND###` | `forgeds.widgets.bundle_widget` | Bundler diagnostics (manifest/spec mismatch, zet stderr, size limits) |
| `DPY###` | `forgeds.widgets.deploy_widget` | Deployer diagnostics (OAuth source, spike gate, conflicting flags) |
| `BLD###` | `forgeds.widgets.build_app` | Build-app orchestrator-entry diagnostics (config validation, orchestrator unreachable, stage flag parsing) |

Widget rule allocation:
- `WG001` — widget root directory missing
- `WG002` — widget `plugin-manifest.json` missing or fails schema validation
- `WG003` — widget `consumes_apis[i]` not declared in `custom_apis`
- `WG004` — schema violation inside a widget's `plugin-manifest.json` (emitted by standalone `forgeds-validate-widget-manifest`; wrapped as `WG002` when surfaced via `lint_hybrid`)

Config rule allocation (`CFG###`, reserved range CFG001-CFG099):
- `CFG001-CFG009` — reserved for top-level `forgeds.yaml` structural errors (future)
- `CFG010` — `custom_apis:` mixes bare-list and dict forms (ERROR)
- `CFG011` — `custom_apis` declared in short (Form A) form; typegen will skip (INFO)
- `CFG012` — `widgets.<w>.consumes_apis[i]` references a name not in `custom_apis` (ERROR) — config-time duplicate of WG003
- `CFG013` — `custom_apis.<name>.returns` or `params[i].type` references unknown named type (WARNING)
- `CFG014` — `custom_apis.<name>.params[i]` missing required key `name` or `type` (ERROR)
- `CFG015` — `custom_apis.<name>.permissions` is not a list of strings (ERROR)

Widget runtime rule allocation (`WGR###`, Phase 2B):
- `WGR001` — widget invoked an undeclared Custom API (ERROR) OR declared a Custom API in `consumes_apis` but never invoked it during runtime (WARNING)
- `WGR002` — widget entry point or `init()` threw / rejected
- `WGR003` — response-shape mismatch vs a declared Custom API schema (stubbed in 2B; emits zero diagnostics until Phase 2A response-map extension lands)
- `WGR004` — widget invoked an SDK method whose `required_permissions` are not listed in `plugin-manifest.json` `permissions`
- `WGR-meta` — entry-point missing, harness timeout, SDK method reached via Proxy fallback (mock drift), or harness crash; non-numbered bucket for operator-facing warnings

Status rule allocation (`STA###`):
- `STA001` — `forgeds.yaml` missing or unparseable (fatal for text mode)
- `STA002` — required language DB missing
- `STA003` — language DB older than 30 days (warning)
- `STA004` — Node required by widgets but not on PATH
- `STA005` — ESLint required but not resolvable via `npx`
- `STA006` — a linter subprocess exited non-zero for non-lint reasons (crash)

Widget-spec rule allocation (`WSP###`, Phase 2C):
- `WSP001` — `widget-spec.yaml` missing or unparseable
- `WSP002` — schema violation (missing required / wrong type / bad enum)
- `WSP003` — name mismatch: `widget-spec.name` vs `plugin-manifest.name` vs directory name
- `WSP004` — `consumes_apis[i]` not in `forgeds.yaml custom_apis` (warning; duplicate of WG003/CFG012 when invoked outside hybrid lint)
- `WSP005` — decorative field has wrong type (warning, proceed)

Scaffolder rule allocation (`SCF###`, Phase 2C):
- `SCF001` — output file collision without `--force` (error)
- `SCF002` — `--force` overwrote an existing file (warning per file)
- `SCF003` — cannot create output dir / write file
- `SCF004` — idempotency drift: on-disk content differs from re-scaffold baseline (warning)

Bundler rule allocation (`BND###`, Phase 2C):
- `BND001` — validation chain failure (aggregate of spec/manifest/cross-ref/structural)
- `BND002` — `zet pack` non-zero exit (or pure-Python fallback raised OSError)
- `BND003` — `zet pack` / lint subprocess stderr warnings
- `BND004` — file-size sanity check exceeded (manifest > 64 KB, any JS > 2 MB — **UNVERIFIED** limits from community posts)
- `BND005` — `TODO` token present in `index.js` at bundle time (ship-as-skeleton warning)
- `BND006` — output ZIP collision without `--force`

Deployer rule allocation (`DPY###`, Phase 2C):
- `DPY001` — `--confirm` without `--target`
- `DPY002` — conflicting flags (`--dry-run --confirm`)
- `DPY003` — no OAuth source resolved (lists every attempted source; value never logged)
- `DPY004` — OAuth source resolved / dry-run preview / non-interactive abort (info)
- `DPY005` — publish endpoint returned non-3000 code (UNVERIFIED shape)
- `DPY006` — spike gate: `--confirm` gated on the §7.5 research spike (exit 3 until spike lands)

Build-app rule allocation (`BLD###`, Phase 2C):
- `BLD001` — `--target` required when `deploy` is in `--stages`
- `BLD002` — Node Orchestrator Service unreachable (exit 3; points at `--plan-only`)
- `BLD003` — invalid `--stages` token
- `BLD004` — `forgeds.yaml` validation surfaced CFG diagnostics (warning, non-halting)
- `BLD005` — `forgeds.yaml` not found from cwd upward

### Envelope versioning policy

- Envelope `version` strings live in a single namespace shared across every `tool` value (diagnostics or status). A bump to `"2"` applies everywhere simultaneously.
- New fields on existing shapes (`Diagnostic`, `StatusCheck`) require a version bump. Renames and removals require a bump. Adding a new `tool` value that reuses the current shape does not bump.
- v1 and v2 may coexist for at least one release; consumers MUST branch on `version`, not on `tool`.
- Optional fields injected by overlying orchestration layers (e.g., an `agent` provenance block added by a multi-agent orchestrator) do NOT require a version bump, provided they are documented as optional and existing consumers are unaffected by their presence.
- `src/forgeds/_shared/envelope.py` is the sole serializer. No other module may construct the v1 envelope shape.

### Typegen emission contract (design-only in Phase 2A)

- Generated clients land in the consumer repo at `src/widgets/_generated/` (TypeScript `.d.ts` + minimal `.js` stub). Never inside the ForgeDS install path.
- ForgeDS tooling owns `_generated/` entirely. Every emitted file begins with a `// DO NOT EDIT` banner naming the regeneration command.
- Consumers add `src/widgets/*/_generated/` to their repo's `.gitignore` and run `forgeds-typegen-widgets` (future command) before widget build.
- `forgeds-status` surfaces stale `_generated/` as a `config_sanity` warning (implementation deferred to the phase that lands the typegen itself).

When adding a new rule: pick the next unused number in the prefix's range, add a
test fixture under `tests/fixtures/`, and document the rule's intent in a
docstring on the check function.

## Widget linting toolchain

`forgeds-lint-widgets` shells out to ESLint with a curated config at
`src/forgeds/widgets/configs/.eslintrc.zoho.json`.

**ForgeDS pip install remains zero-dep.** Node/ESLint is a **runtime-optional**
dependency (same posture as `pyodbc` for Access tools):

- If `npx eslint --version` succeeds → widget lint runs normally.
- If absent → `forgeds-lint-widgets` exits with code 3 and prints an install
  hint. No crash, no partial diagnostics.

To enable widget lint:

```bash
# Global install (simplest)
npm i -g eslint

# Or per-consumer-project
npm i --save-dev eslint
```

Minimum supported: Node ≥ 18, ESLint 8+.

## Widget runtime toolchain (Phase 2B)

`forgeds-run-widget` loads each widget declared in `forgeds.yaml` under
Node, against a mocked `ZOHO` SDK generated from `zoho_widget_sdk.db`.
The harness records every SDK call, and the Python orchestrator diffs
the call log against declarations to emit `WGR###` diagnostics.

Two-step regeneration of the mock (do not combine):

```bash
forgeds-build-widget-db
forgeds-gen-sdk-mock        # writes src/forgeds/widgets/runtime/sdk_mock.js
```

Node posture mirrors the Phase 1 widget-lint toolchain:

- `node --version` succeeds → `forgeds-run-widget` runs normally.
- Node absent → exit **3** with an install hint; no partial diagnostics.

Every widget runs in its own Node subprocess — no daemon, no shared
global state between widgets. Default per-widget timeout is 10 s
(`--timeout-ms` to override).

Entry-point discovery: default `<widget.root>/index.js`. Optional
`entry_point:` under each widget in `forgeds.yaml` (relative to the
widget's `root`) overrides the default.

## Widget build pipeline (Phase 2C)

Four new CLIs ship the widget end-to-end:

- `forgeds-scaffold-widget` — emit a widget tree from `widget-spec.yaml`.
- `forgeds-bundle-widget`   — validate + ZIP the tree for upload.
- `forgeds-deploy-widget`   — upload the ZIP (dry-run default, spike-gated).
- `forgeds-build-app`       — thin entry that POSTs a BuildPlan to the Node Orchestrator Service, or emits `build-plan-request.json` with `--plan-only`.

ZET (Zoho Extension Toolkit) posture mirrors Phase 1 ESLint:

- `npx zet --version` succeeds → `forgeds-bundle-widget` runs normally.
- Absent → exit **3** with an install hint. Pass `--no-zet` to use the
  pure-Python `zipfile` fallback. The fallback excludes `widget-spec.yaml`
  from the bundle (authoring-only, not runtime).

Dry-run posture asymmetry (§9.1 of the spec):

| Command | Default |
|---|---|
| `forgeds-scaffold-widget` | writes files |
| `forgeds-bundle-widget`   | writes files (no network) |
| `forgeds-deploy-widget`   | **dry-run (no network)** unless `--confirm` |
| `forgeds-build-app`       | POSTs to orchestrator; deploy stage itself is dry-run unless invoked directly |

**Spike gate on `forgeds-deploy-widget --confirm`:** The publish
endpoint shape is UNVERIFIED (spec §7.5). `--confirm` exits **3** until
a research spike confirms the endpoint. Bypassable only from pytest via
`FORGEDS_DEPLOY_SPIKE_OVERRIDE_TESTONLY=1` AND `PYTEST_CURRENT_TEST`
set (the second is set automatically by pytest; production runs have
neither and always exit 3). Do not set the override env var outside of
a pytest run — behaviour is undefined.

**Orchestrator service status:** `forgeds-build-app` POSTs to
`http://127.0.0.1:9878/orchestrate`. The Node Orchestrator Service is
designed (see `docs/superpowers/specs/2026-04-23-forgeds-widgets-phase2-orchestration-design.md`)
but not yet implemented. Until it lands, use `--plan-only` — `build-app`
emits the plan-request JSON to stdout and exits 0.

**Token handling:** OAuth resolution order (spec §7.2): `--token` arg →
`ZOHO_ACCESS_TOKEN` env → `config/zoho-api.yaml` → full refresh flow.
The token value is **never** printed, never stored in results; only
the source *name* (`env:ZOHO_ACCESS_TOKEN`, `config:zoho-api.yaml`,
etc.) appears in logs. Unit tests assert this; don't change without
re-asserting.
