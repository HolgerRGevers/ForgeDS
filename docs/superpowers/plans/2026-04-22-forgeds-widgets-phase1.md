# ForgeDS Widgets Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver widget (JS/HTML/manifest) lint scaffolding for ForgeDS: YAML config extension, Zoho Widget SDK database, ESLint orchestrator, manifest validator, and three thin-slice hybrid cross-check rules.

**Architecture:** New `src/forgeds/widgets/` package housing the orchestrator, DB builder, and manifest validator. Polyglot orchestration — Python shells out to ESLint for JS lint, translating findings into the shared `Diagnostic` schema. Hybrid cross-checks (widget↔Deluge) extend the existing `lint_hybrid.py` with `WG###` rules. Node/ESLint is a runtime-optional dependency (pyodbc pattern); ForgeDS pip install remains zero-dep.

**Tech Stack:** Python ≥ 3.10 (stdlib only), SQLite, pytest, ESLint 8+ (optional runtime), JSON Schema draft-07 (stdlib subset validator).

**Reference spec:** `docs/superpowers/specs/2026-04-22-forgeds-widgets-phase1-design.md`

---

## File Structure

### Files to create

```
src/forgeds/widgets/
├── __init__.py                           # Task 2
├── lint_widgets.py                       # Task 7
├── build_widget_sdk_db.py                # Task 2
├── validate_manifest.py                  # Task 4
├── configs/
│   ├── .eslintrc.zoho.json               # Task 6
│   └── plugin-manifest.schema.json       # Task 3
└── seed_data/
    └── widget_sdk_apis.json              # Task 2

tests/
├── test_config_widgets.py                # Task 1
├── test_build_widget_sdk_db.py           # Task 2
├── test_validate_manifest.py             # Task 4
├── test_lint_widgets.py                  # Task 7
├── test_lint_hybrid_wg_rules.py          # Tasks 8-10
└── fixtures/widgets/
    ├── forgeds.yaml                      # Task 7
    ├── good_widget/
    │   ├── plugin-manifest.json          # Task 4
    │   └── index.js                      # Task 7
    ├── bad_widget_missing_manifest/
    │   └── index.js                      # Task 7
    ├── bad_widget_invalid_manifest/
    │   ├── plugin-manifest.json          # Task 4
    │   └── index.js                      # Task 7
    └── bad_widget_undeclared_api/
        ├── plugin-manifest.json          # Task 7
        └── index.js                      # Task 7
```

### Files to modify

```
src/forgeds/_shared/config.py             # Task 1 — add custom_apis + widgets defaults
src/forgeds/hybrid/lint_hybrid.py         # Tasks 8-10 — add WG001/WG002/WG003
pyproject.toml                            # Task 11 — 3 new entry points
templates/forgeds.yaml.example            # Task 12 — document new blocks
CLAUDE.md                                 # Task 13 — rule registry, Node posture, G7 findings
```

### File responsibilities

- `_shared/config.py` — sole owner of `forgeds.yaml` schema defaults. Callers use `.get()`.
- `widgets/build_widget_sdk_db.py` — one-shot DB build from seed JSON. Mirrors `build_deluge_db.py` pattern.
- `widgets/validate_manifest.py` — stdlib-only JSON Schema subset validator. ~200 LOC.
- `widgets/lint_widgets.py` — shells to ESLint, translates findings. Owns JSON envelope v1.
- `hybrid/lint_hybrid.py` — existing file; gains WG### rule checks against `config["widgets"]`.

---

## Commit message conventions

Repo uses `feat(scope):`, `test(scope):`, `fix(scope):` with scopes like `ide`, `core`, `hybrid`. For this work, use scope **`widgets`**. Example: `feat(widgets): add custom_apis and widgets to config defaults`.

---

## Orchestration model (controller → worker dispatch)

Execute this plan with `superpowers:subagent-driven-development`. The controller/worker pattern mirrors a Node.js main-process-with-workers topology — the controller orchestrates; workers implement.

### Roles

- **Controller** (primary session) — reads plan once, extracts every task's full text upfront, dispatches workers, runs the review loop, merges status, marks tasks complete. **Never implements directly.**
- **Implementer subagent** — one fresh agent per task. Receives full task text + relevant spec excerpts + codebase context. Uses TDD. Reports `DONE` / `DONE_WITH_CONCERNS` / `NEEDS_CONTEXT` / `BLOCKED`.
- **Spec reviewer subagent** — fresh agent dispatched *after* each implementer returns `DONE`. Confirms spec compliance (nothing missing, nothing extra).
- **Code-quality reviewer subagent** — fresh agent dispatched *after* spec review passes. Checks for bugs, test quality, naming, consistency.

### Hard rules

1. **Never run two implementers in parallel against the same file.** Parallelism applies only across disjoint-file batches.
2. **Never skip spec review or code-quality review.** Both required, in that order, per task.
3. **Never let an implementer read the plan file directly.** Controller provides the complete task text as part of the prompt (prevents context pollution and plan drift).
4. **Never advance to the next task while any review has unresolved issues.** Re-dispatch the same implementer with the review feedback until the reviewer approves.
5. **Fresh subagent per task.** No implementer carries state from a prior task.

### Worker model (inspired by node-server-orchestrator)

The local `.mcp.json` registers `node-server-orchestrator` — an MCP server for managing Node dev-server processes with stable IDs, per-process lifecycle commands (`start` / `stop` / `status`), and bulk ops (`start-all` / `stop-all`). That tool manages Node servers, not Claude subagents, so we **do not invoke it to dispatch implementers** — but we borrow its mental model.

Treat each implementer subagent as a **managed worker** with:

- **Stable ID** — durable across status checks and review loops (see table below)
- **Lifecycle verbs** — `dispatch` (start), `await` (block until status), `redispatch` (restart with new context)
- **Status** — one of the four subagent-driven-development statuses, mapped to a server-process-like state
- **Bulk ops** — dispatch all workers in a batch with a single controller message (the Claude equivalent of `start-all`)

### Worker ID registry

| Worker ID | Task | Role |
|---|---|---|
| `worker/A1-config-loader` | Task 1 | implementer |
| `worker/A2-sdk-db` | Task 2 | implementer |
| `worker/A3-manifest-schema` | Task 3 | implementer |
| `worker/A5-parser-investigation` | Task 5 | implementer |
| `worker/A6-eslint-config` | Task 6 | implementer |
| `worker/B-manifest-validator` | Task 4 | implementer |
| `worker/C-lint-widgets` | Task 7 | implementer |
| `worker/D1-wg001` | Task 8 | implementer |
| `worker/D2-wg002` | Task 9 | implementer |
| `worker/D3-wg003` | Task 10 | implementer |
| `worker/E-pyproject` | Task 11 | implementer |
| `worker/F1-template` | Task 12 | implementer |
| `worker/F2-claude-md` | Task 13 | implementer |
| `reviewer/spec-<task>` | ephemeral | spec compliance review (one per task) |
| `reviewer/quality-<task>` | ephemeral | code-quality review (one per task) |
| `reviewer/final` | ephemeral | whole-branch review after Batch F |

IDs appear in controller-side TodoWrite entries and in commit-message trailers where useful (e.g. `feat(widgets): ... [worker/A1]`) so logs and diffs can be cross-referenced.

### Worker status → controller action (state machine)

| Worker reports | Process-manager analogue | Controller action |
|---|---|---|
| `DONE` | exit 0 | Proceed to spec review |
| `DONE_WITH_CONCERNS` | exit 0 with warnings on stderr | Read concerns; if correctness/scope, fix before review; else proceed |
| `NEEDS_CONTEXT` | stdout waiting on stdin | Supply missing context, `redispatch` same worker ID |
| `BLOCKED` | nonzero exit / SIGKILL | Diagnose: context gap → redispatch; reasoning gap → upgrade model tier; task too big → split; plan wrong → escalate to human |

**Never** redispatch with unchanged context and unchanged model — something must change between attempts.

### Bulk dispatch semantics

Batch A is the only batch with bulk-dispatch semantics (5 parallel workers). The controller implements it by issuing a **single message containing five Agent tool calls** — the Claude equivalent of `node-server-orchestrator start-all`. The controller then awaits all five completions, routes each through its own review pair, and only advances to Batch B once every Batch-A task is both spec- and quality-approved.

Batches B, C, E: single-worker batches — `dispatch` + `await` + review loop — same as a single `start <server-id>`.

Batches D and F: single-worker batches but with a **strict serial ordering** (`D1 → D2 → D3`, `F1 → F2`) because the workers mutate shared files. Attempting parallel dispatch here is the equivalent of starting two Node servers on the same port — a guaranteed conflict. Never do it.

### Controller-side observability

The controller maintains a live map `{worker_id → status}` via TodoWrite. At any moment you should be able to point at a worker ID and answer:
- What task is it on?
- What's its current status?
- If it's blocked, on what?
- What's the git SHA range of its commits?

This map is the controller's single source of truth for progress — not the plan file, not git log, not individual review transcripts. If the map and reality diverge, stop and reconcile before dispatching more work.

### Dependency graph and batch plan

```
Batch A (parallel, disjoint files)
  ├─ Task 1: config loader           (src/forgeds/_shared/config.py)
  ├─ Task 2: SDK DB                  (src/forgeds/widgets/ — new package)
  ├─ Task 3: manifest JSON Schema    (src/forgeds/widgets/configs/)
  ├─ Task 5: G7 investigation        (read-only grep + notes file)
  └─ Task 6: .eslintrc.zoho.json     (src/forgeds/widgets/configs/)

Batch B (serial after A)
  └─ Task 4: manifest validator      (depends on Task 3 schema file)

Batch C (serial after A+B)
  └─ Task 7: ESLint orchestrator     (depends on Tasks 1, 4, 6)

Batch D (strictly serial — all edit lint_hybrid.py)
  ├─ Task 8: WG001
  ├─ Task 9: WG002 (depends on Task 4)
  └─ Task 10: WG003 + main wiring (depends on Tasks 8, 9)

Batch E (serial after D)
  └─ Task 11: pyproject.toml entry points (needs all modules installable)

Batch F (serial after E — documentation finalisation)
  ├─ Task 12: templates/forgeds.yaml.example
  └─ Task 13: CLAUDE.md
```

