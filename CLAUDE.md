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
| `JS:<rule>` | `forgeds.widgets.lint_widgets` | ESLint rule ID, foreign provenance |
| `CFG###` | `forgeds._shared.config` | Config-schema diagnostics (custom_apis, widgets, types) |
| `STA###` | `forgeds.status.*` | `forgeds-status` aggregate-check diagnostics |

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

Status rule allocation (`STA###`):
- `STA001` — `forgeds.yaml` missing or unparseable (fatal for text mode)
- `STA002` — required language DB missing
- `STA003` — language DB older than 30 days (warning)
- `STA004` — Node required by widgets but not on PATH
- `STA005` — ESLint required but not resolvable via `npx`
- `STA006` — a linter subprocess exited non-zero for non-lint reasons (crash)

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
