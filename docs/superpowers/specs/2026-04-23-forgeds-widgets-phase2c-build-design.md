# ForgeDS Widgets Phase 2C — Build / Scaffold / Deploy Pipeline (DRAFT for user review)

**Date:** 2026-04-23
**Status:** Draft — produced by parallel-agent brainstorming pass, awaits user approval before a plan is written.
**Depends on:** Phase 1, Phase 2A (contract), Phase 2B (runtime).
**Parallel siblings:** Phase 2A, 2B, 2D.

> **Multi-agent note:** Phase 2C's `forgeds-build-app` is now a thin entry point
> that hands off to the Node Orchestrator Service defined in
> `docs/superpowers/specs/2026-04-23-forgeds-widgets-phase2-orchestration-design.md`.
> Stage execution (scaffold, bundle) is performed by worker agents dispatched
> per a BuildPlan. The Python-side scaffold/bundle CLIs
> (`forgeds-scaffold-widget`, `forgeds-bundle-widget`, etc.) remain unchanged —
> they're the underlying tools that MCP exposes.

---

## 1. Problem statement

Phase 1 gave ForgeDS the ability to **lint** widget source trees. Phase 2A gave
it a unified **diagnostics contract**. Phase 2B added **runtime verification**
against a mocked Zoho SDK. None of that actually ships a Creator app.

Phase 2C closes the last-mile gap. To let an AI-in-the-IDE author a Creator
application end-to-end, ForgeDS must be able to:

1. **Scaffold** — turn an AI-authored widget-spec dict into an on-disk widget
   tree (`plugin-manifest.json`, `index.js`, `index.html`, `styles.css`) with
   sensible TODO stubs for subsequent AI passes to fill in.
2. **Bundle** — validate that tree, then produce a ZIP acceptable to Zoho's
   widget-upload pipeline.
3. **Deploy** — push the ZIP to the target Creator application using OAuth
   credentials, with safe defaults.
4. **Orchestrate** — expose a single `forgeds-build-app` command that runs the
   full chain (validate → lint → verify → scaffold → bundle → deploy) with
   explicit stage-gating flags and a consolidated report.

These four things belong together because they share three concerns:

- **Widget-spec authoring schema** — the scaffolder produces it, the bundler
  reads it, the deployer annotates it with upload metadata.
- **Tool-chain shelling** — Zoho's widget tooling (ZET, and the undocumented
  publish endpoint) is JS/Node-first. Python orchestrates it, mirroring the
  pattern Phase 1 established for ESLint.
- **Safety rails** — bundling and deploying are the first ForgeDS operations
  that either emit artifacts intended for a live system or touch a live system
  directly. A coherent dry-run + confirmation model needs to span them.

Splitting these across separate future phases would force us to re-design those
three shared concerns three times.

---

## 2. Scope

### In scope (v1)

| Item | Notes |
| --- | --- |
| `widget-spec.yaml` authoring grammar | Per-widget file, colocated with `plugin-manifest.json`. |
| `forgeds-scaffold-widget` CLI | Python, stdlib only. Emits 4-file tree. |
| `forgeds-bundle-widget` CLI | Python. Shells to `zet pack`. Optional pure-Python ZIP fallback. |
| `forgeds-deploy-widget` CLI | Python. Uploads ZIP via OAuth. `--dry-run` default. |
| `forgeds-build-app` orchestrator | Pipeline stages with flag gating + `build-report.json`. |
| Safety: `--dry-run`, `--force`, confirmation prompts | Standardised semantics across all four CLIs. |
| ZET runtime-optional dependency posture | Exit 3 + install hint (mirrors Phase 1 ESLint pattern). |
| OAuth credential resolution order | env var → config file → explicit arg. |
| Research spike: widget-publish endpoint | Designated as an explicit unblock task before deploy can ship. |

### Out of scope (v1)

| Item | Why |
| --- | --- |
| Automatic rollback of a bad deploy | Zoho API does not clearly support "unpublish version N". Documented manual rollback only. |
| Multi-environment deploy orchestration (dev → staging → prod) | Out of v1 scope. Single deploy target per invocation. |
| Widget source authoring beyond skeletons | The scaffolder produces TODO-filled stubs. The AI next pass, not ForgeDS, writes real widget code. |
| `forgeds.yaml` widgets block extension | Phase 1 already landed the authoritative shape (Option Y). Not re-opened. |
| Publishing anything other than widgets | No scaffolder/bundler/deployer for Deluge files, schemas, or assets. |
| CI integration recipes | Documented in a follow-up Phase 2E recipe doc, not here. |
| Bundle signing / integrity hash | Nice-to-have. Deferred. |

---

## 3. Architecture

### 3.1 New files

```
src/forgeds/widgets/
├── scaffold_widget.py       # forgeds-scaffold-widget entry point
├── bundle_widget.py         # forgeds-bundle-widget entry point
├── deploy_widget.py         # forgeds-deploy-widget entry point
├── build_app.py             # forgeds-build-app orchestrator
├── spec_loader.py           # loads + validates widget-spec.yaml
├── zet_shim.py              # thin wrapper around `zet pack` / `zet publish`
├── publish_client.py        # HTTP client for Zoho upload API (UNVERIFIED shape)
├── templates/
│   ├── plugin-manifest.json.tmpl
│   ├── index.js.tmpl
│   ├── index.html.tmpl
│   └── styles.css.tmpl
└── configs/
    └── widget-spec.schema.json   # Draft-07 JSON Schema for widget-spec.yaml
```

