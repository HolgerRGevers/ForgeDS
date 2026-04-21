# Hybrid IDE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the ForgeDS IDE tree functional end-to-end — browser-first `.ds` parsing on GitHub Pages, with optional bridge enrichment for linting/inspection.

**Architecture:** Port the Python `DSParser` to TypeScript for in-browser parsing. Add file upload UI (drag-drop + picker). Progressive enhancement: tabs/inspector degrade gracefully when bridge is offline, light up when connected.

**Tech Stack:** TypeScript, React 19, Zustand 5, Vite 6, existing Python bridge (WebSocket on localhost:9876)

**Working directory for all tasks:** `C:\Users\User\OneDrive\Documents\Claude\Projects\VS_Clones\ForgeDS`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `web/src/lib/ds-parser.ts` | TypeScript port of DSParser — parses `.ds` content into FormDef[]/ScriptDef[] |
| `web/src/lib/ds-tree-builder.ts` | Converts FormDef[]/ScriptDef[] into TreeNode[] for AppTreeExplorer |
| `web/src/lib/__tests__/ds-parser.test.ts` | Parser unit tests against `.ds` fixtures |
| `bridge/tree_builder.py` | Converts DSParser output to TreeNode dict hierarchy (shared with JS tree builder) |

### Modified Files
| File | Change |
|------|--------|
| `web/src/types/ide.ts` | Add `enrichmentLevel` to `AppStructure` |
| `web/src/stores/ideStore.ts` | Surface `enrichmentLevel` in store |
| `web/src/pages/IdePage.tsx` | Add `loadDsFromFile()`, defer bridge connect, `enrichStructure()` |
| `web/src/components/ide/AppTreeExplorer.tsx` | Add drag-drop zone, file picker button, updated empty state |
| `web/src/components/ide/DevConsole.tsx` | Guard lint/relationships/AI tabs on bridge status |
| `web/src/components/ide/InspectorPanel.tsx` | Hints when bridge offline |
| `bridge/handlers.py` | Replace mock `handle_parse_ds()` with real DSParser call |

---

## Task 1: TypeScript DSParser — Data Types and Form Parsing

**Files:**
- Create: `web/src/lib/ds-parser.ts`

- [ ] **Step 1: Create ds-parser.ts with types and constructor**

```typescript
// web/src/lib/ds-parser.ts

export interface FormField {
  linkName: string;
  displayName: string;
  fieldType: string;
  notes: string;
}

export interface FormDef {
  name: string;
  displayName: string;
  fields: FormField[];
}

export interface ScriptDef {
  name: string;
  displayName: string;
  form: string;
  event: string;
  trigger: string;
  code: string;
  context: "form-workflow" | "scheduled" | "approval";
}

const SKIP_FIELDS = new Set(["Section", "actions", "submit", "reset", "update", "cancel"]);

export class DSParser {
  private lines: string[];
  public forms: FormDef[] = [];
  public scripts: ScriptDef[] = [];

  constructor(content: string) {
    this.lines = content.split("\n");
  }

  parse(): void {
    this.parseForms();
    this.parseWorkflows();
    this.parseSchedules();
    this.parseApprovals();
  }

  private countChar(s: string, ch: string): number {
    let count = 0;
    for (const c of s) if (c === ch) count++;
    return count;
  }

  private parseForms(): void {
    for (let i = 0; i < this.lines.length; i++) {
      const m = this.lines[i].match(/^\t{2,3}form\s+(\w+)\s*$/);
      if (m && i + 1 < this.lines.length && this.lines[i + 1].trim() === "{") {
        const form = this.parseSingleForm(m[1], i);
        if (form && form.fields.length > 0) {
          this.forms.push(form);
        }
      }
    }
  }

  private parseSingleForm(formName: string, start: number): FormDef | null {
    let displayName = formName;
    const fields: FormField[] = [];
    let braceDepth = 0;
    let inForm = false;
    let gotDisplayName = false;

    let i = start;
    while (i < this.lines.length) {
      const stripped = this.lines[i].trim();

      if (stripped.includes("{")) {
        braceDepth += this.countChar(stripped, "{");
        if (!inForm) inForm = true;
      }
      if (stripped.includes("}")) {
        braceDepth -= this.countChar(stripped, "}");
        if (inForm && braceDepth <= 0) break;
      }

      // Extract form-level displayname (first at depth 1)
      const dm = stripped.match(/^\s*displayname\s*=\s*"([^"]*)"/);
      if (dm && braceDepth === 1 && !gotDisplayName) {
        displayName = dm[1];
        gotDisplayName = true;
      }

      // Detect field: word alone on line, next line is (
      const fm = stripped.match(/^\s*(?:must have\s+)?(\w+)\s*$/);
      if (fm && braceDepth === 1 && i + 1 < this.lines.length) {
        const nextLine = this.lines[i + 1].trim();
        if (nextLine === "(") {
          const fieldLink = fm[1];
          if (!SKIP_FIELDS.has(fieldLink)) {
            const f = this.parseField(fieldLink, i + 1);
            if (f) fields.push(f);
          }
        }
      }

      i++;
    }

    if (fields.length === 0) return null;
    return { name: formName, displayName, fields };
  }

  private parseField(linkName: string, parenStart: number): FormField | null {
    let fieldType = "";
    let displayName = linkName;
    const notesParts: string[] = [];
    let parenDepth = 0;

    let i = parenStart;
    while (i < this.lines.length) {
      const stripped = this.lines[i].trim();
      parenDepth += this.countChar(stripped, "(") - this.countChar(stripped, ")");

      const tm = stripped.match(/type\s*=\s*(\w[\w\s]*)/);
      if (tm) fieldType = tm[1].trim();

      const dnm = stripped.match(/displayname\s*=\s*"([^"]*)"/);
      if (dnm) displayName = dnm[1];

      if (stripped.includes("personal data = true")) notesParts.push("personal data");
      if (stripped.includes("private = true")) notesParts.push("private/hidden");

      const ivm = stripped.match(/initial value\s*=\s*(\S+)/);
      if (ivm) notesParts.push(`default: ${ivm[1]}`);

      if (parenDepth <= 0 && i > parenStart) break;
      i++;
    }

    if (!fieldType) return null;
    return { linkName, displayName, fieldType, notes: notesParts.join(", ") };
  }

  // --- Workflow/Schedule/Approval parsing added in Task 2 ---
  private parseWorkflows(): void { /* Task 2 */ }
  private parseSchedules(): void { /* Task 2 */ }
  private parseApprovals(): void { /* Task 2 */ }
  private extractScriptCode(_parenLine: number): string { return ""; /* Task 2 */ }
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd web && npx tsc --noEmit src/lib/ds-parser.ts`
Expected: No errors