### Dispatch table

| Batch | Tasks | Parallel workers | Model tier | Why that tier |
|---|---|---|---|---|
| **A** | 1, 2, 3, 5, 6 | **Up to 5 concurrent** | cheap (1, 3, 5, 6) / standard (2) | Mostly mechanical file creation; Task 2 has multi-table SQL integration |
| **B** | 4 | 1 | standard | Stdlib JSON-Schema-subset validator; non-trivial logic |
| **C** | 7 | 1 | standard | Multi-file integration, subprocess shelling, JSON envelope |
| **D** | 8 → 9 → 10 | 1 (serial) | standard | All mutate `lint_hybrid.py`; serial prevents merge churn |
| **E** | 11 | 1 | cheap | Mechanical config edit + verify |
| **F** | 12 → 13 | 1 (serial) | cheap | Docs edits; serial because both touch shared docs context |

**Model tier guidance** (from `subagent-driven-development`): cheap = fast/inexpensive model for mechanical 1-2-file tasks with a clear spec; standard = default model for integration, multi-file coordination, or moderate judgment. No task in this plan rises to "capable model" territory — plan specificity is high, architecture is decided.

### Context passed to each implementer

For every dispatch, the controller constructs a self-contained prompt containing:

1. **Full task text** (copy-paste from this plan, not a file reference)
2. **Spec excerpts** relevant to the task (section numbers listed in each task's dispatch header below)
3. **Sibling-file pointers** — any existing ForgeDS files the implementer must read (e.g. Task 8–10 implementers need to read `lint_hybrid.py` to match existing rule-function style)
4. **Commit-message convention** (scope `widgets`)
5. **Completion expectation** — all tests green, committed, one of DONE/DONE_WITH_CONCERNS/NEEDS_CONTEXT/BLOCKED

### Per-task review prompts

After each implementer returns `DONE`:

1. Dispatch **spec reviewer** with:
   - Task's original full text
   - Git SHA range of the implementer's commits
   - "Does the committed work satisfy every bullet of this task and no more? List missing/extra."
2. If spec reviewer approves → dispatch **code-quality reviewer** with same SHA range:
   - "Review for bugs, test quality, naming, style consistency with surrounding codebase."
3. Only when code-quality reviewer approves → mark task complete in TodoWrite and advance.

### Final dispatch (after Batch F)

One final code-reviewer subagent against the full branch diff (`git diff main...HEAD`). Its job: holistic sanity check — consistent rule codes, no cross-task drift, JSON envelope matches spec §6. After that, hand off to `superpowers:finishing-a-development-branch`.

### Token-budget rationale

Extracting all task text upfront (vs letting workers re-read the plan file) costs one controller-side read of this file, then zero worker-side reads. Saves ~13 redundant file reads (one per task) plus prevents any worker from accidentally executing adjacent tasks' instructions.

---

## Task 1 — Config loader: add `custom_apis` and `widgets` to defaults

**Dispatch:** Batch A, parallel-safe. Cheap model. Spec refs: §4.1, §4.2. Reviewers: spec → code-quality.

**Files:**
- Modify: `src/forgeds/_shared/config.py:198-214`
- Create: `tests/test_config_widgets.py`

- [ ] **Step 1.1: Write the failing test**

Create `tests/test_config_widgets.py` with:

```python
"""Tests for widgets-related forgeds.yaml config extensions."""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import tempfile
from pathlib import Path

from forgeds._shared.config import load_config


def test_load_config_returns_empty_custom_apis_when_missing():
    """Defaults dict should include an empty custom_apis list."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = load_config(start=tmp)
        assert cfg.get("custom_apis") == []


def test_load_config_returns_empty_widgets_when_missing():
    """Defaults dict should include an empty widgets dict."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = load_config(start=tmp)
        assert cfg.get("widgets") == {}


def test_load_config_parses_custom_apis_list():
    """YAML custom_apis list should parse into config['custom_apis']."""
    yaml = (
        "project:\n"
        "  name: test\n"
        "  version: 0.0.1\n"
        "custom_apis:\n"
        "  - get_pending_claims\n"
        "  - approve_claim\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "forgeds.yaml").write_text(yaml, encoding="utf-8")
        cfg = load_config(start=tmp)
        assert cfg.get("custom_apis") == ["get_pending_claims", "approve_claim"]


def test_load_config_parses_widgets_dict():
    """YAML widgets dict-of-dicts should parse into config['widgets']."""
    yaml = (
        "project:\n"
        "  name: test\n"
        "  version: 0.0.1\n"
        "custom_apis:\n"
        "  - get_pending_claims\n"
        "widgets:\n"
        "  expense_dashboard:\n"
        "    root: src/widgets/expense_dashboard/\n"
        "    consumes_apis:\n"
        "      - get_pending_claims\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "forgeds.yaml").write_text(yaml, encoding="utf-8")
        cfg = load_config(start=tmp)
        widgets = cfg.get("widgets", {})
        assert "expense_dashboard" in widgets
        assert widgets["expense_dashboard"]["root"] == "src/widgets/expense_dashboard/"
        assert widgets["expense_dashboard"]["consumes_apis"] == ["get_pending_claims"]
```

- [ ] **Step 1.2: Run tests, confirm they fail**

Run: `pytest tests/test_config_widgets.py -v`

Expected: First two tests **FAIL** (current defaults dict lacks `custom_apis`/`widgets` keys, so `.get()` returns `None`, not `[]`/`{}`). Last two tests may pass or fail depending on whether the existing YAML parser handles the new keys — inspect output; the fail we need is the defaults-missing case.

- [ ] **Step 1.3: Modify the defaults dict**

In `src/forgeds/_shared/config.py`, find the `return { ... }` block at lines 198-214. Add two new keys just before the closing brace. The block becomes:

```python
    # Sensible defaults when no config exists
    return {
        "project": {"name": "Unknown", "version": "0.0.0"},
        "lint": {
            "threshold_fallback": "999.99",
            "dual_threshold_fallback": "5000.00",
            "demo_email_domains": ["yourdomain.com", "example.com", "placeholder.com"],
        },
        "schema": {
            "mandatory_zoho_fields": [],
            "table_to_form": {},
            "fk_relationships": [],
            "upload_order": [],
            "exclude_fields": ["ID", "Added_User"],
        },
        "seed_data_dir": "config/seed-data",
        "custom_apis": [],
        "widgets": {},
    }
```

- [ ] **Step 1.4: Run tests, confirm all pass**

Run: `pytest tests/test_config_widgets.py -v`

Expected: **4 passed**. If the YAML-parsing tests still fail, inspect the `_load_yaml_simple` function in the same file — it may need updating to handle list-of-strings or dict-of-dicts. Inspect output and iterate only if necessary.

- [ ] **Step 1.5: Commit**

```bash
git add src/forgeds/_shared/config.py tests/test_config_widgets.py
git commit -m "feat(widgets): add custom_apis and widgets to config defaults"
```

---

## Task 2 — SDK DB: schema, seed file, builder

**Dispatch:** Batch A, parallel-safe (disjoint from Tasks 1, 3, 5, 6). Standard model (multi-table SQL + seed integration). Spec refs: §3.1, §7, §7.1, §7.2. Reviewers: spec → code-quality.

**Files:**
- Create: `src/forgeds/widgets/__init__.py`
- Create: `src/forgeds/widgets/seed_data/widget_sdk_apis.json`
- Create: `src/forgeds/widgets/build_widget_sdk_db.py`
- Create: `tests/test_build_widget_sdk_db.py`

- [ ] **Step 2.1: Create package skeleton**

Create `src/forgeds/widgets/__init__.py` (empty file):

```python
"""ForgeDS widgets subsystem: JS lint orchestrator, SDK DB, manifest validator."""
```

Create `src/forgeds/widgets/seed_data/` directory (empty; next step populates it).

- [ ] **Step 2.2: Write seed data file**

Create `src/forgeds/widgets/seed_data/widget_sdk_apis.json` with 30 hand-curated entries. Full content:

```json
{
  "namespaces": [
    {"name": "ZOHO.CREATOR.API",   "description": "Zoho Creator data access API surface."},
    {"name": "ZOHO.CREATOR.UTIL",  "description": "Widget utility helpers (navigation, UI)."},
    {"name": "ZOHO.embeddedApp",   "description": "Lifecycle/init surface for embedded widgets."},
    {"name": "ZOHO.CREATOR.PUBLISH", "description": "Publish/embed management surface."}
  ],
  "methods": [
    {"namespace": "ZOHO.CREATOR.API", "name": "getRecords",         "signature": "(reportName, criteria, page, pageSize) => Promise<Response>", "returns_promise": 1, "required_permissions": "ZOHO.CREATOR.API.read",   "deprecated_in": null, "notes": "Fetch records from a report."},
    {"namespace": "ZOHO.CREATOR.API", "name": "getRecordById",      "signature": "(reportName, recordId) => Promise<Response>",                 "returns_promise": 1, "required_permissions": "ZOHO.CREATOR.API.read",   "deprecated_in": null, "notes": "Fetch one record by ID."},
    {"namespace": "ZOHO.CREATOR.API", "name": "addRecords",         "signature": "(formName, payload) => Promise<Response>",                    "returns_promise": 1, "required_permissions": "ZOHO.CREATOR.API.write",  "deprecated_in": null, "notes": "Create one or more records."},
    {"namespace": "ZOHO.CREATOR.API", "name": "updateRecord",       "signature": "(reportName, recordId, payload) => Promise<Response>",        "returns_promise": 1, "required_permissions": "ZOHO.CREATOR.API.write",  "deprecated_in": null, "notes": "Update a single record."},
    {"namespace": "ZOHO.CREATOR.API", "name": "deleteRecord",       "signature": "(reportName, recordId) => Promise<Response>",                 "returns_promise": 1, "required_permissions": "ZOHO.CREATOR.API.write",  "deprecated_in": null, "notes": "Delete a single record."},
    {"namespace": "ZOHO.CREATOR.API", "name": "bulkUpdateRecords",  "signature": "(reportName, criteria, payload) => Promise<Response>",        "returns_promise": 1, "required_permissions": "ZOHO.CREATOR.API.write",  "deprecated_in": null, "notes": "Update many records matching criteria."},
    {"namespace": "ZOHO.CREATOR.API", "name": "uploadFile",         "signature": "(reportName, recordId, fieldName, file) => Promise<Response>","returns_promise": 1, "required_permissions": "ZOHO.CREATOR.API.write",  "deprecated_in": null, "notes": "Attach file to a record's file field."},
    {"namespace": "ZOHO.CREATOR.API", "name": "downloadFile",       "signature": "(reportName, recordId, fieldName) => Promise<Blob>",          "returns_promise": 1, "required_permissions": "ZOHO.CREATOR.API.read",   "deprecated_in": null, "notes": "Download file field content."},
    {"namespace": "ZOHO.CREATOR.API", "name": "getFileContent",     "signature": "(filepath) => Promise<Blob>",                                 "returns_promise": 1, "required_permissions": "ZOHO.CREATOR.API.read",   "deprecated_in": null, "notes": "Get file content by path."},
    {"namespace": "ZOHO.CREATOR.API", "name": "invokeConnection",   "signature": "(connectionName, payload) => Promise<Response>",              "returns_promise": 1, "required_permissions": "ZOHO.CREATOR.API.read",   "deprecated_in": null, "notes": "Invoke a Creator connection."},
    {"namespace": "ZOHO.CREATOR.API", "name": "invokeApi",          "signature": "(apiName, payload) => Promise<Response>",                     "returns_promise": 1, "required_permissions": "ZOHO.CREATOR.API.read",   "deprecated_in": null, "notes": "Invoke a server-side Custom API by name."},
    {"namespace": "ZOHO.CREATOR.API", "name": "invokeCustomApi",    "signature": "(apiName, payload) => Promise<Response>",                     "returns_promise": 1, "required_permissions": "ZOHO.CREATOR.API.read",   "deprecated_in": null, "notes": "Alias of invokeApi; used by newer SDKs."},
    {"namespace": "ZOHO.CREATOR.API", "name": "callFunction",       "signature": "(functionName, payload) => Promise<Response>",                "returns_promise": 1, "required_permissions": "ZOHO.CREATOR.API.read",   "deprecated_in": null, "notes": "Call a public Deluge function."},
    {"namespace": "ZOHO.CREATOR.UTIL","name": "navigateTo",         "signature": "(pageLinkName) => void",                                      "returns_promise": 0, "required_permissions": null,                         "deprecated_in": null, "notes": "Navigate the embedding Creator app to a page."},
    {"namespace": "ZOHO.CREATOR.UTIL","name": "showAlert",          "signature": "(message) => void",                                           "returns_promise": 0, "required_permissions": null,                         "deprecated_in": null, "notes": "Display an alert modal to the user."},
    {"namespace": "ZOHO.CREATOR.UTIL","name": "showPrompt",         "signature": "(message) => Promise<string>",                                "returns_promise": 1, "required_permissions": null,                         "deprecated_in": null, "notes": "Prompt the user for a text value."},
    {"namespace": "ZOHO.CREATOR.UTIL","name": "closeWidget",        "signature": "() => void",                                                  "returns_promise": 0, "required_permissions": null,                         "deprecated_in": null, "notes": "Close the current widget pane."},
    {"namespace": "ZOHO.embeddedApp", "name": "init",               "signature": "() => Promise<void>",                                         "returns_promise": 1, "required_permissions": null,                         "deprecated_in": null, "notes": "Initialise the embedded app; call once on widget load."},
    {"namespace": "ZOHO.embeddedApp", "name": "on",                 "signature": "(eventName, handler) => void",                                "returns_promise": 0, "required_permissions": null,                         "deprecated_in": null, "notes": "Subscribe to a widget lifecycle event."},
    {"namespace": "ZOHO.embeddedApp", "name": "getInitParams",      "signature": "() => object",                                                "returns_promise": 0, "required_permissions": null,                         "deprecated_in": null, "notes": "Get params the host page provided at init."},
    {"namespace": "ZOHO.embeddedApp", "name": "getUserInfo",        "signature": "() => Promise<UserInfo>",                                     "returns_promise": 1, "required_permissions": null,                         "deprecated_in": null, "notes": "Get current user's profile."},
    {"namespace": "ZOHO.embeddedApp", "name": "logout",             "signature": "() => Promise<void>",                                         "returns_promise": 1, "required_permissions": null,                         "deprecated_in": null, "notes": "Log user out of the embedding session."},
    {"namespace": "ZOHO.CREATOR.PUBLISH","name": "publish",         "signature": "(targetEnv) => Promise<Response>",                            "returns_promise": 1, "required_permissions": "ZOHO.CREATOR.API.publish","deprecated_in": null, "notes": "Publish widget to target environment."},
    {"namespace": "ZOHO.CREATOR.PUBLISH","name": "unpublish",       "signature": "() => Promise<Response>",                                     "returns_promise": 1, "required_permissions": "ZOHO.CREATOR.API.publish","deprecated_in": null, "notes": "Unpublish widget from all environments."}
  ],
  "events": [
    {"name": "PageLoad",    "trigger": "on widget iframe load",            "payload_shape": "{page: string}",                 "notes": "Fires once per navigation."},
    {"name": "RecordSave",  "trigger": "after record successfully saved",  "payload_shape": "{recordId: string, form: string}","notes": "Fires in embedded-form context only."},
    {"name": "RecordDelete","trigger": "after record deletion",            "payload_shape": "{recordId: string}",             "notes": "Fires in embedded-form context only."},
    {"name": "FieldChange", "trigger": "when a bound field value changes", "payload_shape": "{field: string, value: any}",    "notes": "Rate-limited; debounce in handler."}
  ],
  "permissions": [
    {"scope": "ZOHO.CREATOR.API.read",    "description": "Read records from Creator apps."},
    {"scope": "ZOHO.CREATOR.API.write",   "description": "Create/update/delete records."},
    {"scope": "ZOHO.CREATOR.API.publish", "description": "Publish/unpublish widget versions."}
  ],
  "globals": [
    {"name": "ZOHO",    "kind": "namespace"},
    {"name": "Creator", "kind": "object"},
    {"name": "$",       "kind": "object"}
  ]
}
```

**Count check:** 4 namespaces + 24 methods + 4 events + 3 permissions + 3 globals = 38 rows. The spec targets "~30 SDK entries"; this is close enough. Do not trim.

- [ ] **Step 2.3: Write failing test for the DB builder**

Create `tests/test_build_widget_sdk_db.py`:

```python
"""Tests for forgeds.widgets.build_widget_sdk_db — zoho_widget_sdk.db builder."""

from __future__ import annotations

import sqlite3
import sys, os
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from forgeds.widgets.build_widget_sdk_db import build_db


def test_build_db_creates_all_tables(tmp_path):
    """Builder should create 5 tables with correct names."""
    db_path = tmp_path / "zoho_widget_sdk.db"
    build_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cur.fetchall()]
        assert set(tables) == {
            "sdk_namespaces",
            "sdk_methods",
            "sdk_events",
            "sdk_permissions",
            "zoho_widget_globals",
        }
    finally:
        conn.close()


def test_build_db_populates_namespaces(tmp_path):
    db_path = tmp_path / "zoho_widget_sdk.db"
    build_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sdk_namespaces")
        names = {row[0] for row in cur.fetchall()}
        assert "ZOHO.CREATOR.API" in names
        assert "ZOHO.embeddedApp" in names
    finally:
        conn.close()


def test_build_db_populates_methods(tmp_path):
    db_path = tmp_path / "zoho_widget_sdk.db"
    build_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM sdk_methods")
        count = cur.fetchone()[0]
        assert count >= 20, f"expected ≥20 seeded methods, got {count}"
        cur.execute("SELECT name FROM sdk_methods WHERE namespace='ZOHO.CREATOR.API' AND name='getRecords'")
        assert cur.fetchone() is not None
    finally:
        conn.close()


def test_build_db_populates_globals(tmp_path):
    db_path = tmp_path / "zoho_widget_sdk.db"
    build_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM zoho_widget_globals")
        names = {row[0] for row in cur.fetchall()}
        assert names == {"ZOHO", "Creator", "$"}
    finally:
        conn.close()
```

- [ ] **Step 2.4: Run tests, confirm ImportError**

Run: `pytest tests/test_build_widget_sdk_db.py -v`

Expected: All tests **FAIL** with `ModuleNotFoundError: No module named 'forgeds.widgets.build_widget_sdk_db'`.

- [ ] **Step 2.5: Write the DB builder**

Create `src/forgeds/widgets/build_widget_sdk_db.py`:

```python
"""Build zoho_widget_sdk.db from seed_data/widget_sdk_apis.json.

Mirrors the forgeds.core.build_deluge_db pattern but with an SDK-shaped
schema: namespaces + methods + events + permissions + globals.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from forgeds._shared.config import get_db_dir

SEED_FILE = Path(__file__).parent / "seed_data" / "widget_sdk_apis.json"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sdk_namespaces (
  name TEXT PRIMARY KEY,
  description TEXT
);

CREATE TABLE IF NOT EXISTS sdk_methods (
  namespace TEXT NOT NULL,
  name TEXT NOT NULL,
  signature TEXT NOT NULL,
  returns_promise INTEGER NOT NULL,
  required_permissions TEXT,
  deprecated_in TEXT,
  notes TEXT,
  PRIMARY KEY (namespace, name)
);

CREATE TABLE IF NOT EXISTS sdk_events (
  name TEXT PRIMARY KEY,
  trigger TEXT NOT NULL,
  payload_shape TEXT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS sdk_permissions (
  scope TEXT PRIMARY KEY,
  description TEXT
);

CREATE TABLE IF NOT EXISTS zoho_widget_globals (
  name TEXT PRIMARY KEY,
  kind TEXT NOT NULL
);
"""


def build_db(db_path: Path) -> None:
    """Create zoho_widget_sdk.db at db_path and populate from seed JSON."""
    if db_path.exists():
        db_path.unlink()

    with open(SEED_FILE, encoding="utf-8") as f:
        seed = json.load(f)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(SCHEMA_SQL)

        conn.executemany(
            "INSERT INTO sdk_namespaces (name, description) VALUES (?, ?)",
            [(n["name"], n.get("description")) for n in seed["namespaces"]],
        )

        conn.executemany(
            """
            INSERT INTO sdk_methods
              (namespace, name, signature, returns_promise, required_permissions, deprecated_in, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    m["namespace"],
                    m["name"],
                    m["signature"],
                    int(m["returns_promise"]),
                    m.get("required_permissions"),
                    m.get("deprecated_in"),
                    m.get("notes"),
                )
                for m in seed["methods"]
            ],
        )

        conn.executemany(
            "INSERT INTO sdk_events (name, trigger, payload_shape, notes) VALUES (?, ?, ?, ?)",
            [
                (e["name"], e["trigger"], e.get("payload_shape"), e.get("notes"))
                for e in seed["events"]
            ],
        )

        conn.executemany(
            "INSERT INTO sdk_permissions (scope, description) VALUES (?, ?)",
            [(p["scope"], p.get("description")) for p in seed["permissions"]],
        )

        conn.executemany(
            "INSERT INTO zoho_widget_globals (name, kind) VALUES (?, ?)",
            [(g["name"], g["kind"]) for g in seed["globals"]],
        )

        conn.commit()
    finally:
        conn.close()


def main() -> int:
    db_dir = get_db_dir()
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "zoho_widget_sdk.db"
    try:
        build_db(db_path)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"built {db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2.6: Run tests, confirm all pass**

Run: `pytest tests/test_build_widget_sdk_db.py -v`

Expected: **4 passed**.

- [ ] **Step 2.7: Commit**

```bash
git add src/forgeds/widgets/__init__.py \
        src/forgeds/widgets/seed_data/widget_sdk_apis.json \
        src/forgeds/widgets/build_widget_sdk_db.py \
        tests/test_build_widget_sdk_db.py
git commit -m "feat(widgets): add zoho_widget_sdk.db schema, seed data, builder"
```

---

## Task 3 — Plugin manifest JSON Schema file

**Dispatch:** Batch A, parallel-safe. Cheap model (single-file JSON authoring). Spec refs: §10.1. Reviewers: spec → code-quality.

**Files:**
- Create: `src/forgeds/widgets/configs/plugin-manifest.schema.json`

- [ ] **Step 3.1: Create configs directory and schema file**

Create `src/forgeds/widgets/configs/plugin-manifest.schema.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Zoho Creator plugin-manifest.json",
  "type": "object",
  "required": ["name", "version", "config"],
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    },
    "version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+$"
    },
    "config": {
      "type": "object",
      "required": ["widgets"],
      "properties": {
        "widgets": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["location", "url"],
            "properties": {
              "location": {"type": "string", "minLength": 1},
              "url":      {"type": "string", "minLength": 1}
            }
          }
        }
      }
    },
    "permissions": {
      "type": "array",
      "items": {"type": "string"}
    }
  }
}
```

- [ ] **Step 3.2: Sanity-check JSON parses**

Run: `python -c "import json, pathlib; json.loads(pathlib.Path('src/forgeds/widgets/configs/plugin-manifest.schema.json').read_text())"`

Expected: no output (clean exit = valid JSON).

- [ ] **Step 3.3: Commit**

```bash
git add src/forgeds/widgets/configs/plugin-manifest.schema.json
git commit -m "feat(widgets): add plugin-manifest JSON Schema"
```

---

## Task 4 — Manifest validator (stdlib-only JSON Schema subset)

**Dispatch:** Batch B, serial after Task 3 completes. Standard model (non-trivial validator logic). Spec refs: §10.2. Reviewers: spec → code-quality.

**Files:**
- Create: `src/forgeds/widgets/validate_manifest.py`
- Create: `tests/fixtures/widgets/good_widget/plugin-manifest.json`
- Create: `tests/fixtures/widgets/bad_widget_invalid_manifest/plugin-manifest.json`
- Create: `tests/test_validate_manifest.py`

- [ ] **Step 4.1: Create fixture manifests**

Create `tests/fixtures/widgets/good_widget/plugin-manifest.json`:

```json
{
  "name": "good_widget",
  "version": "1.0.0",
  "config": {
    "widgets": [
      {"location": "sidebar", "url": "index.html"}
    ]
  },
  "permissions": ["ZOHO.CREATOR.API.read"]
}
```

Create `tests/fixtures/widgets/bad_widget_invalid_manifest/plugin-manifest.json` (bad version string, missing `config`):

```json
{
  "name": "bad_widget",
  "version": "not-semver"
}
```

- [ ] **Step 4.2: Write failing tests for the validator**

Create `tests/test_validate_manifest.py`:

```python
"""Tests for forgeds.widgets.validate_manifest."""

