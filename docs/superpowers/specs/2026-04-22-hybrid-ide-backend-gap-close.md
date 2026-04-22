# Hybrid-IDE Backend Gap Close — Design Spec

**Date:** 2026-04-22
**Status:** Design, awaiting plan + implementation
**Supersedes/extends:** `2026-04-21-hybrid-ide-design.md` § "Other Mocked Handlers"
**Scope:** Bridge-backend only (Cluster B). Frontend work (Cluster A) is owned by a parallel agent and is explicitly out of scope here.

---

## 1. Context

The 2026-04-21 hybrid-IDE design shipped with four bridge handlers explicitly marked **MOCK**:

| Handler | Intended behaviour | Current state |
|---|---|---|
| `handle_ai_chat` | Route to Claude API with project context | Returns keyword-matched canned strings |
| `handle_inspect_element` | Query parsed AST for relationships + usages | Returns hardcoded per-`element_id` dict lookups |
| `handle_build_project` | Invoke scaffold/build tools | Synthesises fake files and simulates progress |
| `handle_refine_prompt` | Claude-generated structured project sections from idea text | Returns hardcoded sections |

All four block real IDE UX. This spec closes them with real implementations.

The underlying infrastructure needed — Deluge AST (`src/forgeds/lang/`), scaffold/build tools (`src/forgeds/core/`), linter (`src/forgeds/core/lint_deluge.py`), knowledge graph (`src/forgeds/knowledge/`) — already exists in the repo. This spec is about wiring, not foundational work.

---

## 2. Scope and non-goals

**In scope:**
- Four handlers: `handle_ai_chat`, `handle_inspect_element`, `handle_build_project`, `handle_refine_prompt`.
- Shared infrastructure required by the above: Anthropic SDK integration, credentials resolution, effort-level → model mapping, `bridge.ts` type-union fix, error response standardisation, cancellation protocol, logging.

**Out of scope (non-goals):**
- Frontend work (panels, slider UI, thumbs-up/down UX, session lifecycle in-browser). Owned by the frontend agent.
- `handle_parse_ds` — already a real implementation; not touched here except to add relationship-graph hookup (§5).
- Git/PR/commit operations — separate gap, not Cluster B.
- Deluge AST authoring — already exists in `src/forgeds/lang/`; this spec only *consumes* it.
- New bridge transport features (message framing, reconnection) — no change.
- Persistence of chat history across bridge restarts — deliberately in-memory only.

---

## 3. Shared infrastructure

### 3.1 Dependencies

Add to `bridge/requirements.txt`:

```text
anthropic>=0.39.0
pyyaml>=6.0
```

**UNCERTAIN:** `anthropic` version `>=0.39.0` is chosen on the assumption it supports extended thinking + prompt caching + streaming on Opus 4.7 / Sonnet 4.6 / Haiku 4.5. Implementation must verify the minimum version at install time; adjust if newer baseline is required.

### 3.2 Credentials

**Resolution order** (first match wins):

1. Environment variable `ANTHROPIC_API_KEY`.
2. File `~/.forgeds/anthropic.yaml` with shape:
   ```yaml
   api_key: sk-ant-xxxxxxxxxxxxxxxx
   ```

**Rationale:** home-level not project-level because the Anthropic key is a tool-scoped secret — one key per developer install, not per ForgeDS project.

**Template** checked into repo at `templates/anthropic.yaml.template`:

```yaml
# ForgeDS — Anthropic API credentials
# Copy to ~/.forgeds/anthropic.yaml and fill in your key.
# Alternatively, set ANTHROPIC_API_KEY environment variable.
api_key: YOUR_ANTHROPIC_API_KEY_HERE
```

**Defence-in-depth:** add `config/anthropic.yaml` to the root `.gitignore` even though the canonical location is the home directory — prevents accidental commits if a developer drops the file into the project.

**Missing credentials behaviour:** handlers that need Claude (`ai_chat`, `refine_prompt`, `build_project` fill mode) return:

```json
{
  "error": "Anthropic API key not configured.",
  "code": "no_api_key",
  "details": {
    "setup_hint": "Set ANTHROPIC_API_KEY or create ~/.forgeds/anthropic.yaml (see templates/anthropic.yaml.template)"
  }
}
```

`handle_inspect_element` does not require Claude and works regardless.

### 3.3 Effort levels

Single source of truth in `bridge/claude_config.py` (new file):

