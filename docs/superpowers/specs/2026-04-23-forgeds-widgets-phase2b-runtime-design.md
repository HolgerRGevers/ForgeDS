# ForgeDS Widgets Phase 2B — Runtime Verification (DRAFT for user review)

**Date:** 2026-04-23
**Status:** Draft — produced by parallel-agent brainstorming pass, awaits user approval before a plan is written.
**Depends on:** Phase 1, Phase 2A (diagnostic envelope). See `docs/superpowers/specs/`.
**Parallel siblings:** Phase 2A (contract), 2C (build/deploy), 2D (IDE/AI).

---

## 1. Problem statement

Phase 1 ships widget **static** lint: ESLint orchestration, `plugin-manifest.json` schema validation, and three hybrid rules (WG001–WG003) that check declarations on disk. Static analysis stops at the syntax and cross-declaration layer. It does not answer:

- Did the widget actually call every API listed in `consumes_apis`? (declared but unused)
- Did the widget call any API **not** listed in `consumes_apis`? (used but undeclared)
- When invoked, do calls touch only SDK methods present in `zoho_widget_sdk.db`?
- Does the widget's runtime entry point (`init`, `mounted`, etc.) throw before it touches Zoho at all?
- Does the widget request permissions it never exercises, or exercise permissions it never requested?

These are listed as "explicitly deferred to Phase 2" in Phase 1 §8. Phase 2B delivers them via a **runtime harness**: load widget JS under Node with a mocked `ZOHO` global, record every SDK call, and diff the call log against declarations. Phase 2A normalises the diagnostic envelope so runtime diagnostics slot into the same consumer contract; Phase 2B is the first new tool to adopt it.

Phase 2B is additive. No Phase 1 surface changes. Phase 2B introduces a new CLI (`forgeds-run-widget`), a new rule prefix (`WGR###`), and a new in-repo ESLint plugin, all behind the same Node-optional / exit-3 posture Phase 1 established.

## 2. Scope

**In scope**

| Gap | Deliverable |
|---|---|
| G5.1 | `forgeds-run-widget` CLI — Python orchestrator spawning Node harness subprocess |
| G5.2 | `harness.js` — stdlib-only Node harness that stubs `global.ZOHO`, `require()`s the widget, records a call log, serialises JSON to stdout |
| G5.3 | `gen_sdk_mock.py` — generates `sdk_mock.js` from `zoho_widget_sdk.db` (single source of truth) |
| G5.4 | New runtime rules **WGR001–WGR004** emitted by the Python orchestrator after parsing the call log |
| G5.5 | Local ESLint plugin `eslint-plugin-zoho-widget` with static complements `no-undeclared-apis` and `no-unused-apis`; consumes a JSON sidecar emitted by Phase 1's orchestrator |
| G5.6 | Entry-point discovery convention (`root/index.js`) + optional `entry_point` override field under `widgets[name]` |
| G5.7 | Diagnostic v1 envelope (per Phase 2A) with `tool: "forgeds-run-widget"` |

**Out of scope (Phase 2C+ or separate deliverable)**

| Gap | Reason for deferral |
|---|---|
| Response-shape validation against Custom API schemas | Needs Phase 2A extended config (Custom API response maps); harness records shapes but does not validate them in 2B |
| `forgeds-lint-widgets --with-runtime` combined invocation | Keeps static vs runtime boundaries distinct for this phase; reserved flag, not implemented |
| Publishing `@forgeds/eslint-plugin-zoho-widget` to npm | Local plugin only in 2B; promotion is a Phase 2C distribution decision |
| Full Zoho API simulator (realistic data generation, pagination, error modes) | Mock records calls and returns minimal valid shapes; not a sandbox emulator |
| Browser/DOM runtime (JSDOM, headless Chromium) | Node-only; widgets that rely on `window`/`document` beyond minimal stubs will skip runtime with a WGR-meta warning |
| TypeScript widgets | Same as Phase 1 — JS only |

## 3. Architecture

### 3.1 New package layout