### 3.2 Modified files

| File | Change |
| --- | --- |
| `pyproject.toml` | Register four new console scripts. |
| `src/forgeds/_shared/config.py` | Extend `load_config()` to resolve an optional `deploy:` block with OAuth env-var names. No new mandatory fields. |
| `src/forgeds/hybrid/upload_to_creator.py` | Lift the reusable OAuth flow into `_shared/oauth.py`; both `upload_to_creator` and `deploy_widget` import it. |
| `.gitignore` (template) | Add `config/zoho-api.yaml`. |
| `docs/superpowers/specs/2026-04-22-forgeds-widgets-phase1-design.md` | Add pointer-back paragraph noting G8 was intentionally deferred to this phase. Cosmetic only. |

### 3.3 Python ↔ Node shelling model

Mirrors Phase 1 §3's ESLint pattern:

- Python owns **all orchestration, validation, diagnostic emission, and exit
  codes**. Every stage's user-visible error surface is Python.
- Node tooling (ZET) is invoked via `subprocess.run` with captured stdout/stderr
  and a hard timeout.
- If ZET is absent, ForgeDS exits **3** with an install-hint message. It does
  not attempt to fall back silently.
- Optional pure-Python ZIP fallback (Section 11.3) is invoked only when the
  user passes `--no-zet`. This exists because the ZIP format itself is not
  Zoho-specific — it's manifest validation + a standard ZIP.
- Any JS tool output is parsed (JSON-mode where supported), converted to Phase
  2A `Diagnostic` records, and surfaced through the shared diagnostics stream.

---

## 4. Widget-spec authoring schema

### 4.1 Storage location

Option B from the research brief: **one `widget-spec.yaml` per widget**,
colocated with `plugin-manifest.json` at the widget's root.

```
src/widgets/expense_dashboard/
├── widget-spec.yaml         # authoring-intent (load-bearing + decorative)
├── plugin-manifest.json     # Zoho-authoritative, generated-then-hand-edited
├── index.js
├── index.html
└── styles.css
```

**Not** inline in `.ds` (Phase 1 G7 confirmed `.ds` does not carry widget
refs). **Not** an expansion of `forgeds.yaml widgets:` (would duplicate the
manifest and create three sources of truth).

### 4.2 Relationship to `forgeds.yaml` and `plugin-manifest.json`

| Source | Role | Authority |
| --- | --- | --- |
| `forgeds.yaml` `widgets:` block | Project-level index. Maps widget name → root path + declared API contract. | Authoritative for project layout. |
| `widget-spec.yaml` | Per-widget authoring intent. Human- and AI-readable; explains *why* + *what*. Inputs to scaffolder. | Authoritative for authoring intent. |
| `plugin-manifest.json` | Zoho runtime manifest. Permissions, roles, entry file, version. | Authoritative for Zoho. |

Order of truth when they disagree:

- Layout disagreements → `forgeds.yaml` wins.
- Permissions / entry / roles → `plugin-manifest.json` wins.
- All other disagreements → diagnostic emitted; no silent overwrite.

### 4.3 Full grammar

```yaml
# widget-spec.yaml (authoritative grammar for ForgeDS 2C)

name: expense_dashboard              # required, load-bearing
location: form_view                   # required, load-bearing; enum: form_view | report_view | standalone
description: >                        # required, decorative (drives comments)
  Displays expense claims awaiting approval.

consumes_apis:                        # required, load-bearing (cross-checked vs forgeds.yaml)
  - get_pending_claims
  - approve_claim

ui_primitives:                        # optional, decorative
  - card
  - table
  - modal

state_model:                          # optional, decorative (drives TODO stubs in index.js)
  - selectedClaim
  - pendingList

events_bound:                         # optional, decorative (drives event-registration stubs)
  - PageLoad
  - RecordSave

# Deployment-time fields: populated by deployer, not by author.
# Scaffolder leaves these absent.
deployment:
  last_uploaded_at: null              # ISO-8601 timestamp, or null
  last_uploaded_version: null         # matches plugin-manifest.json version at upload
  last_uploaded_target: null          # e.g. "creator:app-id=abc123"
```

### 4.4 Load-bearing vs decorative

| Field | Class | Consumed by |
| --- | --- | --- |
| `name` | load-bearing | scaffolder (directory name), bundler (manifest match), deployer (upload key) |
| `location` | load-bearing | scaffolder (selects template flavor), bundler (manifest check) |
| `consumes_apis` | load-bearing | scaffolder (import stubs), linter (cross-check vs Phase 1 `forgeds.yaml`) |
| `description` | decorative | scaffolder (inserts as top-of-file comment) |
| `ui_primitives` | decorative | scaffolder (inserts TODO-tagged placeholder components) |
| `state_model` | decorative | scaffolder (inserts TODO state initialization stubs) |
| `events_bound` | decorative | scaffolder (inserts TODO event-handler stubs) |
| `deployment.*` | runtime | deployer (writes after successful upload) |

