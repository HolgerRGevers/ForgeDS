# ForgeDS IDE: Hybrid Progressive Enhancement Design

**Date:** 2026-04-21
**Status:** Approved
**Scope:** Make the IDE functional end-to-end with browser-first parsing + optional bridge enrichment

## Problem

The ForgeDS IDE is deployed on GitHub Pages but the IDE tab shows "No app structure loaded" because:

1. `handle_parse_ds()` in the bridge returns **hardcoded mock data** (never calls the real parser)
2. When the bridge is offline (GitHub Pages), there is **no fallback** — the tree stays empty
3. No mechanism exists for users to upload or select a `.ds` file

## Decision

**Option C: Hybrid Progressive Enhancement** — the IDE works on GitHub Pages with a JavaScript `.ds` parser. When the Python bridge runs locally, it lights up additional features (linting, inspection, AI chat).

### Why

- IDE is already deployed on GitHub Pages and publicly visible
- `TreeNode` format is identical regardless of source (JS or Python)
- Bridge detection (`status === "connected"`) already exists in the codebase
- The Python parser is line-by-line regex — straightforward to port to TypeScript
- Users get a working demo immediately (JS parser) and full power when they run the bridge

## Architecture

### Two Modes, Same Data Format

```
Browser Mode (always available)
  .ds file --> JS parser --> TreeNode[] --> AppTreeExplorer
  File editing via Monaco + Deluge syntax highlighting
  GitHub file browsing via API
  Git operations (commit, PR) via GitHub API

Bridge Mode (optional enhancement)
  Real linting (41+ rules + SQLite DB)
  Inspector with relationships/usages
  AI Chat via Claude
  Build/scaffold via Python CLI tools
```

### State Signal

```typescript
interface AppStructure {
  name: string;
  displayName: string;
  tree: TreeNode[];
  nodeIndex: Map<string, TreeNode>;
  enrichmentLevel?: "local" | "bridge-enriched";  // NEW
}
```

- `enrichmentLevel === "local"` — parsed by JS in browser, basic tree
- `enrichmentLevel === "bridge-enriched"` — bridge has added metadata, relationships, usages

### Loading Flow

```
Page loads
  --> show "Upload .ds file or connect repo"
  --> user uploads .ds file (drag-drop / picker / GitHub fetch)
  --> JS parser runs --> tree renders immediately
  --> if bridge is running: auto-enrich tree with metadata
  --> lint/inspect/AI tabs light up when bridge connected
```

## Phase 1: JavaScript .ds Parser

### What to Port

Port `src/forgeds/core/parse_ds_export.py` class `DSParser` to TypeScript at `web/src/lib/ds-parser.ts`.

**Methods to port (344 lines of parsing logic):**

| Method | Purpose |
|--------|---------|
| `__init__(content)` | Split content into lines, init forms/scripts arrays |
| `parse()` | Orchestrate: _parse_forms, _parse_workflows, _parse_schedules, _parse_approvals |
| `_parse_forms()` | Scan for `form <name>` at 2-3 tab indent, dispatch to _parse_single_form |
| `_parse_single_form()` | Brace-depth tracking, extract displayname, find fields by name-then-paren pattern |
| `_parse_field()` | Paren-depth tracking, extract type/displayname/notes from field block |
| `_parse_workflows()` | Scan for `<name> as "<display>"` pattern, extract form/event/trigger/code |
| `_parse_schedules()` | Delegate to _parse_schedule_block |
| `_parse_schedule_block()` | Extract scheduled task scripts |
| `_parse_approvals()` | Delegate to _parse_approval_block |
| `_parse_approval_block()` | Extract on_approve/on_reject scripts |
| `_extract_script_code()` | Paren-balanced code extraction + de-indentation |

**What NOT to port:** File I/O, CLI args, output generation (markdown/JSON), config loading.

### Data Structures

```typescript
interface FormField {
  linkName: string;      // e.g., "Claim_ID"
  displayName: string;   // e.g., "Claim ID"
  fieldType: string;     // e.g., "Auto Number", "Decimal"
  notes: string;         // e.g., "personal data, default: 0"
}

interface FormDef {
  name: string;          // e.g., "Expense_Claims"
  displayName: string;   // e.g., "Expense Claims"
  fields: FormField[];
}

interface ScriptDef {
  name: string;
  displayName: string;
  form: string;
  event: string;         // "on success", "on validate", "on load", etc.
  trigger: string;       // "on add", "on edit", "scheduled", "approval"
  code: string;          // Extracted Deluge code (de-indented)
  context: string;       // "form-workflow", "scheduled", "approval"
}
```

