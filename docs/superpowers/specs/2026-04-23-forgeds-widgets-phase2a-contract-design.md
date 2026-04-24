# ForgeDS Widgets Phase 2A — Polyglot Contract Layer (DRAFT for user review)

**Date:** 2026-04-23
**Status:** Draft — produced by parallel-agent brainstorming pass, awaits user approval before a plan is written.
**Depends on:** Phase 1 (`docs/superpowers/specs/2026-04-22-forgeds-widgets-phase1-design.md`)
**Parallel siblings:** Phase 2B (runtime), 2C (build/deploy), 2D (IDE/AI) — see respective draft specs in this directory.

> **Multi-agent note:** See `docs/superpowers/specs/2026-04-23-forgeds-widgets-phase2-orchestration-design.md` §9 (Diagnostic provenance) for how the optional `agent` field is populated when diagnostics flow through the orchestration layer. This spec defines the envelope shape; the orchestration spec defines how the provenance is injected.

---

## 1. Problem statement

Phase 1 shipped a widget-lint pilot with a versioned JSON diagnostic envelope (`tool`, `version`, `diagnostics[]`). The three pre-existing linters — `forgeds-lint` (Deluge), `forgeds-lint-access`, `forgeds-lint-hybrid` — still emit only text via `str(Diagnostic)` (`_shared/diagnostics.py:37`, dispatch at `lint_deluge.py:1141`, `lint_access.py:749`, `lint_hybrid.py:791`). An IDE or AI agent wanting a uniform programmatic view of a ForgeDS project must scrape four different output formats and there is no single endpoint for aggregate project health.

Simultaneously, `custom_apis:` is a bare `list[str]` in `forgeds.yaml` (Phase 1 §4.1). That is enough for the WG003 cross-check but nowhere near enough to emit typed clients (`.d.ts` / `.js` stubs) into widgets. A future typegen step has no schema to consume.

Phase 2A fixes both: it **promotes the v1 envelope to every linter** under an opt-in flag, introduces **`forgeds-status`** as a single CLI the IDE polls for aggregate project health, and **defines (but does not implement) the extended `custom_apis:` schema** plus the emission contract a later phase's typegen will honor. No linter's text default changes. No code is generated on disk yet. The deliverable is a stable polyglot contract — contracts, not clients.

## 2. Scope

**In scope**

| Gap | Deliverable |
|---|---|
| P2A-1 | `--format {text,json-v1}` flag on `forgeds-lint`, `forgeds-lint-access`, `forgeds-lint-hybrid` (default: text) |
| P2A-2 | `FORGEDS_OUTPUT={text,json-v1}` env var honored by all four linters; explicit `--format` wins |
| P2A-3 | `forgeds-status` — new aggregate-health CLI with text and JSON-v1 modes |
| P2A-4 | Extended `custom_apis:` YAML grammar — full schema definition, loader parses it, config-level diagnostics (`CFG###`) fire on malformed entries |
| P2A-5 | Typegen emission contract — path convention, filename convention, `_generated/` ownership, consumer-build wiring documented; **no generator implementation** |
| P2A-6 | Rule code registry updated in `CLAUDE.md` — adds `CFG###`, `STA###`, documents envelope version policy |

**Deferred to Phase 2A.1 / 2B+**

| Gap | Reason for deferral |
|---|---|
| P2A-D1 | Actual `.d.ts` / `.js` stub emission from extended `custom_apis:` — requires signature autodiscovery or widely-adopted YAML first |
| P2A-D2 | Custom API signature autodiscovery from `custom-api/*.dg` — AST work, parallel sibling Phase 2B |
| P2A-D3 | Permission-scope enforcement (widget consumes API requiring scope the manifest does not declare) — needs runtime from 2B |
| P2A-D4 | Default-format flip from text to json-v1 — explicit migration phase, minimum two ForgeDS releases after 2A ships |
| P2A-D5 | Column/hint/fix fields in Diagnostic — envelope stays v1; new fields are a v2 concern |
| P2A-D6 | `forgeds-status --fix` / remediation suggestions — read-only in 2A |