"Load-bearing" means: absent or wrong → scaffolder / bundler / deployer errors.
"Decorative" means: absent → scaffolder proceeds with a terser stub; wrong →
warning only.

### 4.5 Validation

`widget-spec.schema.json` (Draft-07) at
`src/forgeds/widgets/configs/widget-spec.schema.json`. Schema errors → Phase 2A
`Diagnostic` records with `source="widget-spec"`.

---

## 5. `forgeds-scaffold-widget` contract

### 5.1 CLI

```bash
forgeds-scaffold-widget \
  [--spec SPEC_PATH] \
  [--output ROOT_DIR] \
  [--dry-run] \
  [--force] \
  [--verbose]
```

- `--spec` — path to an authored `widget-spec.yaml`. Default: search cwd for a
  lone `widget-spec.yaml`; error if zero or more than one found.
- `--output` — parent dir for the scaffolded tree. Default:
  `<project-root>/src/widgets/`.
- `--dry-run` — print the file list + file sizes that *would* be created; make
  no filesystem changes.
- `--force` — overwrite collisions. Without this flag, any existing file at the
  target path causes exit 2 with the list of conflicting paths.
- `--verbose` — include full file contents in stdout.

### 5.2 Inputs

1. The widget-spec dict (loaded + validated via `spec_loader.py`).
2. The four Jinja-style `.tmpl` files under `templates/`. These use plain
   `str.format_map()` — no Jinja — to keep the zero-dependency contract.
3. Optional: `forgeds.yaml` widget-block entry for cross-checking
   `consumes_apis`. Missing entry → warning, not error (the author may be
   scaffolding before wiring the forgeds.yaml index).

### 5.3 Output tree

```
<output>/<name>/
├── widget-spec.yaml         # copy of the input spec (canonicalised: key order, indentation)
├── plugin-manifest.json     # minimal valid manifest; Phase 1 schema-passing
├── index.js                 # stubs described below
├── index.html               # minimal HTML shell pointing at index.js
└── styles.css               # empty, with a top-of-file comment only
```

### 5.4 Initial content shape (description, not code)

**`plugin-manifest.json`**
- Fields: `name`, `widget_location` (from `spec.location`), `entry: "index.html"`,
  `version: "0.0.1"`, empty `permissions`, empty `roles`.
- Enough to pass Phase 1's manifest validator.

**`index.js`**
- Top comment block with `spec.description`, `spec.name`, `spec.location`.
- Imports from the Phase 2A typegen client (aspirational path — resolved when
  2A lands; scaffolder uses a placeholder import with a `// TODO(phase-2a)`
  tag).
- One `async function` stub per entry in `spec.consumes_apis`, each with a
  `// TODO: implement` body.
- One handler stub per entry in `spec.events_bound`.
- One top-level `const state = { ... }` object with one field per
  `spec.state_model` entry, each initialised to `null` with a `// TODO: type`.
- Event registration boilerplate for Zoho's widget lifecycle (UNVERIFIED exact
  API shape; scaffolder uses a TODO-tagged placeholder registration block).

**`index.html`**
- `<!doctype html>` shell, `<link rel="stylesheet" href="styles.css">`,
  `<script src="index.js" type="module"></script>`, and a single
  `<div id="root"></div>`.

**`styles.css`**
- Comment header only (`/* TODO: author styles for <name> */`).

### 5.5 Collision behavior

- Existing target directory, any file inside present → exit 2 with path list.
- `--force` → overwrite; emit one `Warning` diagnostic per overwritten file.
- `--dry-run` → ignores existing files for the purpose of exit-code gating; it
  is observation-only.

### 5.6 Idempotency

Re-running the scaffolder on the same spec without `--force` must be a no-op
that exits 0 **if and only if** the on-disk tree exactly matches what the
scaffolder would have emitted (byte-for-byte on generated files; spec file
compared semantically). Any drift → diagnostics listing each drifted file + exit
1 (warning-class; not error-class, because drift is expected after the AI fills
in TODOs).

---

## 6. `forgeds-bundle-widget` contract

### 6.1 CLI

```bash
forgeds-bundle-widget \
  [--widget NAME] \
  [--output DIST_DIR] \
  [--no-zet] \
  [--skip-lint] \
  [--verbose]
```

- `--widget` — widget name from `forgeds.yaml`. If omitted and exactly one
  widget is declared, that one is used. Multiple + no flag → error.
- `--output` — where to write the ZIP. Default: `<project-root>/dist/widgets/`.
- `--no-zet` — use the pure-Python ZIP fallback. Default: shell to `zet pack`.
- `--skip-lint` — don't re-run Phase 1 lint before bundling. Intended for CI
  pipelines where lint ran in an earlier stage.
- `--verbose` — pass `-v` to `zet pack` (when ZET is used).

### 6.2 Validation ordering

Each step runs only if all prior steps exit clean:

1. **Schema validation** — `widget-spec.yaml` against Draft-07 schema.
2. **Manifest validation** — `plugin-manifest.json` against Phase 1 schema.
3. **Cross-reference validation** — `widget-spec.name` == `plugin-manifest.name`
   == directory name. `consumes_apis` subset of `forgeds.yaml` widget entry.
4. **Structural validation** — required files present (`index.html`,
   `index.js`). Entry file referenced by manifest exists.
