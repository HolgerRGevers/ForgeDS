# ForgeDS — Zoho Creator Development Engine

## What this repo is
Pip-installable Python package providing linting, scaffolding, .ds editing,
and import pipeline tools for Zoho Creator applications. Zero external
dependencies (stdlib only). Extracted from the ERM project.

## Tech stack
- **Language**: Python >= 3.10
- **Package format**: pip-installable via pyproject.toml
- **Target platform**: Zoho Creator / Deluge ecosystem
- **Dependencies**: None (stdlib only; pyodbc optional for Access tools)

## Architecture
- `src/forgeds/core/` — Zoho/Deluge tools (lint, build DB, scaffold, parse, edit .ds)
- `src/forgeds/access/` — Access/VBA migration tools (lint SQL, build DB, export CSV)
- `src/forgeds/hybrid/` — Cross-environment tools (hybrid lint, validate, upload)
- `src/forgeds/_shared/` — Shared internals (diagnostics, config loader)
- `templates/` — Starter configs for new consumer projects
- `tests/fixtures/` — Lint test fixtures

## Key design principles
1. **Config over hardcoding**: All project-specific values come from `forgeds.yaml` in the consumer project root. ForgeDS tools auto-discover this file by walking up from cwd.
2. **Shared diagnostics**: All linters use `forgeds._shared.diagnostics.Severity` and `Diagnostic` — never define local copies.
3. **DB path resolution**: Use `get_db_dir()` from `forgeds._shared.config` — never hardcode `Path(__file__).parent`.
4. **Generic framework**: `ds_editor.py` provides generic subcommands. Project-specific subcommands (apply-two-key, apply-esg) live in the consumer repo.
5. **Zero dependencies**: Every tool uses stdlib only. `pyodbc` is optional and guarded by ImportError.

## Development workflow
```bash
# Install in editable mode
pip install -e .

# Test linters against fixtures
forgeds-lint tests/fixtures/lint_test_bad.dg
forgeds-lint-access tests/fixtures/lint_test_access_bad.sql

# Build language databases
forgeds-build-db
forgeds-build-access-db
```

## Rules for contributions
- Every tool must have `def main()` and `if __name__ == "__main__": main()`
- Import shared types: `from forgeds._shared.diagnostics import Severity, Diagnostic`
- Import config: `from forgeds._shared.config import load_config, get_db_dir`
- No project-specific constants — use `load_config()` with sensible defaults
- Exit codes: 0 = clean, 1 = warnings, 2 = errors