```
src/forgeds/widgets/
├── run_widget.py                    # G5.1 — Python orchestrator
├── gen_sdk_mock.py                  # G5.3 — generator (DB → sdk_mock.js)
├── runtime/                         # Node-side artefacts
│   ├── harness.js                   # G5.2 — stdlib-only harness
│   ├── sdk_mock.js                  # G5.3 — GENERATED; do not edit by hand
│   └── package.json                 # "type": "commonjs"; no dependencies
└── eslint-plugin-zoho-widget/       # G5.5 — local ESLint plugin
    ├── index.js                     # plugin entry; registers rules
    ├── package.json                 # name, version, main; no deps
    └── rules/
        ├── no-undeclared-apis.js
        └── no-unused-apis.js
```

### 3.2 Extensions to existing files

- `src/forgeds/widgets/lint_widgets.py` — emit `eslint_plugin_manifest.json` sidecar alongside existing ESLint invocation (additive; no CLI change)
- `src/forgeds/widgets/configs/.eslintrc.zoho.json` — add `"plugins": ["zoho-widget"]` and two rule entries; keep Phase 1 `eslint:recommended` extend
- `src/forgeds/_shared/config.py` — parse optional `widgets[name].entry_point` field; default `None` → resolve to `<root>/index.js`
- `pyproject.toml` — one new entry point: `forgeds-run-widget`
- `templates/forgeds.yaml.example` — document optional `entry_point`
- `CLAUDE.md` — add `WGR###` to rule-code registry; note `eslint-plugin-zoho-widget` local-path plugin; reiterate Node posture

### 3.3 Python ↔ Node IPC model

Python → Node is **stdin-free, argv + stdout-JSON**. Python spawns Node via `subprocess.run`:

```
node <forgeds>/widgets/runtime/harness.js \
  --widget-root <abs_path_to_widget_root> \
  --entry-point <abs_path_to_entry_js> \
  --widget-name <logical_name> \
  --timeout-ms 10000
```

Harness writes exactly one JSON document to **stdout** (the call log, schema in §4.4). Any diagnostics the harness itself needs to raise (uncaught exception, timeout, entry missing) go to **stderr** as single-line `FORGEDS-RUNTIME-ERROR: <json>` records. Exit codes from harness are cooperative (§7.2) but Python treats stdout JSON presence as the source of truth.

No long-lived Node daemon. Each widget runs in its own subprocess (§11.C risk mitigation).

## 4. Runtime harness contract

### 4.1 Responsibilities

1. Parse argv (`--widget-root`, `--entry-point`, `--widget-name`, `--timeout-ms`).
2. Verify entry-point file exists; if not, emit `FORGEDS-RUNTIME-ERROR` to stderr and exit 4 (harness-internal error).
3. Load `./sdk_mock.js` and assign `global.ZOHO = require('./sdk_mock.js').ZOHO`.
4. Assign a minimal `global.window`, `global.document` stub (enough that widgets referencing `document.addEventListener` do not throw immediately — no DOM semantics, just no-op sinks).
5. Start a timeout timer (`setTimeout` → force exit with `timeout` reason).
6. `require(entryPoint)` inside a try/catch.
7. If the entry module exports an `init` function, call it. If it returns a Promise, await it (with the same timeout budget).
8. Once `init` resolves (or the module has finished synchronous side effects with no `init` export), flush `global.ZOHO._callLog` to a JSON document and write to stdout.
9. Exit 0.

### 4.2 Lifecycle — success path

```
parse argv
  → load sdk_mock.js
  → set globals
  → arm timeout
  → require(widget)
  → await widget.init?.()
  → JSON.stringify({widget, status: "ok", callLog, permissionsObserved, durationMs})
  → process.stdout.write(json + "\n")
  → clear timeout
  → process.exit(0)
```

### 4.3 Lifecycle — failure paths

