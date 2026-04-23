# ForgeDS Widgets Phase 2B — Runtime Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use `- [ ]` for progress tracking.

**Goal:** Ship `forgeds-run-widget` — a Node-based runtime harness that executes each widget against a mocked Zoho SDK, records its call log, and diffs the observed behaviour against `consumes_apis` declarations + manifest permissions. Introduce a local ESLint plugin that provides the static complement of two of the runtime rules. All diagnostics emit through the Phase 2A v1 envelope.

**Reference spec:** `docs/superpowers/specs/2026-04-23-forgeds-widgets-phase2b-runtime-design.md`
**Depends on:** Phase 1 (widget lint toolchain) + Phase 2A (envelope + `--format json-v1` + `forgeds-build-widget-db`).

---

## Defaults applied to spec §14 open questions

The user invoked `/forgeplan` option (b) — execute without pausing. The spec's nine open questions are resolved as follows; downstream edits may revisit any of these.

| # | Open question | Default chosen | Rationale |
|---|---|---|---|
| 1 | Harness output destination (stdout vs file) | **stdout JSON** | Matches spec §4.4; widgets unlikely to exceed ~1 MB logs in realistic use. |
| 2 | Compose `gen_sdk_mock.py` into `forgeds-build-widget-db`? | **Separate, two commands** | Matches spec §5.1. Composition deferred to 2C when bundler lifecycle is formalised. |
| 3 | Split WGR001 into two rule numbers? | **Single rule, two severities** | Spec §8 allocation. Error for undeclared invocation, warning for unused declaration. |
| 4 | WGR003 behaviour without 2A response maps | **No-op silently** | Spec lean. Rule number reserved; zero diagnostics emit until response-shape maps land. |
| 5 | `--widget NAME` glob support | **Exact match only** | Spec lean. Globs deferred to 2C where scope widens. |
| 6 | `entry_point` base directory | **Relative to widget `root`** | Symmetric with how `root` is used elsewhere in the widgets block. |
| 7 | Harness module system | **CommonJS** | Broader compat with bare-JS widgets, `require()` works without toolchain. |
| 8 | Subprocess vs worker thread | **Subprocess-per-widget** | Isolation beats throughput at the typical ≤20-widget scale. |
| 9 | `.forgedsignore` support | **Out of scope** | Runs only on widgets declared in `forgeds.yaml`. Ignore-file semantics deferred. |

---

## File Structure

### Files to create

```
src/forgeds/widgets/
├── run_widget.py                       # Task 4 — Python orchestrator
├── gen_sdk_mock.py                     # Task 2 — generator (DB → sdk_mock.js)
├── runtime/
│   ├── harness.js                      # Task 3 — stdlib-only Node harness
│   ├── sdk_mock.js                     # Task 2 — GENERATED; committed
│   └── package.json                    # Task 3 — { "type": "commonjs" }, no deps
└── eslint-plugin-zoho-widget/
    ├── index.js                        # Task 5
    ├── package.json                    # Task 5
    └── rules/
        ├── no-undeclared-apis.js       # Task 5
        └── no-unused-apis.js           # Task 5

tests/
├── test_run_widget.py                  # Task 4 — WGR rule-firing tests
├── test_gen_sdk_mock.py                # Task 2 — generator/coverage/determinism
├── test_harness_contract.py            # Task 3 — harness argv/stdout/exit contract
├── test_eslint_plugin_zoho_widget.py   # Task 5
├── test_config_widgets_entry_point.py  # Task 1
└── fixtures/widgets/runtime/
    ├── forgeds.yaml                    # Task 6 — declares all 7 fixture widgets
    ├── good_runtime_widget/            # Task 6
    │   ├── plugin-manifest.json
    │   └── index.js
    ├── bad_widget_undeclared_call/     # Task 6 — WGR001 (error)
    ├── bad_widget_unused_declaration/  # Task 6 — WGR001 (warning)
    ├── bad_widget_throws_in_init/      # Task 6 — WGR002
    ├── bad_widget_permission_mismatch/ # Task 6 — WGR004
    ├── bad_widget_missing_entry/       # Task 6 — WGR-meta
    └── bad_widget_timeout/             # Task 6 — WGR-meta
```

### Files to modify

```
src/forgeds/_shared/config.py            # Task 1 — parse optional widgets[n].entry_point
src/forgeds/widgets/lint_widgets.py      # Task 5 — emit eslint_plugin_manifest.json sidecar
src/forgeds/widgets/configs/.eslintrc.zoho.json  # Task 5 — register local plugin
pyproject.toml                           # Task 7 — forgeds-run-widget entry point
templates/forgeds.yaml.example           # Task 7 — document entry_point
CLAUDE.md                                # Task 7 — WGR registry, Node posture reminder
```

