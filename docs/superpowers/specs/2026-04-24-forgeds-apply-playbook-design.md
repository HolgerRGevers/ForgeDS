# forgeds-apply-playbook — design spec (2026-04-24)

## 1. Problem statement

Zoho Creator deployments evolve through a markdown "playbook" — a human-authored document that specifies which form-action workflows and custom-action buttons to add to an application. Today the developer manually translates each playbook section into `.ds` syntax, a process that is error-prone, case-sensitive, and unchecked. `forgeds-apply-playbook` ingests the playbook MD and a source `.ds` export, validates every reference against actual form/field inventory, emits syntactically correct Zoho `.ds` workflow and custom-action blocks, and writes them into the `.ds` at the correct insertion points. The consumer re-imports the mutated `.ds` into Creator. Target users: ForgeDS-aware developers maintaining Zoho Creator applications from source-controlled `.ds` exports.

---

## 2. Scope

### 2.1 In scope

- Parse a structured playbook markdown file into a validated intermediate representation (IR).
- Validate all form names, field references, and report names against the inventory extracted from the source `.ds`.
- Emit syntactically correct Zoho `.ds` workflow-entry blocks for form-action events.
- Emit syntactically correct Zoho `.ds` custom-action blocks inside named reports.
- Mutate the source `.ds` at the correct insertion points, respecting all `.ds` structural gotchas documented in CLAUDE.md.
- Output: mutated `.ds` file, sidecar report MD, JSON diagnostic envelope.
- `validate` subcommand (parse + validate only, no mutation).
- `preview` subcommand (dry-run: shows what would be emitted, no file writes).
- `--ir-dump` flag for debugging the parsed IR as JSON.
- `--dry-run` flag on `apply` subcommand (alias for preview behaviour).

### 2.2 Out of scope (explicit)