## 3. Architecture

### 3.1 New files

```
src/forgeds/_shared/
├── envelope.py                     # P2A-1,2 — JSON-v1 serializer, single source of truth
└── output_format.py                # P2A-1,2 — --format / FORGEDS_OUTPUT resolution helper

src/forgeds/status/
├── __init__.py
├── cli.py                          # P2A-3 — forgeds-status entry point
├── checks/
│   ├── __init__.py
│   ├── db_freshness.py             # checks language DBs exist & are non-stale
│   ├── config_sanity.py            # checks forgeds.yaml schema, widget/api cross-refs
│   ├── lint_summary.py             # invokes each linter in json-v1 mode, aggregates
│   └── toolchain.py                # checks Node/ESLint/python versions
└── report.py                       # renders aggregate report in text or JSON
```

### 3.2 Modified files

- `src/forgeds/core/lint_deluge.py` — `main()` gains `--format` / env read; formatter dispatch via `envelope.py`
- `src/forgeds/access/lint_access.py` — same
- `src/forgeds/hybrid/lint_hybrid.py` — same
- `src/forgeds/widgets/lint_widgets.py` — routes through `envelope.py` (removes ad-hoc JSON writer from Phase 1; no user-visible change)
- `src/forgeds/_shared/config.py` — accepts Phase-1 bare-list AND Phase-2A extended dict form for `custom_apis:`; emits `CFG###` diagnostics on malformed entries
- `pyproject.toml` — one new entry point: `forgeds-status`
- `templates/forgeds.yaml.example` — document extended `custom_apis:` shape with a commented example
- `CLAUDE.md` — rule-code registry, envelope versioning policy, `_generated/` ownership note

### 3.3 File responsibilities (key contracts)

| File | Responsibility |
|---|---|
| `_shared/envelope.py` | `to_json_v1(tool: str, diagnostics: list[Diagnostic]) -> str`. No other formatter may serialize JSON. |
| `_shared/output_format.py` | `resolve_format(cli_flag: str \| None) -> Literal["text","json-v1"]`. Precedence: CLI flag → env var → "text". |
| `status/cli.py` | Thin — argument parsing, delegates to `checks/` and `report.py`. |
| `status/checks/*.py` | Each exposes `run(config) -> list[StatusCheck]`. Pure; no side effects except subprocess calls to already-existing ForgeDS CLIs. |
| `status/report.py` | Renders either text banner (§5.2) or JSON-v1 status envelope (§5.3). |

## 4. Diagnostic envelope v1 promotion

### 4.1 Flag behavior

Every linter accepts:

```
--format {text,json-v1}
```

Default when flag absent: read `FORGEDS_OUTPUT` env var; if unset or empty, use `text`. Invalid values on either channel produce exit code 2 and a single stderr line: `forgeds: unknown output format '<x>' (expected: text, json-v1)`. No partial output.

### 4.2 Backwards compatibility

| Concern | Answer |
|---|---|
| Existing scripts grepping `file:line: [RULE] SEVERITY: message` | Unaffected — text remains default |
| Widget JSON consumers from Phase 1 | Unaffected — same envelope shape, same `version: "1"` |
| Default flip | Deferred (P2A-D4). Earliest: two ForgeDS releases after 2A. Migration note in CLAUDE.md. |
| Exit codes | Unchanged. 0/1/2 everywhere; 3 stays widget-toolchain-specific. |

### 4.3 Per-linter envelope examples

Text format (default, all linters — already the status quo for three of four):

```
src/forms/expense_claim.dg:84: [DG014] ERROR: undefined field 'amount_usdd'
```

JSON-v1 format, Deluge (`--format json-v1`):

```json
{
  "tool": "forgeds-lint",
  "version": "1",
  "diagnostics": [
    {
      "file": "src/forms/expense_claim.dg",
      "line": 84,
      "rule": "DG014",
      "severity": "error",
      "message": "undefined field 'amount_usdd'"
    }
  ]
}
```