| Condition | Harness action | Exit code |
|---|---|---|
| Entry file missing | stderr `FORGEDS-RUNTIME-ERROR` with `reason: "entry_not_found"` | 4 |
| `require(entry)` throws synchronously | stderr error + still emit partial `{status: "throw", error: {...}, callLog: [...]}` to stdout | 5 |
| `init()` throws / rejects | stdout `{status: "throw", error, callLog}` | 5 |
| Timeout tripped | stdout `{status: "timeout", callLog}` | 6 |
| Harness-internal bug (mock load fails, etc.) | stderr `FORGEDS-RUNTIME-ERROR` | 7 |

Non-zero harness exits are normal; Python does not treat them as fatal. Exit codes are purely diagnostic — Python reads stdout.

### 4.4 Output format — call log JSON (v1)

```json
{
  "widget": "expense_dashboard",
  "status": "ok",
  "durationMs": 187,
  "permissionsObserved": ["ZOHO.CREATOR.API.read"],
  "callLog": [
    {
      "method": "ZOHO.CREATOR.API.getRecords",
      "args": ["Pending_Claims_Report", "", 1, 50],
      "responseKind": "canned",
      "timestamp": 12
    },
    {
      "method": "ZOHO.CREATOR.API.invokeCustomApi",
      "args": ["approve_claim", { "claim_id": 123 }],
      "responseKind": "canned",
      "timestamp": 54
    }
  ]
}
```

- `timestamp` is milliseconds since harness start (not wall clock), so runs are deterministic for snapshot tests.
- `responseKind` ∈ `{"canned", "undefined-method", "error-stub"}` — lets Python distinguish "widget called a known API" from "widget called something the mock did not recognise" (the latter triggers WGR rules without needing to re-parse args).
- `args` are deep-copied via `JSON.parse(JSON.stringify(args))` at call time, so later mutation by the widget does not rewrite the log. Non-serialisable args (functions, symbols) are replaced with `"__nonserialisable__"`.

### 4.5 How Python parses the call log

`run_widget.py` reads stdout, `json.loads` it, then:

1. Build `observed = { call.method for call in callLog }`.
2. Build `declared = set(config["widgets"][name]["consumes_apis"])`.
3. Diff `declared − observed` → WGR001 warnings (declared-but-unused).
4. Diff `observed − declared` for methods whose last segment is a Custom API → WGR001 errors (undeclared invocation).
5. For each `responseKind == "undeclared-method"` entry → emit `WGR-meta` warning ("widget called SDK method not in `zoho_widget_sdk.db`; seed may be stale").
6. `status == "throw"` → WGR002 error, message includes `error.message` (truncated).
7. `status == "timeout"` → WGR-meta error with the timeout value.
8. Compare `permissionsObserved` to the widget's `plugin-manifest.json` `permissions` array → WGR004 if observed ⊄ declared.

All diagnostics emit through the v1 envelope (§7.4).

## 5. Mocked SDK design

### 5.1 Generation pipeline

```
zoho_widget_sdk.db  (Phase 1 artefact)
        ↓
gen_sdk_mock.py      (Phase 2B, Python, stdlib-only)
        ↓
src/forgeds/widgets/runtime/sdk_mock.js   (generated, checked in)
```

`sdk_mock.js` is **generated and committed**. Regenerate via `forgeds-build-widget-db && python -m forgeds.widgets.gen_sdk_mock`. A CI check (Phase 2C) diffs the committed copy against a fresh regeneration to catch drift.

Rationale:

- DB is the Phase 1 source of truth for the SDK surface. Hand-written mocks drift; generated mocks track additions automatically.
- Keeping the generated file in-tree means running `forgeds-run-widget` does not require a DB build step on every invocation.

### 5.2 Generator behaviour (`gen_sdk_mock.py`)

1. Open `zoho_widget_sdk.db` via `get_db_dir()`.
2. `SELECT namespace, name, signature, required_permissions FROM sdk_methods`.
3. Group by namespace (e.g. `ZOHO.CREATOR.API`, `ZOHO.embeddedApp`).
4. For each method, emit a JS function that:
   - Pushes `{method, args, responseKind, timestamp}` onto `global.ZOHO._callLog`.
   - Tracks `required_permissions` into `global.ZOHO._permissionsObserved`.
   - Returns a canned response (§5.4).