from __future__ import annotations

import sys, os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from forgeds._shared.diagnostics import Severity
from forgeds.widgets.validate_manifest import validate_manifest_file

FIXTURES = Path(__file__).parent / "fixtures" / "widgets"


def test_good_manifest_returns_no_diagnostics():
    path = FIXTURES / "good_widget" / "plugin-manifest.json"
    diags = validate_manifest_file(str(path))
    assert diags == [], f"unexpected diagnostics: {diags}"


def test_bad_manifest_bad_version_produces_error():
    path = FIXTURES / "bad_widget_invalid_manifest" / "plugin-manifest.json"
    diags = validate_manifest_file(str(path))
    assert any(d.severity == Severity.ERROR for d in diags)
    assert any("version" in d.message.lower() for d in diags)


def test_bad_manifest_missing_required_produces_error():
    path = FIXTURES / "bad_widget_invalid_manifest" / "plugin-manifest.json"
    diags = validate_manifest_file(str(path))
    assert any("config" in d.message.lower() and "required" in d.message.lower() for d in diags)


def test_missing_file_produces_error():
    diags = validate_manifest_file(str(FIXTURES / "nonexistent" / "plugin-manifest.json"))
    assert len(diags) == 1
    assert diags[0].severity == Severity.ERROR
    assert "not found" in diags[0].message.lower() or "missing" in diags[0].message.lower()