- [ ] **Step 3: Quick manual test — parse the fixture**

Create a temporary test. Add to end of `ds-parser.ts`:

```typescript
// Temporary — remove after testing
export function _selfTest(dsContent: string): void {
  const p = new DSParser(dsContent);
  p.parse();
  console.log(`Forms: ${p.forms.length}`);
  for (const f of p.forms) {
    console.log(`  ${f.name} (${f.displayName}): ${f.fields.length} fields`);
    for (const field of f.fields) {
      console.log(`    ${field.linkName} [${field.fieldType}]`);
    }
  }
}
```

Run from project root:
```bash
cd web && npx tsx -e "
  import { readFileSync } from 'fs';
  import { _selfTest } from './src/lib/ds-parser';
  _selfTest(readFileSync('../tests/fixtures/validate_ds_good.ds', 'utf-8'));
"
```

Expected output should show `test_form` with fields `name_field` (text), `status_field` (picklist), and `second_form` with `title` (text).

- [ ] **Step 4: Remove _selfTest, commit**

Remove the `_selfTest` function from `ds-parser.ts`.

```bash
git add web/src/lib/ds-parser.ts
git commit -m "feat(web): add TypeScript DSParser — form and field parsing"
```

---

## Task 2: DSParser — Workflow, Schedule, Approval, and Script Extraction

**Files:**
- Modify: `web/src/lib/ds-parser.ts`

- [ ] **Step 1: Implement extractScriptCode()**

Replace the stub in `ds-parser.ts`:

```typescript
  private extractScriptCode(parenLine: number): string {
    const codeLines: string[] = [];
    let parenDepth = 0;
    let started = false;

    let i = parenLine;
    while (i < this.lines.length) {
      const line = this.lines[i];
      const stripped = line.trim();

      parenDepth += this.countChar(stripped, "(") - this.countChar(stripped, ")");

      if (!started && stripped.includes("(")) {
        started = true;
        const afterParen = stripped.split("(").slice(1).join("(").trim();
        if (afterParen) codeLines.push(afterParen);
        i++;
        continue;
      }

      if (started) {
        if (parenDepth <= 0) {
          const beforeParen = stripped.split(")").slice(0, -1).join(")").trim();
          if (beforeParen) codeLines.push(beforeParen);
          break;
        }
        codeLines.push(line.replace(/\r$/, ""));
      }

      i++;
    }

    if (codeLines.length === 0) return "";

    const nonEmpty = codeLines.filter((l) => l.trim().length > 0);
    if (nonEmpty.length === 0) return "";

    const minIndent = Math.min(...nonEmpty.map((l) => l.length - l.trimStart().length));
    const dedented = codeLines.map((l) =>
      l.length > minIndent ? l.slice(minIndent) : l.trimStart()
    );

    return dedented.join("\n").trim();
  }
```