```python
EFFORT_LEVELS = {
    "low":    {"model": "claude-haiku-4-5-20251001", "thinking": None,       "max_tokens": 2048},
    "medium": {"model": "claude-haiku-4-5-20251001", "thinking": 4096,       "max_tokens": 4096},
    "high":   {"model": "claude-sonnet-4-6",         "thinking": None,       "max_tokens": 4096},
    "max":    {"model": "claude-opus-4-7",           "thinking": 16384,      "max_tokens": 8192},
}
DEFAULT_IDE_EFFORT = "high"          # ai_chat default
DEFAULT_APP_CREATION_EFFORT = "max"  # refine_prompt + build_project fill
```

**Semantics:** the effort level is a session-scoped setting. Changing it mid-session applies to the next message; conversation history is preserved; prompt cache is invalidated at the change point (expected, because a different model cannot reuse another model's cache).

**UNCERTAIN:** the `16384` thinking budget for Max/Opus is a proposal based on typical code-generation needs; tune during implementation.

### 3.4 bridge.ts type-union fix

Current file `web/src/types/bridge.ts` declares:

```typescript
export interface BridgeMessage {
  id: string;
  type: "refine_prompt" | "build_project" | "lint_check" | "get_status";
  data: Record<string, unknown>;
}
```

Eight additional handler types are already dispatched via `send()` but missing from the union. This is a pre-existing bug; fix as part of this spec.

**Target:**

```typescript
export type BridgeMessageType =
  | "refine_prompt"
  | "build_project"
  | "lint_check"
  | "get_status"
  | "parse_ds"
  | "read_file"
  | "inspect_element"
  | "ai_chat"
  | "get_schema"
  | "run_validation"
  | "mock_upload"
  | "generate_api_code"
  | "get_api_list"
  | "export_api";

export interface BridgeMessage {
  id: string;
  type: BridgeMessageType;
  data: Record<string, unknown>;
}
```

This is a cross-cutting type-only change; no runtime impact.

### 3.5 Error response shape

All handlers return one of:

**Success:**
```json
{ /* handler-specific payload */ }
```

**Error:**
```json
{
  "error": "human-readable message",
  "code": "machine_readable_code",
  "details": { "optional": "structured_info" }
}
```

Standard `code` values:
- `no_api_key` — credentials missing
- `rate_limited` — Anthropic API returned 429
- `upstream_error` — Anthropic API returned 5xx
- `parse_error` — Claude response could not be parsed into expected schema
- `invalid_request` — required field missing from request
- `not_found` — referenced entity (session_id, scaffold_id, element_id) does not exist
- `timeout` — operation exceeded its time budget
- `cancelled` — client cancelled the operation

### 3.6 Cancellation protocol

For streaming handlers (`ai_chat`, `build_project`):

1. Client sends `{cancel: true, id: <original_message_id>}` on the same WebSocket.
2. Server maintains `active_streams: dict[id, asyncio.Event]`.
3. Handler checks `event.is_set()` between chunks; if set, sends `{error: "...", code: "cancelled"}` and returns.

**Non-streaming handlers** (`refine_prompt`, `inspect_element`) — no cancellation; they complete or error quickly.

### 3.7 Logging

Handler exceptions use existing `bridge.enrichment.log_error()`:

```python
log_error({
    "source": "<handler_name>",
    "message": str(exc),
    "request_id": data.get("id"),
    "details": {"traceback": traceback.format_exc()},
})
```

API-key values must never be logged. Request payloads may contain user prompt text — acceptable to log, but hash or truncate in production deployments (configurable; default = log full).

---

## 4. `handle_ai_chat`

### 4.1 Purpose

Real-time project-aware chat with Claude. Replaces keyword-matched canned strings (lines 479–528 of current `bridge/handlers.py`).

### 4.2 Request schema

```python
{
    "message": str,                          # required — user's message
    "session_id": str,                       # required — frontend-generated; identifies conversation
    "effort": "low"|"medium"|"high"|"max",   # optional — defaults to "high"
    "context": {                             # optional — frontend populates
        "ds_summary": str,                   # structural overview of current .ds (e.g. "5 forms, 12 workflows, 3 schedules")
        "open_file": {"path": str, "content": str},
        "recent_diagnostics": [{"file": str, "line": int, "severity": str, "message": str}],
    },
    "critique": str                          # optional — thumbs-down retry feedback
}
```

### 4.3 Response schema

**Streaming chunks** (via `send_fn`):
```json
{ "chunk": { "text": "partial text..." } }
```

**Final response:**
```json
{
  "response": "full assembled text",
  "model": "claude-sonnet-4-6",
  "session_id": "s_abc123",
  "usage": {
    "input_tokens": 1234,
    "output_tokens": 567,
    "cache_read_tokens": 890
  }
}
```

### 4.4 System prompt composition

System prompt is built once per request from three pieces:

1. **Baseline role prompt** — hardcoded in `bridge/prompts.py`:
   > "You are a senior Zoho Creator / Deluge engineer embedded in the ForgeDS IDE. You help the user build, debug, and refine their Zoho Creator app. Follow all project conventions strictly."

2. **Project conventions digest** — loaded from the repo's root `CLAUDE.md` at bridge startup. The Deluge rules section (operators, built-ins, `Added_User` rule, GL null guards, `Compliance_Config` pattern, ESG fields, etc.) forms the bulk.

3. **Current `.ds` context** — if provided in `context.ds_summary`, appended as "Current app context: ..." block.

The full system block is sent with `cache_control: {"type": "ephemeral"}`. This caches the baseline + conventions (stable across requests in a session) for 5 minutes; only the user turn pays full rate.

### 4.5 Session state

```python
_sessions: dict[str, list[dict]] = {}  # session_id -> [{"role": "user"|"assistant", "content": ...}, ...]
_sessions_lock = asyncio.Lock()
```

- Stored in-memory in the bridge process.
- Lost on bridge restart (deliberate — acceptable for short-lived sessions).
- **GC policy:** session evicted after 1 hour of inactivity. Implementation: background task sweeping `_sessions` every 5 minutes.

### 4.6 Critique handling

If `critique` is present, the previous assistant turn in history is kept, and a synthetic user turn is appended before the new message:

```
[previous assistant turn]
[synthetic user turn]: "I didn't find that response useful. Feedback: {critique}. Please revise."
[real user turn]: {message}
```

This lets Claude see the rejected output and the critique together, leading to a revised answer without losing history context.

### 4.7 Streaming implementation

```python
async with anthropic_client.messages.stream(
    model=effort_config["model"],
    max_tokens=effort_config["max_tokens"],
    system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
    messages=conversation,
    thinking=({"type": "enabled", "budget_tokens": effort_config["thinking"]}
              if effort_config["thinking"] else None),
) as stream:
    async for text in stream.text_stream:
        if event.is_set():  # cancellation check
            return {"error": "...", "code": "cancelled"}
        await send_fn({"chunk": {"text": text}})
    final = await stream.get_final_message()

return {
    "response": "".join(all_text),
    "model": effort_config["model"],
    "session_id": session_id,
    "usage": {
        "input_tokens": final.usage.input_tokens,
        "output_tokens": final.usage.output_tokens,
        "cache_read_tokens": getattr(final.usage, "cache_read_input_tokens", 0),
    },
}
```

**UNCERTAIN ABOUT SYNTAX:** exact Anthropic SDK calling convention for `thinking=` and cache-read token attribute name may differ between versions. Verify against the installed SDK during implementation.

### 4.8 Example I/O

**Request:**
```json
{
  "id": "msg_001",
  "type": "ai_chat",
  "data": {
    "message": "Why does my on_validate script fail when GL_Account is empty?",
    "session_id": "s_abc123",
    "effort": "high",
    "context": {
      "ds_summary": "5 forms (Expense_Claims, GL_Accounts, ...), 12 workflows",
      "open_file": {
        "path": "src/deluge/form-workflows/on_validate.dg",
        "content": "glRec = GL_Accounts[ID == input.GL_Account];\nif (glRec.count() > 0) { ... }"
      }
    }
  }
}
```

**Expected response:** Claude identifies missing null guard (`glRec != null &&`) per CLAUDE.md Deluge rules, streams explanation + corrected snippet.

---

## 5. `handle_inspect_element`

### 5.1 Purpose

Return structural relationships and code usages for a selected tree element, computed from real Deluge AST and `.ds` structure. Replaces hardcoded dict lookups (lines 384–473 of current `handlers.py`).

### 5.2 Strategy

Eager graph construction. At `handle_parse_ds` completion, build a `RelationshipGraph` and cache it. `handle_inspect_element` becomes an O(1) lookup plus formatting.

**Why eager:** for the ERM app (~5 forms, ~30 workflows) the full walk is sub-second. Lazy per-request walks would duplicate work and introduce user-visible latency in the Inspector panel.

**Invalidation:** graph keyed by `(session_id, ds_file_hash)`. A re-parse of the same `.ds` regenerates the graph. A new `.ds` upload produces a new key; old graph evicted.

### 5.3 Graph schema

```python
@dataclass
class NodeInfo:
    id: str                      # stable ID (e.g. "form:Expense_Claims", "field:Expense_Claims.Amount_ZAR")
    element_type: str            # "form" | "field" | "workflow" | "schedule" | "approval" | "report" | "api" | "function"
    display_name: str
    properties: dict             # type-specific

@dataclass
class Edge:
    source: str                  # NodeInfo.id
    target: str                  # NodeInfo.id OR external ref (see §5.6)
    edge_type: str               # enumerated (see §5.4)
    metadata: dict = field(default_factory=dict)  # e.g. {"file": str, "line": int}

@dataclass
class Usage:
    identifier: str              # name of referenced symbol
    file: str
    line: int
    context: str                 # the source line text, trimmed

@dataclass
class RelationshipGraph:
    nodes: dict[str, NodeInfo]
    edges: list[Edge]
    usages: dict[str, list[Usage]]   # identifier -> all its usages
    external_refs: set[str]          # unresolved symbols
```

### 5.4 Edge types (enumerated)

| Edge type | Source → Target | Notes |
|---|---|---|
| `form_has_field` | form → field | |
| `form_has_workflow` | form → workflow | |
| `form_has_schedule` | form → schedule | |
| `form_has_approval` | form → approval | |
| `form_has_report` | form → report | |
| `workflow_triggered_on` | workflow → form | with `{trigger: "on_add"/"on_validate"/...}` |
| `workflow_queries_form` | workflow → form | via `FormName[criteria]` |
| `workflow_inserts_into` | workflow → form | via `insert into FormName [...]` |
| `workflow_references_gl` | workflow → form:GL_Accounts | specific case of `queries_form`, worth surfacing separately |
| `workflow_references_config_key` | workflow → form:Compliance_Config | same |
| `field_read_by` | field → workflow | `input.FieldName` or `rec.FieldName` |
| `field_written_by` | field → workflow | `input.FieldName = X` or `row.FieldName = X` |
| `field_lookup_target` | field → form | lookup relationships |
| `field_lookup_source` | field → form | reverse of above |
| `function_calls_function` | function → function | |
| `report_source` | report → form | |
| `api_queries_form` | api → form | |
| `schedule_targets_form` | schedule → form | |
| `approval_reviews_form` | approval → form | |

### 5.5 Graph build process

1. **Form/field nodes** — from `DSParser.forms`.
2. **Workflow/schedule/approval/api nodes** — from `DSParser.scripts`.
3. **Per-script AST walk** — use `forgeds.lang.lexer` + `forgeds.lang.parser` to produce AST from each `.dg` script body. Walker (new module: `bridge/relationship_builder.py`) collects:
   - Query calls: `FormName[criteria]` → `workflow_queries_form` edge
   - Insert tasks: `insert into FormName [...]` → `workflow_inserts_into` edge
   - Field reads: `input.X`, `rec.X`, `row.X` → `field_read_by` edge (requires form-context tracking during walk)
   - Field writes: assignment LHS on `input.X` / `row.X` / `rec.X` → `field_written_by` edge
   - Function calls → `function_calls_function` edge
   - Special identifiers: `GL_Accounts`, `Compliance_Config` → distinguished edge types
4. **Resolution** — identifiers resolved against node table. Unresolved → `external_refs` set plus an edge with `target` preserved as-is and metadata `{"unresolved": true}`.
5. **Usages index** — every identifier reference recorded as `Usage(identifier, file, line, context)`.

**UNCERTAIN:** the exact API surface of `forgeds.lang.parser` (class names, method signatures, AST node types) was not verified during recon. Implementation must read `src/forgeds/lang/` first and adapt. If the parser cannot produce the needed AST detail, a fallback regex-based walker is acceptable for v1 with a follow-up gap item logged.

### 5.6 External references

A workflow referencing `SomeForm` that is not in the parsed `.ds` is a real scenario (the `.ds` export might not include every form). These must not silently drop. They are:

- Added to `RelationshipGraph.external_refs`
- Included in the response with `{target: "SomeForm", type: "...", unresolved: true, note: "form not defined in this .ds export"}`

Frontend renders them in a muted style with the note tooltip.

### 5.7 Response per element type

**Form:**
```json
{
  "properties": {
    "fieldCount": 8,
    "hasWorkflows": true,
    "displayName": "Expense Claims",
    "enrichmentLevel": "bridge-enriched"
  },
  "fields": [{"id": "field:Expense_Claims.Claim_ID", "name": "Claim_ID", "type": "Auto Number"}, ...],
  "relationships": [
    {"target": "form:GL_Accounts",       "targetName": "GL Accounts",       "type": "field_lookup_target"},
    {"target": "workflow:on_validate",   "targetName": "on_validate",       "type": "form_has_workflow"},
    ...
  ],
  "usages": []
}
```

**Field:**
```json
{
  "properties": {
    "type": "Decimal",
    "form": "Expense Claims",
    "displayName": "Amount (ZAR)",
    "required": true,
    "unique": false
  },
  "relationships": [
    {"target": "workflow:on_validate", "type": "field_read_by"},
    {"target": "workflow:on_success",  "type": "field_written_by"}
  ],
  "usages": [
    {"script": "on_validate.dg", "line": 2, "context": "claimAmt = input.Amount_ZAR;"},
    {"script": "on_success.dg",  "line": 12, "context": "input.Estimated_Carbon_KG = input.Amount_ZAR * carbonFactor;"}
  ]
}
```

**Workflow / Schedule / Approval / API / Report:** analogous — properties reflect the element type, relationships+usages follow the graph.

### 5.8 Request schema

```python
{
    "element_id": str,        # required; e.g. "field:Expense_Claims.Amount_ZAR"
    "element_type": str,      # required; one of the enumerated types
    "session_id": str         # required; identifies which parsed graph to query
}
```

**Fallback:** unknown `element_id` in known `element_type` → return `{"error": "Element not found in graph.", "code": "not_found", "details": {"element_id": ..., "element_type": ...}}`. No more silent generic stubs.

### 5.9 Example I/O

**Request:**
```json
{
  "id": "msg_002",
  "type": "inspect_element",
  "data": {
    "element_id": "workflow:expense_claim.on_validate",
    "element_type": "workflow",
    "session_id": "s_abc123"
  }
}
```

**Response:** includes workflow properties, relationships (`workflow_triggered_on` Expense_Claims, `workflow_references_config_key` Compliance_Config, `workflow_queries_form` GL_Accounts), and usages.

---

## 6. `handle_build_project`

### 6.1 Purpose

Generate a real Zoho Creator project from refined sections. Two-mode design separates deterministic scaffolding from AI-assisted content fill, matching the user-approval gate in the frontend flow.

### 6.2 Request schema

```python
{
    "mode": "scaffold" | "fill",
    "sections": [...]                        # from refine_prompt output
    "approved_scaffold": {                   # required when mode="fill"
        "scaffold_id": str,
        "files": [...]                       # the scaffold the user approved
    },
    "effort": "low"|...|"max",               # defaults to "max"
    "project_name": str                      # optional; derived from sections[0].title if absent
}
```

### 6.3 Scaffold mode — pipeline

Deterministic; no Claude calls. Invokes existing ForgeDS Python tooling.

1. **Plan extraction** — parse `sections` into a `GenerationPlan`:
   ```python
   @dataclass
   class GenerationPlan:
       project_name: str
       forms: list[str]
       workflows: list[tuple[str, str]]     # (form_name, workflow_name)
       reports: list[str]
       apis: list[str]
       approvals: list[str]
       schedules: list[str]
   ```
2. **Schema generation** — call `forgeds.core.build_ds.build_ds_structure(plan)` (or equivalent — verify at implementation) → `.ds` skeleton with forms + placeholder fields.
3. **Script scaffolding** — for each workflow/script/API in plan: `forgeds.core.scaffold_deluge.scaffold(name, template="skeleton")` → stub `.dg` with function signature + `// TODO: implement` marker.
4. **Config generation** — write `forgeds.yaml`:
   ```yaml
   project:
     name: "{project_name}"
     platform: zoho-creator
     generated_by: ForgeDS IDE
     scaffold_id: {uuid}
   ```
5. **Lint pass** — `forgeds.core.lint_deluge.lint(skeleton_files)` → diagnostic report.
6. **Response**:
   ```json
   {
     "status": "success",
     "project_name": "Expense_Reimbursement",
     "scaffold_id": "sc_b8f2a1",
     "files": [
       {"name": "on_submit.dg", "path": "src/deluge/form-workflows/on_submit.dg",
        "content": "// TODO: implement\nmap on_submit(...) { ... }", "language": "deluge"},
       ...
     ],
     "lint_result": {"errors": 0, "warnings": 3, "details": [...]}
   }
   ```
7. **Streamed progress:**
   ```json
   { "chunk": { "step": 2, "total": 5, "message": "Generating form definitions..." } }
   ```

**Scaffold ID:** UUID, stored in `_active_scaffolds: dict[scaffold_id, GenerationPlan]` in bridge memory for validation during fill mode. Evicted after 24h or on new scaffold for the same session.

**UNCERTAIN:** exact public APIs of `forgeds.core.build_ds`, `forgeds.core.scaffold_deluge`, and `forgeds.core.lint_deluge` were not verified during recon. Implementation must read those modules first. If their current public surface does not match what this spec assumes, wrap them via a thin `bridge/build_pipeline.py` adapter.

### 6.4 Fill mode — pipeline

AI-assisted content generation, runs only after user approval of the scaffold.

1. **Scaffold validation** — verify `approved_scaffold.scaffold_id` exists in `_active_scaffolds`. If missing or expired, return `{"error": "...", "code": "not_found"}`.
2. **Per-file fill loop** — for each skeleton file:
   a. Build prompt: section context for this script + skeleton content + CLAUDE.md Deluge conventions + summary of `forgeds.compiler.lint_rules` (rules this output must satisfy).
   b. Call Claude at requested `effort` (Max default).
   c. Validate response via `forgeds.core.lint_deluge.lint(content)`.
   d. If lint errors: one retry with error details injected into prompt. If still failing: flag in `errors[]` and keep the scaffolded stub for that file.
3. **Schema refinement** — collect field additions/changes proposed across filled scripts. Re-generate `.ds` merging proposed fields with scaffold fields.
4. **Final lint pass** — whole project.
5. **Response:**
   ```json
   {
     "status": "success" | "partial_success",
     "project_name": "...",
     "files": [/* enriched */],
     "lint_result": {...},
     "errors": [
       {"step": "fill:on_validate.dg", "message": "Lint failed twice; kept scaffold stub.", "code": "..."}
     ]
   }
   ```
6. **Streamed progress** — one event per file: `{chunk: {file: "on_validate.dg", stage: "generating"|"linting"|"retrying"|"done"}}`.

### 6.5 Partial-success rule

A single failed fill step does not abort the whole build. Failures accumulate in `errors[]`; successful files retain their real content; failed files retain their scaffold. Frontend displays the `errors[]` list to the user.

### 6.6 Example I/O

**Scaffold request:**
```json
{
  "id": "msg_003",
  "type": "build_project",
  "data": {
    "mode": "scaffold",
    "sections": [
      {"id": "forms", "title": "Forms", "items": ["Expense_Claims", "GL_Accounts"]},
      {"id": "workflows", "title": "Workflows", "items": ["on_submit_validate"]}
    ],
    "effort": "max",
    "project_name": "Expense_Reimbursement"
  }
}
```

**Scaffold response** — skeleton files + `scaffold_id: "sc_b8f2a1"`.

**Fill request** — same `type`, `mode: "fill"`, `approved_scaffold.scaffold_id = "sc_b8f2a1"`, `approved_scaffold.files = <scaffold response files>`.

**Fill response** — real script contents in each file, lint-clean or flagged in `errors[]`.

---

## 7. `handle_refine_prompt`

### 7.1 Purpose

Convert raw user idea text into a structured Zoho Creator project specification (forms, workflows, reports, approvals, APIs). Replaces hardcoded mock (lines 27–82 of current `handlers.py`).

### 7.2 Request schema

```python
{
    "prompt": str,                            # required — raw idea text
    "effort": "low"|...|"max",                # optional — defaults to "max"
    "critique": str,                          # optional — thumbs-down iteration feedback
    "prior_output": {"sections": [...]}       # optional — previous output for iteration
}
```

### 7.3 Response schema (preserved from existing mock — no frontend change)

```json
{
  "sections": [
    {
      "id": "forms",
      "title": "Forms",
      "icon": "[F]",
      "content": "...",
      "items": ["Form_Name_1", "Form_Name_2", ...],
      "isEditable": true
    },
    {"id": "workflows", "title": "Workflows", ...},
    {"id": "reports", "title": "Reports & Dashboards", ...},
    {"id": "approvals", "title": "Approval Processes", ...},
    {"id": "apis", "title": "API Endpoints", ...}
  ]
}
```

### 7.4 System prompt

Hardcoded role prompt + project conventions digest + sections-schema specification + few-shot example (reuse the current mock output as a gold example). Cached via `cache_control: {"type": "ephemeral"}`.

### 7.5 Critique loop

When `critique` and `prior_output` are both present, prompt structure:

```
[system prompt as above]

Previous output you produced:
{prior_output as JSON}

The user rejected this with feedback:
{critique}

New idea (may be the same as before):
{prompt}

Produce a revised sections specification.
```

### 7.6 Response parsing

Claude returns a structured JSON block. Extract via:

1. Look for fenced JSON in the response.
2. Parse with `json.loads`.
3. Validate against the `sections` schema with pydantic (or manual dict validation — no hard dep required).
4. On parse/validation failure: one retry with a clarifying "Your previous output was not valid JSON / missing required fields: ..." message.
5. On second failure: return `{"error": "Could not parse model response.", "code": "parse_error", "details": {"raw_response": "<truncated>"}}`.

### 7.7 Non-streaming

refine_prompt returns a single structured object; streaming provides no UX value here (no progressive reveal of a single spec). Single-response flow.

### 7.8 Example I/O

**Request:**
```json
{
  "id": "msg_004",
  "type": "refine_prompt",
  "data": {
    "prompt": "I need an app for tracking staff expense claims with multi-level approval and ESG reporting.",
    "effort": "max"
  }
}
```

**Response:** sections list with `Expense_Claims`, `GL_Accounts`, `Approval_History` forms; validation + approval workflows; an approval-audit report; multi-level approval process; dashboard-summary and claim-status APIs.

**Critique request:** add `{"critique": "add a workflow for automatic GL-code assignment based on vendor", "prior_output": <above response>}` → revised sections including new workflow.

---

## 8. Testing strategy

### 8.1 Unit tests

Located in `bridge/tests/` (new — mirror existing structure).

- **Anthropic client mocking:** patch `AsyncAnthropic` at test boundary. Assert prompt construction, effort→model mapping, cache_control application, critique injection, history growth.
- **Effort-level mapping:** table-driven test over `EFFORT_LEVELS`.
- **Session GC:** inject fake clock, verify eviction after idle threshold.
- **Refine-prompt parsing:** feed mock Claude responses (valid, malformed JSON, missing fields) → assert correct handling.

### 8.2 AST / graph tests

- **Fixture `.ds` files:** check in 2-3 small `.ds` exports under `bridge/tests/fixtures/`. Reuse existing `.ds` exports from the ERM repo where possible.
- **Graph correctness:** parse fixture → assert expected nodes, edges, external_refs, usages.
- **Edge-type coverage:** fixtures designed to exercise every enumerated edge type at least once.

### 8.3 Integration tests

- **Gated by `ANTHROPIC_API_KEY`:** skip if absent (pytest marker `@pytest.mark.live_api`). CI without key skips these.
- **Real-API smoke tests:**
  - `ai_chat` single-turn with a fixed prompt; assert response contains expected substring (e.g. "ifnull").
  - `refine_prompt` with fixed idea; assert response parses + has all 5 sections.
- **End-to-end:**
  - Upload `.ds` → parse → inspect elements → assert graph matches expectations.
  - Scaffold → fill round-trip on a small plan; assert files are lint-clean (or lint failures are reported in `errors[]`).

### 8.4 Budget discipline

Live-API integration tests must stay small — target <$0.10 per full CI run at real rates. Use `effort: "low"` in tests where quality isn't what's being asserted.

---

## 9. Rollout order

Implementation sequence, each step shippable independently:

1. **Shared infrastructure** (§3) — deps, credentials, effort mapping, `bridge.ts` type-union, error shape, cancellation, logging. Unlocks everything downstream.
2. **`handle_ai_chat`** (§4) — smallest real-world change, fastest user-visible improvement. Validates the shared infrastructure on a simple handler before heavier ones.
3. **`handle_refine_prompt`** (§7) — reuses the Claude client, credentials, and effort scaffolding from #2.
4. **`handle_inspect_element`** (§5) — no Claude dep, but the largest structural work (relationship graph + AST walker). Can parallelise with #3 if needed.
5. **`handle_build_project`** (§6) — depends on `inspect_element` graph work (optional — fill prompts benefit from structural context) and on `ai_chat` Claude infra.

Each step ships with its own tests before moving to the next.

---

## 10. Open questions (documented, not blocking)

1. **Chat session TTL** — proposed 1 hour idle eviction; confirm at implementation or tune based on real usage telemetry.
2. **Rate limiting** — no per-user / per-session limit proposed. Deferred to operational concern once real usage is observed. Anthropic SDK surfaces upstream rate-limit errors; `handle_ai_chat` already maps these to `code: "rate_limited"`.
3. **`parse_ds` graph surfacing** — should the `parse_ds` response include a graph *summary* (node counts, external_refs) so frontend can signal "bridge enrichment applied"? Proposed: yes, include counts + `enrichmentLevel: "bridge-enriched"` in `parse_ds` response; full graph accessed only via `inspect_element`. Implementation detail, can be decided at code time.
4. **Windows path handling** — ForgeDS tooling has Windows support (existing CLAUDE.md notes). Scaffold/build output paths must use forward slashes in the response (for the frontend Monaco editor) regardless of OS. Confirm `scaffold_deluge` and `build_ds` outputs are already normalised, or add normalisation at the bridge layer.
5. **Retry policy on Anthropic 5xx** — proposed: one retry with 1s backoff on transient 5xx; immediate error on 4xx. Codify at implementation.

---

## 11. Assumptions and uncertainties

Per OmniScript rules, explicit list of assumptions this design rests on:

1. **Anthropic SDK calling conventions** (streaming with thinking + cache_control) are accurate as drafted — verify against installed version at implementation.
2. **`forgeds.lang.parser`** produces an AST rich enough to extract query calls, inserts, field reads/writes, function calls. If not, implementation can fall back to a regex-based walker for v1 with a gap logged.
3. **`forgeds.core.build_ds` / `scaffold_deluge` / `lint_deluge`** have invokable public APIs. If their current entrypoints are CLI-only, a thin adapter in `bridge/build_pipeline.py` wraps them.
4. **`forgeds.compiler.lint_rules`** exposes an enumerable set of rules with human-readable descriptions usable in a Claude prompt.
5. **`CLAUDE.md` at repo root** is the canonical source for project conventions to digest into the system prompt. Confirmed by inspection.
6. **Effort-level thinking budget for Opus (16384 tokens)** is a starting value, not a binding API constraint. Tunable.
7. **Session-level effort semantics** — changing the slider mid-session affects subsequent messages only, preserves history, invalidates prompt cache at change point. Frontend responsibility to surface the cache-invalidation cost (if any) to the user.
8. **Scaffold ID lifetime** (24h) is a proposal; tune based on real usage.

Items flagged **UNCERTAIN** inline above are the strongest candidates for implementation-time verification.

---

## 12. Self-review

Per OmniScript rule 6, identified weak points:

- **AST walker complexity underspecified.** §5.5 describes what the walker must extract; it does not specify how to handle Deluge control-flow constructs (nested conditionals, loops) when tracking form context for field reads/writes. The walker may need a scope stack. Left to implementation with a note — if the walker becomes a large subproject, split into its own spec.
- **Claude JSON-extraction is fragile.** §7.6 relies on Claude returning a fenced JSON block. Claude sometimes adds prose before/after. The parser must tolerate leading/trailing commentary. Use structured output / JSON mode if the SDK version supports it for refine_prompt.
- **No test for cancel mid-stream.** §8 covers handler logic but not the cancel-race — plan a specific test that cancels during active streaming.
- **Session memory unbounded in principle.** The 1h GC mitigates this; under abuse (many idle sessions) memory could grow. Worst case: bridge restart clears everything. Acceptable.
- **Effort-level change within a session inflates latency invisibly.** When the user moves the slider, their next message incurs a full-cache-miss rebuild. Consider surfacing this in UI ("higher effort; first response will be slower"); frontend concern, out of this spec's scope but noted for the frontend agent.
- **External refs handling depends on frontend UX.** §5.6 specifies backend behaviour; frontend must actually render the `unresolved` flag. Verify with frontend agent before shipping.
- **`build_project` fill mode cost** could be substantial on large scaffolds (N files × Opus call). Add a cost estimate in the scaffold response (`estimated_fill_tokens`) so UI can warn before proceeding. Minor addition; fold into implementation.

Minimal test cases for each handler are embedded in §§4.8, 5.9, 6.6, 7.8.

---

**End of spec.** Next step: `superpowers:writing-plans` to produce an implementation plan from this design.