5. **Ready-for-upload validation** — no `TODO` tokens in `index.js` (warning,
   not error; the AI may intentionally ship a skeleton widget). File size
   sanity check (manifest < 64 KB, individual JS < 2 MB — UNVERIFIED limits;
   source: Zoho community posts, not docs).

### 6.3 ZET invocation pattern

```
zet pack --source <widget-root> --dist <output>/
```

ForgeDS changes into a temp workdir, symlinks/copies the widget tree into
ZET's expected layout, runs `zet pack`, captures stdout/stderr, surfaces as
diagnostics, and moves the resulting ZIP to `--output`.

Timeout: 120s. Exit 3 if the `zet` binary is not on PATH. Exit 2 if `zet pack`
returns non-zero. Exit 1 if `zet pack` succeeds but emits stderr warnings.

**Caller change under the multi-agent model.** In the original draft, Python
`build_app.py` shelled to `zet pack` directly as part of its internal pipeline.
Under the orchestration spec
(`docs/superpowers/specs/2026-04-23-forgeds-widgets-phase2-orchestration-design.md`),
the call chain becomes:

1. `worker/bundler` agent invokes the `forgeds_bundle_app` MCP tool.
2. That MCP tool's implementation calls the ForgeDS Python sidecar's
   `/forgeds/bundle` endpoint.
3. The sidecar calls `bundle_widget.py`'s `main()`.
4. `bundle_widget.py` calls `zet_shim.py` (this file).
5. `zet_shim.py` invokes `zet pack` exactly as described above.

The CLI-level invocation of `zet pack` is **identical**. Only the *caller* has
changed — from an in-process Python subprocess invocation to an MCP tool call
dispatched by the Node Orchestrator. All the bundle logic (temp workdir,
symlink/copy, stderr→diagnostic conversion, timeout, exit-code mapping) stays
in Python. `forgeds-bundle-widget` remains a first-class CLI that the MCP tool
wraps; running it by hand is unchanged.

### 6.4 Pure-Python fallback (`--no-zet`)

The ZIP file format is not Zoho-proprietary. Fallback builds the same ZIP
using `zipfile.ZipFile` directly. Caveat: we cannot guarantee it exactly
matches `zet pack`'s output until the research spike confirms what ZET does
beyond plain ZIP'ing. Flagged UNVERIFIED.

### 6.5 Output

```
<output>/<widget-name>-<version>.zip
```

Version from `plugin-manifest.json`. Existing file → error unless `--force`
(inherited from shared flag; see §9).

### 6.6 Exit codes

- 0 — bundle written, no warnings.
- 1 — bundle written, warnings emitted.
- 2 — validation failed or `zet pack` failed.
- 3 — required toolchain missing (ZET absent without `--no-zet`).

---

## 7. `forgeds-deploy-widget` contract

### 7.1 CLI

```bash
forgeds-deploy-widget \
  [--widget NAME] \
  [--zip PATH] \
  [--target TARGET] \
  [--token TOKEN] \
  [--dry-run] \
  [--confirm] \
  [--verbose]
```

- `--widget` — as for bundle; selects the ZIP by name if `--zip` omitted.
- `--zip` — explicit ZIP path. Overrides widget-name lookup.
- `--target` — deploy target identifier (e.g., `creator:app-id=abc123`).
  Required. No default, because picking one silently is dangerous.
- `--token` — explicit OAuth access token. **Discouraged**; bypasses env / config
  resolution. Redacted in all logs.
- `--dry-run` — **default ON.** Prints the HTTP request (method, URL, headers
  with `Authorization` redacted, body summary) and exits 0 without sending.
- `--confirm` — must be passed to actually deploy. Without it, the tool behaves
  as if `--dry-run` was set, regardless of other flags.
- `--verbose` — include full response body in logs (still redacting tokens).

### 7.2 OAuth token resolution order

1. `--token` CLI arg, if present.
2. `ZOHO_ACCESS_TOKEN` environment variable.
3. `config/zoho-api.yaml` → `access_token:` field.
4. Full OAuth exchange using `ZOHO_CLIENT_ID` + `ZOHO_CLIENT_SECRET` +
   `ZOHO_REFRESH_TOKEN` (env vars) or the same keys from
   `config/zoho-api.yaml`.

First source to resolve wins. Each step logs *which source was used* (not the
token value). If all four fail → exit 2 with a diagnostic listing each
attempted source and why it didn't resolve.

### 7.3 Request/response schema sketch (UNVERIFIED)

Speculative shape, pending research spike (§7.5):

**Request**
```
POST https://creator.zoho.com/api/v2.1/applications/{app_id}/plugins/upload
Authorization: Zoho-oauthtoken <access_token>
Content-Type: multipart/form-data
Body:
  file: <binary, the widget ZIP>
  metadata: {
    "name": "<widget name>",
    "version": "<semver from plugin-manifest>"
  }
```

**Response (expected)**
```json
{
  "code": 3000,
  "message": "success",
  "plugin": {
    "id": "<opaque>",
    "name": "<widget name>",
    "version": "<semver>",
    "uploaded_at": "<iso-8601>"
  }
}
```

Error shape (expected): non-3000 `code` + `message` string. ForgeDS converts
to Phase 2A `Diagnostic` records.