```

- [ ] **Step 4.3: Run tests, confirm ImportError**

Run: `pytest tests/test_validate_manifest.py -v`

Expected: All tests **FAIL** with `ModuleNotFoundError: No module named 'forgeds.widgets.validate_manifest'`.

- [ ] **Step 4.4: Write the validator**

Create `src/forgeds/widgets/validate_manifest.py`:

```python
"""Stdlib-only JSON Schema (draft-07 subset) validator for plugin-manifest.json.

Supported keywords:
  type, required, enum, pattern, minLength, properties, items,
  additionalProperties (bool form only).

Intentionally limited. Promote to `jsonschema` as soft-optional dep
if the subset proves inadequate.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from forgeds._shared.diagnostics import Diagnostic, Severity

SCHEMA_PATH = Path(__file__).parent / "configs" / "plugin-manifest.schema.json"

_JSON_TYPES = {
    "string":  str,
    "integer": int,
    "number":  (int, float),
    "boolean": bool,
    "array":   list,
    "object":  dict,
    "null":    type(None),
}


def _diag(file: str, line: int, severity: Severity, code: str, message: str) -> Diagnostic:
    return Diagnostic(file=file, line=line, rule=code, severity=severity, message=message)


def _validate(
    instance, schema: dict, path: str, file: str, out: list[Diagnostic],
) -> None:
    t = schema.get("type")
    if t is not None:
        py = _JSON_TYPES.get(t)
        # Special-case: integer is not bool, but bool is int in Python
        if t == "integer" and isinstance(instance, bool):
            out.append(_diag(file, 1, Severity.ERROR, "WG-SCHEMA",
                             f"{path}: expected integer, got boolean"))
            return
        if py is not None and not isinstance(instance, py):
            out.append(_diag(file, 1, Severity.ERROR, "WG-SCHEMA",
                             f"{path}: expected {t}, got {type(instance).__name__}"))
            return

    if "enum" in schema and instance not in schema["enum"]:
        out.append(_diag(file, 1, Severity.ERROR, "WG-SCHEMA",
                         f"{path}: value {instance!r} not in enum {schema['enum']}"))

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            out.append(_diag(file, 1, Severity.ERROR, "WG-SCHEMA",
                             f"{path}: string shorter than minLength {schema['minLength']}"))
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            out.append(_diag(file, 1, Severity.ERROR, "WG-SCHEMA",
                             f"{path}: does not match pattern {schema['pattern']!r} (value: {instance!r})"))

    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                out.append(_diag(file, 1, Severity.ERROR, "WG-SCHEMA",
                                 f"{path}: missing required property {req!r}"))
        props = schema.get("properties", {})
        for key, val in instance.items():
            if key in props:
                _validate(val, props[key], f"{path}.{key}" if path else key, file, out)
            elif schema.get("additionalProperties") is False:
                out.append(_diag(file, 1, Severity.ERROR, "WG-SCHEMA",
                                 f"{path}: additional property {key!r} not allowed"))

    if isinstance(instance, list):
        items_schema = schema.get("items")
        if items_schema is not None:
            for i, item in enumerate(instance):
                _validate(item, items_schema, f"{path}[{i}]", file, out)


def validate_manifest_file(path: str) -> list[Diagnostic]:
    """Validate one plugin-manifest.json file. Returns list of Diagnostics."""
    p = Path(path)
    if not p.exists():
        return [_diag(path, 1, Severity.ERROR, "WG-SCHEMA",
                      f"plugin-manifest.json not found at {path}")]

    try:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
    except OSError as exc:
        return [_diag(path, 1, Severity.ERROR, "WG-SCHEMA",
                      f"failed to load schema: {exc}")]

    try:
        with open(p, encoding="utf-8") as f:
            instance = json.load(f)
    except json.JSONDecodeError as exc:
        return [_diag(path, exc.lineno, Severity.ERROR, "WG-SCHEMA",
                      f"invalid JSON: {exc.msg}")]
    except OSError as exc:
        return [_diag(path, 1, Severity.ERROR, "WG-SCHEMA",
                      f"could not read file: {exc}")]

    diagnostics: list[Diagnostic] = []
    _validate(instance, schema, path="", file=path, out=diagnostics)
    return diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Zoho Creator plugin-manifest.json files against the ForgeDS schema."
    )
    parser.add_argument("paths", nargs="+", help="plugin-manifest.json file paths")
    args = parser.parse_args()

    all_diags: list[Diagnostic] = []
    for path in args.paths:
        all_diags.extend(validate_manifest_file(path))

    for d in all_diags:
        print(str(d))

    if any(d.severity == Severity.ERROR for d in all_diags):
        return 2
    if any(d.severity == Severity.WARNING for d in all_diags):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4.5: Run tests, confirm all pass**

Run: `pytest tests/test_validate_manifest.py -v`

Expected: **4 passed**.

- [ ] **Step 4.6: Commit**

```bash
git add src/forgeds/widgets/validate_manifest.py \
        tests/test_validate_manifest.py \
        tests/fixtures/widgets/good_widget/plugin-manifest.json \
        tests/fixtures/widgets/bad_widget_invalid_manifest/plugin-manifest.json
git commit -m "feat(widgets): add stdlib JSON Schema manifest validator"
```

---

## Task 5 — Parser investigation (G7)

**Dispatch:** Batch A, parallel-safe. Cheap model (read-only grep + notes). Spec refs: §13. Reviewers: spec only (no code to quality-review).

**Files:**
- Read: sample `.ds` files under `tests/fixtures/`
- Document findings (will update `CLAUDE.md` in Task 13)

- [ ] **Step 5.1: Grep sample .ds exports for widget tokens**

Run (these are read-only, no file changes):

```bash
grep -l -i -E "widget|plugin|script-source" tests/fixtures/*.ds 2>/dev/null
grep -i -E "widget|plugin" tests/fixtures/validate_ds_good.ds 2>/dev/null | head -20
```

Record the output. If nothing matches → hypothesis confirmed (widgets not in .ds). If something matches → read those lines fully and record the surrounding context.

- [ ] **Step 5.2: Write findings to a scratch file**

Create `docs/superpowers/specs/2026-04-22-g7-parser-investigation-notes.md`:

```markdown
# G7 — .ds parser investigation notes

**Date:** 2026-04-22

## Question
Does `.ds` carry widget references or blobs?

## Method
- Grep `tests/fixtures/*.ds` for tokens: `widget`, `plugin`, `script-source`
- Inspect any matches for context

## Findings
<FILL IN BASED ON STEP 5.1 OUTPUT. One of:>

### If no matches:
`.ds` exports do not carry widget references. Widgets are packaged
separately as zip blobs (manifest + JS/HTML/CSS) and uploaded via the
Creator portal. `parse_ds_export.py` needs no changes.

### If matches found:
Record file paths, line numbers, and surrounding context. Promote G7
from investigation to code-work; file a Phase 2 ticket to extend
parse_ds_export.py. Phase 1 still ships without parser changes.

## Decision
<FILL IN: no code changes / Phase 2 ticket filed>
```

- [ ] **Step 5.3: Commit notes**

```bash
git add docs/superpowers/specs/2026-04-22-g7-parser-investigation-notes.md
git commit -m "docs(widgets): G7 parser investigation findings"
```

(The CLAUDE.md summary update happens in Task 13 to keep docs together.)

---

## Task 6 — `.eslintrc.zoho.json` curated config

**Dispatch:** Batch A, parallel-safe. Cheap model (single-file JSON authoring). Spec refs: §9.2. Reviewers: spec → code-quality.

**Files:**
- Create: `src/forgeds/widgets/configs/.eslintrc.zoho.json`

- [ ] **Step 6.1: Create the config file**

Create `src/forgeds/widgets/configs/.eslintrc.zoho.json`:

```json
{
  "extends": ["eslint:recommended"],
  "env": {
    "browser": true,
    "es2021": true
  },
  "globals": {
    "ZOHO": "readonly",
    "Creator": "readonly",
    "$": "readonly"
  },
  "parserOptions": {
    "ecmaVersion": 2021,
    "sourceType": "module"
  }
}
```

- [ ] **Step 6.2: Sanity-check JSON parses**

Run: `python -c "import json, pathlib; json.loads(pathlib.Path('src/forgeds/widgets/configs/.eslintrc.zoho.json').read_text())"`

Expected: no output.

- [ ] **Step 6.3: Commit**

```bash
git add src/forgeds/widgets/configs/.eslintrc.zoho.json
git commit -m "feat(widgets): add curated ESLint config with Zoho globals"
```

---

## Task 7 — ESLint orchestrator (`lint_widgets.py`)

**Dispatch:** Batch C, serial after Batches A+B complete. Standard model (multi-file, subprocess, JSON envelope design, many fixtures). Spec refs: §5.2, §5, §6, §9, §11. Reviewers: spec → code-quality. **Controller must pass:** implementation of `_shared/diagnostics.py` (for `Diagnostic`/`Severity` types) and the config loader's widget dict shape from Task 1.

**Files:**
- Create: `src/forgeds/widgets/lint_widgets.py`
- Create: `tests/fixtures/widgets/forgeds.yaml`
- Create: `tests/fixtures/widgets/good_widget/index.js`
- Create: `tests/fixtures/widgets/bad_widget_missing_manifest/index.js`
- Create: `tests/fixtures/widgets/bad_widget_invalid_manifest/index.js`
- Create: `tests/fixtures/widgets/bad_widget_undeclared_api/index.js`
- Create: `tests/fixtures/widgets/bad_widget_undeclared_api/plugin-manifest.json`
- Create: `tests/test_lint_widgets.py`

- [ ] **Step 7.1: Create fixture forgeds.yaml and widget sources**

Create `tests/fixtures/widgets/forgeds.yaml`:

```yaml
project:
  name: "widget_fixture"
  version: "0.0.1"

custom_apis:
  - get_pending_claims
  - approve_claim

widgets:
  good_widget:
    root: tests/fixtures/widgets/good_widget/
    consumes_apis: [get_pending_claims]
  bad_widget_missing_manifest:
    root: tests/fixtures/widgets/bad_widget_missing_manifest/
    consumes_apis: [get_pending_claims]
  bad_widget_invalid_manifest:
    root: tests/fixtures/widgets/bad_widget_invalid_manifest/
    consumes_apis: [get_pending_claims]
  bad_widget_undeclared_api:
    root: tests/fixtures/widgets/bad_widget_undeclared_api/
    consumes_apis: [undeclared_api_name]
```

Create `tests/fixtures/widgets/good_widget/index.js`:

```javascript
/* Good widget fixture — should pass ESLint. */
ZOHO.embeddedApp.on('PageLoad', function (data) {
  ZOHO.CREATOR.API.invokeApi('get_pending_claims', { page: 1 });
});
ZOHO.embeddedApp.init();
```

Create `tests/fixtures/widgets/bad_widget_missing_manifest/index.js`:

```javascript
/* Widget with no plugin-manifest.json sibling. */
ZOHO.embeddedApp.init();
```

Create `tests/fixtures/widgets/bad_widget_invalid_manifest/index.js`:

```javascript
/* Widget whose manifest already fails validation. */
ZOHO.embeddedApp.init();
```

Create `tests/fixtures/widgets/bad_widget_undeclared_api/plugin-manifest.json`:

```json
{
  "name": "bad_widget_undeclared_api",
  "version": "1.0.0",
  "config": {
    "widgets": [
      {"location": "sidebar", "url": "index.html"}
    ]
  },
  "permissions": ["ZOHO.CREATOR.API.read"]
}
```

Create `tests/fixtures/widgets/bad_widget_undeclared_api/index.js`:

```javascript
/* Widget that declares consumes_apis pointing at an undeclared API. */
ZOHO.CREATOR.API.invokeApi('undeclared_api_name', {});
```

- [ ] **Step 7.2: Write failing tests for the orchestrator**

Create `tests/test_lint_widgets.py`:

```python
"""Tests for forgeds.widgets.lint_widgets — ESLint orchestrator."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import forgeds.widgets.lint_widgets as lw