- Fully idempotent re-application: v1 includes a sentinel-comment guard (DS030 ERROR + DS032 WARNING) that prevents the most common double-apply footgun, but full idempotency (where the second apply is a true no-op) is deferred to v2 (see §8.4).
- Scheduled-task blocks: not represented in the playbook format defined here.
- Approval-process blocks: not represented in the playbook format defined here.
- Page/ZML mutation: not within scope.
- Widget declarations: widgets are not serialised in `.ds` exports (CLAUDE.md gotcha #5); no widget blocks are emitted.
- Deluge syntax validation beyond field-token cross-checking: full Deluge parsing is out of scope for v1.
- Automatic re-export from Creator or re-import into Creator: the tool operates on files only.
- TypeScript/generated-client emission: not applicable here.
- Any network calls: this is a purely local, zero-dependency tool.
- Validation of Deluge `<FormName>[<criteria>]` form-access patterns — too many false-positives on generic subscripts to implement reliably without a full Deluge parser. Deferred to v2.

---

## 3. Inputs and outputs

### 3.1 Inputs

| Name | Type | Required | Description |
|---|---|---|---|
| `--ds` | `Path` (file) | Required | Source `.ds` export file. Read-only during `validate`/`preview`; read then written during `apply`. |
| `--playbook` | `Path` (file) | Required | Playbook markdown file. UTF-8, structured per §6. |
| `--out` | `Path` (file) | Required for `apply` | Destination path for the mutated `.ds`. May equal `--ds` (in-place). If different, source is copied then mutated. |
| `--force` | flag | Optional | Overwrite `--out` if it already exists. Without `--force`, collision exits 2. |
| `--custom-action-workflow-mode` | `form\|standalone\|stub-unwired` | Optional (default: `stub-unwired`) | Controls how the backing workflow entry is emitted for custom-action blocks (§7.3). `form` and `standalone` are spike-gated (exit 3); only `stub-unwired` is unblocked in v1. |
| `--ir-dump` | `Path` (`.json` file) | Optional | Write the parsed `PlaybookIR` as JSON to this path after parsing. Useful for debugging. |
| `--json` | flag | Optional | Emit diagnostic envelope as JSON to stdout instead of human-readable text. |
| `--dry-run` | flag | Optional (on `apply`) | Parse, validate, emit to stdout/preview only; do not write any file. |

### 3.2 Outputs

| Output | Description |
|---|---|
| Mutated `.ds` | The `--out` path. Contains the original `.ds` content with workflow-entry and custom-action blocks inserted at valid positions. |
| Sidecar report MD | Written alongside `--out` as `<stem>-apply-playbook-report.md`. Lists every action taken, every diagnostic, and the exact byte offsets of each insertion. |
| JSON diagnostic envelope | Emitted to stdout when `--json` is set, or always when stderr is a non-TTY in CI. Format: v1 envelope with `tool = "forgeds-apply-playbook"` (§13). |
| Exit code | `0` = clean (no warnings or errors); `1` = warnings present; `2` = errors present (no `.ds` written); `3` = spike-gate exit — `--custom-action-workflow-mode=form\|standalone` requested without spike validation (DS043). |

---

## 4. Architecture

### 4.1 Module layout

```
src/forgeds/core/apply_playbook/
    __init__.py          # package marker; exports apply_playbook_main
    cli.py               # argparse wiring; subcommands apply / validate / preview
    parser.py            # PlaybookParser: MD -> PlaybookIR + DS001-DS019 diagnostics
    ir.py                # Dataclasses: PlaybookIR, FormAction, CustomAction, DelugeBlock, DeferredSection
    landmarks.py         # DSLandmarks: brace-depth state machine over .ds text; DS060-DS069 diagnostics
    validator.py         # cross-check IR against DSLandmarks inventory; DS020-DS039 diagnostics
    emitter.py           # render IR objects to .ds syntax strings; DS040-DS049 diagnostics
    mutator.py           # splice emitter output into .ds at landmark offsets; DS050-DS059 diagnostics
    orchestrator.py      # wire parser -> validator -> emitter -> mutator; collect all diagnostics
```

### 4.2 Component responsibilities

**Parser** (`parser.py`): Accepts raw playbook markdown text. Walks lines top-to-bottom. Identifies H2 section boundaries (form context) and H3 sub-sections (individual actions). Extracts fenced code blocks as Deluge bodies. Extracts bullet metadata (event phrase, display name, link name). Attaches blockquote text as implementation notes. Emits `DS001`–`DS019` diagnostics for structural deviations. Returns a `PlaybookIR`.

**IR** (`ir.py`): Stable typed schema (Python dataclasses). The IR is the contract between parser and all downstream components. See §5 for full schema. The IR is serialisable to JSON for `--ir-dump`.

**Landmarks** (`landmarks.py`): Accepts raw `.ds` text. Runs a single-pass brace-depth state machine that tracks string-literal context (to avoid misreading `{` inside quoted values). Returns a `DSLandmarks` object carrying byte/line offsets for: `forms` block open/close, `reports` block open/close, `workflow` block open/close (or `None` if absent), per-report body open/close offsets keyed by report link name, per-form body open/close offsets keyed by form link name. Emits `DS060`–`DS069` diagnostics on structural failure (e.g. unclosed `forms` block).

**Validator** (`validator.py`): Accepts `PlaybookIR` + `DSLandmarks` + `DSParser` result (form/field inventory from `parse_ds_export.DSParser`). Performs all cross-checks listed in §9. Emits `DS020`–`DS039` diagnostics. Returns a boolean `valid` and the full diagnostic list. If `valid` is False, the orchestrator does not proceed to emit/mutate.

**Emitter** (`emitter.py`): Accepts validated `PlaybookIR`. For each `FormAction`, renders the `.ds` workflow-entry block (§7.1). For each `CustomAction`, renders the custom-action block (§7.2) and, if `--custom-action-workflow-mode` is not `stub-unwired` (and the spike gate is bypassed in tests), renders the backing workflow entry (§7.3). Emits `DS040`–`DS049` diagnostics (e.g. `DS040` WARNING on every custom-action backing-workflow emission). Returns a list of `EmitResult` named tuples: `(target: str, content: str, insertion_hint: str)`.

**Mutator** (`mutator.py`): Accepts the raw `.ds` text, `DSLandmarks`, and `EmitResult` list. Operates in two strictly-ordered phases: (1) **Validation phase** — compute all insertion offsets and run all guardrails (DS050–DS059) against the complete `EmitResult` list. A guardrail failure on any single insertion aborts the entire apply; no partial in-memory mutation is propagated. (2) **Splice phase** — apply all insertions in reverse byte-offset order (highest offset first) to avoid cascading index shifts. No disk write may occur if phase 1 reported any ERROR. Emits `DS050`–`DS059` diagnostics on guardrail violations. Returns the mutated text. Add a mutator unit test: fixture with 5 insertions where the 3rd triggers DS050 → assert output file byte-equals input file.

**Orchestrator** (`orchestrator.py`): Top-level function `run_apply_playbook(args) -> tuple[str, list[Diagnostic]]`. Calls parser → validator → emitter → mutator in sequence. Collects all diagnostics. Handles `--dry-run` (stops before writing). Writes mutated `.ds` and sidecar report. Calls `to_json_v1` from `forgeds._shared.envelope` for JSON output.

**CLI** (`cli.py`): Three subcommands: `apply`, `validate`, `preview`. `argparse` wiring only. Entry point registered in `pyproject.toml` as `forgeds-apply-playbook = "forgeds.core.apply_playbook.cli:main"`.

### 4.3 Data flow

```
playbook.md ──► Parser ──────────────────► PlaybookIR
                                                │
source.ds ───► DSParser (parse_ds_export) ──► form/field inventory
                                                │
source.ds ───► Landmarks ────────────────► DSLandmarks
                                                │
                       PlaybookIR + inventory + DSLandmarks
                                                │
                                         Validator
                                     (DS020-DS039 diags)
                                                │
                                    [if valid]  ▼
                                           Emitter
                                     (DS040-DS049 diags)
                                                │
                                          EmitResult[]
                                                │
                                           Mutator
                                     (DS050-DS059 diags)
                                                │
                                        mutated .ds text
                                                │
                                        write --out file
                                        write sidecar .md
                                        emit JSON envelope
```

---

## 5. IR schema

```python
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class DelugeBlock:
    """A fenced Deluge code block extracted from the playbook.

    Invariant: `body` is never empty when produced by the parser (DS005
    fires and the parent action is dropped if the fenced block is absent
    or contains only whitespace). `implementation_notes` collects the
    text of any blockquotes immediately following the fence (§6.4).
    """
    body: str
    """Raw Deluge source exactly as written in the playbook fence."""
    implementation_notes: list[str] = field(default_factory=list)
    """Text lines from blockquotes immediately following this fence."""


@dataclass
class FormAction:
    """A single workflow entry attached to a form event.

    Models one H3 subsection inside a form's H2 section. Represents a
    workflow-entry block that will be inserted into the .ds `workflow {}`
    section. Invariant: `form_name` must match a form link name in the
    .ds (validated in DS021). `link_name` must be unique across all
    FormActions in the IR (DS006 fires on collision).
    """
    form_name: str
    """Link name of the target form (case-sensitive, from H2 context)."""
    display_name: str
    """Human-readable workflow entry name (from bullet metadata `name:`)."""
    link_name: str
    """Zoho link name for this workflow entry (from bullet metadata `link:`)."""
    event: str
    """Trigger phrase, e.g. 'on add', 'on edit', 'on add or edit' (from bullet metadata)."""
    record_event: str
    """Record-event qualifier, e.g. 'on success', 'on validate' (from bullet metadata)."""
    deluge: DelugeBlock
    """The Deluge body and associated notes."""


@dataclass
class CustomAction:
    """A custom-action button declaration for a named report.

    Models one H3 subsection specifying a button to be added to a report's
    action bar. Invariant: `report_name` must match a report link name in
    the .ds (DS022). `link_name` must be unique within the IR (DS006).
    """
    report_name: str
    """Link name of the target report (case-sensitive)."""
    display_name: str
    """Button label shown in Creator UI (from bullet metadata `name:`)."""
    link_name: str
    """Zoho link name for this custom action (from bullet metadata `link:`)."""
    backing_form: str
    """Form whose field inventory backs the Deluge body (from bullet metadata `form:`)."""
    deluge: DelugeBlock
    """The Deluge body and associated notes."""


@dataclass
class DeferredSection:
    """A playbook section that was recognised but deliberately skipped.

    Used for §4-style transition descriptions (narrative-only sections
    that carry no Deluge body). The parser emits DS015 INFO and
    populates this object instead of FormAction/CustomAction.
    Downstream components ignore DeferredSection objects entirely.
    """
    heading: str
    """The H2 or H3 heading text of the skipped section."""
    reason: str
    """Why the section was deferred (e.g. 'no fenced Deluge block found')."""


@dataclass
class PlaybookIR:
    """Top-level intermediate representation for a parsed playbook file.

    Invariant: `form_actions` and `custom_actions` together contain only
    fully-parsed entries. Entries that could not be parsed appear in
    `deferred`. The `diagnostics` list is populated by the parser; it is
    additive (validator/emitter/mutator append their own diagnostics to
    a separate list in the orchestrator, not to this object).
    """
    form_actions: list[FormAction] = field(default_factory=list)
    custom_actions: list[CustomAction] = field(default_factory=list)
    deferred: list[DeferredSection] = field(default_factory=list)
    source_file: str = ""
    """Absolute path to the playbook file, for diagnostic attribution."""
```

### 5.5 IR escape contract

The following character constraints are enforced by the validator (DS027, DS028) before the emitter runs:

- **`display_name`** — allowed characters: `[a-zA-Z0-9 _.-]`. The characters `"`, `\`, `{`, `}`, and control characters MUST be absent. Any `"` in `display_name` triggers DS027 ERROR. The validator rejects before emission.
- **Deluge bodies** — embedded verbatim into the `.ds` workflow block. The validator performs a string-literal-aware parenthesis-balance check; unbalanced parens trigger DS028 ERROR. The validator rejects before emission.

Both DS027 and DS028 have corresponding fixtures (see §12).

---

## 6. Parser contract

### 6.1 Playbook MD landmarks

| Landmark | Pattern | Notes |
|---|---|---|
| Form H2 | `^## ([A-Za-z0-9_]+)` | Sets current form context for all H3 sections until next H2. Group 1 is the form link name. |
| Action H3 | `^### (.+)` | Begins a new action within the current form context. |
| Bullet metadata | `^[-*]\s+(\w[\w -]+):\s+(.+)$` | Key-value pairs under an H3. Recognised keys: `name`, `link`, `event`, `record_event`, `form`, `report`. |
| Fenced code block | ` ```deluge` ... ` ``` ` | Deluge body. Only the first fenced block per H3 section is used; additional fences emit DS003 WARNING. |
| Event phrase | `on add\|on edit\|on add or edit\|on success\|on validate\|on load\|on custom action` | Matched in the `event:` bullet value. |
| Blockquote | `^>\s+(.+)` | Lines immediately following the closing ` ``` ` fence; attached as `implementation_notes` (§6.4). |

**Form-name inheritance:** An H3 section inherits the form context from its enclosing H2. If an H3 specifies a `report:` key in its bullet metadata, it is classified as a `CustomAction`; the form context provides the `backing_form`. If neither `report:` nor a valid `event:` is found, the section becomes a `DeferredSection`.

### 6.2 What the parser emits per section

| Playbook section type | IR object populated | Fields set | Diagnostic on deviation |
|---|---|---|---|
| H2 with no children | (skipped) | — | DS002 INFO |
| H3 with `event:` bullet + fenced block | `FormAction` | `form_name` (from H2), `display_name`, `link_name`, `event`, `record_event`, `deluge` | DS001 if H3 has no H2 parent |
| H3 with `report:` bullet + fenced block | `CustomAction` | `report_name`, `display_name`, `link_name`, `backing_form`, `deluge` | DS004 if `form:` bullet missing |
| H3 with fenced block but no `event:` or `report:` | `DeferredSection` | `heading`, `reason` | DS015 INFO |
| H3 with no fenced block | `DeferredSection` | `heading`, `reason` | DS005 ERROR if link name present; DS015 INFO otherwise |
| Duplicate `link_name` across any actions | — | — | DS006 ERROR |

### 6.3 §4 handling

Playbook sections that function as narrative transitions (prose-only, no fenced Deluge block, no actionable bullet metadata) are detected when: (a) an H3 is found, (b) no ` ```deluge ` fence is present anywhere before the next H3 or H2, and (c) no `event:` or `report:` bullet is present.

The parser creates a `DeferredSection` in the IR with `reason = "no fenced Deluge block"`. DS015 INFO is emitted pointing at the H3 heading line number. No `FormAction` or `CustomAction` is created. Downstream components (validator, emitter, mutator) ignore `DeferredSection` objects entirely.

### 6.4 Blockquote handling

Blockquote lines (`> text`) appearing immediately after the closing ` ``` ` of a fenced code block (with no intervening blank line or heading) are collected into `DelugeBlock.implementation_notes` as plain strings (the `> ` prefix stripped).

During emission (§7), each note is prepended to the emitted Deluge body as a comment:
```
/* NOTE from playbook: <note text> */
```
These comments appear inside the `custom deluge script ( ... )` wrapper, before the first user-authored line.

---

## 7. Zoho .ds workflow-block syntax contract

### 7.1 Form-action workflow entry (VERIFIED)

Based on the workflow-block patterns observed in `parse_ds_export.py:_parse_workflows` (src/forgeds/core/parse_ds_export.py:196-257).

```
<link_name> as "<display_name>"
{
    form = <form_name>
    record event = <record_event>
    <event_phrase>
    {
        custom deluge script
        (
<deluge_body>
        )
    }
}
```

Fields:
- `link_name` — from `FormAction.link_name`; must be unique within the `workflow { }` block.
- `display_name` — from `FormAction.display_name`; double-quoted.
- `form_name` — from `FormAction.form_name`; must match a form link name.
- `record_event` — from `FormAction.record_event` (e.g. `on add`, `on edit`, `on add or edit`).
- `event_phrase` — from `FormAction.event` (e.g. `on success`, `on validate`).
- `deluge_body` — from `FormAction.deluge.body`; indented consistently.

### 7.2 Custom-action block inside a report (VERIFIED)

Based on patterns in `ds_editor.py` and established Creator `.ds` structure.

```
custom action <link_name>
(
    displayname = "<display_name>"
    action type = workflow
    workflow = <workflow_link_name>
)
```

Fields:
- `link_name` — from `CustomAction.link_name`.
- `display_name` — from `CustomAction.display_name`.
- `workflow_link_name` — the link name of the backing workflow entry emitted per §7.3. By convention equals `<link_name>_workflow` unless `--custom-action-workflow-mode stub-unwired` is used.

This block is inserted immediately before the closing `}` of the target report's body.

### 7.3 Custom-action backing workflow (UNVERIFIED — decision record)

**UNVERIFIED**: The exact `.ds` syntax for a workflow entry triggered by a custom-action button has not been confirmed against a live Creator export. The design below is derived from community documentation and the pattern in §7.1. `DS040 WARNING` is emitted on every emission of this block to flag the residual risk (promotes to exit code 1 whenever custom-action workflow entries are emitted).

**Note on `record event` field (UNVERIFIED):** The `record event` phrase after `on custom action` uses the `<link_name>` of the custom action, not its `<display_name>`. Example: if `link_name = approve_action`, the line is `record event = on custom action approve_action`. This remains UNVERIFIED against a live Creator export.

Three modes via `--custom-action-workflow-mode`:

| Mode | Behaviour |
|---|---|
| `form` | **Spike-gated (exit 3).** Emits a normal workflow entry with `type = form`, `form = <backing_form>`, `record event = on custom action <link_name>`. Blocked by DS043 until the research spike validates this syntax. |
| `standalone` | **Spike-gated (exit 3).** Emits a workflow entry with no `form =` or `type =` line; the `record event` line is the sole trigger specifier. Blocked by DS043. |
| `stub-unwired` (default) | Unblocked in v1. Does not emit a backing workflow entry. The custom-action block references `workflow = <link_name>_workflow` but the workflow itself must be authored manually in Creator Builder. This mode lets you wire the button text, column header, and condition declaratively, then hand-finish the Deluge via the UI. |

**DS043 spike-gate:** When `--custom-action-workflow-mode=form` or `--custom-action-workflow-mode=standalone` is requested, the tool exits 3 immediately with DS043 ERROR, unless the environment variable `FORGEDS_APPLY_PLAYBOOK_SPIKE_OVERRIDE_TESTONLY=1` is set AND `PYTEST_CURRENT_TEST` is also set (the latter is set automatically by pytest; production runs will have neither). Do not set the override env var outside of a pytest run — behaviour is undefined.

Emitted shape (mode `form`, SPIKE-GATED — for documentation only):

```
<link_name>_workflow as "<display_name> Workflow"
{
    form = <backing_form>
    type = form
    record event = on custom action <link_name>
    on load
    {
        custom deluge script
        (
<deluge_body>
        )
    }
}
```

DS040 WARNING is emitted for every custom-action backing workflow emitted in `form` or `standalone` mode (when spike-gate is bypassed in tests), with message: `"Custom-action backing workflow emitted using UNVERIFIED 'on custom action' record-event syntax; verify against Creator import"`. Exit code will be at least 1.

### 7.4 Deluge string-literal escape convention — empirical finding (TO BE COMPLETED BY IMPLEMENTER)

TODO: Task 3 must inspect `C:\Users\User\OneDrive\Documents\GitHub\Expense_Reimbursement_Manager\docs\Expense_Reimbursement_Management-development.ds` and document the convention here. Specifically: (a) locate at least 2 strings containing `"` or `{` in the file, (b) determine whether Deluge uses `\"` or some other escape sequence, (c) determine whether `{` inside a quoted string is literal or escaped, and record the findings. Until this subsection is filled in, the state machine defaults to treating `\"` as an escaped quote (does not toggle `in_string`). The implementer MAY override this default after completing the study.