- [ ] **Step 2: Implement parseWorkflows()**

Replace the stub:

```typescript
  private parseWorkflows(): void {
    let i = 0;
    while (i < this.lines.length) {
      const stripped = this.lines[i].trim();
      const wm = stripped.match(/^\s*(\w+)\s+as\s+"([^"]*)"/);
      if (wm) {
        const name = wm[1];
        const display = wm[2];
        let formName = "";
        let recordEvent = "";
        let eventType = "";
        let code = "";

        let j = i + 1;
        let braceDepth = 0;
        let inBlock = false;
        while (j < this.lines.length) {
          const line = this.lines[j].trim();
          if (line.includes("{")) {
            braceDepth += this.countChar(line, "{");
            inBlock = true;
          }
          if (line.includes("}")) {
            braceDepth -= this.countChar(line, "}");
            if (inBlock && braceDepth <= 0) break;
          }

          const fm = line.match(/form\s*=\s*(\w+)/);
          if (fm) formName = fm[1];

          const rem = line.match(/record event\s*=\s*(.+)/);
          if (rem) recordEvent = rem[1].trim();

          for (const evt of ["on success", "on validate", "on load", "on update of"]) {
            if (line.startsWith(evt)) eventType = evt;
          }

          if (line === "custom deluge script") {
            code = this.extractScriptCode(j + 1);
          }

          j++;
        }

        if (code && formName) {
          this.scripts.push({
            name, displayName: display, form: formName,
            event: eventType || "on success",
            trigger: recordEvent || "on add",
            code, context: "form-workflow",
          });
        }
      }
      i++;
    }
  }
```

- [ ] **Step 3: Implement parseSchedules() and parseScheduleBlock()**

Replace the stubs:

```typescript
  private parseSchedules(): void {
    for (let i = 0; i < this.lines.length; i++) {
      const stripped = this.lines[i].trim();
      if (stripped.startsWith("schedule") && i + 1 < this.lines.length) {
        if (this.lines[i + 1].trim() === "{") {
          this.parseScheduleBlock(i + 2);
        }
      }
    }
  }

  private parseScheduleBlock(start: number): void {
    let i = start;
    while (i < this.lines.length) {
      const stripped = this.lines[i].trim();
      const sm = stripped.match(/(\w+)\s+as\s+"([^"]*)"/);
      if (sm) {
        const name = sm[1];
        const display = sm[2];
        let formName = "";
        let code = "";

        let j = i + 1;
        let braceDepth = 0;
        while (j < this.lines.length) {
          const line = this.lines[j].trim();
          braceDepth += this.countChar(line, "{") - this.countChar(line, "}");

          const fm = line.match(/form\s*=\s*(\w+)/);
          if (fm) formName = fm[1];

          if (line === "on load") {
            if (j + 1 < this.lines.length && this.lines[j + 1].includes("(")) {
              code = this.extractScriptCode(j + 1);
            }
          }

          if (braceDepth < 0) break;
          j++;
        }

        if (code) {
          this.scripts.push({
            name, displayName: display, form: formName,
            event: "on load", trigger: "scheduled",
            code, context: "scheduled",
          });
        }
      }
      i++;
    }
  }
```

- [ ] **Step 4: Implement parseApprovals() and parseApprovalBlock()**

Replace the stubs:

```typescript
  private parseApprovals(): void {
    for (let i = 0; i < this.lines.length; i++) {
      const stripped = this.lines[i].trim();
      if (stripped.startsWith("approval") && i + 1 < this.lines.length) {
        if (this.lines[i + 1].trim() === "{") {
          this.parseApprovalBlock(i + 2);
          break;
        }
      }
    }
  }

  private parseApprovalBlock(start: number): void {
    let i = start;
    let currentApproval = "";
    let currentDisplay = "";

    while (i < this.lines.length) {
      const stripped = this.lines[i].trim();

      const am = stripped.match(/(\w+)\s+as\s+"([^"]*)"/);
      if (am) {
        currentApproval = am[1];
        currentDisplay = am[2];
      }

      for (const event of ["on approve", "on reject"] as const) {
        if (stripped.startsWith(event)) {
          let j = i + 1;
          while (j < this.lines.length) {
            const lineJ = this.lines[j].trim();
            if (lineJ === "on load") {
              if (j + 1 < this.lines.length && this.lines[j + 1].includes("(")) {
                const code = this.extractScriptCode(j + 1);
                if (code) {
                  this.scripts.push({
                    name: `${currentApproval}_${event.replace(" ", "_")}`,
                    displayName: `${currentDisplay} - ${event.split(" ").map(w => w[0].toUpperCase() + w.slice(1)).join(" ")}`,
                    form: "expense_claims",
                    event, trigger: "approval",
                    code, context: "approval",
                  });
                }
              }
              break;
            }
            if (lineJ.includes("}") && !lineJ.includes("{")) break;
            j++;
          }
        }
      }

      i++;
    }
  }
```