### Regex Patterns (exact, transfer 1:1)

| Purpose | Pattern |
|---------|---------|
| Form name | `^\t{2,3}form\s+(\w+)\s*$` |
| Display name | `\s*displayname\s*=\s*"([^"]*)"` |
| Field name | `^\s*(?:must have\s+)?(\w+)\s*$` |
| Field type | `type\s*=\s*(\w[\w\s]*)` |
| Field display | `displayname\s*=\s*"([^"]*)"` |
| Script name | `\s*(\w+)\s+as\s+"([^"]*)"` |
| Form ref | `form\s*=\s*(\w+)` |
| Record event | `record event\s*=\s*(.+)` |

### Tree Building

Separate function `buildTree(forms: FormDef[], scripts: ScriptDef[]): TreeNode[]` that converts parser output to the UI tree:

```
app-root (application)
  Forms (section)
    <FormDef.displayName> (form)
      Fields (section)
        <FormField.linkName> (field, fieldType=...)
      Workflows (section)
        <ScriptDef.displayName> (workflow, trigger=..., filePath=...)
  Schedules (section)
    <ScriptDef.displayName> (schedule, trigger=..., filePath=...)
  Approval Processes (section)
    <ScriptDef.displayName> (workflow, trigger=..., filePath=...)
```

**ID generation:** `form-{name.toLowerCase()}`, `field-{linkName.toLowerCase()}`, `wf-{name.toLowerCase()}`, etc.

**filePath synthesis:**
- Form workflow: `src/deluge/form-workflows/{form}.{event_underscored}.dg`
- Scheduled: `src/deluge/scheduled/{name}.dg`
- Approval: `src/deluge/approval-scripts/{name}.dg`

### Edge Cases

1. **Bracket/paren depth** — count per line with `.split(char).length - 1`, check `<= 0` after full line processed
2. **Field skipping** — skip `Section`, `actions`, `submit`, `reset`, `update`, `cancel`
3. **Display name once** — only first `displayname` at brace depth 1 per form
4. **De-indentation** — find min indent of non-empty lines, strip that amount from all lines
5. **Empty code** — scripts with empty code are discarded
6. **Multi-word field types** — regex allows spaces: `(\w[\w\s]*)`

### File Input Mechanisms

1. **Drag-drop** — onDragOver/onDrop on AppTreeExplorer, filter for `.ds` extension
2. **File picker** — upload button in explorer header, `<input type="file" accept=".ds">`
3. **GitHub fetch** — detect `.ds` file in connected repo, fetch content via GitHub API

## Phase 2: Progressive Enhancement UI

### Component Degradation Matrix

| Component | Browser mode (local) | + Bridge (enriched) |
|-----------|---------------------|---------------------|
| AppTreeExplorer | Full tree, search, expand/collapse | Same + richer metadata on nodes |
| Editor (Monaco) | Full editing + Deluge highlighting | Same |
| Lint tab | "Start bridge for linting" message | Real forgeds-lint diagnostics |
| Build tab | Console output only | Real CLI output |
| Relationships tab | "Start bridge for analysis" message | Full relationship graph |
| AI Chat tab | "Start bridge for AI Chat" message | Claude-powered responses |
| Inspector | Basic node info (name, type, fieldType) | Rich: relationships, usages, code refs |

### Files to Modify

| File | Change |
|------|--------|
| `web/src/types/ide.ts` | Add `enrichmentLevel?` to `AppStructure` |
| `web/src/stores/ideStore.ts` | Track `enrichmentLevel`, update `loadAppStructure` |
| `web/src/pages/IdePage.tsx` | New `loadDsFromFile()`, defer bridge connect, add `enrichStructure()` |
| `web/src/components/ide/AppTreeExplorer.tsx` | Add drag-drop + file picker + upload button, update empty state |
| `web/src/components/ide/DevConsole.tsx` | Guard lint/relationships/AI tabs on `enrichmentLevel` |
| `web/src/components/ide/InspectorPanel.tsx` | Show hints when local-only ("connect bridge for full details") |

