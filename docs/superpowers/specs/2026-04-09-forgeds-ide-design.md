# ForgeDS_IDE — Design Specification

**Date:** 2026-04-09
**Author:** Holger Gevers + Claude
**Status:** Draft

## Problem

ForgeDS is a powerful CLI toolkit for Zoho Creator development, but it has no visual interface. Developers must use the terminal for every operation (linting, scaffolding, parsing, editing .ds files). Meanwhile, Zoho Creator's built-in IDE is limited — no element inspection, no relationship mapping, no AI assistance, no cross-environment database tooling.

**ForgeDS_IDE** bridges this gap: a web-based IDE that wraps the ForgeDS engine in a modern developer experience, adds AI-powered code generation, and automatically enriches the engine with every use.

## Solution

A React SPA hosted on GitHub Pages, linked from the ForgeDS README. It communicates with a local WebSocket bridge that invokes Claude Code CLI and ForgeDS Python tools.

## Architecture

### Monorepo Structure

```
ForgeDS/
├── src/forgeds/          # Existing Python CLI tools (unchanged)
├── web/                  # React + Tailwind + Vite SPA
│   ├── src/
│   │   ├── components/   # Shared UI components
│   │   ├── pages/        # Route pages
│   │   ├── hooks/        # React hooks (useBridge, useForgeDS)
│   │   ├── services/     # WebSocket bridge client
│   │   ├── stores/       # State management
│   │   ├── lib/          # Deluge language definition, utils
│   │   └── types/        # TypeScript interfaces
│   ├── public/
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── package.json
├── bridge/               # WebSocket bridge server (Python)
│   ├── server.py         # WebSocket server on localhost:9876
│   └── handlers.py       # Claude Code invocation, file ops
└── README.md             # Updated with IDE link
```

### Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | React 18 + TypeScript | Component model, rich ecosystem |
| Styling | Tailwind CSS | Rapid UI development, consistent design |
| Build | Vite | Fast dev server, optimized builds |
| Code Editor | Monaco Editor | VS Code engine, syntax highlighting, autocomplete |
| State | Zustand | Lightweight, no boilerplate |
| Routing | React Router v6 | Client-side routing for SPA |
| Hosting | GitHub Pages | Free, linked from README |
| AI Backend | Claude Code CLI | Local execution, full ForgeDS context |
| Bridge | Python WebSocket | Invokes CLI tools, streams output |

### Communication

```
Browser (GitHub Pages)
    ↕ WebSocket (ws://localhost:9876)
Bridge Server (Python)
    ↕ subprocess / filesystem
Claude Code CLI + ForgeDS tools + SQLite DBs
```

## Pages

### 1. AI Prompt Interface (`/`) — Phase 1

**Purpose:** Entry point. User describes an app, AI refines the prompt, generates Zoho Creator code.

**Layout:** Three panels — left sidebar (nav + history), center (prompt workspace), right (code preview).

**Flow:**
1. User types app description in textarea (optional: drop screenshots/files)
2. "Refine" → Claude Code returns structured prompt (forms, workflows, reports, APIs)
3. User edits sections in accordion UI, confirms
4. "Build" → Claude Code generates forgeds.yaml, .dg scripts, .ds structure, seed data
5. "Open in IDE" → navigates to `/ide`

**Components:** PromptInput, RefinedPrompt, BuildProgress, CodePreview, ProjectHistory, ConnectionStatus

**Bridge Messages:** `refine_prompt`, `build_project`, `lint_check`, `get_status`

### 2. .ds Code IDE (`/ide`) — Phase 2

**Purpose:** Developer IDE for Zoho Creator code with DevTools-level inspection.

**Layout:** Four resizable panels — tree explorer, Monaco editor, inspector, dev console.

**Left — App Tree Explorer:**
- Hierarchical: Application → Forms → Fields/Workflows → Reports → Pages → Schedules → APIs
- Parsed from .ds export via `parse_ds_export.py`
- Filter by type, search by name
- Click node → opens in editor

**Center — Monaco Editor:**
- Custom Deluge language definition (keywords, operators, built-ins, Zoho variables)
- Autocomplete from `deluge_lang.db`
- Inline lint diagnostics (squiggly underlines from `forgeds-lint`)
- Click-to-inspect: click identifier → Inspector shows metadata
- Tab system, breadcrumb bar

**Right — Inspector Panel:**
- Field: type, form, display name, help text, linked workflows/reports
- Function: signature, params, examples (from `deluge_lang.db`)
- Form: field count, workflows, reports, approval process
- Mini relationship graph (SVG)

**Bottom — Developer Console (tabs):**
- Lint: forgeds-lint output with clickable file:line
- Build: code generation and ds_editor logs
- Relationships: dependency graph visualization
- AI Chat: inline prompt for code questions

### 3. Database Integrations (`/database`) — Phase 3

**Purpose:** Visual Access → Zoho migration management.

**Layout:** Source/target panels, field mapping table, validation console.

**Features:**
- Visual table mapping (Access tables ↔ Zoho forms)
- Auto-mapped fields from `type_mappings` and `field_name_mappings`
- Type compatibility warnings (data-loss risks)
- Run `forgeds-lint-hybrid` and `forgeds-validate` via bridge
- Upload wizard (mock preview → `--live`)
- CSV drop zone for Access exports

### 4. API Connection Builder (`/api`) — Phase 4

**Purpose:** Visual Custom API builder with AI-generated Deluge functions.

**Layout:** API list, 5-step wizard, AI prompt box.

**Features:**
- Mirrors Zoho Creator's Custom API Builder wizard (Basic Details → Request → Response → Actions → Summary)
- Method/Auth/Scope/Content Type selectors matching Zoho's options
- Parameter definition (key-value or Entire JSON)
- Standard vs Custom response toggle
- Live Monaco preview of generated Deluge function
- AI prompt: describe what the API should do → generates function
- Export: .dg file + Creator UI setup instructions

## Enrichment Loop

When Claude Code encounters Deluge errors during code generation:

1. Error logged to `forgeds_errors.json` (rule_id, pattern, file, context)
2. Pattern classifier categorizes: banned function, syntax, variable misuse, new pattern
3. New patterns auto-added to `build_deluge_db.py` data tables
4. `forgeds-build-db` re-runs to rebuild `deluge_lang.db`
5. Next lint pass catches the pattern
6. UI notification: "New rule added: DG0XX — description"

## Phasing

| Phase | Scope | Dependencies |
|-------|-------|-------------|
| 1 | AI Prompt Interface + Bridge server + app shell | None |
| 2 | .ds Code IDE (editor, tree, inspector, console) | Phase 1 (bridge, shell) |
| 3 | Database Integrations page | Phase 1 (bridge) |
| 4 | API Connection Builder page | Phase 1 (bridge), Phase 2 (editor components) |

Each phase is a complete, usable feature. Phase 1 is the foundation — bridge server, app shell, routing, and the core AI interaction.

## Non-Goals (for now)

- Multi-user collaboration / real-time editing
- Cloud-hosted bridge (always local)
- Direct Zoho Creator API integration from the browser (goes through bridge)
- Mobile-responsive layout (desktop-first IDE)
- Offline mode