def test_eslint_missing_returns_exit_3(capsys):
    """When `npx eslint --version` fails, main() must exit 3 with an install hint."""
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("npx not found")

    with patch.object(lw.subprocess, "run", side_effect=fake_run):
        rc = lw.main(["--no-args-discover"])  # CLI args placeholder; see impl
    assert rc == 3
    captured = capsys.readouterr()
    assert "eslint" in captured.err.lower()
    assert "install" in captured.err.lower()


def test_emit_text_format_matches_shared_diag(capsys):
    """Text mode prints Diagnostic.__str__ output, one per line."""
    diags = [
        lw._mk_diag("src/widgets/x/index.js", 1, "JS:no-unused-vars", "WARNING", "unused variable"),
    ]
    lw._emit(diags, fmt="text")
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1
    assert "src/widgets/x/index.js:1:" in out[0]
    assert "[JS:no-unused-vars]" in out[0]
    assert "WARNING" in out[0]


def test_emit_json_envelope_shape(capsys):
    """JSON mode emits the v1 envelope with tool/version/diagnostics keys."""
    diags = [
        lw._mk_diag("a.js", 2, "JS:semi", "ERROR", "missing semicolon"),
    ]
    lw._emit(diags, fmt="json")
    payload = json.loads(capsys.readouterr().out)
    assert payload["tool"] == "forgeds-lint-widgets"
    assert payload["version"] == "1"
    assert len(payload["diagnostics"]) == 1
    d = payload["diagnostics"][0]
    assert d["file"] == "a.js"
    assert d["line"] == 2
    assert d["rule"] == "JS:semi"
    assert d["severity"] == "error"
    assert d["message"] == "missing semicolon"


def test_translate_eslint_result_maps_severity():
    """ESLint severity 2 → ERROR, 1 → WARNING; severity 0 is dropped."""
    eslint_json = [
        {
            "filePath": "/abs/a.js",
            "messages": [
                {"line": 1, "ruleId": "no-unused-vars", "severity": 1, "message": "unused"},
                {"line": 2, "ruleId": "no-undef",       "severity": 2, "message": "undef"},
                {"line": 3, "ruleId": "off-rule",       "severity": 0, "message": "ignored"},
            ],
        }
    ]
    diags = lw._translate_eslint(eslint_json)
    assert len(diags) == 2
    by_rule = {d.rule: d for d in diags}
    assert by_rule["JS:no-unused-vars"].severity.value == "WARNING"
    assert by_rule["JS:no-undef"].severity.value == "ERROR"