### 7.4 Post-deploy side effects

On success, `deploy_widget.py` writes back into `widget-spec.yaml`:

```yaml
deployment:
  last_uploaded_at: "2026-04-23T18:20:00Z"
  last_uploaded_version: "0.0.1"
  last_uploaded_target: "creator:app-id=abc123"
```

This is the only write the deployer performs on success. The file is
re-serialised preserving author key order where possible.

### 7.5 UNVERIFIED — research spike

> **Blocking unknown.** Zoho's widget-publish REST endpoint is not clearly
> documented. Community references suggest
> `POST /creator/v2.1/applications/{app_id}/plugins/upload`, but this has not
> been confirmed against an official spec. `zet publish` exists but is equally
> under-documented.
>
> **Spike task:** Before shipping `forgeds-deploy-widget`, perform a one-day
> research spike that: (a) stands up a throwaway Creator app; (b) uploads a
> trivial widget via the Zoho UI and captures the network trace; (c) uploads
> the same widget via `zet publish` and captures its outbound calls; (d)
> documents the actual endpoint, auth shape, and response format.
>
> Until the spike lands, `forgeds-deploy-widget` ships with `--dry-run` as the
> **only** supported mode — `--confirm` returns exit 3 with a pointer to this
> section.

---

## 8. `forgeds-build-app` orchestrator (thin entry point)

### 8.1 Revised model — thin Python entry, Node Orchestrator does the work

Under the orchestration spec
(`docs/superpowers/specs/2026-04-23-forgeds-widgets-phase2-orchestration-design.md`),
`forgeds-build-app` is no longer an in-process Python pipeline. It is a thin
entry point whose responsibilities are:

1. **Validate `forgeds.yaml`** (UNCHANGED — still Python, still stdlib-only).
   Schema check on the config file plus per-widget `widget-spec.yaml` validation.
2. **Build a project snapshot** — collect the set of forms, widgets, and
   custom-API names declared in `forgeds.yaml`, plus the absolute config path.
3. **Emit a `build-plan-request.json`** to stdout. This is the handoff payload;
   its exact shape is in §8.4.
4. **With `--plan-only`** — exit 0 after emitting the plan request. The IDE
   (Phase 2D) reads the output and can inspect / gate on it before dispatch.
5. **Without `--plan-only`** — POST the same payload to the Node Orchestrator
   Service at `http://127.0.0.1:9878/orchestrate` (override via
   `--orchestrator-url`). All subsequent stage execution (lint, verify,
   scaffold, bundle, deploy) happens in Node-side worker agents dispatched per
   the returned BuildPlan.
6. **Stream results** — the orchestrator responds with NDJSON, one line per
   stage completion. `forgeds-build-app` surfaces these as Phase 2A
   `Diagnostic` records and assembles the final `build-report.json` from the
   `orchestrator:session:done` event.

The pipeline stages themselves (`validate-config → lint → verify → scaffold →
bundle → deploy`) are preserved *conceptually* — they are the stages the Node
Orchestrator dispatches worker agents for. They are no longer Python function
calls inside `build_app.py`. The Python-side scaffold/bundle/deploy CLIs are
still first-class and still callable by hand; they are the underlying tools
that MCP exposes to worker agents.

### 8.2 CLI

```bash
forgeds-build-app \
  [--stages=lint,verify,bundle,deploy] \
  [--plan-only] \
  [--orchestrator-url URL] \
  [--dry-run] [--force] [--collect-all] [--fail-fast] \
  [--target TARGET] \
  [--report PATH]
```

| Flag | Purpose |
| --- | --- |
| `--stages` | Comma-separated subset of stages the orchestrator should dispatch. Default: all stages except `deploy`. Stage names are `lint,verify,scaffold,bundle,deploy`. Still controls *what* the orchestrator dispatches; no longer controls Python-internal execution (which no longer exists). |
| `--plan-only` | Emit `build-plan-request.json` to stdout and exit 0 without contacting the orchestrator. The IDE uses this to preview / gate before dispatch. |
| `--orchestrator-url` | Base URL of the Node Orchestrator Service. Default `http://127.0.0.1:9878`. |
| `--dry-run` | Propagated into the plan request; each worker agent respects it. Deploy stage remains dry-run-by-default regardless. |
| `--force` | Propagated into the plan request (used by scaffold worker for collision overwrite). |
| `--collect-all` | Passed through to the orchestrator in `collect_all: true`. Tells the orchestrator to run every dispatched stage regardless of predecessor status. |
| `--fail-fast` | Passed through to the orchestrator. Default orchestrator posture; flag is here for explicitness / to override a config default. |
| `--target` | Deploy target identifier. Required when `deploy` is in `--stages`. |
| `--report` | Destination path for the assembled `build-report.json`. Default `<project-root>/dist/build-report.json`. |

Flags that presumed Python-internal stage execution (the old `--lint` /
`--verify` / `--bundle` / `--deploy` *implies-up-through-me* boolean stage
gates) are removed in favor of the explicit `--stages` enumeration, because
the orchestrator dispatches an explicit set, not an implicit prefix.

Passing `deploy` in `--stages` without `--target` → exit 2 (unchanged safety
rail).