JSON-v1, Access (`forgeds-lint-access --format json-v1`):

```json
{
  "tool": "forgeds-lint-access",
  "version": "1",
  "diagnostics": [
    {
      "file": "queries/claim_summary.sql",
      "line": 12,
      "rule": "AV007",
      "severity": "warning",
      "message": "SELECT * without explicit column list"
    }
  ]
}
```

JSON-v1, Hybrid: identical shape, `tool: "forgeds-lint-hybrid"`. JSON-v1, Widgets: unchanged from Phase 1 §6 (`tool: "forgeds-lint-widgets"`).

> **Multi-agent annotation (optional):** When diagnostics flow through the multi-agent orchestration layer, each diagnostic gains an optional `agent` field with provenance. Direct CLI invocations omit it. Backward-compatible — no envelope version bump.

Annotated form (produced only by the orchestration layer):

```json
{
  "file": "src/forms/expense_claim.dg",
  "line": 84,
  "rule": "DG014",
  "severity": "error",
  "message": "undefined field 'amount_usdd'",
  "agent": {
    "id": "worker/linter",
    "role": "linter",
    "model": "claude-haiku-4",
    "session_id": "sess_01abc..."
  }
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| agent.id | string | yes if agent present | Stable worker ID (e.g. `worker/linter`, `architect/build-plan`) |
| agent.role | string | yes if agent present | Human-readable role |
| agent.model | string | yes if agent present | Model ID from SDK `ResultMessage` |
| agent.session_id | string | no | For cross-referencing transcripts; omit for non-agent CLI |

### 4.4 Envelope invariants

- `tool` MUST equal the exact CLI entry-point name (no historic aliases, no version suffix).
- `version` is a string not an integer — future values `"2"`, `"2.1"` sort lexicographically within each major.
- `diagnostics` is always present, even when empty (`[]`), even in clean runs. No null shortcuts.
- Severity strings are lowercase: `"error" | "warning" | "info"`.
- All fields in the base diagnostic object are required. The `agent` field is OPTIONAL and populated only by multi-agent orchestration consumers; direct CLI invocations omit it. When `agent` IS present, `agent.id`, `agent.role`, and `agent.model` are all required; `agent.session_id` is optional.

## 5. `forgeds-status` contract

### 5.1 CLI surface

```
forgeds-status [--format {text,json-v1}] [--skip-lint] [--skip-toolchain] [-q]
```

| Flag | Effect |
|---|---|
| `--format` | Same semantics as §4.1 |
| `--skip-lint` | Omit `lint_summary` check (useful in CI where lint ran separately) |
| `--skip-toolchain` | Omit `toolchain` check (useful when Node absence is a known non-blocker) |
| `-q` | Suppress non-failing check output in text mode; JSON mode ignores `-q` |

No positional args. `forgeds-status` always operates on the project rooted at the discovered `forgeds.yaml` (walks up from cwd — existing behavior).

### 5.2 Text output shape

Rendered in a fixed section order so downstream scraping by AI agents remains stable:

```
ForgeDS Project Health Report
==============================
Database Freshness:
  OK   deluge_lang.db         (built 2026-04-15)
  OK   access_vba_lang.db     (built 2026-04-15)
  MISS zoho_widget_sdk.db     (missing — run: forgeds-build-widget-db)

Config Sanity:
  OK   forgeds.yaml           (found at ./forgeds.yaml)
  OK   custom_apis            (2 declared, all well-formed)
  WARN widget 'expense_dashboard' consumes 'get_records' not in custom_apis  [CFG012]

Lint Summary:
  OK   Deluge                 (0 errors, 0 warnings)
  OK   Access                 (0 errors, 0 warnings)
  WARN Hybrid                 (0 errors, 1 warning)
  OK   Widgets                (0 errors, 0 warnings)

Toolchain:
  OK   Python                 3.11.6
  OK   Node                   v20.10.0
  OK   ESLint                 9.0.0