---

## 8. Mutator contract

### 8.1 Landmark detection

`DSLandmarks` is produced by a single-pass state machine in `landmarks.py`. The machine maintains:

- `brace_depth: int` — incremented on `{`, decremented on `}`.
- `in_string: bool` — toggled on unescaped `"` characters; while true, brace characters are not counted.
- `current_block: str | None` — the keyword (`forms`, `reports`, `workflow`, `pages`) whose opening `{` was last seen at depth 1.

Returns a `DSLandmarks` dataclass with fields:

```python
@dataclass
class DSLandmarks:
    forms_open: int          # byte offset of 'forms' keyword line
    forms_close: int         # byte offset of closing } of forms block
    reports_open: int        # byte offset of 'reports' keyword line
    reports_close: int       # byte offset of closing } of reports block
    workflow_open: int | None  # byte offset of 'workflow' keyword, or None
    workflow_close: int | None
    pages_open: int | None
    report_bodies: dict[str, tuple[int, int]]  # link_name -> (open, close) offsets
    form_bodies: dict[str, tuple[int, int]]    # link_name -> (open, close) offsets
```

**String-literal escape convention:** Before finalising `landmarks.py`, the implementer MUST inspect the real ERM `.ds` file to determine Deluge's escape convention empirically (see §7.4). The state machine defaults to treating `\"` as an escaped quote (does not toggle `in_string`), but the empirical finding in §7.4 may override this. Both DS062 and DS063 abort with exit 2; both must fire on their respective conditions.