### 8.3 Fail-fast vs `--collect-all`

Semantically unchanged from the original design — but now enforced *in the
orchestrator*, not in Python:

- **Default (fail-fast)** — first stage that returns non-zero halts further
  dispatch. Subsequent stages are marked `skipped` in the stream + final
  report.
- **`--collect-all`** — every dispatched stage runs to completion regardless
  of predecessor exit. Stages whose inputs are missing (e.g., bundle after
  failed scaffold) emit a `missing-input` diagnostic instead of running.
  Final exit code = max exit code of any stage.

Both flags are forwarded in the plan-request body (§8.4).

### 8.4 Handoff contract — plan request and streamed response

**Request.** `forgeds-build-app` POSTs this JSON body to the orchestrator:

```json
POST http://127.0.0.1:9878/orchestrate
{
  "prompt": "<user-supplied or auto-generated from project diff>",
  "project_snapshot": {
    "config_path": "/abs/path/to/forgeds.yaml",
    "forms": ["expense_claim", "expense_approval"],
    "widgets": ["expense_dashboard"],
    "custom_apis": ["get_pending_claims", "approve_claim"]
  },
  "stage_flags": {
    "lint": true, "verify": true, "bundle": true, "deploy": false
  },
  "dry_run": true,
  "collect_all": false
}
```

With `--plan-only`, this identical payload is written to stdout as
`build-plan-request.json` and the process exits 0. The IDE may inspect, edit,
or hand-dispatch from it.

**Response.** The orchestrator streams NDJSON. Each line is a JSON object
matching one stage entry in the original `build-report.json` `stages[]` array
(see §8.5). The final line is an `orchestrator:session:done` event carrying
the `summary` block.

### 8.5 `build-report.json` schema (preserved, backward-compatible)

The assembled report retains the original schema — this is the document the
IDE and CI consume. Each stage entry's diagnostics now carry the optional
`agent` provenance field documented in Phase 2A (identifying which worker
agent produced the diagnostic); the rest of the shape is unchanged:

```json
{
  "forgeds_version": "2.0.0",
  "started_at": "2026-04-23T18:00:00Z",
  "finished_at": "2026-04-23T18:02:11Z",
  "target": "creator:app-id=abc123",
  "mode": "collect-all",
  "stages": [
    {
      "name": "validate-config",
      "status": "ok",
      "exit_code": 0,
      "duration_s": 0.12,
      "diagnostics": []
    },
    {
      "name": "lint",
      "status": "warnings",
      "exit_code": 1,
      "duration_s": 4.30,
      "diagnostics": [ /* Phase 2A Diagnostic[] — each may include `agent`: "worker/lint" */ ]
    },
    {
      "name": "deploy",
      "status": "skipped",
      "reason": "flag-not-set",
      "exit_code": null,
      "duration_s": null,
      "diagnostics": []
    }
  ],
  "widgets": [
    {
      "name": "expense_dashboard",
      "bundle_path": "dist/widgets/expense_dashboard-0.0.1.zip",
      "deployed": false
    }
  ],
  "summary": {
    "total_errors": 0,
    "total_warnings": 3,
    "overall_exit_code": 1
  }
}
```

Written to `--report` path, default `<project-root>/dist/build-report.json`.
Schema is backward-compatible with the original Phase 2C draft — existing
consumers parse it unchanged.

### 8.6 Exit codes (overall)

Computed from the `summary.overall_exit_code` in the streamed session-done
event:

- 0 — every stage exit 0.
- 1 — at least one stage exit 1, none exit 2 or 3.
- 2 — at least one stage exit 2, or `--target` missing when `deploy` requested,
  or orchestrator unreachable.
- 3 — at least one stage exit 3 (missing toolchain reported by a worker), or
  orchestrator HTTP 5xx.

---

## 9. Safety rails

### 9.1 Dry-run posture

| Command | Default |
| --- | --- |
| `forgeds-scaffold-widget` | writes files |
| `forgeds-bundle-widget` | writes files (no network) |
| `forgeds-deploy-widget` | **dry-run — no network call** unless `--confirm` |
| `forgeds-build-app` | runs through selected stage; deploy stage is dry-run unless user invokes deploy directly |

The asymmetry is intentional: scaffold and bundle are local and reversible.
Deploy is neither.

> **Multi-agent safety rail.** The `worker/bundler` agent is NOT allowed
> `forgeds_deploy_zoho` — deploy remains IDE-user-initiated only, as specified
> in the orchestration spec §13 (Security model). The three-layer defense
> (`AgentDefinition.tools` allowlist on the worker, a PreToolUse hook that
> rejects off-allowlist tool calls, and omission of the deploy tool from the
> MCP server wiring for the worker) ensures no worker can reach the deploy
> surface even under prompt injection. The dry-run-default posture from this
> section is unchanged: `forgeds-deploy-widget` is still driven only by an
> explicit human-initiated invocation with `--confirm`.

### 9.2 Confirmation prompts

`forgeds-deploy-widget --confirm` prints a one-screen summary (target, widget
name, version, ZIP size, resolved OAuth source) and waits for the user to type
`deploy` at a prompt. `--non-interactive` skips the prompt but still requires
`--confirm`. This pairing is intended to make it hard to accidentally deploy
from a script that was supposed to be doing something else.