Overall: WARN (exit 1)
```

Status tokens are fixed ASCII three-letter codes (`OK`, `WARN`, `FAIL`, `MISS`, `SKIP`) — no Unicode glyphs, no colors unless stdout is a TTY (color is cosmetic; scrapers rely on the tokens).

### 5.3 JSON-v1 status envelope

Parallel to the diagnostic envelope: same top-level `tool` + `version`, but with a `checks[]` array instead of `diagnostics[]`. Envelope version strings occupy a single namespace, so the status envelope is also `"1"`.

```json
{
  "tool": "forgeds-status",
  "version": "1",
  "overall": "warn",
  "checks": [
    {
      "category": "db_freshness",
      "id": "zoho_widget_sdk.db",
      "status": "miss",
      "message": "missing — run: forgeds-build-widget-db",
      "rule": "STA002"
    },
    {
      "category": "config_sanity",
      "id": "widgets.expense_dashboard.consumes_apis[0]",
      "status": "warn",
      "message": "widget 'expense_dashboard' consumes 'get_records' not in custom_apis",
      "rule": "CFG012"
    },
    {
      "category": "lint_summary",
      "id": "forgeds-lint-hybrid",
      "status": "warn",
      "message": "0 errors, 1 warning",
      "rule": null
    },
    {
      "category": "toolchain",
      "id": "node",
      "status": "ok",
      "message": "v20.10.0",
      "rule": null
    }
  ]
}
```

`rule` is nullable on purpose: lint-summary aggregation and toolchain-version reports are not rule-attributed. `category` values are a closed set: `db_freshness | config_sanity | lint_summary | toolchain`. `status` values are a closed lowercase set mirroring the text tokens: `ok | warn | fail | miss | skip`. `overall` is drawn from the same set (without `skip` or `miss`, collapsed into `fail`): `ok | warn | fail`.

> Each `StatusCheck` object may optionally carry the same `agent` provenance field as diagnostics, set when a status check is produced by a worker agent (e.g., `worker/linter` calling `forgeds_status`). Direct invocations (user running `forgeds-status` from terminal) omit it.

### 5.4 Exit-code logic

| Observed | Exit |
|---|---|
| All checks `ok` | 0 |
| Any check `warn`, none `fail`/`miss` | 1 |
| Any check `fail` or `miss` | 2 |
| `forgeds-status` itself crashes (uncaught) | Python default (non-zero, typically 1) — treated as infrastructure error, not a check result |

`miss` folds into exit 2 because a missing DB breaks any downstream lint that queries it. Toolchain `skip` (deliberately skipped via `--skip-toolchain`) never contributes to exit code.

### 5.5 Execution order of checks

Ordered for progressive failure isolation — fail-fast on foundational problems:

1. **Config sanity** first. If `forgeds.yaml` is missing or invalid YAML, emit `STA001` (fatal), exit 2, skip remaining checks.
2. **Database freshness** second. DB absence affects lint results; reporting it before running lint gives clear root cause.
3. **Toolchain** third. Cheap, informational; separate from lint because widget-lint's exit 3 is toolchain-specific and we want that signal even if the lint pass couldn't run.
4. **Lint summary** last. Most expensive (spawns four subprocesses); output is most useful when the preceding checks are green.

In JSON mode, all checks run regardless of early failures (caller may want the full picture); text mode honors early-abort on step 1 only.

## 6. Extended `custom_apis:` schema

### 6.1 Grammar

Two forms accepted; loader normalizes both to the extended form in memory.

**Form A — Phase-1 compatible (still valid):**

```yaml
custom_apis:
  - get_pending_claims
  - approve_claim
```

**Form B — Phase-2A extended:**

```yaml
custom_apis:
  get_pending_claims:
    params:
      - { name: "status", type: "string", required: true }
      - { name: "limit",  type: "integer", required: false, default: 50 }
    returns: "PendingClaim[]"
    permissions: ["api.read"]
    description: "Lists claims awaiting approval."
  approve_claim:
    params:
      - { name: "claim_id", type: "integer", required: true }
    returns: "ApprovalResult"
    permissions: ["api.write"]