```

- [ ] **Step 7.3: Run tests, confirm ImportError**

Run: `pytest tests/test_lint_widgets.py -v`

Expected: All tests **FAIL** with `ModuleNotFoundError: No module named 'forgeds.widgets.lint_widgets'`.

- [ ] **Step 7.4: Write the orchestrator**

Create `src/forgeds/widgets/lint_widgets.py`:

```python
"""ESLint orchestrator for Zoho Creator widgets.

Shells out to `npx eslint` using the curated config at
`configs/.eslintrc.zoho.json`. Translates ESLint JSON output into
ForgeDS Diagnostic objects (rule prefix `JS:` signals foreign provenance).

Emits text format (matching other linters) by default; `--format json`
emits the v1 envelope intended for downstream verification agents.

Exit codes:
  0 clean, 1 warnings, 2 errors, 3 toolchain missing.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from forgeds._shared.config import find_project_root, load_config
from forgeds._shared.diagnostics import Diagnostic, Severity

CONFIG_PATH = Path(__file__).parent / "configs" / ".eslintrc.zoho.json"
ESLINT_CMD = ["npx", "--yes", "eslint"]  # --yes: auto-accept npx prompt

INSTALL_HINT = (
    "ESLint/Node not found. forgeds-lint-widgets requires Node ≥ 18 and ESLint 8+.\n"
    "  Install globally:      npm i -g eslint\n"
    "  Or per-project:        npm i --save-dev eslint\n"
)


def _mk_diag(file: str, line: int, rule: str, severity: str, message: str) -> Diagnostic:
    sev = {"ERROR": Severity.ERROR, "WARNING": Severity.WARNING, "INFO": Severity.INFO}[severity]
    return Diagnostic(file=file, line=line, rule=rule, severity=sev, message=message)


def _eslint_available() -> bool:
    try:
        r = subprocess.run(
            ESLINT_CMD + ["--version"],
            capture_output=True, text=True, timeout=15,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _translate_eslint(eslint_json: list[dict]) -> list[Diagnostic]:
    """Translate ESLint JSON output to ForgeDS Diagnostics.

    ESLint severity: 0=off (dropped), 1=warn, 2=error.
    """
    sev_map = {1: "WARNING", 2: "ERROR"}
    out: list[Diagnostic] = []
    for file_result in eslint_json:
        file_path = file_result.get("filePath", "<unknown>")
        for msg in file_result.get("messages", []):
            sev_num = msg.get("severity", 0)
            if sev_num not in sev_map:
                continue
            rule_id = msg.get("ruleId") or "unknown"
            out.append(_mk_diag(
                file=file_path,
                line=int(msg.get("line", 1)),
                rule=f"JS:{rule_id}",
                severity=sev_map[sev_num],
                message=str(msg.get("message", "")),
            ))
    return out


def _run_eslint_on(paths: list[str]) -> list[Diagnostic]:
    """Invoke ESLint and parse JSON output. Returns Diagnostics."""
    if not paths:
        return []
    cmd = ESLINT_CMD + ["-c", str(CONFIG_PATH), "--format", "json", "--no-eslintrc"] + paths
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    # ESLint exits 0 clean, 1 with findings, 2 with fatal error. JSON valid for 0 and 1.
    if r.returncode >= 2 and not r.stdout.strip():
        # fatal error, no parseable output
        return [_mk_diag("<eslint>", 1, "JS:fatal", "ERROR", (r.stderr or "ESLint fatal error").strip())]
    try:
        parsed = json.loads(r.stdout or "[]")
    except json.JSONDecodeError:
        return [_mk_diag("<eslint>", 1, "JS:parse-error", "ERROR",
                         f"could not parse ESLint JSON output: {r.stdout[:200]!r}")]
    return _translate_eslint(parsed)


def _discover_js_files(widget_root: Path) -> list[str]:
    """Return .js files under widget_root (recursive)."""
    if not widget_root.is_dir():
        return []
    return [str(p) for p in sorted(widget_root.rglob("*.js"))]


def _emit(diagnostics: list[Diagnostic], fmt: str) -> None:
    if fmt == "json":
        payload = {
            "tool": "forgeds-lint-widgets",
            "version": "1",
            "diagnostics": [
                {
                    "file": d.file,
                    "line": d.line,
                    "rule": d.rule,
                    "severity": d.severity.value.lower(),
                    "message": d.message,
                }
                for d in diagnostics
            ],
        }
        print(json.dumps(payload))
    else:
        for d in diagnostics:
            print(str(d))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lint Zoho Creator widget JavaScript via ESLint with a ForgeDS-curated config."
    )
    parser.add_argument("paths", nargs="*", help="Optional explicit file/dir paths. "
                        "If omitted, widget roots are discovered from forgeds.yaml config['widgets'].")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress INFO diagnostics.")
    parser.add_argument("--errors-only", action="store_true", help="Suppress WARNING and INFO diagnostics.")
    parser.add_argument("--no-args-discover", action="store_true",
                        help=argparse.SUPPRESS)  # test hook
    args = parser.parse_args(argv)

    if not _eslint_available():
        print(INSTALL_HINT, file=sys.stderr)
        return 3

    targets: list[str] = list(args.paths)
    if not targets and not args.no_args_discover:
        cfg = load_config()
        root = find_project_root()
        for _widget_name, decl in (cfg.get("widgets") or {}).items():
            w_root = root / decl.get("root", "")
            targets.extend(_discover_js_files(w_root))

    diagnostics = _run_eslint_on(targets) if targets else []

    if args.quiet:
        diagnostics = [d for d in diagnostics if d.severity != Severity.INFO]
    if args.errors_only:
        diagnostics = [d for d in diagnostics if d.severity == Severity.ERROR]

    _emit(diagnostics, fmt=args.format)

    if any(d.severity == Severity.ERROR for d in diagnostics):
        return 2
    if any(d.severity == Severity.WARNING for d in diagnostics):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 7.5: Run tests, confirm all pass**

Run: `pytest tests/test_lint_widgets.py -v`

Expected: **4 passed**. (Tests avoid shelling to real npx/eslint — they mock `subprocess.run` and test pure-Python helpers `_emit`, `_mk_diag`, `_translate_eslint`.)

- [ ] **Step 7.6: Commit**

```bash
git add src/forgeds/widgets/lint_widgets.py \
        tests/test_lint_widgets.py \
        tests/fixtures/widgets/forgeds.yaml \
        tests/fixtures/widgets/good_widget/index.js \
        tests/fixtures/widgets/bad_widget_missing_manifest/index.js \
        tests/fixtures/widgets/bad_widget_invalid_manifest/index.js \
        tests/fixtures/widgets/bad_widget_undeclared_api/index.js \
        tests/fixtures/widgets/bad_widget_undeclared_api/plugin-manifest.json
git commit -m "feat(widgets): add ESLint orchestrator with JSON envelope v1"
```

---

## Task 8 — Hybrid rule WG001: widget `root` directory missing

**Dispatch:** Batch D.1, strictly serial (shares `lint_hybrid.py` with Tasks 9, 10). Standard model. Spec refs: §8 (WG001 row), §12. Reviewers: spec → code-quality. **Controller must pass:** an excerpt of `lint_hybrid.py` around existing `check_hy###` functions so the implementer matches the surrounding pattern.

**Files:**
- Modify: `src/forgeds/hybrid/lint_hybrid.py` (add `check_wg001` + wire into main)
- Create: `tests/test_lint_hybrid_wg_rules.py` (grows across Tasks 8-10)

- [ ] **Step 8.1: Read the existing `lint_hybrid.py` structure**

Skim `src/forgeds/hybrid/lint_hybrid.py:1-120` and `:216-260` to confirm the rule-function signature pattern (e.g., `check_hy001(...) -> list[Diagnostic]`) and how rules are wired into `main`. The WG functions must match the existing shape.

- [ ] **Step 8.2: Write failing test for WG001**

Create `tests/test_lint_hybrid_wg_rules.py`:

```python
"""Tests for widget-related hybrid rules (WG001-WG003)."""

from __future__ import annotations

import sys, os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from forgeds._shared.diagnostics import Severity
from forgeds.hybrid.lint_hybrid import check_wg001, check_wg002, check_wg003

FIXTURES = Path(__file__).parent / "fixtures" / "widgets"


def test_wg001_flags_missing_root():
    widgets = {
        "ghost_widget": {"root": "tests/fixtures/widgets/does_not_exist/", "consumes_apis": []},
    }
    diags = check_wg001(widgets, project_root=Path("."))
    assert len(diags) == 1
    assert diags[0].rule == "WG001"
    assert diags[0].severity == Severity.ERROR
    assert "ghost_widget" in diags[0].message


def test_wg001_passes_when_root_exists():
    widgets = {
        "good_widget": {"root": str(FIXTURES / "good_widget"), "consumes_apis": []},
    }
    diags = check_wg001(widgets, project_root=Path("."))
    assert diags == []
```

- [ ] **Step 8.3: Run tests, confirm ImportError**

Run: `pytest tests/test_lint_hybrid_wg_rules.py -v`

Expected: `ImportError: cannot import name 'check_wg001' from 'forgeds.hybrid.lint_hybrid'`.

- [ ] **Step 8.4: Add `check_wg001` to `lint_hybrid.py`**

Open `src/forgeds/hybrid/lint_hybrid.py`. Append these additions near the other rule functions (after existing `check_hy###` definitions, before `main()`):

```python
# ============================================================
# Widget hybrid rules (WG001-WG003)
# ============================================================

def check_wg001(
    widgets: dict[str, dict],
    project_root: Path,
) -> list[Diagnostic]:
    """WG001: Widget `root` directory missing on disk."""
    diags: list[Diagnostic] = []
    for name, decl in (widgets or {}).items():
        root_rel = decl.get("root", "")
        root_path = project_root / root_rel
        if not root_path.is_dir():
            diags.append(Diagnostic(
                file="forgeds.yaml",
                line=1,
                rule="WG001",
                severity=Severity.ERROR,
                message=f"widget '{name}' root directory does not exist: {root_rel}",
            ))
    return diags
```

If `Path` or `Diagnostic` imports are not already at the top of the file, add them. (The explorer showed the file already uses both.)

- [ ] **Step 8.5: Run tests, confirm WG001 tests pass**

Run: `pytest tests/test_lint_hybrid_wg_rules.py::test_wg001_flags_missing_root tests/test_lint_hybrid_wg_rules.py::test_wg001_passes_when_root_exists -v`

Expected: **2 passed**.

- [ ] **Step 8.6: Commit**

```bash
git add src/forgeds/hybrid/lint_hybrid.py tests/test_lint_hybrid_wg_rules.py
git commit -m "feat(widgets): add WG001 hybrid rule (widget root missing)"
```

---

## Task 9 — Hybrid rule WG002: manifest missing or invalid

**Dispatch:** Batch D.2, strictly serial after Task 8. Standard model. Spec refs: §8 (WG002 row). Reviewers: spec → code-quality. **Controller must pass:** confirmation that Task 4's `validate_manifest_file` export is on main.

**Files:**
- Modify: `src/forgeds/hybrid/lint_hybrid.py` (add `check_wg002`)
- Modify: `tests/test_lint_hybrid_wg_rules.py` (add WG002 tests)

- [ ] **Step 9.1: Write failing tests for WG002**

Append to `tests/test_lint_hybrid_wg_rules.py`:

```python
def test_wg002_flags_missing_manifest():
    widgets = {
        "bad_widget_missing_manifest": {
            "root": str(FIXTURES / "bad_widget_missing_manifest"),
            "consumes_apis": [],
        },
    }
    diags = check_wg002(widgets, project_root=Path("."))
    assert any(d.rule == "WG002" and "bad_widget_missing_manifest" in d.message for d in diags)


def test_wg002_flags_invalid_manifest():
    widgets = {
        "bad_widget_invalid_manifest": {
            "root": str(FIXTURES / "bad_widget_invalid_manifest"),
            "consumes_apis": [],
        },
    }
    diags = check_wg002(widgets, project_root=Path("."))
    assert any(d.rule == "WG002" and d.severity == Severity.ERROR for d in diags)


def test_wg002_passes_on_good_manifest():
    widgets = {
        "good_widget": {"root": str(FIXTURES / "good_widget"), "consumes_apis": []},
    }
    diags = check_wg002(widgets, project_root=Path("."))
    assert diags == []
```

- [ ] **Step 9.2: Run tests, confirm ImportError**

Run: `pytest tests/test_lint_hybrid_wg_rules.py -v`

Expected: ImportError for `check_wg002`.

- [ ] **Step 9.3: Add `check_wg002` to `lint_hybrid.py`**

Append after `check_wg001`:

```python
def check_wg002(
    widgets: dict[str, dict],
    project_root: Path,
) -> list[Diagnostic]:
    """WG002: Widget's plugin-manifest.json is missing or fails schema validation."""
    from forgeds.widgets.validate_manifest import validate_manifest_file

    diags: list[Diagnostic] = []
    for name, decl in (widgets or {}).items():
        root_rel = decl.get("root", "")
        manifest_path = project_root / root_rel / "plugin-manifest.json"
        if not manifest_path.exists():
            diags.append(Diagnostic(
                file="forgeds.yaml",
                line=1,
                rule="WG002",
                severity=Severity.ERROR,
                message=f"widget '{name}' is missing plugin-manifest.json at {root_rel}",
            ))
            continue
        sub_diags = validate_manifest_file(str(manifest_path))
        for sd in sub_diags:
            diags.append(Diagnostic(
                file=sd.file,
                line=sd.line,
                rule="WG002",
                severity=Severity.ERROR,
                message=f"widget '{name}': {sd.message}",
            ))
    return diags