Error diagnostics from landmark detection:

| Code | Severity | Condition |
|---|---|---|
| DS060 | ERROR | `forms` block not found in `.ds` |
| DS061 | ERROR | `reports` block not found in `.ds` |
| DS062 | ERROR | Unbalanced braces at EOF (brace_depth != 0) |
| DS063 | ERROR | State machine exits with `in_string == True` at EOF — orphaned opening quote |
| DS064 | WARNING | `workflow` block not found; will be synthesised during mutation |
| DS065 | ERROR | Named report from IR not found in `.ds` report bodies |
| DS066 | ERROR | Named form from IR not found in `.ds` form bodies |

### 8.2 Insertion rules

**Form-action workflow entries:**
1. If a `workflow { }` block exists (`DSLandmarks.workflow_open` is not None): append the new entry immediately before the closing `}` of the `workflow` block (at `DSLandmarks.workflow_close` offset).
2. If no `workflow { }` block exists: synthesise a new `workflow { <entry> }` block. Insert this block between `DSLandmarks.reports_close` and `DSLandmarks.pages_open`. DS064 WARNING is already emitted by landmarks detection; the mutator emits no additional diagnostic for the synthesis itself.

**Custom-action blocks:**
- Insert immediately before the closing `}` of the named report's body at `DSLandmarks.report_bodies[link_name][1]`.
- NEVER insert inside a form body.
- NEVER insert between `forms_close` and the `reports` keyword.
- NEVER insert between `reports_close` and the `pages` keyword (except for a synthesised `workflow` block per rule above).

### 8.3 Placement guardrails (DS050-DS059)

These enforce the CLAUDE.md gotchas as hard preconditions before any byte insertion.

| Code | Severity | Condition checked | Gotcha ref |
|---|---|---|---|
| DS050 | ERROR | Computed insertion point falls between `forms_close` offset and `reports_open` offset | CLAUDE.md gotcha #1 |
| DS051 | ERROR | Computed insertion point falls between `reports_close` offset and `pages_open` offset (except synthesised `workflow` block) | CLAUDE.md gotchas #2, #4 |
| DS052 | ERROR | Computed insertion point is not inside any recognised block (depth 0 at target offset) | CLAUDE.md general structural principle |
| DS053 | WARNING | `--out` equals `--ds` (in-place mutation); sidecar is written but original is overwritten | operator UX |

**Atomicity invariant:** ALL guardrail checks (DS050–DS059) MUST execute against the complete `EmitResult` list and computed insertion offsets BEFORE the first byte is spliced. Guardrail failure on any single insertion aborts the entire apply; no partial in-memory mutation is propagated. No disk write may occur if any guardrail emitted an ERROR. When any DS050–DS052 fires, the orchestrator exits 2 and no `.ds` file is written.