5. Emit lifecycle-event registrar stubs for `ZOHO.embeddedApp.on(event, cb)` — record the registration, do not fire callbacks (Phase 2B scope: declarative observation, not event simulation).
6. Write to `runtime/sdk_mock.js` with a generator banner line `// GENERATED by gen_sdk_mock.py — do not edit`.

### 5.3 Coverage test

`tests/test_sdk_mock_covers_all_seeded_apis` — load DB method list, load `sdk_mock.js` via subprocess `node -e "console.log(Object.keys(...))"`, assert every `namespace.name` is reachable. Prevents generator drift.

### 5.4 Canned responses

Deterministic, minimal, shape-only. Not realistic data; just enough that widgets do not null-dereference.

| Method family | Canned response |
|---|---|
| `getRecords`, `getRecordById` | `{ code: 3000, data: [] }` (empty success) |
| `addRecords`, `updateRecord`, `deleteRecord` | `{ code: 3000, data: { ID: "0" } }` |
| `uploadFile`, `downloadFile` | `{ code: 3000, data: { file_id: "0" } }` |
| `invokeCustomApi`, `invokeConnection`, `invokeApi`, `callFunction` | `{ code: 0, data: null }` |
| `getInitParams`, `getUserInfo` | `{ appLinkName: "mock", loginName: "mock" }` |
| `showAlert`, `showPrompt`, `navigateTo`, `closeWidget` | `undefined` (fire-and-forget) |
| Unknown method hit via proxy trap | log with `responseKind: "undeclared-method"`, return `undefined` |

An unknown-method proxy (`new Proxy(realNamespace, { get })`) covers methods the widget reaches that exist in the DB but were added after the committed mock (drift) **and** methods that do not exist at all. The drift branch is caught by the coverage test; the real-unknown branch is what feeds WGR-meta warnings.

### 5.5 Boundary

The mock **records and returns**. It does not:

- Simulate error responses (Phase 2C may add a `--fault-inject` mode)
- Validate request payloads against Custom API schemas (Phase 2A extension territory)
- Fire lifecycle events or emit change notifications
- Persist state between calls (fresh object per subprocess — each widget run is isolated)

## 6. ESLint custom plugin

### 6.1 Rationale

Two of the deferred Phase 1 rules — "widget must invoke all declared APIs" and "widget must not invoke undeclared APIs" — have a static complement that ESLint can check cheaply without spawning Node twice. The runtime harness catches dynamic/conditional calls the static pass misses; the static plugin catches code paths the runtime never reaches. Both are valuable; they are not redundant.

The plugin is **local** (loaded by relative path, not npm-published) in Phase 2B.

### 6.2 Layout

```
src/forgeds/widgets/eslint-plugin-zoho-widget/
├── package.json            # { "name": "eslint-plugin-zoho-widget", "main": "index.js" }
├── index.js                # exports { rules: { 'no-undeclared-apis': ..., 'no-unused-apis': ... } }
└── rules/
    ├── no-undeclared-apis.js
    └── no-unused-apis.js
```

### 6.3 Sidecar JSON emitted by Phase 1 orchestrator

`lint_widgets.py` writes a **sidecar** to a deterministic path (e.g. `<forgeds-cache>/eslint_plugin_manifest.json`) **before** invoking ESLint. Rules read it via `require(process.env.FORGEDS_ESLINT_SIDECAR)`; Python sets the env var in the subprocess call.

Sidecar shape:

```json
{
  "version": "1",
  "widgets": {
    "expense_dashboard": {
      "root": "/abs/path/to/src/widgets/expense_dashboard",
      "entryPoint": "/abs/path/to/src/widgets/expense_dashboard/index.js",
      "consumesApis": ["get_pending_claims", "approve_claim"],
      "knownSdkMethods": [
        "ZOHO.CREATOR.API.getRecords",
        "ZOHO.CREATOR.API.invokeCustomApi",
        "ZOHO.embeddedApp.on"
      ]
    }
  }
}
```