```

- [ ] **Step 9.4: Run tests, confirm all WG002 tests pass**

Run: `pytest tests/test_lint_hybrid_wg_rules.py -v`

Expected: all tests so far passing (WG001 × 2 + WG002 × 3 = 5 passed).

- [ ] **Step 9.5: Commit**

```bash
git add src/forgeds/hybrid/lint_hybrid.py tests/test_lint_hybrid_wg_rules.py
git commit -m "feat(widgets): add WG002 hybrid rule (manifest missing or invalid)"
```

---

## Task 10 — Hybrid rule WG003: consumes_apis not declared

**Dispatch:** Batch D.3, strictly serial after Task 9. Standard model (also wires all 3 WG rules into `main()`). Spec refs: §8 (WG003 row). Reviewers: spec → code-quality. **Controller must pass:** the current shape of `main()` in `lint_hybrid.py` (variable names, ordering) so wiring matches surrounding code.

**Files:**
- Modify: `src/forgeds/hybrid/lint_hybrid.py` (add `check_wg003` + wire all three into `main`)
- Modify: `tests/test_lint_hybrid_wg_rules.py` (add WG003 tests + wiring smoke test)

- [ ] **Step 10.1: Write failing tests for WG003 and main wiring**

Append to `tests/test_lint_hybrid_wg_rules.py`:

```python
def test_wg003_flags_undeclared_consumes_api():
    widgets = {
        "some_widget": {
            "root": str(FIXTURES / "good_widget"),
            "consumes_apis": ["undeclared_api_name"],
        },
    }
    custom_apis = ["get_pending_claims", "approve_claim"]
    diags = check_wg003(widgets, custom_apis)
    assert len(diags) == 1
    assert diags[0].rule == "WG003"
    assert diags[0].severity == Severity.ERROR
    assert "undeclared_api_name" in diags[0].message
    assert "some_widget" in diags[0].message


def test_wg003_passes_when_all_apis_declared():
    widgets = {
        "some_widget": {
            "root": str(FIXTURES / "good_widget"),
            "consumes_apis": ["get_pending_claims"],
        },
    }
    diags = check_wg003(widgets, ["get_pending_claims", "approve_claim"])
    assert diags == []


def test_main_runs_wg_rules_end_to_end(monkeypatch, capsys):
    """lint_hybrid.main should exit non-zero when WG rules find issues.

    Calls main() with no args via sys.argv patch, to match the existing
    `def main():` (no-argv) signature used by lint_deluge/lint_access/lint_hybrid.
    """
    import forgeds.hybrid.lint_hybrid as lh

    def fake_load_config(*a, **kw):
        return {
            "custom_apis": ["get_pending_claims"],
            "widgets": {
                "ghost": {"root": "does/not/exist", "consumes_apis": ["bad_name"]},
            },
            # minimal other keys so the existing main() path does not KeyError
            "schema": {"mandatory_zoho_fields": [], "table_to_form": {}, "fk_relationships": [],
                       "upload_order": [], "exclude_fields": []},
            "lint": {"threshold_fallback": "999.99", "dual_threshold_fallback": "5000.00",
                     "demo_email_domains": []},
        }

    monkeypatch.setattr(lh, "load_config", fake_load_config)
    monkeypatch.setattr("sys.argv", ["forgeds-lint-hybrid"])  # no positional paths
    rc = lh.main()
    captured = capsys.readouterr()
    assert rc == 2
    assert "WG001" in captured.out or "WG003" in captured.out
```

- [ ] **Step 10.2: Run tests, confirm ImportError for `check_wg003`**

Run: `pytest tests/test_lint_hybrid_wg_rules.py -v`

Expected: `ImportError: cannot import name 'check_wg003'`.

- [ ] **Step 10.3: Add `check_wg003` and wire all three rules into `main`**

Append after `check_wg002`:

```python
def check_wg003(
    widgets: dict[str, dict],
    custom_apis: list[str],
) -> list[Diagnostic]:
    """WG003: widget `consumes_apis[i]` not declared in config `custom_apis`."""
    known = set(custom_apis or [])
    diags: list[Diagnostic] = []
    for name, decl in (widgets or {}).items():
        for api in decl.get("consumes_apis", []) or []:
            if api not in known:
                diags.append(Diagnostic(
                    file="forgeds.yaml",
                    line=1,
                    rule="WG003",
                    severity=Severity.ERROR,
                    message=(
                        f"widget '{name}' declares consumes_apis entry '{api}' "
                        "which is not in config custom_apis"
                    ),
                ))
    return diags
```

Now wire the three new rules into `main()`. Find the existing body of `main()` in `lint_hybrid.py` (look for `def main()` near the bottom). Immediately before diagnostics are printed/returned, add:

```python
    # --- Widget hybrid checks (WG001-WG003) ---
    widgets_cfg = cfg.get("widgets") or {}
    custom_apis_cfg = cfg.get("custom_apis") or []
    project_root = find_project_root()
    diagnostics.extend(check_wg001(widgets_cfg, project_root))
    diagnostics.extend(check_wg002(widgets_cfg, project_root))
    diagnostics.extend(check_wg003(widgets_cfg, custom_apis_cfg))
```

If `find_project_root` is not already imported at the top of the file, add:

```python
from forgeds._shared.config import find_project_root, load_config
```

(The `load_config` import likely already exists; the edit only adds `find_project_root`.)

**Variable name check:** the existing `main()` may use a different local name than `cfg` or `diagnostics`. Read the surrounding code and adapt the two additions to match whatever names the file uses. Do not blindly paste.

- [ ] **Step 10.4: Run all WG rule tests**

Run: `pytest tests/test_lint_hybrid_wg_rules.py -v`

Expected: **8 passed** (WG001 × 2 + WG002 × 3 + WG003 × 2 + main-wiring × 1).

- [ ] **Step 10.5: Run full test suite to confirm no regressions**

Run: `pytest tests/ -v`

Expected: all existing tests plus the new widgets tests pass. If any existing test fails, inspect — the most likely cause is a `main()` edit that disturbed the existing flow. Read, fix, re-run.

- [ ] **Step 10.6: Commit**

```bash
git add src/forgeds/hybrid/lint_hybrid.py tests/test_lint_hybrid_wg_rules.py
git commit -m "feat(widgets): add WG003 hybrid rule and wire WG001-003 into lint_hybrid main"
```

---

## Task 11 — Register CLI entry points

**Dispatch:** Batch E, serial after Batch D. Cheap model (mechanical config edit + verify). Spec refs: §5.1. Reviewers: spec → code-quality (terse — tiny change).

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 11.1: Add three entry points**

Open `pyproject.toml`. Under `[project.scripts]` (starts at line 22), append three new lines after the existing `forgeds-lint-hybrid` entry (preserve the existing two-space alignment style):

```
forgeds-lint-widgets = "forgeds.widgets.lint_widgets:main"
forgeds-validate-widget-manifest = "forgeds.widgets.validate_manifest:main"
forgeds-build-widget-db = "forgeds.widgets.build_widget_sdk_db:main"
```

- [ ] **Step 11.2: Reinstall package to pick up new entry points**

Run: `pip install -e .`

Expected output: ends with `Successfully installed forgeds-0.1.0`.

- [ ] **Step 11.3: Verify CLIs resolve**

Run these three commands, each should emit its help text (not "command not found"):

```bash
forgeds-build-widget-db --help 2>&1 | head -5
forgeds-validate-widget-manifest --help 2>&1 | head -5
forgeds-lint-widgets --help 2>&1 | head -5
```

Expected: each prints an argparse `usage:` line.

- [ ] **Step 11.4: Smoke-test DB builder end-to-end**

Run: `forgeds-build-widget-db`

Expected: single line `built <path>/zoho_widget_sdk.db`; exit 0.

- [ ] **Step 11.5: Commit**

```bash
git add pyproject.toml
git commit -m "feat(widgets): register forgeds-lint-widgets + validate + build-db entry points"
```

---

## Task 12 — Update `templates/forgeds.yaml.example`

**Dispatch:** Batch F.1, serial after Task 11. Cheap model (docs edit). Spec refs: §4.1. Reviewers: spec only.

**Files:**
- Modify: `templates/forgeds.yaml.example`

- [ ] **Step 12.1: Append widget example blocks**

Open `templates/forgeds.yaml.example`. Append at the end of the file (after the `knowledge:` block, preserving the file's existing indentation style and trailing newline):

```yaml