### 9.3 Rollback guidance

No automatic rollback. Documentation (not code) will walk users through the
manual rollback procedure: revert in source control, bump version in
`plugin-manifest.json`, re-deploy. A `ROLLBACK.md` ships in the ForgeDS docs
tree (not in consumer repos).

### 9.4 Forbidden / warned flag combinations

| Combination | Behavior |
| --- | --- |
| `forgeds-deploy-widget --dry-run --confirm` | exit 2, "conflicting flags" |
| `forgeds-deploy-widget --confirm` without `--target` | exit 2 |
| `forgeds-scaffold-widget --force` on a non-empty tree with `--deploy` anywhere upstream | **warn loudly**: scaffold-force may overwrite production-quality code that is about to be deployed |
| `forgeds-build-app --deploy` with no `--target` | exit 2 |
| `forgeds-build-app --deploy --collect-all` | allowed but emits a notice: collect-all does not prevent deploy, so a failed lint does not block deploy — intentional for emergency-deploy scenarios, but it is loud |

---

## 10. Credential handling

### 10.1 Environment variables

| Var | Purpose |
| --- | --- |
| `ZOHO_ACCESS_TOKEN` | Directly usable bearer token. Skips refresh. |
| `ZOHO_REFRESH_TOKEN` | Long-lived refresh token. |
| `ZOHO_CLIENT_ID` | OAuth client id. |
| `ZOHO_CLIENT_SECRET` | OAuth client secret. |
| `ZOHO_AUTH_BASE` | Override for accounts/auth base URL (DC-dependent). |

### 10.2 Config file

`config/zoho-api.yaml` (gitignored). Schema:

```yaml
access_token: ...           # optional
refresh_token: ...          # optional
client_id: ...
client_secret: ...
auth_base: https://accounts.zoho.com    # optional; default per-DC
```

### 10.3 Gitignore

ForgeDS's consumer-project templates add `config/zoho-api.yaml` and
`build-report.json` to `.gitignore`. Existing consumer projects must update
their own `.gitignore`; ForgeDS emits a warning at first-run if the file is
tracked.

### 10.4 What Phase 2D / IDE may or may not see

- **Never** exposed to the IDE layer: raw tokens, client secrets, refresh
  tokens.
- **Exposed**: "a valid OAuth source was resolved from `env:ZOHO_REFRESH_TOKEN`"
  (source name only, never the value).
- The Phase 2D bridge is responsible for injecting the tokens as env vars into
  the ForgeDS subprocess invocation; the IDE never reads them from disk
  directly.

---

## 11. Dependency posture

### 11.1 ZET as runtime-optional

Same pattern as Phase 1's ESLint:

- Not a Python dependency.
- Not installed by `pip install forgeds`.
- Missing at runtime → exit 3 with install hint:
  `npm install -g zoho-extension-toolkit`.

### 11.2 Version pinning

`docs/TOOLCHAIN.md` pins a known-good ZET version and references the
upstream changelog. CI tests against that version.

### 11.3 Vendored-ZET fallback

If upstream ZET proves unstable, ForgeDS may vendor a known-good release into
`tools/zet-vendor/` and shell to it explicitly via
`FORGEDS_ZET_PATH` env var. This is a contingency, not default behavior.

### 11.4 Pure-Python ZIP fallback

`--no-zet` on `forgeds-bundle-widget`. Flagged UNVERIFIED until the research
spike (§7.5) confirms ZET's output matches a plain `zipfile` output byte-for-byte.
If not, `--no-zet` remains documented-beta.

---

## 12. Testing

Fixture layout:

```
tests/fixtures/widgets_phase2c/
├── spec_minimal/
│   └── widget-spec.yaml                    # minimal valid spec
├── spec_malformed_missing_name/
│   └── widget-spec.yaml
├── spec_malformed_bad_location/
│   └── widget-spec.yaml
├── scaffold_existing_tree/
│   └── <pre-populated tree for collision tests>
├── bundle_happy_path/
│   └── <valid scaffolded tree>
├── bundle_no_zet/
│   └── <same tree; test uses --no-zet>
├── bundle_missing_manifest/
├── bundle_stale_widget_spec/               # spec disagrees with manifest
├── deploy_dry_run/
├── deploy_bad_creds/
└── build_app_full_happy/
```

Test names (no code):

- `test_scaffold_emits_full_tree_from_minimal_spec`
- `test_scaffold_emits_diagnostics_for_malformed_spec`
- `test_scaffold_errors_on_collision_without_force`
- `test_scaffold_overwrites_with_force_and_warns`
- `test_scaffold_dry_run_touches_no_files`
- `test_scaffold_is_idempotent_on_unchanged_spec`
- `test_bundle_happy_path_produces_zip_at_expected_path`
- `test_bundle_exits_3_when_zet_missing`
- `test_bundle_succeeds_with_no_zet_flag`
- `test_bundle_rejects_spec_manifest_mismatch`
- `test_bundle_surfaces_zet_stderr_as_diagnostics`
- `test_deploy_dry_run_performs_no_network_call`
- `test_deploy_confirm_without_target_exits_2`
- `test_deploy_resolves_token_from_env_over_config`
- `test_deploy_redacts_token_in_all_logs`
- `test_deploy_writes_deployment_block_back_to_spec_on_success`
- `test_build_app_fail_fast_halts_on_lint_error`
- `test_build_app_collect_all_runs_every_stage`
- `test_build_app_deploy_requires_target`
- `test_build_app_report_json_matches_schema`