- [ ] **Step 5: Verify full parser compiles and test with fixture**

Run: `cd web && npx tsc --noEmit src/lib/ds-parser.ts`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add web/src/lib/ds-parser.ts
git commit -m "feat(web): complete DSParser — workflows, schedules, approvals, script extraction"
```

---

## Task 3: Tree Builder — Convert DSParser Output to TreeNode[]

**Files:**
- Create: `web/src/lib/ds-tree-builder.ts`

- [ ] **Step 1: Create ds-tree-builder.ts**

```typescript
// web/src/lib/ds-tree-builder.ts

import type { TreeNode } from "../types/ide";
import type { FormDef, ScriptDef } from "./ds-parser";

export function buildAppTree(
  forms: FormDef[],
  scripts: ScriptDef[],
  appName: string,
  appDisplayName: string
): TreeNode[] {
  const root: TreeNode = {
    id: "app-root",
    label: appDisplayName,
    type: "application",
    isExpanded: true,
    children: [],
  };

  // --- Forms section ---
  const formsSection: TreeNode = {
    id: "forms-section",
    label: "Forms",
    type: "section",
    isExpanded: true,
    children: [],
  };

  for (const form of forms) {
    const formNode: TreeNode = {
      id: `form-${form.name.toLowerCase()}`,
      label: form.displayName,
      type: "form",
      isExpanded: false,
      children: [],
    };

    // Fields subsection
    if (form.fields.length > 0) {
      const fieldsSection: TreeNode = {
        id: `field-section-${form.name.toLowerCase()}`,
        label: "Fields",
        type: "section",
        isExpanded: false,
        children: form.fields.map((f) => ({
          id: `field-${form.name.toLowerCase()}-${f.linkName.toLowerCase()}`,
          label: f.linkName,
          type: "field" as const,
          fieldType: f.fieldType,
          metadata: {
            displayName: f.displayName,
            notes: f.notes,
          },
        })),
      };
      formNode.children!.push(fieldsSection);
    }

    // Workflows subsection
    const formWorkflows = scripts.filter(
      (s) => s.form === form.name && s.context === "form-workflow"
    );
    if (formWorkflows.length > 0) {
      const wfSection: TreeNode = {
        id: `wf-section-${form.name.toLowerCase()}`,
        label: "Workflows",
        type: "section",
        isExpanded: false,
        children: formWorkflows.map((s) => ({
          id: `wf-${s.name.toLowerCase()}`,
          label: s.displayName,
          type: "workflow" as const,
          trigger: s.trigger,
          filePath: `src/deluge/form-workflows/${s.form}.${s.event.replace(/ /g, "_")}.dg`,
          metadata: { code: s.code, context: s.context },
        })),
      };
      formNode.children!.push(wfSection);
    }

    formsSection.children!.push(formNode);
  }

  root.children!.push(formsSection);

  // --- Schedules section ---
  const schedules = scripts.filter((s) => s.context === "scheduled");
  if (schedules.length > 0) {
    root.children!.push({
      id: "schedules-section",
      label: "Schedules",
      type: "section",
      isExpanded: false,
      children: schedules.map((s) => ({
        id: `schedule-${s.name.toLowerCase()}`,
        label: s.displayName,
        type: "schedule" as const,
        trigger: s.trigger,
        filePath: `src/deluge/scheduled/${s.name}.dg`,
        metadata: { code: s.code },
      })),
    });
  }

  // --- Approval Processes section ---
  const approvals = scripts.filter((s) => s.context === "approval");
  if (approvals.length > 0) {
    root.children!.push({
      id: "approvals-section",
      label: "Approval Processes",
      type: "section",
      isExpanded: false,
      children: approvals.map((s) => ({
        id: `approval-${s.name.toLowerCase()}`,
        label: s.displayName,
        type: "workflow" as const,
        trigger: s.trigger,
        filePath: `src/deluge/approval-scripts/${s.name}.dg`,
        metadata: { code: s.code, event: s.event },
      })),
    });
  }

  return [root];
}
```

- [ ] **Step 2: Verify compilation**

Run: `cd web && npx tsc --noEmit src/lib/ds-tree-builder.ts`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add web/src/lib/ds-tree-builder.ts
git commit -m "feat(web): add tree builder — converts DSParser output to TreeNode[]"
```