---

## Commit conventions

Repo uses `feat(scope):`, `test(scope):`, `fix(scope):`, `docs(scope):`. Scope for this work: **`widgets`** (consistent with Phase 1 / 2A).

---

## Orchestration (controller-driven, fast-path)

Executed by the orchestrating session directly, same pattern as Phase 2A. Each task goes through: failing test → implementation → tests green → commit. Optional whole-branch review via `feature-dev:code-reviewer` at the end.

Rationale for fast-path: spec is detailed at contract-level; most surface is additive (no changes to Phase 1 / 2A CLIs); open questions are pre-resolved above.

---

## Task 1 — Config loader: optional `entry_point` field

**Spec refs:** §3.2, §9.

### 1.1 Failing tests

Create `tests/test_config_widgets_entry_point.py`:
- `test_widget_without_entry_point_defaults_to_none`
- `test_widget_with_entry_point_parses_string`
- `test_resolve_entry_point_defaults_to_root_index_js`
- `test_resolve_entry_point_uses_override_when_present`
- `test_resolve_entry_point_is_relative_to_root`

### 1.2 Implement

Extend `src/forgeds/_shared/config.py`:

Add helper:

```python
def resolve_widget_entry_point(widget_def: dict, project_root: Path) -> Path:
    """Resolve a widget's runtime entry point to an absolute Path.

    If `entry_point` is present under the widget definition, it is
    interpreted relative to the widget's `root`. Otherwise falls back
    to `<root>/index.js`.
    """
    root_rel = widget_def.get("root", "").rstrip("/\\")
    root_abs = (project_root / root_rel).resolve() if root_rel else project_root
    override = widget_def.get("entry_point")
    if override:
        return (root_abs / override).resolve()
    return (root_abs / "index.js").resolve()
```

No changes to the YAML parser itself — the existing loader already accepts arbitrary keys under `widgets[name]`.

### 1.3 Commit

`feat(widgets): add resolve_widget_entry_point with optional override`

---

## Task 2 — `gen_sdk_mock.py` + runtime package skeleton

**Spec refs:** §3.1, §5.

### 2.1 Failing tests

Create `tests/test_gen_sdk_mock.py`:
- `test_generator_emits_banner_comment` — first line is `// GENERATED by gen_sdk_mock.py — do not edit`
- `test_generator_covers_all_seeded_namespaces` — every namespace in `sdk_namespaces` table appears as a property on the emitted `ZOHO` object
- `test_generator_is_deterministic` — two runs produce byte-identical output
- `test_sdk_mock_covers_all_seeded_apis` — node subprocess loads the mock and enumerates reachable method paths; every `(namespace, name)` row in `sdk_methods` is reachable
- `test_generated_mock_logs_calls_to_call_log` — node subprocess calls one mock method, inspects `global.ZOHO._callLog[0].method`
- `test_generated_mock_unknown_method_falls_through_proxy` — accessing `ZOHO.CREATOR.API.someMadeUpFn` returns a callable that logs with `responseKind: "undeclared-method"`

### 2.2 Implement

Create `src/forgeds/widgets/runtime/package.json`:

```json
{
  "name": "forgeds-widget-runtime",
  "private": true,
  "type": "commonjs",
  "description": "Node harness + generated SDK mock for forgeds-run-widget. Do not publish."
}
```

Create `src/forgeds/widgets/gen_sdk_mock.py`:

- Open DB via `get_db_dir() / "zoho_widget_sdk.db"`.
- `SELECT namespace, name, signature, required_permissions FROM sdk_methods ORDER BY namespace, name` (sort → determinism).
- Group rows by namespace.
- Emit JS that:
  1. Writes the banner.
  2. Builds per-namespace objects. Each method is a function that:
     - Pushes `{method: "<ns>.<name>", args: JSON.parse(JSON.stringify(arguments)), responseKind, timestamp: Date.now() - __start}` onto `global.ZOHO._callLog`.
     - If `required_permissions` → add each to `global.ZOHO._permissionsObserved` (Set-like).
     - Returns a canned response per spec §5.4.
  3. Wraps each namespace in a `Proxy` whose `get` trap returns a fallback logging function when the requested property is not a known method (`responseKind: "undeclared-method"`).
  4. Exports `{ ZOHO }` and initialises `_callLog = []`, `_permissionsObserved = []`.

Canned-response map (spec §5.4) lives as a Python dict keyed by last-segment method name, with a default of `undefined` for navigation/UI methods.