All tests use Phase 2A `Diagnostic` records as the assertion surface.

---

## 13. Risks

| Risk | Severity | Mitigation |
| --- | --- | --- |
| **A. Zoho SDK maturity** — ZET or the publish endpoint breaks without notice. | High | Pin ZET version. Vendored-ZET fallback (§11.3). Research spike (§7.5). Pure-Python ZIP fallback (§11.4). |
| **B. Scaffold diverges from deploy reality** — scaffolder emits manifests that Zoho accepts today but rejects after a silent Creator update. | Medium | Phase 1 manifest schema is regenerated from upstream docs quarterly. Bundle stage re-validates against the current schema, not the scaffolded-at version. |
| **C. Accidental deploy** — user runs `forgeds-build-app --deploy` without realising. | High | `--confirm` required on the underlying deploy command. `build-app` does *not* forward `--confirm` silently. Interactive confirmation prompt. Redacted summary screen. |
| **D. Credential leak** — tokens printed in logs or in `build-report.json`. | High | Token values never written to diagnostics, logs, or reports. Only source *names* are logged. Unit tests (`test_deploy_redacts_token_in_all_logs`) guard this. |
| **E. Spec/manifest drift** — AI next-pass edits `index.js` + updates `widget-spec.yaml`, but forgets to bump `plugin-manifest.json` version. | Medium | Bundle stage emits a warning if `widget-spec.yaml` `deployment.last_uploaded_version` == current manifest version. |
| **F. Collision between scaffolder and hand-edited code** — AI re-invokes scaffolder, wipes hand-edits. | High | `--force` is opt-in and warns per file. Idempotency story (§5.6) emits diagnostics on drift rather than silently overwriting. |
| **G. ZET changes its invocation surface** — `zet pack` flags rename. | Low | `zet_shim.py` centralises the invocation; one change site. |

---

## 14. Non-goals

Explicit non-goals for v1 (repeating §2 out-of-scope items plus a few that
deserve individual calling out):

- No automatic rollback.
- No multi-environment orchestration.
- No authoring-side widget code generation beyond TODO stubs.
- No bundle signing / integrity hashing.
- No `forgeds.yaml` schema expansion.
- No CI recipe documentation (deferred to Phase 2E).
- No "preview" step that renders the widget before upload (Phase 2B covers
  runtime verification; a visual preview is a separate future phase).
- No OAuth interactive flow (device code, browser popup). Phase 2C expects
  tokens to already exist in env or config. Interactive provisioning is a
  Phase 2D concern.
- **No Python-internal orchestration pipeline for `forgeds-build-app`.** Stage
  execution (lint, verify, scaffold, bundle, deploy) is handed off to the
  Node Orchestrator Service; Python retains only `forgeds.yaml` validation and
  the handoff itself. The Python stage functions that would have driven the
  pipeline in the original draft are explicitly out of scope.

---

## 15. Open questions

1. **Publish endpoint (blocking).** See §7.5. The research spike is a
   prerequisite for shipping `--confirm` mode on the deployer.
2. **ZET output parity with plain `zipfile`.** Until confirmed, `--no-zet` is
   beta-only.
3. **Widget lifecycle API in `index.js`.** The exact shape of Zoho's widget
   event-registration API is under-documented. Scaffolder uses TODO-tagged
   placeholder code; the research spike should confirm the real shape so we can
   replace the placeholder in v1.1.
4. **Version bump policy.** Should bundle auto-bump `plugin-manifest.json`
   version? Current design says no — authors and AI passes control versioning.
   Open for discussion.
5. **Report retention.** Where do historical `build-report.json` files go?
   Proposal: last N reports under `dist/reports/` with timestamp suffix. Not in
   v1; tracked as a follow-up.
6. **Cross-DC OAuth base URLs.** `ZOHO_AUTH_BASE` covers this, but do we need a
   per-DC detection heuristic? Probably not in v1; documented as a user
   responsibility.
7. **Bundle vs deploy on different machines.** Can a ZIP bundled on machine A
   be deployed from machine B? Design says yes — the ZIP is self-contained.
   Needs test coverage once the publish endpoint is confirmed.

---

## Self-review notes (draft author)

- Placeholders cross-checked: all `<name>`, `<version>`, `<output>` are
  parameterised, not literal holes.
- Contradictions: `--dry-run` default on deploy vs `forgeds-build-app --deploy`
  behavior explicitly reconciled in §8.3 and §9.1. No residual conflict.
- Ambiguity: "load-bearing vs decorative" given a concrete table (§4.4) so
  future readers don't re-litigate.
- Scope-creep check: no "Deluge scaffold" mention, no ".ds generator" mention,
  no "bundle signing" mention outside of non-goals.
- UNVERIFIED tags explicit at §5.4 (lifecycle API), §6.2 (size limits), §6.4
  (ZIP parity), §7.3 (request/response), §7.5 (endpoint), §11.4 (ZIP
  fallback). No other speculative claims hidden in prose.