---

## Task 4: Add enrichmentLevel to AppStructure Type and Store

**Files:**
- Modify: `web/src/types/ide.ts:31-37`
- Modify: `web/src/stores/ideStore.ts`

- [ ] **Step 1: Update AppStructure interface**

In `web/src/types/ide.ts`, add `enrichmentLevel` to `AppStructure` (after line 36):

```typescript
export interface AppStructure {
  name: string;
  displayName: string;
  tree: TreeNode[];
  /** Flat lookup: node ID -> TreeNode for fast access */
  nodeIndex: Map<string, TreeNode>;
  /** How this structure was loaded */
  enrichmentLevel?: "local" | "bridge-enriched";
}
```

- [ ] **Step 2: Verify compilation**

Run: `cd web && npx tsc --noEmit`
Expected: No errors (enrichmentLevel is optional, so no downstream breakage)

- [ ] **Step 3: Commit**

```bash
git add web/src/types/ide.ts
git commit -m "feat(web): add enrichmentLevel to AppStructure type"
```

---

## Task 5: File Upload UI in AppTreeExplorer

**Files:**
- Modify: `web/src/components/ide/AppTreeExplorer.tsx`

- [ ] **Step 1: Add onLoadDsFile callback prop and upload UI**

At the top of `AppTreeExplorer.tsx`, update imports and add prop:

```typescript
import { useCallback, useMemo, useRef } from "react";
```

Update the function signature (currently at line 167):

```typescript
interface AppTreeExplorerProps {
  onLoadDsFile?: (file: File) => void;
}

export function AppTreeExplorer({ onLoadDsFile }: AppTreeExplorerProps) {
```

Add file input ref and handlers inside the component (before the return):

```typescript
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const file = Array.from(e.dataTransfer.files).find((f) =>
        f.name.endsWith(".ds")
      );
      if (file && onLoadDsFile) onLoadDsFile(file);
    },
    [onLoadDsFile]
  );

  const handleFilePick = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.currentTarget.files?.[0];
      if (file && onLoadDsFile) onLoadDsFile(file);
      e.currentTarget.value = "";
    },
    [onLoadDsFile]
  );
```

- [ ] **Step 2: Add drag-drop zone and upload button to the render**

Wrap the root div with drag handlers. Update the header to include an upload button. Update the empty state message. The return should start like:

```tsx
  return (
    <div
      className="flex h-full flex-col bg-gray-900"
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-700 px-3 py-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
          App Structure
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => fileInputRef.current?.click()}
            className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-gray-200"
            title="Upload .ds file"
          >
            <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M8 1v10M5 4l3-3 3 3M2 13h12" />
            </svg>
          </button>
          <button
            onClick={handleCollapseAll}
            className="rounded p-1 text-gray-400 hover:bg-gray-700 hover:text-gray-200"
            title="Collapse All"
          >
            {/* existing collapse icon */}
```

Add the hidden file input just before the closing `</div>`:

```tsx
      <input
        ref={fileInputRef}
        type="file"
        accept=".ds"
        onChange={handleFilePick}
        className="hidden"
      />
    </div>
```

- [ ] **Step 3: Update empty state**

Replace the "No app structure loaded" message (around line 227) with:

```tsx
      {!appStructure && (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 px-4 text-center">
          <svg className="h-8 w-8 text-gray-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M12 2v14m0 0l-4-4m4 4l4-4M4 20h16" />
          </svg>
          <p className="text-sm text-gray-400">
            Upload a .ds file to explore
          </p>
          <p className="text-xs text-gray-600">
            Drag & drop or click the upload button
          </p>
        </div>
      )}
```

- [ ] **Step 4: Verify compilation**

Run: `cd web && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add web/src/components/ide/AppTreeExplorer.tsx
git commit -m "feat(web): add .ds file upload to AppTreeExplorer — drag-drop + file picker"
```

---

## Task 6: Wire IdePage to JS Parser

**Files:**
- Modify: `web/src/pages/IdePage.tsx`

- [ ] **Step 1: Add imports for parser and tree builder**

Add at the top of `IdePage.tsx`:

```typescript
import { DSParser } from "../lib/ds-parser";
import { buildAppTree } from "../lib/ds-tree-builder";
```

- [ ] **Step 2: Add loadDsFromFile callback**

