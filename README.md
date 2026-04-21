# ForgeDS

Zoho Creator rapid development engine. Lint, scaffold, edit, and deploy
Deluge scripts and `.ds` exports — with zero external dependencies.

Tidally locked to the Zoho/Deluge ecosystem. Built for teams that treat
Creator apps as code, not click-ops.

## ForgeDS IDE

**[Launch ForgeDS IDE](https://holgerrgevers.github.io/ForgeDS/)** -- AI-powered web IDE for Zoho Creator development.

- Describe your app in plain language, AI generates the code
- Visual .ds code editor with element inspection
- Database migration management (Access to Zoho)
- Custom API builder with AI assistance

> Requires the ForgeDS bridge server running locally. See [IDE Setup](#ide-setup) below.

## What it does

| Capability | Tool | Rules/Features |
|---|---|---|
| **Lint Deluge** | `forgeds-lint` | 41 rules (DG001-DG018+) |
| **Lint Access SQL** | `forgeds-lint-access` | 8 rules (AV001-AV008) |
| **Lint Hybrid** | `forgeds-lint-hybrid` | 16 rules (HY001-HY016) |
| **Build language DBs** | `forgeds-build-db`, `forgeds-build-access-db` | SQLite reference data |
| **Scaffold scripts** | `forgeds-scaffold` | Generate `.dg` from manifest |
| **Parse .ds exports** | `forgeds-parse-ds` | Extract forms, scripts, field docs |
| **Edit .ds files** | `forgeds-ds-editor` | Descriptions, reports, menus, dashboards |
| **Validate .ds files** | `forgeds-validate-ds` | 17 rules (DS101-DS304): structure, references, Deluge fields |
| **Validate imports** | `forgeds-validate` | Pre-flight CSV data validation |
| **Upload to Creator** | `forgeds-upload` | REST API v2.1 (mock mode default) |
| **Knowledge Base** | `forgeds-kb-init` | Scrape, tokenize, graph, validate |
| **Reality Check** | `forgeds-kb-project` | HRC projection — find app gaps |
| **Shadow Learning** | `KnowledgeBase.learn()` | Runtime discovery recording |

## Install

```bash
pip install git+https://github.com/HolgerRGevers/ForgeDS.git
```

## Quick Start

```bash
# 1. Install
pip install git+https://github.com/HolgerRGevers/ForgeDS.git

# 2. Create project config
cp templates/forgeds.yaml.example forgeds.yaml
# Edit forgeds.yaml with your project's table/form mappings

# 3. Build language databases
forgeds-build-db
forgeds-build-access-db

# 4. Lint your scripts
forgeds-lint src/deluge/
forgeds-lint-access src/access/

# 5. Parse and edit .ds exports
forgeds-parse-ds exports/MyApp.ds --extract-scripts src/deluge/
forgeds-ds-editor audit exports/MyApp.ds
```

## Project Config

Create a `forgeds.yaml` in your Zoho Creator project root. This file tells
ForgeDS about your project's schema, thresholds, and mappings.

See [templates/forgeds.yaml.example](templates/forgeds.yaml.example) for the
full template with comments.

```yaml
project:
  name: "My Zoho Creator App"

lint:
  threshold_fallback: "999.99"
  demo_email_domains:
    - "yourdomain.com"

schema:
  table_to_form:
    Departments: "departments"
    Employees: "employees"

  upload_order:
    - ["Departments", "departments"]
    - ["Employees", "employees"]
```

## Architecture

ForgeDS is the **engine**. Your project provides the **config** (`forgeds.yaml`)
and optional **extensions** (custom dashboard builders, project-specific
`ds_editor` subcommands).

```
Your Project (e.g., ERM)          ForgeDS (this package)
+---------------------------+     +---------------------------+
| forgeds.yaml              | --> | _shared/config.py         |
| config/seed-data/         |     | _shared/diagnostics.py    |
|   form-fields.json        | --> | core/build_deluge_db.py   |
|   valid-statuses.json     | --> | core/lint_deluge.py       |
|   valid-actions.json      | --> |                           |
| src/deluge/*.dg           | --> | core/lint_deluge.py       |
| src/access/*.sql          | --> | access/lint_access.py     |
| exports/*.ds              | --> | core/ds_editor.py         |
| exports/csv/*.csv         | --> | hybrid/validate_import.py |
| knowledge/reality.db      | <-- | knowledge/librarian.c     |
| knowledge/holographic.db  | <-- | knowledge/api.py          |
+---------------------------+     +---------------------------+
```

### Knowledge Base and the Librarian

The KB subsystem implements the **Holographic Reality Coherence (HRC)**
framework. It operates two databases managed by a central C gatekeeper
called the **Librarian**:

```
          Python layer (token_parser, app_ingest, shadow_learning, app_projection)
                |               |                |                |
                +---------------+--------+-------+----------------+
                                         |
                                    +----v----+
                                    |LIBRARIAN|  (C -- sole authority)
                                    |         |
                                    | SHA REG |  Global uniqueness invariant
                                    | CREATE  |  Compute SHA, check, INSERT
                                    | DESTROY |  Verify, DELETE, revoke SHA
                                    | WEIGHT  |  Only mutable property
                                    | EXPORT  |  JSON only (closed world)
                                    |         |
                                    +----+----+
                                    | RB | HB |
                                    +----+----+
                                      |    |
                              reality.db  holographic.db
                              (permanent)  (ephemeral)
```

**RB (Reality Database)** -- the source of truth. Scraped documentation,
ingested app structures, promoted shadow cases. Tokens are permanent and
immutable except for weight.

**HB (Holographic Database)** -- the projection surface. Contains hologram
tokens created during analysis: the gaps between what an app IS and what
the KB says it SHOULD be. After analysis completes and the user confirms
the results, the Librarian destroys every HB token.

**Invariants enforced by the Librarian:**

1. No two tokens (across RB + HB) may share a SHA
2. Once created, only weight is mutable
3. All INSERT/DELETE go through the Librarian
4. Only analysis results leave the system (as JSON) -- closed world theorem

The Librarian is coded in C (`librarian.c`) for efficiency in data I/O,
with an automatic pure-Python fallback if no C compiler is available.

## Package Structure

```
src/forgeds/
  core/           # Zoho/Deluge core tools
    lint_deluge.py, build_deluge_db.py, scaffold_deluge.py,
    parse_ds_export.py, ds_editor.py
  access/         # Access/VBA migration tools
    lint_access.py, build_access_vba_db.py, export_access_csv.py
  hybrid/         # Cross-environment tools
    lint_hybrid.py, validate_import.py, upload_to_creator.py
  knowledge/      # HRC knowledge base
    librarian.c, librarian.h   # Token lifecycle authority (C)
    sha_hashmap.h              # Shared hash map (C)
    librarian_io.py            # Python ctypes wrapper + fallback
    api.py                     # KnowledgeBase public API
    token_parser.py            # Markdown -> tokens
    app_ingest.py              # .ds app -> tokens
    app_projection.py          # KB x App -> holograms
    shadow_learning.py         # Runtime discovery recording
    graph_builder.py           # Edge inference (4 passes)
    kb_core.c                  # Graph compute (CSR, BFS, PageRank)
    retriever.py               # SEED-EXPAND-RANK-ORDER-ASSEMBLE
    hrc_bridge.py              # External HRC integration
  _shared/        # Internal utilities
    diagnostics.py, config.py
```

## CLI Commands

After `pip install`, these commands are available:

```bash
# Linting
forgeds-lint src/deluge/              # Lint .dg files
forgeds-lint --fix src/deluge/        # Auto-fix + lint
forgeds-lint-access src/access/       # Lint .sql files
forgeds-lint-hybrid                   # Validate Access<->Zoho mappings

# Build & scaffold
forgeds-build-db                      # Build deluge_lang.db
forgeds-build-access-db               # Build access_vba_lang.db
forgeds-scaffold --name SCRIPT_NAME   # Scaffold .dg from manifest

# .ds editing & migration
forgeds-parse-ds exports/FILE.ds      # Parse .ds export
forgeds-ds-editor audit exports/FILE.ds
forgeds-validate exports/csv/         # Pre-flight CSV validation
forgeds-upload --config config/zoho-api.yaml  # Upload (mock by default)

# Knowledge base (HRC)
forgeds-kb-init                       # Full pipeline: scrape + parse + build + validate
forgeds-kb-scrape                     # Scrape Zoho docs into raw_md/
forgeds-kb-parse                      # Tokenize raw_md/ via the Librarian
forgeds-kb-build                      # Build graph edges
forgeds-kb-validate                   # HRC consistency check
forgeds-kb-query "sendmail"           # Search tokens by keyword
forgeds-kb-ingest exports/App.ds      # Ingest .ds app into KB
forgeds-kb-project app:App            # Project KB onto app (reveal holograms)
```

## Requirements

- Python >= 3.10
- Zero external dependencies (stdlib only)
- Optional: `pyodbc` for Access database operations (Windows only)

## IDE Setup

The ForgeDS IDE is a web app that connects to a local bridge server for AI-powered code generation.

### Prerequisites

- Python >= 3.10
- [Claude Code](https://claude.ai/claude-code) CLI installed
- ForgeDS installed (`pip install git+https://github.com/HolgerRGevers/ForgeDS.git`)

### Running the Bridge

```bash
# Install bridge dependencies
pip install websockets

# Start the bridge server
cd ForgeDS
python -m bridge
# Bridge running on ws://localhost:9876
```

Then open [https://holgerrgevers.github.io/ForgeDS/](https://holgerrgevers.github.io/ForgeDS/) in your browser.

## License

MIT