# Custom API registry — the Custom APIs this project exposes server-side.
# Widget lint (WG003) cross-checks widgets[*].consumes_apis against this list.
# Phase 2 may autodiscover from .ds / custom-api/*.dg; Phase 1 is declare-first.
custom_apis:
  - get_pending_claims
  - approve_claim

# Widget declarations — dict keyed by widget name.
# Each entry declares the directory root (containing plugin-manifest.json) and
# the list of custom_apis this widget is allowed to consume.
# Permissions/roles/entry point are read from plugin-manifest.json at lint time.
widgets:
  expense_dashboard:
    root: src/widgets/expense_dashboard/
    consumes_apis:
      - get_pending_claims
      - approve_claim
```

- [ ] **Step 12.2: Sanity-check YAML parses**

Run: `python -c "import pathlib; from forgeds._shared.config import _load_yaml_simple; print(list(_load_yaml_simple('templates/forgeds.yaml.example').keys()))"`

Expected: printed dict keys include both `custom_apis` and `widgets`.

- [ ] **Step 12.3: Commit**

```bash
git add templates/forgeds.yaml.example
git commit -m "docs(widgets): document custom_apis and widgets blocks in template"
```

---

## Task 13 — Update `CLAUDE.md` (registry + Node posture + G7 findings)

**Dispatch:** Batch F.2, serial after Task 12. Cheap model (docs edit). Spec refs: §11, §12, §13. Reviewers: spec only. **Controller must pass:** the output/notes from Task 5's G7 investigation so the gotcha-5 bullet reflects actual findings.

**Files:**
- Modify: `CLAUDE.md`
- Read: `docs/superpowers/specs/2026-04-22-g7-parser-investigation-notes.md`

- [ ] **Step 13.1: Add rule-code registry section**

Open `CLAUDE.md`. After the existing `## Rules for contributions` section, add a new section:

```markdown

## Rule code registry

All linters emit `Diagnostic` objects with a `rule` field using these prefixes:

| Prefix | Owner | Meaning |
|---|---|---|
| `DG###` | `forgeds.core.lint_deluge` | Deluge lint rules |
| `AV###` / `AC###` | `forgeds.access.lint_access` | Access / VBA rules |
| `HY###` | `forgeds.hybrid.lint_hybrid` | Deluge↔Access cross-checks |
| `WG###` | `forgeds.hybrid.lint_hybrid` | Widget↔Deluge cross-checks |
| `JS:<rule>` | `forgeds.widgets.lint_widgets` | ESLint rule ID, foreign provenance |

When adding a new rule: pick the next unused number in the prefix's range, add a
test fixture under `tests/fixtures/`, and document the rule's intent in a
docstring on the check function.
```

- [ ] **Step 13.2: Add widget-lint toolchain section**

Immediately after the new registry section, add:

```markdown

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
```

- [ ] **Step 13.3: Add G7 findings to `.ds file format gotchas`**

Read `docs/superpowers/specs/2026-04-22-g7-parser-investigation-notes.md` (the file created in Task 5) to confirm findings. Then in `CLAUDE.md`, find the section headed `## .ds file format gotchas` and append a new numbered item (continue from the existing numbering, likely `5.`):

```markdown
5. **Widgets are not represented in `.ds` exports**: Creator widgets are
   packaged separately (plugin-manifest.json + JS/HTML/CSS bundled as a zip)
   and uploaded through the Creator portal, not serialized into `.ds`.
   `parse_ds_export.py` does not inspect widgets and does not need to.
   Widget declarations live in `forgeds.yaml` under the `widgets:` block,
   and on disk under the path configured as each widget's `root`.
```

**If the G7 investigation found the opposite** (widgets *are* in .ds), replace
the above with an accurate description of what was found, and file a Phase 2
ticket for extending `parse_ds_export.py`.

- [ ] **Step 13.4: Add widgets to the Architecture section**

In `CLAUDE.md`, find the existing `## Architecture` section (the bulleted
package list). Insert a new bullet between `hybrid/` and `knowledge/`:

```markdown
- `src/forgeds/widgets/` — Widget lint tools (ESLint orchestrator, SDK DB, manifest validator)
```

- [ ] **Step 13.5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(widgets): add rule registry, Node posture, G7 finding, widgets package entry"
```

---

## Final verification (controller-driven)

After Batch F completes, the controller runs these steps directly (no worker dispatch — integration smoke is the controller's job):

- [ ] **Step F.1: Full test suite**

Run: `pytest tests/ -v`

Expected: all tests pass, including:
- `test_config_widgets.py` (4)
- `test_build_widget_sdk_db.py` (4)
- `test_validate_manifest.py` (4)
- `test_lint_widgets.py` (4)
- `test_lint_hybrid_wg_rules.py` (8)
- plus all pre-existing tests

- [ ] **Step F.2: End-to-end CLI smoke**

Run from the repo root:

```bash
forgeds-build-widget-db
forgeds-validate-widget-manifest tests/fixtures/widgets/good_widget/plugin-manifest.json
forgeds-lint-hybrid
```

Expected:
- `forgeds-build-widget-db` prints `built <path>/zoho_widget_sdk.db`; exit 0.
- `forgeds-validate-widget-manifest` on the good fixture prints no diagnostics; exit 0.
- `forgeds-lint-hybrid` runs to completion without crashing (exit code depends
  on repo state — the goal is "no exception", not a specific code).

- [ ] **Step F.3: JSON envelope shape check**

Run with a known-bad fixture (outside any real consumer config, so adjust args
to point at a fixture JS file directly):

```bash
forgeds-lint-widgets tests/fixtures/widgets/good_widget/index.js --format json
```

Expected: one line of JSON with keys `tool`, `version`, `diagnostics`. If ESLint
is not installed on the dev machine, expected: exit code 3 with install hint
(to stderr) and no JSON emitted — that is also a correct outcome proving the
Node-optional posture works.

---

## Final subagent dispatch: whole-branch review

- [ ] **Step G.1: Dispatch final code-reviewer subagent**

Prompt (controller composes):

> Review the complete branch diff `git diff main...HEAD` for the ForgeDS widgets Phase 1 feature. Spec at `docs/superpowers/specs/2026-04-22-forgeds-widgets-phase1-design.md`. Focus checks:
>
> 1. Rule codes — are `WG001`/`WG002`/`WG003`/`JS:<rule>` used consistently with the registry in CLAUDE.md?
> 2. JSON envelope — does `forgeds-lint-widgets --format json` emit exactly `{tool, version, diagnostics[]}` with lowercase severity strings?
> 3. Zero-dep invariant — no new Python runtime imports beyond stdlib in `src/forgeds/widgets/**`.
> 4. No cross-task drift — field names, function signatures, exit codes match between tasks.
> 5. All spec non-goals (§16) respected — no G5/G8/G9/G10 code, no .ds parser edits, no TypeScript.
>
> Return: pass / fail list. If fail, specify files and line numbers.

- [ ] **Step G.2: Address reviewer findings**

If findings exist, controller dispatches a fresh implementer subagent with exact file paths and the reviewer's feedback. Loop until the final reviewer approves.

- [ ] **Step G.3: Hand off to `superpowers:finishing-a-development-branch`**

All tasks done, all reviews passed. Invoke the branch-finishing skill to select merge/PR/cleanup.

---

## Self-review checklist (engineer runs before declaring done)

- [ ] Every new `.py` file has a module docstring.
- [ ] No `TBD`/`TODO`/`FIXME` tokens in committed files.
- [ ] `grep -r "custom_apis" src/forgeds/` shows consistent usage (always `.get("custom_apis", [])`, never bare `config["custom_apis"]`).
- [ ] `grep -r "widgets" src/forgeds/` shows consistent `config.get("widgets", {})` pattern.
- [ ] WG rule codes in diagnostics exactly match the registry table (`WG001`, `WG002`, `WG003`).
- [ ] The JSON envelope emitted by `--format json` uses lowercase severity strings (`"error"` / `"warning"`), matching the test expectations.
- [ ] `pyproject.toml` has exactly 3 new entries; no duplicates.

---

## Out of scope (do not implement in Phase 1)

Called out explicitly so scope creep is visible:

- **No runtime / dynamic widget execution** (deferred G5).
- **No widget scaffolder** (deferred G8).
- **No OpenAPI / TypeScript typegen from Custom APIs** (deferred G9).
- **No widget zip / bundle pipeline** (deferred G10).
- **No changes to existing DG/AC/HY linter CLIs** — JSON envelope pilot is widgets-only.
- **No `parse_ds_export.py` code changes** — investigation only (Task 5).
- **No TypeScript support** — `.js` and `.html` only in Phase 1.
- **No `jsonschema` dependency** — stdlib-only subset validator.
- **No autodiscovery of `custom_apis` from `.ds` or `custom-api/*.dg`** — declare-first.
