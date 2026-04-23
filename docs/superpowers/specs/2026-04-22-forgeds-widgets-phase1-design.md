# ForgeDS Widgets — Phase 1 Design

**Date:** 2026-04-22
**Branch target:** `claude/forgeds-widgets-phase1` (cut from `main`, independent of `claude/ide-shell-overhaul`)
**Posture:** Scaffolding-first. Stable external surfaces; thin rule depth; optional toolchains.

---

## 1. Problem statement

ForgeDS lints Deluge (`.dg`), Access SQL (`.sql`), and Deluge↔Access hybrid. There is no infrastructure for Zoho Creator widget code (`.js` / `.html` / `plugin-manifest.json`). A future JS verification agent has nothing to bind to.

Phase 1 delivers a minimum widget-lint infrastructure so downstream tools have stable CLI and data contracts. Rule coverage stays thin; coverage accretes in later phases.

## 2. Scope

**In scope**

| Gap | Deliverable |
|---|---|
| G4 | `widgets:` + `custom_apis:` blocks in `forgeds.yaml` + loader parsing |
| G2 | `zoho_widget_sdk.db` schema + 30 hand-curated seed APIs |
| G1 | `forgeds-lint-widgets` — Python orchestrator shelling to ESLint with curated config |
| G6 | `forgeds-validate-widget-manifest` — JSON Schema check (stdlib validator) |
| G3 | Hybrid rules WG001–WG003 in `lint_hybrid.py` (thin slice) |
| G7 | Parser investigation: does `.ds` carry widget refs? Document findings in CLAUDE.md |

**Deferred to Phase 2+**

| Gap | Reason for deferral |
|---|---|
| G5 | Runtime verification (Node + vitest + mocked SDK) — separate project-scale effort |
| G8 | Widget scaffolder — not blocking any downstream agent |
| G9 | OpenAPI/TS typegen from Custom APIs — consumer-ergonomics only |
| G10 | Widget zip/bundle pipeline — deployment concern, not verification |

## 3. Architecture

### 3.1 New package layout

```
src/forgeds/widgets/
├── __init__.py
├── lint_widgets.py              # G1 — ESLint orchestrator
├── build_widget_sdk_db.py       # G2 — DB builder
├── validate_manifest.py         # G6 — manifest validator
├── configs/
│   ├── .eslintrc.zoho.json      # G1 — curated ESLint rules + Zoho globals
│   └── plugin-manifest.schema.json  # G6 — JSON Schema for manifests
└── seed_data/
    └── widget_sdk_apis.json     # G2 — 30 hand-curated SDK entries
```

### 3.2 Extensions to existing files

- `src/forgeds/_shared/config.py` — parse new `widgets:` and `custom_apis:` YAML blocks
- `src/forgeds/hybrid/lint_hybrid.py` — add WG001–WG003 rule checks
- `pyproject.toml` — add 3 entry points under `[project.scripts]`
- `templates/forgeds.yaml.example` — document new blocks
- `CLAUDE.md` — rule code registry, Node-dependency posture, G7 findings

## 4. Config contract — `forgeds.yaml` additions

### 4.1 New blocks

```yaml
# Minimal registry of Custom APIs this project exposes.
# Phase 2 may autodiscover from .ds / custom-api/*.dg; Phase 1 is declare-first.
custom_apis:
  - get_pending_claims
  - approve_claim

# Widget declarations (Option Y: dict keyed by name, manifest-authoritative).
widgets:
  expense_dashboard:
    root: src/widgets/expense_dashboard/     # directory containing plugin-manifest.json
    consumes_apis:                            # must resolve against custom_apis above
      - get_pending_claims
      - approve_claim
```

### 4.2 Loader changes (`_shared/config.py`)

```python
# in defaults dict
"custom_apis": [],          # list[str]
"widgets": {},              # dict[str, WidgetDecl]
```

`WidgetDecl` is a plain dict with keys `{root: str, consumes_apis: list[str]}`. No dataclass in Phase 1 — keep it minimal.

### 4.3 Why Option Y (for spec self-reference)

- Manifest is authoritative for permissions/roles/entry — no duplication, no drift.
- Dict-keyed-by-name produces clean diagnostic messages: `"widget 'expense_dashboard' calls undefined API 'bar'"` rather than `"widgets[2].consumes_apis[1] ..."`.
- Extensible: new fields added to a widget's entry don't reshape list indices.

## 5. CLI contracts

### 5.1 Entry points (`pyproject.toml`)

```
forgeds-lint-widgets = "forgeds.widgets.lint_widgets:main"
forgeds-validate-widget-manifest = "forgeds.widgets.validate_manifest:main"
forgeds-build-widget-db = "forgeds.widgets.build_widget_sdk_db:main"
```

### 5.2 `forgeds-lint-widgets`