### 8.4 Idempotency and sentinel banner

**v1 idempotency guard:** Running `forgeds-apply-playbook apply` twice against the same `.ds` (without re-exporting from Creator between runs) will produce duplicate workflow entries and duplicate custom-action blocks without the sentinel guard below.

The intended user workflow is: `forgeds-apply-playbook apply` → import to Creator → further changes → re-export from Creator → `forgeds-apply-playbook apply` again on the fresh export.

**DS030 ERROR** is emitted by the validator when a workflow-entry `link_name` from the IR already appears in the existing `.ds` workflow block. This is promoted to ERROR (blocking) to prevent the most common double-apply footgun. Pass `--allow-duplicate-links` to downgrade to DS031 WARNING and proceed.

**DS031 WARNING** is emitted when `--allow-duplicate-links` is passed and a duplicate `link_name` is detected. The apply proceeds.

**Sentinel comment mechanism (v1):** The emitter prepends a sentinel comment to every generated workflow entry:

```
/* forgeds-apply-playbook: from playbook <basename> sha256=<first-8-of-hash> */
```

Before emitting, the mutator scans the existing `.ds` workflow block for any entry containing a matching sentinel (same playbook basename + hash prefix). If found, the tool exits 1 with **DS032 WARNING**: `"Already-applied; re-export from Creator before re-applying"`. Pass `--allow-reapply` to suppress DS032 and proceed. This is approximately 15 LOC and prevents the most common double-apply footgun.

The `--allow-duplicate-links` and `--allow-reapply` flags are independent; both may be passed simultaneously.

---

## 9. Validator contract (DS020-DS039)

All checks run after landmark detection and form/field inventory extraction (via `parse_ds_export.DSParser`). A single ERROR-severity diagnostic causes `valid = False`; WARNING-severity diagnostics do not block emission.

| Code | Severity | Cross-check |
|---|---|---|
| DS021 | ERROR | Form link name referenced in `FormAction.form_name` exists in the `.ds` form inventory. Case-sensitive. |
| DS022 | ERROR | Report link name referenced in `CustomAction.report_name` exists in `DSLandmarks.report_bodies`. Case-sensitive. |
| DS023 | ERROR | Every `input.<field>` token in a `DelugeBlock.body` matches a field link name in the target form with case-exact equality. Extracted via regex `input\.(\w+)`, applied **only to substrings that the string-literal state machine (§8.1) marks as outside string literals**. DS023 MUST NOT fire on tokens inside Deluge string literals. For chained accesses like `input.Employee_Name1.first_name`, DS023 validates `Employee_Name1`; subfield validation is out of scope (see §15). See CLAUDE.md gotcha #3. |
| DS025 | ERROR | `CustomAction.backing_form` (the `form:` bullet value) exists in the `.ds` form inventory. |
| DS026 | ERROR | `CustomAction` declares `backing_form=X` but the `report_name` report's underlying form is `Z` (X != Z). Requires `DSLandmarks` (or `DSParser`) to expose report→form mapping — add to Task 3 (landmarks). |
| DS006 | ERROR | No two `FormAction` or `CustomAction` objects share the same `link_name` within the IR. (Also emitted by parser as DS006; re-checked here against `.ds` existing content.) |
| DS005 | ERROR | `DelugeBlock.body` is non-empty. (Redundant with parser check; re-validated here as a safety net.) |
| DS027 | ERROR | `display_name` contains unescaped `"`. Fires in validator phase before emitter runs. |
| DS028 | ERROR | Deluge body has unbalanced parentheses (string-literal aware). Fires in validator phase before emitter runs. |
| DS030 | ERROR | A `link_name` from `FormAction` or `CustomAction` already appears as an identifier in the existing `.ds` workflow block. Blocks the apply. Pass `--allow-duplicate-links` to downgrade to DS031 WARNING. |
| DS031 | WARNING | Duplicate `link_name` detected but `--allow-duplicate-links` was passed; proceeding. |
| DS032 | WARNING | Sentinel comment for this playbook already found in `.ds`; re-export from Creator before re-applying. Pass `--allow-reapply` to suppress. |

**DS024 is dropped from v1.** Validation of Deluge `<FormName>[<criteria>]` form-access patterns produces too many false-positives on generic subscripts to implement reliably without a full Deluge parser. Deferred to v2 (see §2.2).

---

## 10. Rule code registry

Consistent with `forgeds._shared.diagnostics.Severity` (src/forgeds/_shared/diagnostics.py:12-16).

**Rule:** Rule codes are component-exclusive; cross-component reuse is a spec bug. If a code appears in two different component rows, that is an error in this document.