`knownSdkMethods` is populated from `zoho_widget_sdk.db` at sidecar-write time, so rules do not need DB access.

### 6.4 Rule: `zoho-widget/no-undeclared-apis`

**Trigger:** `CallExpression` whose callee MemberExpression chain resolves to `ZOHO.CREATOR.API.<x>` (or any namespace in `knownSdkMethods`).

**Behaviour:**

1. Resolve the widget context from the file being linted by matching its path against sidecar `widgets[*].root` (longest-prefix wins).
2. Extract the last-segment method: e.g. `ZOHO.CREATOR.API.invokeCustomApi` called with `('approve_claim', ...)` — the API name is the first string-literal argument.
3. If the resolved API name is not in `consumesApis`, report an ESLint error.

**Reported via ESLint → v1 envelope** as `rule: "JS:zoho-widget/no-undeclared-apis"` (Phase 1 prefix convention).

### 6.5 Rule: `zoho-widget/no-unused-apis`

**Trigger:** `Program:exit` — after walking the whole file, compute the set of invoked Custom APIs. At the end of the lint pass per widget (orchestrator-level, not per-file), diff against `consumesApis`. Items in `consumesApis` never invoked become ESLint warnings.

Because `Program:exit` fires per file, the per-widget aggregate check is finalised by a small **post-pass** in the orchestrator: after ESLint returns findings, Python also reads a `consumed_apis_seen.json` file rules may append to (env-var path), or re-parses ESLint's message metadata to aggregate. Phase 2B uses the file-append approach for simplicity.

### 6.6 Envelope mapping

Phase 1 already maps ESLint severity to `Diagnostic.severity` and emits `rule` as `JS:<rule-id>`. No change in 2B beyond the new rule IDs.

## 7. CLI contracts

### 7.1 New entry point (`pyproject.toml`)

```
forgeds-run-widget = "forgeds.widgets.run_widget:main"
```

### 7.2 `forgeds-run-widget`

```
forgeds-run-widget [--widget NAME] [--format {text,json}] [--config PATH]
                   [--timeout-ms INT] [-q] [--errors-only]
```

| Flag | Default | Meaning |
|---|---|---|
| `--widget NAME` | all widgets in config | Run only this widget |
| `--format` | `text` | `text` for humans, `json` for Phase 2A envelope |
| `--config PATH` | auto-discover `forgeds.yaml` | Override config discovery |
| `--timeout-ms` | `10000` | Per-widget timeout passed to harness |
| `-q` | off | Suppress info-level lines in text format |
| `--errors-only` | off | Exit-code logic ignores warnings |

| Exit | Meaning |
|---|---|
| 0 | Clean (no WGR* diagnostics) |
| 1 | Warnings only |
| 2 | Errors present |
| **3** | **Node/toolchain missing** (matches Phase 1 posture) |

Exit 3 prints a one-line install hint to stderr and emits no diagnostics, mirroring Phase 1's ESLint-missing path.

### 7.3 Text output

```
=== forgeds-run-widget: expense_dashboard ===
  entry:   src/widgets/expense_dashboard/index.js
  invoked: ZOHO.CREATOR.API.getRecords (x2)
           ZOHO.CREATOR.API.invokeCustomApi (x1; api=approve_claim)
  declared-but-unused: get_pending_claims
src/widgets/expense_dashboard/index.js:1: [WGR001] WARNING: widget 'expense_dashboard' declares 'get_pending_claims' in consumes_apis but never invoked it

Summary: 0 errors, 1 warning across 1 widget
```

### 7.4 JSON envelope (Phase 2A v1)

```json
{
  "tool": "forgeds-run-widget",
  "version": "1",
  "diagnostics": [
    {
      "file": "src/widgets/expense_dashboard/index.js",
      "line": 1,
      "rule": "WGR001",
      "severity": "warning",
      "message": "widget 'expense_dashboard' declares 'get_pending_claims' in consumes_apis but never invoked it"
    }
  ]
}
```