```
forgeds-lint-widgets [PATHS...] [--format {text,json}] [-q] [--errors-only]
```

| Exit | Meaning |
|---|---|
| 0 | Clean |
| 1 | Warnings only |
| 2 | Errors present |
| **3** | **Toolchain missing (Node/ESLint not resolvable)** |

Exit 3 prints a single-line install hint to stderr and no diagnostics.

### 5.3 `forgeds-validate-widget-manifest`

```
forgeds-validate-widget-manifest [PATHS...]
```

Same exit code convention (0/1/2). Emits Diagnostics in text format.

### 5.4 `forgeds-build-widget-db`

```
forgeds-build-widget-db
```

Mirrors `forgeds-build-db`. Reads seed JSON; writes `zoho_widget_sdk.db` into the same directory `get_db_dir()` returns.

## 6. Diagnostic JSON envelope (widgets-only pilot, v1)

```json
{
  "tool": "forgeds-lint-widgets",
  "version": "1",
  "diagnostics": [
    {
      "file": "src/widgets/expense_dashboard/index.js",
      "line": 42,
      "rule": "WG003",
      "severity": "error",
      "message": "widget 'expense_dashboard' declares consumes_apis: ['approve_claim'] but 'approve_claim' is not in custom_apis"
    }
  ]
}
```

**Rationale for explicit `version: "1"`:** future schema evolution (new fields like `column`, `hint`, `fix`) lands as `version: "2"` without breaking v1 consumers. Downstream agents can route on `tool` across linters.

Text format (default) matches existing linters' `file:line: [rule] SEVERITY: message`.

**Scope boundary:** This pilot is widgets-only. Deluge/Access/Hybrid linters' CLIs are untouched in Phase 1. If the envelope proves out, Phase 2 promotes it to those linters.

## 7. SDK DB schema — `zoho_widget_sdk.db`

Tailored to SDK shape (object-namespaced methods + lifecycle events), not a mirror of `deluge_lang.db` (flat function/task tables). Force-fitting would hide the hierarchy.

```sql
CREATE TABLE sdk_namespaces (
  name TEXT PRIMARY KEY,                    -- e.g. "ZOHO.CREATOR.API"
  description TEXT
);

CREATE TABLE sdk_methods (
  namespace TEXT NOT NULL,                  -- references sdk_namespaces.name
  name TEXT NOT NULL,                       -- e.g. "getRecords"
  signature TEXT NOT NULL,                  -- e.g. "(reportName, criteria, page, pageSize) => Promise<Response>"
  returns_promise INTEGER NOT NULL,         -- 0 | 1
  required_permissions TEXT,                -- comma-separated permission scopes
  deprecated_in TEXT,                       -- SDK version string, nullable
  notes TEXT,
  PRIMARY KEY (namespace, name)
);

CREATE TABLE sdk_events (
  name TEXT PRIMARY KEY,                    -- e.g. "PageLoad", "RecordSave"
  trigger TEXT NOT NULL,
  payload_shape TEXT,                       -- JSON Schema string
  notes TEXT
);

CREATE TABLE sdk_permissions (
  scope TEXT PRIMARY KEY,                   -- e.g. "ZOHO.CREATOR.API.read"
  description TEXT
);

CREATE TABLE zoho_widget_globals (
  name TEXT PRIMARY KEY,                    -- "ZOHO", "Creator", etc.
  kind TEXT NOT NULL                        -- "namespace" | "object"
);
```

### 7.1 Seed data — `seed_data/widget_sdk_apis.json`

Hand-curated, 30 entries covering:

- **CRUD (6):** `ZOHO.CREATOR.API.getRecords`, `getRecordById`, `addRecords`, `updateRecord`, `deleteRecord`, `bulkUpdateRecords`
- **File / upload (3):** `uploadFile`, `downloadFile`, `getFileContent`
- **Publish / embed lifecycle (6):** `ZOHO.CREATOR.init`, `ZOHO.embeddedApp.on`, `ZOHO.embeddedApp.init`, `getInitParams`, `getUserInfo`, `logout`
- **Navigation / UI (4):** `navigateTo`, `showAlert`, `showPrompt`, `closeWidget`
- **Integration / API invoke (4):** `invokeConnection`, `invokeApi`, `invokeCustomApi`, `callFunction`
- **Events (4):** `PageLoad`, `RecordSave`, `RecordDelete`, `FieldChange`
- **Permissions (3):** `ZOHO.CREATOR.API.read`, `.write`, `.publish`

### 7.2 Why hand-curated (not scraped)

Scaffolding-first. The knowledge-base scraper (`forgeds-kb-*`) exists but introduces runtime coupling and Zoho-doc-shape fragility. Phase 1 ships static JSON; Phase 2 can hook the scraper if seed maintenance burden grows.

## 8. Hybrid rules (thin slice)