Inside the `IdePage` component, add after the existing `loadDs` callback (around line 79):

```typescript
  const loadDsFromFile = useCallback(
    async (file: File) => {
      try {
        const content = await file.text();
        const parser = new DSParser(content);
        parser.parse();

        const appName = file.name.replace(/\.ds$/, "").replace(/_/g, " ");
        const tree = buildAppTree(parser.forms, parser.scripts, appName, appName);

        const nodeIndex = new Map<string, TreeNode>();
        const walk = (nodes: TreeNode[]) => {
          for (const n of nodes) {
            nodeIndex.set(n.id, n);
            if (n.children) walk(n.children);
          }
        };
        walk(tree);

        loadAppStructure({
          name: file.name.replace(/\.ds$/, ""),
          displayName: appName,
          tree,
          nodeIndex,
          enrichmentLevel: "local",
        });

        addConsoleEntry({
          type: "info",
          message: `Loaded ${file.name}: ${parser.forms.length} forms, ${parser.scripts.length} scripts (browser-parsed)`,
        });
      } catch (err) {
        addConsoleEntry({
          type: "error",
          message: `Failed to parse ${file.name}: ${err instanceof Error ? err.message : String(err)}`,
        });
      }
    },
    [loadAppStructure, addConsoleEntry]
  );
```

- [ ] **Step 3: Pass onLoadDsFile to AppTreeExplorer**

Find where `<AppTreeExplorer />` is rendered (around line 305) and add the prop:

```tsx
<AppTreeExplorer onLoadDsFile={loadDsFromFile} />
```

- [ ] **Step 4: Update the bridge status message**

Find the "Bridge offline — GitHub mode active" message (around line 289) and update:

```tsx
{status !== "connected" && (
  <span className="text-[10px] text-gray-500">
    {appStructure
      ? "Local parse — start bridge for linting & inspection"
      : "Bridge offline — upload a .ds file to explore"}
  </span>
)}
```

- [ ] **Step 5: Verify compilation and test**

Run: `cd web && npx tsc --noEmit`
Expected: No errors