### 7.5 Why runtime stays separate from `forgeds-lint-widgets` in this phase

The two tools share config loading and diagnostic shape but differ in toolchain posture and failure modes:

- Static lint runs ESLint (subprocess, fast, idempotent); runtime boots a Node process per widget (slower, side-effectful if a widget has file-system imports).
- Static lint is safe to run on CI bots with no Node — exit 3 is a skippable signal. Runtime *is* the Node-requiring step; conflating them loses the Phase 1 "lint always works, runtime is optional" framing.
- Static findings and runtime findings have distinct cadence and different reviewer audiences (static: PR blocker; runtime: integration-test signal).

A `--with-runtime` flag on `forgeds-lint-widgets` is reserved for Phase 2C, when distribution and cross-tool wiring are the actual deliverable. Phase 2B keeps the surfaces orthogonal so each can evolve independently.

## 8. New rule codes — WGR###

New prefix, registered in CLAUDE.md: **WGR = Widget Runtime**. Complementary to static WG### and foreign JS:\* rules.

| Rule | Owner | Trigger | Severity | Example message |
|---|---|---|---|---|
| **WGR001** | `run_widget.py` | Widget invokes SDK method or Custom API not in `consumes_apis`, OR declares API in `consumes_apis` but never invokes it during runtime | ERROR (undeclared call) / WARNING (unused declaration) | `widget 'expense_dashboard' invoked 'delete_claim' but it is not in consumes_apis` |
| **WGR002** | `run_widget.py` | Widget entry point or `init()` throws / rejects | ERROR | `widget 'expense_dashboard' threw during init: TypeError: Cannot read properties of undefined (reading 'data')` |
| **WGR003** | `run_widget.py` | Response shape mismatch vs declared Custom API schema — **stubbed for Phase 2B** (emits only if Phase 2A-extended response maps are present); no-op otherwise | ERROR | `widget 'expense_dashboard' read 'response.rows' but 'approve_claim' schema declares 'response.data'` |
| **WGR004** | `run_widget.py` | Widget invoked a method whose `required_permissions` are not listed in `plugin-manifest.json` `permissions` | ERROR | `widget 'expense_dashboard' invoked method requiring 'ZOHO.CREATOR.API.write' but manifest declares only ['ZOHO.CREATOR.API.read']` |

Plus one **meta** bucket (not a numbered rule, reported with `rule: "WGR-meta"`):

- Entry point missing
- Harness timeout
- Unknown SDK method invoked (mock drift signal)
- Widget runtime skipped (e.g. required DOM APIs not stubbed)