Added to `src/forgeds/hybrid/lint_hybrid.py`:

| Rule | Check | Severity |
|---|---|---|
| **WG001** | Widget `root` directory does not exist on disk | ERROR |
| **WG002** | `plugin-manifest.json` under `root` is missing or fails schema validation | ERROR |
| **WG003** | `widgets[name].consumes_apis[i]` not present in `config.custom_apis` | ERROR |

**Explicitly deferred to Phase 2** (listed so reviewers know the contract is incomplete by design):

- "Widget JS actually invokes each declared `consumes_apis` entry" — requires AST data from ESLint pass-through
- "Widget JS does not invoke any API outside declared `consumes_apis`" — same
- "Response shape in widget matches Custom API response map"
- "Widget references forms that exist in .ds"
- "Widget uses only SDK methods present in `sdk_methods`"

Accreting these later does not require schema changes — just new rule functions querying existing tables.

## 9. ESLint orchestrator (`lint_widgets.py`)

### 9.1 Flow

1. Load `config["widgets"]` via `load_config()`.
2. Optional: scan `src/widgets/*/` for orphan directories not registered in config → emit WG-meta warning (not error; lets new widgets be introduced without breaking lint).
3. For each registered widget:
   - Resolve JS files under `root/` (glob `**/*.js`).
   - Shell out: `npx eslint -c <forgeds>/widgets/configs/.eslintrc.zoho.json --format json <files>`.
   - Parse JSON output; translate findings to `Diagnostic(rule="JS:<eslint-rule-id>", severity=<mapped>, ...)`.
4. If `npx` / `eslint` absent (exec fails, or `npx eslint --version` returns non-zero):
   - Print install hint to stderr
   - Exit code 3
   - No partial diagnostics emitted

### 9.2 `.eslintrc.zoho.json` v1

Minimum-viable:

```json
{
  "extends": ["eslint:recommended"],
  "env": { "browser": true, "es2021": true },
  "globals": {
    "ZOHO": "readonly",
    "Creator": "readonly",
    "$": "readonly"
  },
  "parserOptions": { "ecmaVersion": 2021, "sourceType": "module" }
}
```

No opinionated style rules (semi, quotes, indent) — those are consumer-project decisions. Phase 2 can add Zoho-specific custom rules via a local ESLint plugin if needed.

### 9.3 ESLint → Diagnostic severity mapping

| ESLint severity | Diagnostic severity |
|---|---|
| 2 (error) | `Severity.ERROR` |
| 1 (warn) | `Severity.WARNING` |
| 0 / off | (not emitted) |

## 10. Manifest validator (`validate_manifest.py`)

### 10.1 Schema — `configs/plugin-manifest.schema.json`

JSON Schema draft-07. Fields derived from Zoho's widget plugin spec, empirically seeded. Initial fields:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["name", "version", "config"],
  "properties": {
    "name":    { "type": "string", "minLength": 1 },
    "version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "config":  {
      "type": "object",
      "required": ["widgets"],
      "properties": {
        "widgets": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["location", "url"],
            "properties": {
              "location": { "type": "string" },
              "url":      { "type": "string" }
            }
          }
        }
      }
    },
    "permissions": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
```

Schema is authoritative for Phase 1; iterate as real widgets expose gaps.

### 10.2 Stdlib-only validator

~200 LOC implementing the JSON Schema subset ForgeDS actually uses: `type`, `required`, `enum`, `pattern`, `minLength`, `properties`, `items`, `additionalProperties: false`. Keeps zero-dep rule intact (`pyodbc`-equivalent optional deps are the only exception pattern in the codebase).

If the subset proves inadequate, Phase 2 promotes `jsonschema` to a soft-optional dep with graceful ImportError.

## 11. Node dependency posture

ForgeDS pip install remains **zero-dep**. Node/ESLint is **runtime-optional**:

- Presence: detected via `npx eslint --version` on first widget-lint invocation
- Absence: exit code 3 + install hint to stderr, no crash
- Documented in:
  - `forgeds-lint-widgets --help`
  - `CLAUDE.md` ("Widget linting requires Node ≥ 18 and ESLint 8+. Install globally with `npm i -g eslint`, or add to your consumer project's devDependencies.")

This matches the existing `pyodbc` pattern: optional backend, graceful failure, clear install path.

## 12. Rule code registry (formalized in `CLAUDE.md`)

| Prefix | Owner | Meaning |
|---|---|---|
| `DG###` | `core.lint_deluge` | Deluge lint rules |
| `AV###` / `AC###` | `access.lint_access` | Access / VBA rules (existing mixed prefix; cleanup deferred) |
| `HY###` | `hybrid.lint_hybrid` | Deluge↔Access cross-checks |
| `WG###` | `hybrid.lint_hybrid` | **Widget↔Deluge cross-checks (NEW)** |
| `JS:<rule>` | `widgets.lint_widgets` (pass-through) | **ESLint rule ID, foreign provenance (NEW convention)** |