```

Mixing forms in one file is disallowed — loader emits `CFG010` and refuses to normalize. Rationale: migration is an all-or-nothing project-level choice; silent coexistence hides intent.

### 6.2 Field requirements for typegen

| Field | Required for typegen? | Notes |
|---|---|---|
| api name (key) | Yes | becomes exported symbol |
| `params[].name` | Yes | becomes parameter identifier |
| `params[].type` | Yes | maps to TS type (§6.4) |
| `params[].required` | No (default: true) | false → param emitted as optional `?` |
| `params[].default` | No | informational only; no default-value code emission |
| `returns` | Yes | maps to TS type |
| `permissions` | No | informational in 2A; enforced in 2B |
| `description` | No | emitted as JSDoc `@description` |

Form A entries lack every typegen-required field — they remain valid for WG003 cross-checking but typegen skips them with a `CFG011` info diagnostic ("api 'X' declared in short form; typegen skipped").

### 6.3 Type grammar (minimal)

Types are strings. Grammar accepted in 2A:

```
primitive  := "string" | "integer" | "number" | "boolean" | "any"
named_ref  := <identifier>              # user-defined, e.g. "PendingClaim"
array_of   := <type> "[]"
type       := primitive | named_ref | array_of
```

Named references resolve against a future `types:` block (not in scope for 2A; documented as reserved). Unknown named refs in 2A emit `CFG013` (warning, not error) so projects can introduce extended-form APIs before the `types:` block exists.

### 6.4 Config diagnostics (`CFG###`)

| Rule | Check | Severity |
|---|---|---|
| `CFG010` | `custom_apis:` mixes list and dict forms | ERROR |
| `CFG011` | `custom_apis.<name>` declared in short (Form A) form; typegen will skip | INFO |
| `CFG012` | `widgets.<w>.consumes_apis[i]` references name not in `custom_apis` | ERROR (duplicates WG003 at config-time; same wording, earlier detection) |
| `CFG013` | `custom_apis.<name>.returns` or `params[i].type` references unknown named type | WARNING |
| `CFG014` | `custom_apis.<name>.params[i]` missing required key `name` or `type` | ERROR |
| `CFG015` | `custom_apis.<name>.permissions` is not a list of strings | ERROR |

`CFG012` is deliberately redundant with WG003. `forgeds-status` surfaces it earlier (no lint pass required); `lint_hybrid` keeps emitting it for standalone `forgeds-lint-hybrid` runs.

## 7. Typegen emission contract (design only, not implementation)

### 7.1 Landing zone

Generated files land in **the consumer repo**, not inside ForgeDS:

```
<consumer_project>/src/widgets/_generated/
├── custom_apis.d.ts        # TypeScript declarations
├── custom_apis.js          # Minimal fetch-wrapper JS stub
└── .gitignore              # generated-for-this-directory marker
```

`_generated/` is owned entirely by ForgeDS tooling. Hand-edits are forbidden and will be silently overwritten by the next typegen run. A leading banner in every emitted file makes this explicit:

```
// DO NOT EDIT. Generated by forgeds-typegen-widgets from forgeds.yaml.
// Regenerate: forgeds-typegen-widgets
// Source of truth: custom_apis: block in forgeds.yaml
```

### 7.2 Why consumer repo, not ForgeDS

Three options were evaluated:

| Option | Verdict |
|---|---|
| (A) Consumer repo `src/widgets/_generated/` | **Chosen.** Mirrors Prisma, GraphQL codegen, OpenAPI generators. Fully within the consumer's build context; IDE intellisense works natively; `.gitignore` keeps repo lean. |
| (B) Shared npm package published by ForgeDS | Rejected. Per-project APIs mean per-project packages mean per-project versioning — cost/benefit dismal for a tooling repo. |
| (C) Inside the ForgeDS install path | Rejected. Widgets can't reliably import from the pip install path; path fragility across OSes and venvs is a known anti-pattern. |