| Code | Severity | Component | Meaning |
|---|---|---|---|
| DS001 | ERROR | Parser | H3 action section has no enclosing H2 form context |
| DS002 | INFO | Parser | H2 section has no H3 children; nothing to emit |
| DS003 | WARNING | Parser | Multiple fenced code blocks in one H3; only first used |
| DS004 | ERROR | Parser | H3 classified as CustomAction but `form:` bullet is missing |
| DS005 | ERROR | Parser/Validator | Fenced Deluge block is absent or empty for a named action |
| DS006 | ERROR | Parser/Validator | Duplicate `link_name` across IR actions |
| DS007-DS014 | — | Parser | Reserved for future parser rules |
| DS015 | INFO | Parser | §4 blueprint-transition section detected; deferred (no Deluge block / no actionable event) |
| DS016-DS019 | — | Parser | Reserved for future parser rules |
| DS021 | ERROR | Validator | Form name in FormAction not found in `.ds` form inventory |
| DS022 | ERROR | Validator | Report name in CustomAction not found in `.ds` report inventory |
| DS023 | ERROR | Validator | `input.<field>` token (outside string literals) not found in target form (case-exact) |
| DS024 | — | — | **DROPPED in v1** — `<form>[<expr>]` pattern validation deferred to v2 (too many false-positives; see §2.2) |
| DS025 | ERROR | Validator | `backing_form` in CustomAction not found in `.ds` form inventory |
| DS026 | ERROR | Validator | CustomAction `backing_form` does not match the underlying form of the target report |
| DS027 | ERROR | Validator | `display_name` contains unescaped `"` (fires before emitter) |
| DS028 | ERROR | Validator | Deluge body has unbalanced parentheses (string-literal aware; fires before emitter) |
| DS029 | — | Validator | Reserved |
| DS030 | ERROR | Validator | `link_name` already present in existing `.ds` workflow block; blocks apply (pass `--allow-duplicate-links` to downgrade to DS031) |
| DS031 | WARNING | Validator | Duplicate `link_name` — `--allow-duplicate-links` passed; proceeding |
| DS032 | WARNING | Validator | Sentinel comment for this playbook already found in `.ds`; re-export from Creator first (pass `--allow-reapply` to suppress) |
| DS033-DS039 | — | Validator | Reserved |
| DS040 | WARNING | Emitter | Custom-action backing workflow emitted using UNVERIFIED `on custom action` syntax (exit code ≥ 1) |
| DS041-DS042 | — | Emitter | Reserved |
| DS043 | ERROR | Emitter/CLI | `--custom-action-workflow-mode=form\|standalone` requested; spike-gated (exit 3) until research spike validates syntax. Bypassable only via `FORGEDS_APPLY_PLAYBOOK_SPIKE_OVERRIDE_TESTONLY=1` AND `PYTEST_CURRENT_TEST`. |
| DS044-DS049 | — | Emitter | Reserved |
| DS050 | ERROR | Mutator | Computed insertion point falls between `forms` close and `reports` keyword |
| DS051 | ERROR | Mutator | Computed insertion point falls between `reports` close and `pages` keyword |
| DS052 | ERROR | Mutator | Computed insertion point is at depth 0 (outside any block) |
| DS053 | WARNING | Mutator | In-place mutation (`--out` == `--ds`); original overwritten |
| DS054-DS059 | — | Mutator | Reserved |
| DS060 | ERROR | Landmarks | `forms` block not found in `.ds` |
| DS061 | ERROR | Landmarks | `reports` block not found in `.ds` |
| DS062 | ERROR | Landmarks | Unbalanced braces at EOF (`brace_depth != 0`); aborts with exit 2 |
| DS063 | ERROR | Landmarks | State machine exits with `in_string == True` at EOF — orphaned opening quote; aborts with exit 2 |
| DS064 | WARNING | Landmarks | `workflow` block absent; will be synthesised |
| DS065 | ERROR | Landmarks | Named report from IR not found in `.ds` |
| DS066 | ERROR | Landmarks | Named form from IR not found in `.ds` |
| DS067-DS069 | — | Landmarks | Reserved |
| DS090 | ERROR | CLI | `--out` path exists and `--force` not specified |
| DS091 | ERROR | CLI | `--ds` file does not exist or is not readable |
| DS092 | ERROR | CLI | `--playbook` file does not exist or is not readable |
| DS093-DS099 | — | CLI | Reserved |

---

## 11. CLI surface

```
forgeds-apply-playbook apply
    --ds <path>          (required) source .ds export
    --playbook <path>    (required) playbook markdown
    --out <path>         (required) destination .ds path
    [--force]            overwrite --out if it exists
    [--custom-action-workflow-mode form|standalone|stub-unwired]
                         (default: stub-unwired) backing-workflow emission mode
                         NOTE: form and standalone are spike-gated (exit 3 via DS043)
    [--allow-duplicate-links]   downgrade DS030 ERROR to DS031 WARNING; allow duplicate link_names
    [--allow-reapply]    suppress DS032 sentinel-already-applied warning
    [--ir-dump <path>]   write parsed IR as JSON to this path
    [--json]             emit diagnostic envelope as JSON to stdout
    [--dry-run]          parse + validate + emit preview; no file writes

forgeds-apply-playbook validate
    --ds <path>          (required) source .ds export
    --playbook <path>    (required) playbook markdown
    [--json]             emit diagnostic envelope as JSON to stdout

forgeds-apply-playbook preview
    --ds <path>          (required) source .ds export
    --playbook <path>    (required) playbook markdown
    [--custom-action-workflow-mode form|standalone|stub-unwired]
    [--json]             emit diagnostic envelope as JSON to stdout
```

Exit codes:

| Code | Meaning |
|---|---|
| 0 | Clean — no diagnostics at WARNING or above |
| 1 | Warnings present — file written (apply) or report produced (validate/preview) |
| 2 | Errors present — no `.ds` written; sidecar may still be written |
| 3 | Spike-gate exit — `--custom-action-workflow-mode=form\|standalone` requested without spike validation (DS043). Also reserved for future optional-dep bail-outs. |

---

## 12. Test surface

### Component tests

- `tests/fixtures/apply_playbook/` — all fixture files (see below)
- `tests/test_apply_playbook_parser.py` — unit tests for `PlaybookParser`:
  - Valid H2+H3+fenced block → `FormAction` populated correctly.
  - H3 with `report:` bullet → `CustomAction`.
  - H3 without fenced block → `DeferredSection` + DS015 INFO.
  - Duplicate `link_name` → DS006 ERROR.
  - Blockquote after fence → `DelugeBlock.implementation_notes` populated.
- `tests/test_apply_playbook_landmarks.py` — unit tests for `DSLandmarks`:
  - Nominal `.ds` → all offsets resolved correctly.
  - Missing `forms` block → DS060 ERROR.
  - String-literal with `{` inside → not counted as block open.
  - Missing `workflow` block → DS064 WARNING, not ERROR.
  - `.ds` with a form displayname containing `\"` → not misread as string-toggle; offsets remain valid.
  - `.ds` with a string literal containing `{` and `}` → braces ignored; DSLandmarks output matches expected.
  - `.ds` with intentionally-orphaned opening quote → DS063 ERROR.
  - `test_landmarks_large_file_regression` (against `erm_snapshot_sha256.ds`): asserts (a) brace balance at EOF, (b) `in_string == False` at EOF, (c) every form in `DSParser.forms` is findable in `DSLandmarks.form_bodies`, (d) specific offsets (`forms_open`, `forms_close`, `reports_open`, `reports_close`) match pinned known-good values computed on first pass.
- `tests/test_apply_playbook_validator.py`:
  - Unknown form name → DS021 ERROR.
  - Unknown report name → DS022 ERROR.
  - `input.WRONG_CASE_field` → DS023 ERROR (case-exact).
  - `alert("input.bad_field")` where `.ds` has no `bad_field` → DS023 does NOT fire (false-positive regression for string-literal exclusion).
  - Valid IR → no errors.
  - Duplicate `link_name` in existing `.ds` without `--allow-duplicate-links` → DS030 ERROR.
  - Duplicate `link_name` with `--allow-duplicate-links` → DS031 WARNING, apply proceeds.
  - Sentinel already present in `.ds` without `--allow-reapply` → DS032 WARNING, exit 1.
  - `display_name` containing `"` → DS027 ERROR.
  - Deluge body with unbalanced parens → DS028 ERROR.
  - CustomAction `backing_form` != report's underlying form → DS026 ERROR.