Run dev server: `cd web && npm run dev`
Open browser, navigate to `/ide`, upload `tests/fixtures/validate_ds_good.ds`.
Expected: Tree renders with `test_form` and `second_form` nodes.

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/IdePage.tsx
git commit -m "feat(web): wire IdePage to JS parser — .ds upload loads tree immediately"
```

---

## Task 7: Graceful Degradation in DevConsole

**Files:**
- Modify: `web/src/components/ide/DevConsole.tsx`

- [ ] **Step 1: Add bridge status check to tabs that require it**

The `DevConsole` component already imports `useBridgeStore`. Add a helper message component at the top of the file (after imports):

```typescript
function BridgeRequiredMessage({ feature }: { feature: string }) {
  return (
    <div className="flex h-full items-center justify-center px-4">
      <div className="text-center">
        <p className="text-sm text-gray-400">{feature} requires the bridge server</p>
        <p className="mt-1 text-xs text-gray-600">
          Run <code className="rounded bg-gray-800 px-1">python -m bridge</code> locally to enable
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Guard lint tab rendering**

In the main `DevConsole` component, find where the lint tab content is rendered (around line 407). Wrap with bridge check:

```tsx
{activeConsoleTab === "lint" && (
  status === "connected"
    ? <LintTab diagnostics={diagnostics} onFileClick={handleLintFileClick} />
    : <BridgeRequiredMessage feature="Linting" />
)}
```

- [ ] **Step 3: Guard relationships tab**

Similarly for the relationships tab:

```tsx
{activeConsoleTab === "relationships" && (
  status === "connected"
    ? <RelationshipsTab relationships={inspectorData?.relationships ?? []} elementName={inspectorData?.name ?? null} />
    : <BridgeRequiredMessage feature="Relationship analysis" />
)}
```

- [ ] **Step 4: AI Chat tab already handles this**

The AI Chat tab (line 270-276) already shows "Connect bridge to use AI Chat" when disconnected. No changes needed.

- [ ] **Step 5: Verify compilation**

Run: `cd web && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add web/src/components/ide/DevConsole.tsx
git commit -m "feat(web): graceful degradation in DevConsole — bridge-required tabs show message"
```

---

## Task 8: Graceful Degradation in InspectorPanel

**Files:**
- Modify: `web/src/components/ide/InspectorPanel.tsx`

- [ ] **Step 1: Import bridge store**

Add to imports:

```typescript
import { useBridgeStore } from "../../stores/bridgeStore";
```

- [ ] **Step 2: Add bridge hint to empty state**

Inside the `InspectorPanel` component, add the bridge store hook:

```typescript
const status = useBridgeStore((s) => s.status);
```

Update the empty state message (around line 109-114) to include a bridge hint:

```tsx
{!inspectorData && (
  <div className="flex flex-1 items-center justify-center px-4">
    <div className="text-center">
      <p className="text-sm text-gray-500">Select an element to inspect</p>
      {status !== "connected" && (
        <p className="mt-1 text-xs text-gray-600">
          Start bridge for relationships & usages
        </p>
      )}
    </div>
  </div>
)}
```

- [ ] **Step 3: Add hints to relationships/usages sections when empty**

After the Relationships section (around line 179-191), add a fallback when bridge is offline and no data:

```tsx
{relationships.length === 0 && status !== "connected" && (
  <Section title="Relationships">
    <p className="text-xs text-gray-600">
      Available with bridge enrichment
    </p>
  </Section>
)}
```

Same for usages (around line 194-208).

- [ ] **Step 4: Verify compilation**

Run: `cd web && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add web/src/components/ide/InspectorPanel.tsx
git commit -m "feat(web): inspector hints for bridge-offline mode"
```

---

## Task 9: Bridge — Replace Mock handle_parse_ds with Real Parser

**Files:**
- Modify: `bridge/handlers.py`
- Create: `bridge/tree_builder.py`

- [ ] **Step 1: Create bridge/tree_builder.py**

```python
# bridge/tree_builder.py
"""Convert DSParser output to TreeNode hierarchy for the frontend."""

from __future__ import annotations
from typing import Any


def build_tree_response(
    forms: list,
    scripts: list,
    file_path: str = "",
) -> dict[str, Any]:
    """Convert DSParser forms/scripts to the frontend TreeNode[] format."""
    import os

    app_name = os.path.splitext(os.path.basename(file_path))[0] if file_path else "App"
    display_name = app_name.replace("_", " ")

    root: dict[str, Any] = {
        "id": "app-root",
        "label": display_name,
        "type": "application",
        "isExpanded": True,
        "children": [],
    }

    # --- Forms ---
    forms_section: dict[str, Any] = {
        "id": "forms-section",
        "label": "Forms",
        "type": "section",
        "isExpanded": True,
        "children": [],
    }

    for form in forms:
        form_node: dict[str, Any] = {
            "id": f"form-{form.name.lower()}",
            "label": form.display_name,
            "type": "form",
            "isExpanded": False,
            "children": [],
        }

        if form.fields:
            fields_section = {
                "id": f"field-section-{form.name.lower()}",
                "label": "Fields",
                "type": "section",
                "isExpanded": False,
                "children": [
                    {
                        "id": f"field-{form.name.lower()}-{f.link_name.lower()}",
                        "label": f.link_name,
                        "type": "field",
                        "fieldType": f.field_type,
                    }
                    for f in form.fields
                ],
            }
            form_node["children"].append(fields_section)

        form_wfs = [s for s in scripts if s.form == form.name and s.context == "form-workflow"]
        if form_wfs:
            wf_section = {
                "id": f"wf-section-{form.name.lower()}",
                "label": "Workflows",
                "type": "section",
                "isExpanded": False,
                "children": [
                    {
                        "id": f"wf-{s.name.lower()}",
                        "label": s.display_name,
                        "type": "workflow",
                        "trigger": s.trigger,
                        "filePath": f"src/deluge/form-workflows/{s.form}.{s.event.replace(' ', '_')}.dg",
                    }
                    for s in form_wfs
                ],
            }
            form_node["children"].append(wf_section)

        forms_section["children"].append(form_node)

    root["children"].append(forms_section)

    # --- Schedules ---
    scheds = [s for s in scripts if s.context == "scheduled"]
    if scheds:
        root["children"].append({
            "id": "schedules-section",
            "label": "Schedules",
            "type": "section",
            "isExpanded": False,
            "children": [
                {
                    "id": f"schedule-{s.name.lower()}",
                    "label": s.display_name,
                    "type": "schedule",
                    "trigger": s.trigger,
                    "filePath": f"src/deluge/scheduled/{s.name}.dg",
                }
                for s in scheds
            ],
        })

    # --- Approvals ---
    approvals = [s for s in scripts if s.context == "approval"]
    if approvals:
        root["children"].append({
            "id": "approvals-section",
            "label": "Approval Processes",
            "type": "section",
            "isExpanded": False,
            "children": [
                {
                    "id": f"approval-{s.name.lower()}",
                    "label": s.display_name,
                    "type": "workflow",
                    "trigger": s.trigger,
                    "filePath": f"src/deluge/approval-scripts/{s.name}.dg",
                }
                for s in approvals
            ],
        })

    return {
        "name": app_name,
        "displayName": display_name,
        "tree": [root],
    }
```

- [ ] **Step 2: Replace handle_parse_ds in handlers.py**

Find `handle_parse_ds` (line 294 in `bridge/handlers.py`). Replace the entire function with:

```python
async def handle_parse_ds(data: dict) -> dict:
    """Parse a .ds export and return app structure as TreeNode hierarchy."""
    import sys
    from pathlib import Path as _Path

    # Ensure forgeds is importable
    src_dir = str(_Path(__file__).parent.parent / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    from forgeds.core.parse_ds_export import DSParser
    from bridge.tree_builder import build_tree_response

    file_path = data.get("file_path", "")
    content = data.get("content", "")

    if not content and not file_path:
        return {"error": "file_path or content is required"}

    if not content:
        try:
            content = _Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            return {"error": f"Failed to read file: {e}"}

    try:
        parser = DSParser(content)
        parser.parse()
    except Exception as e:
        return {"error": f"Parse error: {e}"}

    return build_tree_response(parser.forms, parser.scripts, file_path)
```

- [ ] **Step 3: Test bridge parse with fixture**

```bash
cd "C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS"
python -c "
import sys, json
sys.path.insert(0, 'src')
from forgeds.core.parse_ds_export import DSParser
from bridge.tree_builder import build_tree_response

content = open('tests/fixtures/validate_ds_good.ds', encoding='utf-8').read()
parser = DSParser(content)
parser.parse()
result = build_tree_response(parser.forms, parser.scripts, 'validate_ds_good.ds')
print(f'Forms: {len(parser.forms)}')
print(f'Scripts: {len(parser.scripts)}')
print(f'Tree children: {len(result[\"tree\"][0][\"children\"])}')
print(json.dumps(result, indent=2)[:500])
"
```

Expected: Shows forms (test_form, second_form), tree structure with Forms section.

- [ ] **Step 4: Commit**

```bash
git add bridge/tree_builder.py bridge/handlers.py
git commit -m "feat(bridge): replace mock handle_parse_ds with real DSParser + tree builder"
```

---

## Task 10: End-to-End Verification

**Files:** None (testing only)

- [ ] **Step 1: Test browser-only flow (GitHub Pages mode)**

```bash
cd web && npm run dev
```

1. Open browser to `http://localhost:5173/ForgeDS/ide`
2. Do NOT start the bridge
3. Verify "Bridge offline" status shows
4. Click upload button in tree explorer
5. Select `tests/fixtures/validate_ds_good.ds`
6. Verify tree renders: Test App > Forms > Test Form (name_field, status_field), Second Form (title)
7. Verify console shows "Loaded validate_ds_good.ds: 2 forms, 0 scripts (browser-parsed)"
8. Verify Lint tab shows "Linting requires the bridge server"
9. Verify Inspector shows "Select an element to inspect" with bridge hint
10. Click a field in tree — verify it's selected

- [ ] **Step 2: Test bridge-connected flow**

In a separate terminal:
```bash
cd "C:/Users/User/OneDrive/Documents/Claude/Projects/VS_Clones/ForgeDS"
python -m bridge
```

1. Refresh IDE page — verify "Bridge..." status appears
2. Verify Lint tab is now active (can click "Run Lint")

- [ ] **Step 3: Build for production**

```bash
cd web && npm run build
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 4: Commit any fixes from testing**

```bash
git add -A
git commit -m "fix(web): end-to-end testing adjustments for hybrid IDE"
```

---

## Summary

| Task | What | Files | Est. |
|------|------|-------|------|
| 1 | DSParser: types + form/field parsing | `ds-parser.ts` (create) | 5 min |
| 2 | DSParser: workflows, schedules, approvals | `ds-parser.ts` (modify) | 5 min |
| 3 | Tree builder: FormDef/ScriptDef → TreeNode[] | `ds-tree-builder.ts` (create) | 3 min |
| 4 | AppStructure enrichmentLevel type | `ide.ts` (modify) | 2 min |
| 5 | File upload UI in AppTreeExplorer | `AppTreeExplorer.tsx` (modify) | 5 min |
| 6 | Wire IdePage to JS parser | `IdePage.tsx` (modify) | 5 min |
| 7 | DevConsole graceful degradation | `DevConsole.tsx` (modify) | 3 min |
| 8 | InspectorPanel graceful degradation | `InspectorPanel.tsx` (modify) | 3 min |
| 9 | Bridge: real handle_parse_ds | `handlers.py` + `tree_builder.py` | 5 min |
| 10 | End-to-end verification | Testing only | 5 min |