### 7.3 Naming convention

One file per top-level `custom_apis` block for now — not one file per API. Rationale: small number of APIs per project, bundlers handle tree-shaking, single import line in widget code:

```js
import { getPendingClaims, approveClaim } from "./_generated/custom_apis.js";
```

If a project grows past ~50 APIs and HMR cost becomes real, 2B can switch to per-API files with no breaking change to the `.d.ts` surface (the public types don't move).

### 7.4 `.d.ts` emission shape (design — representative)

```ts
// Generated. Do not edit.
export interface PendingClaim { /* user-defined, resolved from types: block (future) */ }
export interface ApprovalResult { /* ditto */ }

/**
 * Lists claims awaiting approval.
 * @permissions api.read
 */
export function getPendingClaims(status: string, limit?: number): Promise<PendingClaim[]>;

/**
 * @permissions api.write
 */
export function approveClaim(claim_id: number): Promise<ApprovalResult>;
```

### 7.5 `.js` stub emission shape (design — representative)

```js
// Generated. Do not edit.
export function getPendingClaims(status, limit) {
  return ZOHO.CREATOR.API.invokeCustomApi("get_pending_claims", { status, limit });
}
export function approveClaim(claim_id) {
  return ZOHO.CREATOR.API.invokeCustomApi("approve_claim", { claim_id });
}
```

The stub is intentionally dumb: it forwards args to `invokeCustomApi`. Type safety comes from the `.d.ts`; runtime surface is minimal so ForgeDS doesn't own request/response behavior (the SDK does).

### 7.6 Consumer build wiring

Documented in `CLAUDE.md` and `templates/forgeds.yaml.example`:

1. Add `src/widgets/*/_generated/` to the consumer repo's `.gitignore`.
2. Run `forgeds-typegen-widgets` (future command, 2A.1/2B) before widget build.
3. `forgeds-status` surfaces stale `_generated/` output (older than `forgeds.yaml` mtime) as a `config_sanity` warning — design ready, implementation deferred with typegen itself.

## 8. Testing

### 8.1 Fixtures (additions to `tests/fixtures/`)

```
tests/fixtures/envelope/
├── deluge_sample_bad.dg           # drives DG errors for --format json-v1 test
├── access_sample_bad.sql          # same for AV
└── hybrid_sample_bad/             # small project fixture for HY
    ├── forms/...
    └── queries/...

tests/fixtures/status/
├── all_green/                     # every check passes
├── missing_db/                    # deluge_lang.db absent
├── config_only_warnings/          # WG003-equiv config warning
└── broken_yaml/                   # invalid forgeds.yaml (step-1 early-abort)

tests/fixtures/custom_apis/
├── form_a_bare_list/              # Phase-1 compatible
├── form_b_extended/               # full schema
├── mixed_forms/                   # triggers CFG010
├── missing_param_keys/            # triggers CFG014
└── unknown_named_type/            # triggers CFG013
```

### 8.2 Unit test names (no code)

- `test_envelope_emits_empty_diagnostics_array` — clean run still yields `"diagnostics": []`
- `test_envelope_version_is_string` — serializer writes `"version": "1"` not `1`
- `test_output_format_env_var_honored`
- `test_output_format_cli_flag_overrides_env`
- `test_output_format_rejects_unknown_value`
- `test_lint_deluge_json_v1_shape` — full roundtrip against a known bad fixture
- `test_lint_access_json_v1_shape`
- `test_lint_hybrid_json_v1_shape`
- `test_lint_widgets_uses_shared_envelope_serializer` — regression guard that Phase-1 widget JSON now routes through `_shared/envelope.py`
- `test_status_text_report_sections_order` — exact section order per §5.2
- `test_status_json_envelope_shape` — checks closed-set `category` values and `rule` nullability
- `test_status_exit_code_matrix` — parameterized over fixtures
- `test_status_aborts_on_broken_yaml_in_text_mode`
- `test_status_runs_all_checks_in_json_mode_despite_config_failure`
- `test_config_loader_accepts_form_a_custom_apis`
- `test_config_loader_accepts_form_b_custom_apis`
- `test_config_loader_rejects_mixed_custom_apis_forms` — CFG010
- `test_cfg011_info_on_short_form` — typegen-skip info
- `test_cfg013_warn_on_unknown_named_type`
- `test_cfg014_error_on_missing_param_keys`
- `test_cfg015_error_on_non_list_permissions`

### 8.3 No new test framework

Existing stdlib-`unittest`-based setup applies. JSON roundtrip assertions use `json.loads` + dict equality; no golden-file comparison (line-ending fragility).

## 9. Rule code registry update

Updated `CLAUDE.md` table (replaces Phase 1 §12 table when merged):

| Prefix | Owner | Meaning |
|---|---|---|
| `DG###` | `core.lint_deluge` | Deluge lint rules |
| `AV###` / `AC###` | `access.lint_access` | Access / VBA rules (mixed legacy prefix; cleanup deferred) |
| `HY###` | `hybrid.lint_hybrid` | Deluge↔Access cross-checks |
| `WG###` | `hybrid.lint_hybrid` | Widget↔Deluge cross-checks |
| `JS:<rule>` | `widgets.lint_widgets` (pass-through) | ESLint rule ID, foreign provenance |
| **`CFG###`** | **`_shared.config`** | **Config-schema diagnostics (custom_apis, widgets, types) — NEW in 2A** |
| **`STA###`** | **`status.*`** | **`forgeds-status` aggregate-check diagnostics — NEW in 2A** |

### 9.1 `CFG###` allocation (first block)

Reserved range `CFG001–CFG099` for config-schema issues. Initial entries defined in §6.4: CFG010–CFG015. `CFG001–CFG009` reserved for top-level `forgeds.yaml` structural errors (missing key, wrong type at root) addressed when the loader grows strict mode.

### 9.2 `STA###` allocation (first block)

| Rule | Fires in | Meaning |
|---|---|---|
| `STA001` | `config_sanity` | `forgeds.yaml` missing or unparseable |
| `STA002` | `db_freshness` | Required language DB missing |
| `STA003` | `db_freshness` | Language DB older than 30 days (warning — threshold documented) |
| `STA004` | `toolchain` | Node required by widgets but not on PATH |
| `STA005` | `toolchain` | ESLint required but not resolvable via `npx` |
| `STA006` | `lint_summary` | A linter subprocess exited non-zero for non-lint reasons (crash) |
| `STA007` | `config_sanity` | `_generated/` directory older than `forgeds.yaml` (stale typegen output — design-ready, emission deferred) |

### 9.3 Envelope versioning policy (appended to `CLAUDE.md`)

- Envelope version strings live in a single namespace shared across `tool` values.
- New fields on existing shapes (`Diagnostic`, `StatusCheck`) require a bump to `"2"`.
- Renames and removals require a bump.
- Adding a new `tool` value reusing the current shape does not bump.
- v1 and v2 may coexist for at least one release; consumers MUST branch on `version`, not on `tool`.
- Optional fields added by overlying orchestration layers (e.g., `agent` provenance injected by the Phase 2 multi-agent orchestrator) do NOT require a version bump, provided they are documented as optional and existing consumers are unaffected by their presence.

## 10. Risks

| Risk | Mitigation |
|---|---|
| **Text-format downstream consumers break** when default flips | Default flip deferred (P2A-D4); minimum two releases' notice in CLAUDE.md changelog; `FORGEDS_OUTPUT=text` lets any consumer pin. |
| **Typegen crosses the "ForgeDS doesn't touch consumer code" line** | All emission confined to `_generated/` with a DO-NOT-EDIT banner; directory fully owned by ForgeDS; industry-standard pattern (Prisma/OpenAPI/GraphQL codegen). Design documented; actual emission deferred. |
| **`custom_apis:` extended form without signature autodiscovery is tedious to maintain** | Form A (bare list) remains first-class and sufficient for WG003. Extended form is strictly opt-in; CFG011 is info not warn so short-form projects see no nag. |
| **Envelope v1 schema drifts silently** as new fields sneak in | `_shared/envelope.py` is the single serializer; unit test asserts exact field set; any new field requires a version bump (documented §9.3). |
| **`forgeds-status` fans out four subprocesses and becomes CI-expensive** | `--skip-lint` flag; JSON consumers can keep state and poll only `db_freshness` + `config_sanity`; lint subprocesses run sequentially with early-exit if the first fails catastrophically. |
| **Status text scraping breaks** when section renderer evolves | Fixed-token status words (OK/WARN/FAIL/MISS/SKIP), fixed section names, fixed section order (§5.2), regression test locks the order. JSON-v1 is the officially recommended machine-readable channel. |
| **CFG012 / WG003 duplication confuses users** ("same thing twice?") | CLAUDE.md note documents the intentional duplication: WG003 is a lint-time check (widget file context), CFG012 is a config-time check (no file context). Both cite each other in their messages. |

## 11. Explicit non-goals

Stating out loud to prevent scope creep during implementation:

- No change to Deluge/Access/Hybrid text-format output bytes (not one character)
- No `--format yaml`, no `--format sarif`, no `--format junit` — json-v1 only
- No new diagnostic fields (`column`, `hint`, `fix`, `code_actions`) — envelope stays v1
- No typegen implementation — `.d.ts` / `.js` files are not written in 2A
- No `types:` block in `forgeds.yaml` — reserved syntax only, schema in 2B
- No permission-scope enforcement at any layer
- No `forgeds-status --fix` / `--suggest`; it is read-only
- No color/Unicode in status text output (ASCII-stable tokens only)
- No removal of Phase 1's widget-specific JSON emission path before the shared `envelope.py` routing is verified in CI
- No default-format flip from text to json-v1 in this phase

## 12. Open questions

| # | Question | Leaning |
|---|---|---|
| 1 | Should `--format` accept `json` as an alias for `json-v1`? | **No.** Forces consumers to commit to a version string; removes "json" as a moving target. |
| 2 | Does `forgeds-status` exit 1 or 2 when only info-severity issues exist? | **0 (clean).** Info is non-blocking by definition; exit 1 is reserved for warnings. |
| 3 | Should the `_generated/` banner include a hash of `forgeds.yaml` for stale-detection? | **Yes, likely** — simpler than mtime on Windows. Pin decision to typegen impl (2B). |
| 4 | Does `forgeds-lint-widgets` keep exit code 3 (toolchain missing), or promote it into `STA005`? | **Keep 3 on the linter; surface STA005 on status.** Two different CLIs, two appropriate exit semantics. |
| 5 | Should Form-A bare-list `custom_apis:` emit CFG011 per entry, or once per file? | **Once per file** — less noisy, same signal. Confirm during implementation. |
| 6 | When both `--format json-v1` and `-q` are passed, does `-q` filter anything? | **No.** JSON mode is always full; `-q` is a text-mode comfort flag. |
| 7 | Does `forgeds-status` cache lint results for a TTL to cut CI cost? | **No (2A).** Read-only, stateless. Caching is an IDE-layer concern (2D). |
| 8 | Should `custom_apis.<name>.permissions` cross-check against `sdk_permissions` table (Phase 1 §7)? | **Defer to 2B.** Cross-check requires DB lookup; 2A stays schema-only. |
| 9 | What happens if `forgeds.yaml` uses extended form but the project targets a ForgeDS release older than 2A? | Loader in older releases falls back to treating the dict as an error. Document version gate. |
| 10 | Is `tool: "forgeds-status"` a "linter" for envelope-shape purposes? | **No — distinct shape (`checks[]` not `diagnostics[]`), same envelope version namespace.** Documented §5.3. |