Write to `src/forgeds/widgets/runtime/sdk_mock.js`. Exit 0 on success.

### 2.3 Commit

`feat(widgets): add gen_sdk_mock generator + runtime package skeleton`

The generated `sdk_mock.js` is committed alongside the generator.

---

## Task 3 — Node harness (`harness.js`)

**Spec refs:** §3.3, §4.

### 3.1 Failing tests

Create `tests/test_harness_contract.py` — each test invokes `harness.js` directly via `subprocess.run` against a throwaway widget in `tmp_path`:

- `test_harness_prints_callog_json_to_stdout_on_success`
- `test_harness_exit_0_on_success`
- `test_harness_exit_4_on_missing_entry_point`
- `test_harness_exit_5_on_sync_throw`
- `test_harness_exit_5_on_init_rejects`
- `test_harness_exit_6_on_timeout`
- `test_harness_records_declared_permissions_from_mock`
- `test_harness_callog_args_are_deep_copied`
- `test_harness_timestamp_is_ms_since_start`
- `test_harness_captures_non_serialisable_args_as_placeholder`

### 3.2 Implement

Create `src/forgeds/widgets/runtime/harness.js`:

```javascript
#!/usr/bin/env node
// ForgeDS Phase 2B — widget runtime harness.
// Runs under Node >= 18, no external dependencies.

'use strict';

const path = require('path');
const fs = require('fs');

function parseArgs(argv) {
  const out = { widgetRoot: null, entryPoint: null, widgetName: null, timeoutMs: 10000 };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    const next = argv[i + 1];
    if (a === '--widget-root')   { out.widgetRoot = next; i++; }
    else if (a === '--entry-point') { out.entryPoint = next; i++; }
    else if (a === '--widget-name') { out.widgetName = next; i++; }
    else if (a === '--timeout-ms')  { out.timeoutMs = parseInt(next, 10); i++; }
  }
  return out;
}

function writeRuntimeError(reason, detail) {
  process.stderr.write(
    'FORGEDS-RUNTIME-ERROR: ' + JSON.stringify({ reason, detail }) + '\n'
  );
}

function main() {
  const args = parseArgs(process.argv);
  if (!args.entryPoint) {
    writeRuntimeError('entry_not_found', { reason: 'no entry_point arg' });
    process.exit(4);
  }
  if (!fs.existsSync(args.entryPoint)) {
    writeRuntimeError('entry_not_found', { path: args.entryPoint });
    process.exit(4);
  }

  const sdk = require(path.join(__dirname, 'sdk_mock.js'));
  global.ZOHO = sdk.ZOHO;
  global.window = { addEventListener: () => {}, removeEventListener: () => {} };
  global.document = {
    addEventListener: () => {},
    removeEventListener: () => {},
    querySelector: () => null,
    querySelectorAll: () => [],
    createElement: () => ({ appendChild: () => {}, setAttribute: () => {} }),
    body: {},
  };
  global.fetch = () => { throw new Error('fetch disabled in forgeds-run-widget harness'); };
  global.XMLHttpRequest = function () { throw new Error('XHR disabled in harness'); };
  global.WebSocket = function () { throw new Error('WebSocket disabled in harness'); };

  const start = Date.now();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    emit('timeout');
    process.exit(6);
  }, args.timeoutMs);

  function emit(status, error) {
    const payload = {
      widget: args.widgetName || 'unknown',
      status,
      durationMs: Date.now() - start,
      permissionsObserved: Array.from(new Set(global.ZOHO._permissionsObserved || [])),
      callLog: global.ZOHO._callLog || [],
    };
    if (error) {
      payload.error = {
        message: String(error.message || error).slice(0, 512),
        name: error.name,
      };
    }
    process.stdout.write(JSON.stringify(payload) + '\n');
  }

  let loaded;
  try {
    loaded = require(args.entryPoint);
  } catch (err) {
    clearTimeout(timer);
    if (timedOut) return;
    writeRuntimeError('sync_throw', { message: String(err.message || err) });
    emit('throw', err);
    process.exit(5);
  }

  Promise.resolve()
    .then(() => {
      if (loaded && typeof loaded.init === 'function') {
        return loaded.init();
      }
    })
    .then(() => {
      clearTimeout(timer);
      if (timedOut) return;
      emit('ok');
      process.exit(0);
    })
    .catch((err) => {
      clearTimeout(timer);
      if (timedOut) return;
      emit('throw', err);
      process.exit(5);
    });
}

main();
```

### 3.3 Commit

`feat(widgets): add Node runtime harness (stdlib-only, CommonJS)`

---

## Task 4 — `run_widget.py` Python orchestrator