WGR003 is declared now and shipped as a stub (always emits zero diagnostics until Phase 2A's response maps land) so the rule number is reserved and downstream agents can bind to it.

## 9. Entry-point discovery

### 9.1 Convention

Default: `<widget.root>/index.js`. No config needed for the common case.

### 9.2 Optional override

```yaml
widgets:
  expense_dashboard:
    root: src/widgets/expense_dashboard/
    consumes_apis:
      - get_pending_claims
      - approve_claim
    entry_point: src/main.js    # OPTIONAL — relative to `root`
```

`entry_point` is validated at config load: if present, it must resolve to an existing file under `root`. If absent, loader sets it to `<root>/index.js` (resolution deferred; orchestrator verifies existence).

### 9.3 Missing entry

If neither the override nor the default resolves, `forgeds-run-widget` emits a **WGR-meta** error for that widget and moves on to the next one. Other widgets still run; one bad entry does not abort the batch.

## 10. Node dependency posture

Phase 1's zero-pip-dep / Node-optional / exit-3 pattern is **unchanged**. Restated for 2B:

- Presence check: `node --version` before harness invocation. Cached within a single `forgeds-run-widget` run.
- Absence: exit 3, one-line stderr hint (`install Node ≥ 18 from https://nodejs.org or via nvm; forgeds-run-widget requires it`).
- No `npm install` step. `runtime/package.json` has **no dependencies** block. `sdk_mock.js` is generated Python-side.
- The local ESLint plugin adds no npm deps either — ESLint is already consumed via `npx` in Phase 1.

**Escalation flag:** Phase 2C may introduce CI-level enforcement (treat exit 3 as a CI failure in consumer projects that opt in). That is a posture decision for Phase 2C; Phase 2B ships exit-3-as-skippable.

## 11. Testing

### 11.1 Fixtures

```
tests/fixtures/widgets/runtime/
├── good_runtime_widget/
│   ├── plugin-manifest.json         # valid; permissions match invocations
│   └── index.js                     # invokes exactly consumes_apis
├── bad_widget_undeclared_call/      # WGR001 (error)
│   ├── plugin-manifest.json
│   └── index.js                     # calls approve_claim without declaring it
├── bad_widget_unused_declaration/   # WGR001 (warning)
│   ├── plugin-manifest.json
│   └── index.js                     # declares get_pending_claims, never calls it
├── bad_widget_throws_in_init/       # WGR002
│   ├── plugin-manifest.json
│   └── index.js                     # throw in init()
├── bad_widget_permission_mismatch/  # WGR004
│   ├── plugin-manifest.json         # read-only
│   └── index.js                     # calls addRecords (requires write)
├── bad_widget_missing_entry/        # WGR-meta
│   └── plugin-manifest.json         # no index.js, no entry_point override
└── bad_widget_timeout/              # WGR-meta
    ├── plugin-manifest.json
    └── index.js                     # `while(true){}` in init
```

Matching `tests/fixtures/widgets/runtime/forgeds.yaml` declares each widget + a `custom_apis` list sized to exercise each case.

### 11.2 Unit tests

- `test_run_widget_good_runtime` — clean exit 0, empty diagnostics, callLog contains both declared APIs
- `test_run_widget_undeclared_call` — WGR001 error emitted with correct API name
- `test_run_widget_unused_declaration` — WGR001 warning emitted
- `test_run_widget_throws_in_init` — WGR002 error, message includes original exception
- `test_run_widget_permission_mismatch` — WGR004 error
- `test_run_widget_missing_entry` — WGR-meta error; other widgets in batch still run
- `test_run_widget_timeout` — WGR-meta error after `--timeout-ms 500`
- `test_run_widget_node_missing` — exit 3 (simulated via `PATH` manipulation)
- `test_sdk_mock_covers_all_seeded_apis` — coverage test (§5.3)
- `test_sdk_mock_generator_deterministic` — regenerate twice, byte-identical output
- `test_eslint_plugin_no_undeclared_apis` — ESLint fires on fixture with undeclared call
- `test_eslint_plugin_no_unused_apis` — ESLint fires on fixture with unused declaration
- `test_eslint_plugin_sidecar_shape` — sidecar JSON validates against its own schema
- `test_entry_point_override` — custom `entry_point` resolves correctly; missing override file raises config error

### 11.3 Snapshot fixtures for call logs

Because `timestamp` is deterministic (ms since harness start, and mock responses are synchronous) and `JSON.stringify` is stable for the shapes we produce, call-log outputs for the good fixture can be snapshot-tested byte-for-byte. Failing snapshots flag harness drift early.

## 12. Risks

**A. Node-optional vs runtime-essential tension.** Runtime verification without Node is vacuous. Mitigation: exit 3 + install hint is the exact Phase 1 pattern; treat it as "skipped, not failed". Phase 2C can escalate if adoption warrants.

**B. Mocked SDK drift.** `sdk_mock.js` generated from DB + coverage test + CI diff against fresh regeneration. Any new seed API triggers a mock regeneration; the unknown-method proxy catches the transitional window.

**C. Runtime flakiness.** Timebombs (`setInterval` without clear), network attempts (widget tries to `fetch`), non-determinism (Math.random-dependent branches). Mitigation: hard timeout wraps every widget; harness stubs `global.fetch`, `global.XMLHttpRequest`, `global.WebSocket` to log-and-throw; each widget runs in an isolated subprocess so poisoned global state does not leak.

**D. ESLint plugin authoring and distribution.** Local-path plugin in 2B; promotes to npm only if multiple consumer repos adopt. Avoids versioning and registry complexity prematurely.

**E. Widget entry-point discovery.** Convention + override covers known cases. For non-standard layouts (bundled `dist/main.js`), override handles it. Widgets that only run after a build step are out of scope for Phase 2B — document as Phase 2C territory.

**F. DOM-dependent widgets.** Widgets that read `document.querySelector` at module load will fail against the minimal stub. Mitigation: harness stub exposes a read-only `document` that returns null for queries and no-ops mutators. Widgets whose `init()` requires a real DOM skip runtime with a WGR-meta warning ("widget appears to require DOM; consider Phase 2C JSDOM backend"). A follow-up phase can add JSDOM as a soft-optional dep if demand appears.

**G. Widget code importing npm packages.** `require('lodash')` will fail if the consumer project has not installed it. Phase 2B does not run `npm install` on consumer repos. If resolution fails, WGR002 (threw during init) fires with a clear message; the orchestrator's text output includes a hint: "widget imports npm package 'lodash'; ensure it is installed in consumer project".

**H. Determinism / snapshot rot.** See §11.3; stable timestamps and sorted keys in JSON output make snapshots robust. A generator header comment includes the DB schema version so regenerations show up as self-describing diffs.

**I. Security.** Running arbitrary widget JS is code execution. Mitigation: subprocess isolation, no network stubs wired to real network, no filesystem write access beyond stdout. Documented in CLAUDE.md and `forgeds-run-widget --help`: "this tool executes widget code under Node; run only on trusted widget source in the consumer repo".

## 13. Non-goals

Stated explicitly to prevent scope creep:

- No JSDOM or headless-browser runtime
- No combined `forgeds-lint-widgets --with-runtime` CLI (reserved for Phase 2C)
- No npm publication of `eslint-plugin-zoho-widget`
- No Custom API response-shape validation (WGR003 stubbed until Phase 2A extension)
- No fault-injection / error-response simulation
- No lifecycle-event firing (only registration recording)
- No widget bundling, building, or zip packaging
- No TypeScript support
- No automatic seed regeneration from Zoho docs (Phase 1's scraper stays unhooked)
- No mutation of Phase 1 CLI surfaces (`forgeds-lint-widgets`, `forgeds-validate-widget-manifest`, `forgeds-build-widget-db`)

## 14. Open questions

| Q | Current lean | Needs user input? |
|---|---|---|
| Should harness write call log to a file instead of stdout (for large logs)? | Stdout in v1; revisit if widgets exceed ~1 MB logs | No (revisit in 2C if observed) |
| Should `gen_sdk_mock.py` run automatically as part of `forgeds-build-widget-db`, or stay a separate step? | Separate step in 2B so the generator is reviewable per run; compose in 2C | Yes, user preference |
| Should `WGR001` split into two rule numbers (undeclared-call vs unused-declaration)? | Single rule with two severities in 2B; split if downstream agents need per-rule routing | Yes, downstream-agent needs dictate |
| How should WGR003 behave when Phase 2A schemas are absent — no-op silently, or emit `WGR-meta`? | No-op silently in 2B; emitting meta warnings for every call would be noisy | Confirm |
| Should `--widget NAME` accept a glob (e.g. `expense_*`) in 2B? | Exact match only in 2B; globs in 2C | Low-priority |
| Is `entry_point` relative to `root` or to the project root? | Relative to `root` (symmetric with how `root` is used) | Confirm |
| Should the harness be CommonJS or ESM? | CommonJS in 2B (`require()` broader widget compat, zero toolchain); ESM on demand in 2C | Confirm |
| Subprocess-per-widget vs worker-thread-per-widget? | Subprocess (isolation beats throughput for ≤20 widgets typical); worker threads if scale demands | Low-priority; revisit if >50 widgets |
| Should `forgeds-run-widget` honour `.forgedsignore` or similar? | Out of scope for 2B; tool runs only on widgets registered in config | Confirm |