- `tests/test_apply_playbook_emitter.py`:
  - `FormAction` → expected `.ds` workflow-entry string (includes sentinel comment line).
  - `CustomAction` (mode `form`, spike override set) → custom-action block + backing workflow + DS040 WARNING; `record event` uses `link_name` not `display_name`.
  - `CustomAction` (mode `stub-unwired`) → custom-action block only; no DS040.
  - `CustomAction` (mode `form`, no spike override) → DS043 ERROR, exit 3.
  - Implementation note in `DelugeBlock` → emitted as `/* NOTE ... */` comment.
  - Emitted workflow entry contains sentinel comment `/* forgeds-apply-playbook: from playbook <basename> sha256=<first-8> */`.
- `tests/test_apply_playbook_mutator.py`:
  - Insertion into existing `workflow { }` → content appended before closing `}`.
  - Insertion with no `workflow` block → synthesised block placed between reports-close and pages-open.
  - Guardrail: computed offset in forms-reports gap → DS050 ERROR, no file written.
  - Atomicity: fixture with 5 insertions where the 3rd triggers DS050 → assert output file byte-equals input file (no partial mutation).

### Required end-to-end cases (verbatim from blueprint §8)

**E2E-1: happy path apply**
```
Fixture: tests/fixtures/apply_playbook/e2e_basic.ds
         tests/fixtures/apply_playbook/e2e_basic_playbook.md
Command: forgeds-apply-playbook apply --ds e2e_basic.ds --playbook e2e_basic_playbook.md --out e2e_basic_out.ds
Assert:  exit 0; e2e_basic_out.ds contains the expected workflow entry block; sidecar .md exists.
```

**E2E-2: field case mismatch → error, no output**
```
Fixture: tests/fixtures/apply_playbook/e2e_case_mismatch.ds
         tests/fixtures/apply_playbook/e2e_case_mismatch_playbook.md
         (playbook references input.Merchant_Account; ds has merchant_account)
Command: forgeds-apply-playbook apply --ds e2e_case_mismatch.ds --playbook e2e_case_mismatch_playbook.md --out /tmp/out.ds
Assert:  exit 2; DS023 ERROR in diagnostics; /tmp/out.ds not created.
```

**E2E-3: custom-action UNVERIFIED mode warning (spike-gate bypassed in pytest)**
```
Fixture: tests/fixtures/apply_playbook/e2e_custom_action.ds
         tests/fixtures/apply_playbook/e2e_custom_action_playbook.md
Command: forgeds-apply-playbook apply --ds e2e_custom_action.ds --playbook e2e_custom_action_playbook.md --out e2e_custom_action_out.ds --custom-action-workflow-mode form
Env:     FORGEDS_APPLY_PLAYBOOK_SPIKE_OVERRIDE_TESTONLY=1 (pytest sets PYTEST_CURRENT_TEST automatically)
Assert:  exit 1; DS040 WARNING present in diagnostics; emitted .ds contains 'on custom action <link_name>' record event line (link_name, not display_name).
```

**E2E-4: custom-action spike gate blocks without override**
```
Fixture: same as E2E-3
Command: forgeds-apply-playbook apply --ds e2e_custom_action.ds --playbook e2e_custom_action_playbook.md --out e2e_custom_action_out.ds --custom-action-workflow-mode form
Env:     (no override env var)
Assert:  exit 3; DS043 ERROR in diagnostics; no .ds written.
```

### Fixture files list

```
tests/fixtures/apply_playbook/
    e2e_basic.ds
    e2e_basic_playbook.md
    e2e_basic_out.expected.ds          # golden output for E2E-1
    e2e_case_mismatch.ds
    e2e_case_mismatch_playbook.md
    e2e_custom_action.ds
    e2e_custom_action_playbook.md
    e2e_custom_action_out.expected.ds  # golden output for E2E-3
    minimal_no_workflow.ds             # .ds with no workflow block (for DS064 test)
    malformed_unclosed_forms.ds        # .ds with unclosed forms block (for DS062 test)
    string_escape_displayname.ds       # .ds with form displayname containing \" (DS063/escape convention test)
    string_literal_braces.ds           # .ds with string literal containing { and } inside a field value
    orphaned_quote.ds                  # .ds with intentionally-orphaned opening quote (DS063 test)
    display_name_unescaped_quote_playbook.md  # playbook with display_name containing " (DS027 fixture)
    unbalanced_parens_playbook.md      # playbook with Deluge body with unbalanced parens (DS028 fixture)
    string_literal_false_positive_playbook.md # playbook with alert("input.bad_field") — DS023 must NOT fire
    erm_snapshot_sha256.ds             # pinned copy of real ERM .ds (or synthetic 3000+-line equivalent);
                                       # if too large to commit, store SHA256 + fetch/generate logic
```

**Task 0 note:** All fixtures listed above (including `erm_snapshot_sha256.ds`) must be generated as the first task before any implementation work. If the real ERM `.ds` file exceeds repo size limits for committing, generate a synthetic 3000+-line fixture with equivalent structural complexity — forms with many fields, reports with conditional formatting, picklists containing braces — and record its SHA256 in a companion `.sha256` file.

---

## 13. Envelope contract

- Tool name: `"forgeds-apply-playbook"` (passed as the `tool` argument to `to_json_v1` in `forgeds._shared.envelope.to_json_v1`; see src/forgeds/_shared/envelope.py:20-36). This uses the `forgeds-<name>` convention, aligning with `forgeds-lint`, `forgeds-lint-access`, `forgeds-lint-hybrid`.
- Envelope version: `"1"` — no version bump required. Per CLAUDE.md envelope versioning policy: "Adding a new `tool` value that reuses the current shape does not bump." `forgeds-apply-playbook` reuses the existing `Diagnostic` shape unchanged.
- `ENVELOPE_VERSION` constant in `src/forgeds/_shared/envelope.py:15` is `"1"` and must not be changed for this feature.
- The sidecar report MD is not part of the JSON envelope; it is a separate human-readable artefact written to disk.

**Namespace note:** Newer Phase-2C tools (`bundle_widget`, `scaffold_widget`) use the module-name convention in their `tool` field. The inconsistency in the ForgeDS namespace is pre-existing drift; future work should normalise. New tools from this point forward SHOULD adopt `forgeds-<name>` per this decision.

---

## 14. Open questions / known risks

### Risk 1 — UNVERIFIED: `on custom action` record-event syntax — HIGH (ship-blocker)

The exact `.ds` syntax for a workflow entry that responds to a custom-action button click has not been verified against a real Creator `.ds` export. The emitted shape in §7.3 is based on community documentation only. If incorrect, Creator will silently reject the import.