**Spec refs:** §4.5, §7, §8.

### 4.1 Failing tests

Create `tests/test_run_widget.py` — fixture-driven tests covering each WGR rule. Each test uses a temporary `forgeds.yaml` + fixture widget copied in; CLI is invoked via `subprocess.run` so exit codes are covered end-to-end.

- `test_run_widget_good_runtime_exits_clean`
- `test_run_widget_undeclared_call_emits_wgr001_error`
- `test_run_widget_unused_declaration_emits_wgr001_warning`
- `test_run_widget_throws_in_init_emits_wgr002`
- `test_run_widget_permission_mismatch_emits_wgr004`
- `test_run_widget_missing_entry_emits_wgr_meta`
- `test_run_widget_timeout_emits_wgr_meta`
- `test_run_widget_json_envelope_shape`
- `test_run_widget_node_missing_exits_3` — skip if we cannot simulate (keep as `pytest.mark.skipif`)
- `test_run_widget_single_bad_widget_does_not_abort_batch`

### 4.2 Implement

Create `src/forgeds/widgets/run_widget.py`:

- Argparse: `--widget NAME`, `--format {text,json-v1}` (delegated to `resolve_format`), `--config PATH`, `--timeout-ms INT`, `-q`, `--errors-only`.
- Node-availability check via `shutil.which("node")`; exit 3 with install hint if absent.
- Load config via `load_config_with_diagnostics`; surface CFG diagnostics through the envelope.
- For each widget in `cfg["widgets"]` (filtered by `--widget`):
  1. Resolve entry point via `resolve_widget_entry_point` (Task 1).
  2. If entry does not exist → emit `WGR-meta` error and skip to next widget.
  3. Spawn `node <runtime>/harness.js --widget-root ... --entry-point ... --widget-name ... --timeout-ms ...`.
  4. Parse stdout; if stderr contains `FORGEDS-RUNTIME-ERROR: {...}` record it for meta diagnostics.
  5. Apply WGR rules per spec §4.5.
- Emit diagnostics via `to_json_v1` (JSON) or existing text renderer pattern (text mode).
- Exit code: 0 / 1 / 2 per severity aggregate; 3 reserved for toolchain missing.

Key helper:

```python
def diff_call_log(observed: list[dict], declared: set[str],
                  custom_apis: set[str]) -> list[Diagnostic]:
    """Return WGR001 diagnostics (errors + warnings) for a single widget run."""
```

### 4.3 Commit

`feat(widgets): add forgeds-run-widget Python orchestrator and WGR diagnostics`

---

## Task 5 — Local ESLint plugin + sidecar

**Spec refs:** §6.

### 5.1 Failing tests

Create `tests/test_eslint_plugin_zoho_widget.py`:

- `test_sidecar_emitted_on_lint_widgets_run` — after `lint_widgets.main()` (or its subprocess), the sidecar file exists at the configured path, validates against its shape
- `test_eslint_rule_no_undeclared_apis_flags_missing_declaration` — run ESLint subprocess against a fixture file; expect a diagnostic for an undeclared Custom API invocation
- `test_eslint_rule_no_unused_apis_flags_unused_declaration` — run ESLint against fixture; expect a warning after Program:exit
- `test_eslint_rule_skips_when_sidecar_missing_env` — ESLint run without `FORGEDS_ESLINT_SIDECAR` exits cleanly with no rule fires

### 5.2 Implement

Create `src/forgeds/widgets/eslint-plugin-zoho-widget/package.json`:

```json
{ "name": "eslint-plugin-zoho-widget", "version": "1.0.0", "main": "index.js" }
```

Create `src/forgeds/widgets/eslint-plugin-zoho-widget/index.js`:

```javascript
'use strict';
module.exports = {
  rules: {
    'no-undeclared-apis': require('./rules/no-undeclared-apis'),
    'no-unused-apis': require('./rules/no-unused-apis'),
  },
};
```

Create `src/forgeds/widgets/eslint-plugin-zoho-widget/rules/no-undeclared-apis.js` — walks `CallExpression` nodes whose callee is `ZOHO.CREATOR.API.invokeCustomApi` (or similar), reads first-argument string literal, checks against sidecar's `widgets[*].consumesApis` (matched by file path vs `widgets[*].root`, longest-prefix wins), reports if not declared.

Create `rules/no-unused-apis.js` — on `Program:exit`, diff `consumesApis` vs invoked APIs in the current file and append to a JSON file at `process.env.FORGEDS_UNUSED_APIS_LOG` (one line per entry). The Python orchestrator finalises warnings from that log.

Update `src/forgeds/widgets/lint_widgets.py`:

- Before invoking ESLint, write `<cache-dir>/eslint_plugin_manifest.json` with the sidecar shape from spec §6.3.
- Set `FORGEDS_ESLINT_SIDECAR=<path>` in the subprocess env.
- After ESLint returns, read the unused-APIs log and emit WGR warnings (aggregated post-pass) — OR leave that aggregation inside `run_widget.py` to keep the static pass purely warnings-via-ESLint (decision: keep in orchestrator; the sidecar log is what the orchestrator reads).

Update `src/forgeds/widgets/configs/.eslintrc.zoho.json` — add `"plugins": ["zoho-widget"]` and rule entries.

### 5.3 Commit

`feat(widgets): add local eslint-plugin-zoho-widget with sidecar manifest`

---

## Task 6 — Fixture widgets + integration

**Spec refs:** §11.1.

### 6.1 Fixture tree

Create `tests/fixtures/widgets/runtime/forgeds.yaml` declaring all seven fixture widgets, each with appropriate `consumes_apis` declarations to exercise its intended rule.

Create the seven widget directories with minimal `plugin-manifest.json` + `index.js` contents. Each `index.js` is a tiny CommonJS module exporting `{ init }` as needed; widgets designed to throw / time out / mismatch permissions do so deterministically.

### 6.2 Integration tests

Covered by the `test_run_widget_*` cases written in Task 4. This task is primarily fixture authoring; no additional tests unless gaps appear during Task 4.

### 6.3 Commit

`test(widgets): add runtime fixture widgets for WGR rule coverage`

---

## Task 7 — `pyproject.toml` + `CLAUDE.md` + template updates

### 7.1 Entry point

Add to `[project.scripts]`:

```
forgeds-run-widget = "forgeds.widgets.run_widget:main"
```

### 7.2 CLAUDE.md

Under the rule-code registry table, add:

```
| `WGR###` | `forgeds.widgets.run_widget` | Runtime verification (widget executed against mocked SDK) |
```

Under widget rule allocation, add:

- `WGR001` — widget invoked an undeclared Custom API (ERROR) OR declared API never invoked (WARNING)
- `WGR002` — widget entry or `init()` threw
- `WGR003` — response-shape mismatch (stubbed until 2A response maps land)
- `WGR004` — invoked method's required permissions not in `plugin-manifest.json`
- `WGR-meta` — entry missing, harness timeout, unknown SDK method reached via proxy, widget skipped

Add a short "Widget runtime toolchain" section mirroring the Phase 1 widget-linting block: Node ≥ 18 required at runtime, exit 3 if absent, install hint.

### 7.3 templates/forgeds.yaml.example

Append a commented `entry_point` example under the widgets block:

```yaml
# widgets:
#   expense_dashboard:
#     root: src/widgets/expense_dashboard/
#     consumes_apis: [get_pending_claims]
#     # entry_point: src/main.js   # OPTIONAL — relative to `root`
```

### 7.4 Commit

`docs(widgets): register forgeds-run-widget entry point + WGR rule registry`

---

## Task 8 — Final verification

### 8.1 Full test suite

```
pytest tests/ --ignore=tests/test_build_ds.py
```

Must be all green. Any failures trigger a focused fix commit.

### 8.2 CLI smoke

```
pip install -e .
python -m forgeds.widgets.gen_sdk_mock
forgeds-run-widget --format json-v1 --config tests/fixtures/widgets/runtime/forgeds.yaml
```

Valid v1 envelope; exit code reflects aggregated severity.

### 8.3 Branch review (optional)

Dispatch a `feature-dev:code-reviewer` agent over the Phase 2B diff focusing on:

1. Envelope is sole serializer (no inline `json.dumps` of v1-shaped payloads).
2. Node-optional / exit-3 posture preserved (never hard-crash on missing Node).
3. Subprocess isolation is real — no shared global state across widget runs.
4. `sdk_mock.js` is fully reachable from the coverage test.
5. WGR rule numbers match spec allocation.
6. `canUseTool` / permission-model surfaces not touched (2B is additive).

---

## Non-goals reiterated (spec §13)

- No JSDOM / headless-browser runtime.
- No `forgeds-lint-widgets --with-runtime` combined CLI.
- No npm publication of `eslint-plugin-zoho-widget`.
- No Custom API response-shape validation (WGR003 stubbed).
- No fault-injection / error-response simulation.
- No lifecycle-event firing (only registration recording).
- No TypeScript widget support.
- No mutation of Phase 1 CLI surfaces (`forgeds-lint-widgets`, `forgeds-validate-widget-manifest`, `forgeds-build-widget-db`).