### IdePage Flow Change

**Before:**
```
mount --> connect() --> wait for bridge --> loadDs() via bridge RPC
```

**After:**
```
mount --> show upload UI
  user uploads .ds --> JS parser --> loadAppStructure({..., enrichmentLevel: "local"})
  optionally: bridge connects --> enrichStructure() --> loadAppStructure({..., enrichmentLevel: "bridge-enriched"})
```

## Phase 3: Bridge Real Parser

### handle_parse_ds() — Mock to Real

Replace the hardcoded mock in `bridge/handlers.py` with a real call to `DSParser`:

```python
async def handle_parse_ds(data: dict) -> dict:
    from forgeds.core.parse_ds_export import DSParser
    
    file_path = data.get("file_path", "")
    content = data.get("content", "")  # Alternative: receive content directly
    
    if not content and file_path:
        content = Path(file_path).read_text(encoding="utf-8")
    
    parser = DSParser(content)
    parser.parse()
    
    return build_tree_response(parser.forms, parser.scripts, file_path)
```

The `build_tree_response()` function converts `FormDef[]` + `ScriptDef[]` to the same TreeNode hierarchy the frontend expects.

**Import requirement:** `pip install -e .` from project root (editable install), or add `src/` to `sys.path`.

### Other Mocked Handlers (Future Work)

| Handler | Status | To make real |
|---------|--------|-------------|
| `handle_lint_check` | REAL | Already calls forgeds-lint subprocess |
| `handle_get_status` | REAL | Already reports bridge/tool versions |
| `handle_read_file` | SEMI-REAL | Reads disk, falls back to mock |
| `handle_parse_ds` | MOCK -> **THIS SPEC** | Call DSParser |
| `handle_inspect_element` | MOCK | Query parsed AST for relationships |
| `handle_refine_prompt` | MOCK | Route to Claude Code CLI |
| `handle_build_project` | MOCK | Invoke scaffold/build tools |
| `handle_ai_chat` | MOCK | Route to Claude API |
| `handle_get_schema` | MOCK | Load from forgeds.yaml + parsed .ds |
| `handle_run_validation` | MOCK | Call forgeds-lint-hybrid |
| `handle_mock_upload` | MOCK | Zoho Creator API integration |
| `handle_generate_api_code` | MOCK | Claude Code CLI |
| `handle_get_api_list` | MOCK | Read from project config |
| `handle_export_api` | MOCK | Format .dg + setup instructions |

## Implementation Sequence

### Phase 1 — JS Parser (unblocks GitHub Pages immediately)
1. Create `web/src/lib/ds-parser.ts` — port DSParser class
2. Create `web/src/lib/ds-tree-builder.ts` — buildTree function (FormDef/ScriptDef -> TreeNode[])
3. Add file upload UI to AppTreeExplorer (drag-drop + picker button)
4. Wire IdePage to call JS parser on file upload
5. Test with existing `.ds` fixtures (`tests/fixtures/validate_ds_good.ds`, `tests/apps/`)

### Phase 2 — Progressive Enhancement UI
6. Add `enrichmentLevel` to AppStructure type in `ide.ts`
7. Update ideStore to track enrichment level
8. Update IdePage loading flow (no auto-bridge, defer connection)
9. Graceful degradation in DevConsole tabs (lint, relationships, AI)
10. Graceful degradation in InspectorPanel
11. Update toolbar status messages

### Phase 3 — Bridge Real Parser
12. Replace mock `handle_parse_ds()` with real DSParser call
13. Add `build_tree_response()` utility in bridge
14. Add content-based parsing (receive .ds content over WebSocket, not just file path)
15. Test bridge-connected flow end-to-end

## Testing Strategy

- **JS parser:** Compare output against Python parser on same `.ds` fixtures
- **Tree building:** Verify TreeNode structure matches what AppTreeExplorer renders
- **Progressive enhancement:** Test with bridge off (tree loads), then bridge on (tabs activate)
- **Bridge parser:** Test with real `.ds` files from exports/

## Non-Goals

- Reports/Pages/APIs extraction from `.ds` files (Python parser doesn't handle these either)
- Full linting in browser (requires SQLite data — bridge-only)
- Mobile responsive layout
- Multi-user real-time collaboration
- Direct Zoho Creator API calls from browser