**Mitigation:** DS040 WARNING flags every emission (exit code ≥ 1). DS043 spike gate blocks `--custom-action-workflow-mode=form|standalone` (exit 3) until a research spike validates the syntax. The `--custom-action-workflow-mode stub-unwired` escape hatch (default) allows users to skip backing-workflow emission and wire the action manually. Resolving this risk is a ship-blocker for removing the UNVERIFIED marker from §7.3.

### Risk 2 — Brace-depth state machine correctness in string literals — HIGH (ship-blocker)

The landmarks machine counts `{` and `}` inside double-quoted string values as block delimiters unless the `in_string` flag suppresses them. If a Deluge body or display name contains an unescaped `"`, the flag may desynchronise and all subsequent offset calculations will be wrong.

**Mitigation:** The implementer MUST perform an empirical study (open the real ERM `.ds` and locate at least 2 strings containing `"` or `{`) and document the escape convention in §7.4 before finalising `landmarks.py`. DS062 (unbalanced braces at EOF) and DS063 (orphaned opening quote at EOF) both abort with exit 2. Three fixtures cover the escape edge cases. Resolving this risk is a ship-blocker for correct landmark detection.

### Risk 3 — Duplicate application produces silently corrupt `.ds` — MEDIUM

As documented in §8.4, running apply twice without re-exporting from Creator duplicates entries. Creator's import behaviour on duplicate workflow-entry names is not documented and may silently discard the duplicate or raise a generic error.

**Mitigation:** DS030 ERROR on known duplicates (blocks apply by default; pass `--allow-duplicate-links` to downgrade). Sentinel-comment mechanism (DS032) detects previous applications of the same playbook for approximately 15 LOC cost. The intended workflow (re-export before re-apply) must be documented in CLI `--help` text and sidecar report header.

### Risk 4 — `parse_ds_export.DSParser` form-name extraction coverage — MEDIUM (prerequisite fix required)

The existing `DSParser` (src/forgeds/core/parse_ds_export.py:69) skips forms with no fields (`if not fields: return None` at line 152). A form that exists in the `.ds` but has zero parsed fields will not appear in the inventory, causing a false DS021 ERROR.

**Mitigation:** Land a prerequisite fix to `parse_ds_export.py` that emits zero-field `FormDef`s with an empty `fields` list (approximately 3 LOC change: update lines 96 and 150-151 to stop filtering on `form.fields` truthiness). This is a separate small PR and MUST land before Task 4 (validator) is implemented. Do NOT build a shadow form-discovery path in `landmarks.py` — fix DSParser directly.

### Risk 5 — `forgeds.yaml` not required — LOW

Unlike most ForgeDS tools, `apply_playbook` does not need `forgeds.yaml` for its core operation. If a consumer project has no `forgeds.yaml`, `load_config()` will return defaults; this is fine. However, the CLI should not fail if `forgeds.yaml` is absent, and it must not call `get_db_dir()` unconditionally.

**Mitigation:** Do not call `load_config()` at module import time. Only call it inside `main()` and only if a config-dependent feature (e.g., future `custom_apis` cross-check) is needed. The core apply pipeline is config-independent.

---

## 15. Implementation notes for workers

- **Case-sensitive field references are the #1 bug source.** DS023 is the most critical validator rule. Write the E2E-2 fixture first and make it pass before implementing any emitter code. DS023 applies only to bare `input.<field>` tokens outside string literals; chained accesses like `input.Employee_Name1.first_name` validate the first segment (`Employee_Name1`) only — subfield validation (`first_name`) is out of scope for v1.
- **Test fixtures live at `tests/fixtures/apply_playbook/`.** Create the directory. Minimal fixtures: a `.ds` with one form (two fields, mixed case link names) and one report; a playbook MD with one FormAction and one CustomAction.
- **Reuse `DSParser` from `parse_ds_export.py` for form/field inventory.** Do not duplicate the parsing logic. Import `from forgeds.core.parse_ds_export import DSParser, FormDef`. The prerequisite DSParser fix (Risk 4) must land before Task 4.
- **Sentinel comment is in scope for v1.** Emit `/* forgeds-apply-playbook: from playbook <basename> sha256=<first-8> */` at the top of each generated workflow entry. Scan for existing sentinels in the mutator before splicing; emit DS032 WARNING if found.
- **Insertions must be applied in reverse offset order.** The mutator must sort `EmitResult` list by insertion offset descending before splicing; otherwise earlier insertions shift later offsets. This is a common off-by-one source — test with multi-action playbooks.
- **The `workflow { }` block sits inside the top-level application block, not inside `forms { }` or `reports { }`.** Its correct position is after `reports { }` and before `pages { }`. Do not confuse with per-form workflow entries in the `forms { }` block (there are no such nested workflow blocks in the `.ds` format; all workflow entries are in the single top-level `workflow { }` block).
- **`--json` output goes to stdout; human-readable output goes to stderr.** This matches the convention used by all other ForgeDS linters (`lint_deluge.py`, `lint_hybrid.py`). Do not mix channels.

---

## 16. Build sequence

**Prerequisite task (separate PR, must land before Task 4):** Fix `parse_ds_export.py` zero-field skip. Update lines 96 and 150-151 to stop filtering on `form.fields` truthiness — emit zero-field `FormDef` with `fields=[]`. Approximately 3 LOC + 1 test. This must land before validator (Task 4) depends on the fixed DSParser.

| Task | Description | Blocks on | Can parallel with |
|---|---|---|---|
| Task 0 | Fixture generation — ALL fixtures from §12 including `erm_snapshot_sha256.ds` | — | — |
| Task 1 | IR (`ir.py`) + diagnostics codes (`DS###` constants) | Task 0 | — |
| Task 2 | Parser (`parser.py`) + parser tests | Task 1 | Task 3 |
| Task 3 | Landmarks (`landmarks.py`) + landmarks tests; includes §7.4 empirical study | Task 1 | Task 2 |
| Task 4 | Validator (`validator.py`) + validator tests | Task 1 + Task 3 + prerequisite DSParser fix | — |
| Task 5 | Emitter (`emitter.py`) + emitter tests | Task 1 | — |
| Task 6 | Mutator (`mutator.py`) + mutator tests | Task 3 + Task 5 | — |
| Task 7 | Orchestrator (`orchestrator.py`) + E2E tests | All previous tasks | — |
| Task 8 | CLI wiring (`cli.py`) + `--help` text + CLAUDE.md rule-code table update | Task 7 | — |

Tasks 2 and 3 may run in parallel after Task 1. Tasks 4 and 5 may run in parallel after Task 1 (Task 4 also needs Task 3 and the prerequisite fix). Task 6 blocks on both Task 3 and Task 5.