Colon in `JS:<rule>` intentionally distinguishes foreign-tool findings from ForgeDS-owned rules; human-readable text format renders as `[JS:no-unused-vars]`.

## 13. Parser investigation (G7)

**Effort:** 30 minutes, no code changes expected.

**Steps:**

1. Grep a real `.ds` export (use an existing consumer repo) for tokens like `widget`, `plugin`, `script-source`.
2. Read relevant Zoho Creator docs / developer-portal pages on widget packaging.
3. Append findings to `CLAUDE.md` under `.ds file format gotchas` as a new numbered item.

**Expected outcome:** Widgets are *not* represented in `.ds` exports; they are packaged as zip blobs uploaded through the Creator portal. `parse_ds_export.py` needs no changes. Documentation makes this explicit so future contributors don't search for widget handling in the parser.

**Contingency:** If `.ds` does carry widget references, G7 is promoted from investigation to code-work and a Phase 2 ticket is filed; Phase 1 ships without parser changes regardless.

## 14. Testing

### 14.1 Fixtures

```
tests/fixtures/widgets/
├── good_widget/
│   ├── plugin-manifest.json        # valid
│   └── index.js                    # clean JS
├── bad_widget_missing_manifest/    # WG002
│   └── index.js
├── bad_widget_invalid_manifest/    # WG002
│   ├── plugin-manifest.json        # violates schema
│   └── index.js
└── bad_widget_undeclared_api/      # WG003
    ├── plugin-manifest.json
    └── index.js                    # consumes_apis references non-existent API
```

And a matching fixture `forgeds.yaml` declaring each widget + a minimal `custom_apis` list.

### 14.2 Unit tests

- `test_config_loader_widgets` — `custom_apis` and `widgets` parsed correctly; missing blocks default to `[]` / `{}`
- `test_build_widget_sdk_db` — DB builds from seed JSON; row counts match
- `test_validate_manifest` — good fixture passes; each bad fixture fails with expected diagnostic
- `test_lint_widgets_eslint_missing` — orchestrator exits 3 when ESLint absent (simulated via `PATH` manipulation)
- `test_lint_hybrid_wg_rules` — WG001/WG002/WG003 fire on appropriate fixtures

Existing test infrastructure applies; no new framework.

## 15. Multi-agent execution plan

For `writing-plans` to operationalize into per-agent checklists:

| Batch | Tasks | Parallelism | Unit |
|---|---|---|---|
| **A** (parallel, no deps) | §4 config loader (G4) | | Agent-A1 |
|  | §7 SDK DB schema + 30 seed APIs (G2) | | Agent-A2 |
|  | §10 manifest validator + schema file (G6) | | Agent-A3 |
|  | §13 parser investigation (G7) | | Agent-A4 |
| **B** (sequential on A) | §9 ESLint orchestrator + `.eslintrc.zoho.json` (G1) | 1 | Agent-B |
| **C** (sequential on B) | §8 hybrid WG001–WG003 (G3) | 1 | Agent-C |
| **D** (sequential on C) | §12 CLAUDE.md rule-code registry + Node posture + G7 findings | 1 | Agent-D (merge cleanup) |

Each batch-A unit has isolated tests and touches disjoint files; parallelism is safe.

## 16. Explicit non-goals

Stating these out loud to prevent scope creep during implementation:

- No Node installation, bundling, or pinning of ESLint versions inside ForgeDS
- No ESLint custom rules authored by ForgeDS (Phase 2+)
- No widget build/zip/upload pipeline
- No changes to existing DG/AC/HY linters' CLI surface or output format
- No changes to `parse_ds_export.py` code (investigation only)
- No TypeScript support in Phase 1 (`.ts`/`.tsx` are out; only `.js`/`.html`/`.json`)

## 17. Open questions (resolved and logged for future reference)

| Q | Resolution |
|---|---|
| JSON envelope blast radius | Widgets-only pilot, v1 explicit. Promote later if stable. |
| `widgets:` YAML shape | Option Y — dict keyed by name, manifest-authoritative. |
| SDK DB schema | Tailored (namespaces + methods + events + permissions), not mirror of deluge_lang.db. |
| Seed source | Hand-curated JSON, ~30 APIs. Scraper integration deferred. |
| Node dependency | Optional runtime, exit 3 + install hint on absence. Zero pip deps preserved. |
| `custom_apis:` config field | Added as minimal `list[str]` in Phase 1. Autodiscovery deferred. |
| Manifest-schema validator | Stdlib-only subset (~200 LOC). `jsonschema` as soft-optional in Phase 2 if needed. |
| Rule-code prefix | `WG###` for ForgeDS-owned widget hybrid rules; `JS:<rule>` for ESLint pass-through. |
