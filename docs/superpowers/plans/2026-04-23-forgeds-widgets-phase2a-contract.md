# ForgeDS Widgets Phase 2A — Polyglot Contract Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use `- [ ]` for progress tracking.

**Goal:** Promote the Phase-1 JSON envelope (`tool`, `version`, `diagnostics[]`) to every linter under an opt-in flag, ship `forgeds-status` as the aggregate-health CLI, and define (but do not implement) the extended `custom_apis:` schema plus a typegen emission contract.

**Reference spec:** `docs/superpowers/specs/2026-04-23-forgeds-widgets-phase2a-contract-design.md`
**Depends on:** Phase 1 (completed in commits `d9b0110..914165a` on branch `claude/ide-shell-overhaul`).

---

## File Structure

### Files to create

```
src/forgeds/_shared/
├── envelope.py                     # Task 1 — JSON-v1 serializer (Diagnostic + StatusCheck)
└── output_format.py                # Task 1 — --format / FORGEDS_OUTPUT resolution helper

src/forgeds/status/
├── __init__.py                     # Task 5
├── cli.py                          # Task 5 — forgeds-status entry point
├── report.py                       # Task 5 — renders text or JSON
└── checks/
    ├── __init__.py                 # Task 5
    ├── config_sanity.py            # Task 5 — CFG checks + STA001
    ├── db_freshness.py             # Task 5 — STA002/STA003
    ├── toolchain.py                # Task 5 — STA004/STA005
    └── lint_summary.py             # Task 5 — spawns each linter in json-v1 mode

tests/
├── test_envelope.py                # Task 1
├── test_output_format.py           # Task 1
├── test_lint_json_v1.py            # Task 2 — covers DG/AV/HY/WG json-v1 output
├── test_custom_apis_schema.py      # Task 3
├── test_status_checks.py           # Task 5
├── test_status_cli.py              # Task 5
└── fixtures/
    ├── envelope/
    │   ├── deluge_sample_bad.dg    # Task 2
    │   ├── access_sample_bad.sql   # Task 2
    │   └── hybrid_sample_project/  # Task 2
    ├── status/
    │   ├── all_green/              # Task 5
    │   ├── missing_db/             # Task 5
    │   ├── config_only_warnings/   # Task 5
    │   └── broken_yaml/            # Task 5
    └── custom_apis/
        ├── form_a_bare_list/       # Task 3
        ├── form_b_extended/        # Task 3
        ├── mixed_forms/            # Task 3 (CFG010)
        ├── missing_param_keys/     # Task 3 (CFG014)
        └── unknown_named_type/     # Task 3 (CFG013)
```

### Files to modify

```
src/forgeds/core/lint_deluge.py          # Task 2 — --format / FORGEDS_OUTPUT
src/forgeds/access/lint_access.py        # Task 2 — same
src/forgeds/hybrid/lint_hybrid.py        # Task 2 — same
src/forgeds/widgets/lint_widgets.py      # Task 2 — route through _shared/envelope.py; accept json-v1
src/forgeds/_shared/config.py            # Task 3 — accept Form A and Form B custom_apis
pyproject.toml                           # Task 4 — one new entry point: forgeds-status
templates/forgeds.yaml.example           # Task 6 — document extended custom_apis
CLAUDE.md                                # Task 6 — CFG/STA registry, envelope policy, typegen _generated/ ownership
```

---

## Commit conventions

Repo uses `feat(scope):`, `test(scope):`, `fix(scope):`, `docs(scope):`. Scope for this work: **`widgets`** (consistent with Phase 1). Two logically distinct surfaces here — lint envelope and status CLI — both still fall under widgets for continuity.

---

## Orchestration (controller-driven, fast-path)

This plan is executed by the orchestrating session directly (fast-path), not via per-task subagent dispatch. Each task still goes through: failing test → implementation → all tests green → commit. Final whole-branch review is dispatched to a `feature-dev:code-reviewer` agent at the end.

Rationale for fast-path: Phase 1 established the widget package shape; Phase 2A is incremental and mostly mechanical (envelope + CLI + schema). Spec is fully detailed with contract-level specificity.

---

## Task 1 — Shared envelope + output-format resolver

**Spec refs:** §3.1, §4.1, §4.4, §5.3.

### 1.1 Write failing tests

Create `tests/test_envelope.py`:
- `test_envelope_emits_empty_diagnostics_array` — clean run yields `"diagnostics": []`
- `test_envelope_version_is_string` — `"version": "1"` not `1`
- `test_envelope_tool_field_exact_name` — rejects historic aliases via assertion
- `test_envelope_severity_is_lowercase` — `"error"`, not `"ERROR"`
- `test_envelope_all_base_fields_required` — serializer includes file/line/rule/severity/message
- `test_status_envelope_shape` — `checks[]` array variant with `category`, `id`, `status`, `message`, `rule`
- `test_status_overall_derivation` — ok/warn/fail mapping from check statuses

Create `tests/test_output_format.py`:
- `test_format_cli_flag_wins` — `--format json-v1` overrides env
- `test_format_env_var_honored` — `FORGEDS_OUTPUT=json-v1` picked up
- `test_format_default_is_text` — no flag, no env → text
- `test_format_invalid_value_raises` — bogus value → explicit exception carrying the rejected value

### 1.2 Implement

Create `src/forgeds/_shared/envelope.py`:

```python
"""JSON v1 envelope serializers — single source of truth.

No other module may serialize the ForgeDS JSON envelope. Linters and
forgeds-status import from here. New fields on the envelope require a
version bump per CLAUDE.md's envelope versioning policy.
"""

from __future__ import annotations

import json
from typing import Iterable, Literal

from forgeds._shared.diagnostics import Diagnostic, Severity

ENVELOPE_VERSION = "1"
StatusToken = Literal["ok", "warn", "fail", "miss", "skip"]
OverallToken = Literal["ok", "warn", "fail"]


def to_json_v1(tool: str, diagnostics: Iterable[Diagnostic]) -> str:
    """Serialize a list of Diagnostics as the JSON-v1 envelope."""
    payload = {
        "tool": tool,
        "version": ENVELOPE_VERSION,
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
    return json.dumps(payload)


def status_envelope_v1(
    tool: str,
    overall: OverallToken,
    checks: list[dict],
) -> str:
    """Serialize a forgeds-status aggregate report as the JSON-v1 envelope.

    Each check dict must carry: category, id, status, message, rule (nullable).
    """
    payload = {
        "tool": tool,
        "version": ENVELOPE_VERSION,
        "overall": overall,
        "checks": checks,
    }
    return json.dumps(payload)


def derive_overall(check_statuses: list[StatusToken]) -> OverallToken:
    """Collapse per-check statuses into overall: miss→fail, skip→ok."""
    if any(s in ("fail", "miss") for s in check_statuses):
        return "fail"
    if any(s == "warn" for s in check_statuses):
        return "warn"
    return "ok"
```

Create `src/forgeds/_shared/output_format.py`:

```python
"""Resolve CLI `--format` against `FORGEDS_OUTPUT` env var."""

from __future__ import annotations

import os
from typing import Literal

Format = Literal["text", "json-v1"]
_VALID = ("text", "json-v1")


class UnknownFormatError(ValueError):
    """Raised when an unknown format value is supplied via CLI or env."""

    def __init__(self, value: str, source: str) -> None:
        super().__init__(
            f"forgeds: unknown output format {value!r} "
            f"(expected: {', '.join(_VALID)}) [source: {source}]"
        )
        self.value = value
        self.source = source


def resolve_format(cli_flag: str | None) -> Format:
    """CLI flag wins over env; env wins over default 'text'."""
    if cli_flag is not None:
        if cli_flag not in _VALID:
            raise UnknownFormatError(cli_flag, "CLI flag --format")
        return cli_flag  # type: ignore[return-value]
    env = os.environ.get("FORGEDS_OUTPUT")
    if env:
        if env not in _VALID:
            raise UnknownFormatError(env, "FORGEDS_OUTPUT")
        return env  # type: ignore[return-value]
    return "text"
```

### 1.3 Commit

`feat(widgets): add shared JSON-v1 envelope serializer and format resolver`

---

## Task 2 — Promote --format to all 4 linters

**Spec refs:** §4.1, §4.3.

Each linter gains: `--format {text,json-v1}` arg, env-var fallback, and dispatches through `envelope.to_json_v1()`. Widget linter is refactored to remove ad-hoc JSON serializer — route through shared.

Key rules:
- **Default behavior unchanged.** Text is default. Text output byte-for-byte identical to current.
- Invalid `--format` value → exit 2 with a single stderr line; no partial output.
- Widget linter's existing `--format {text,json}` becomes `--format {text,json-v1}` (spec §4.1 says the flag accepts exactly those two). `json` alias is deliberately rejected (spec open question #1 leaning: no).

### 2.1 Failing tests

Create `tests/test_lint_json_v1.py`:
- `test_lint_deluge_json_v1_shape` — run against fixture, parse stdout as JSON, assert shape
- `test_lint_access_json_v1_shape`
- `test_lint_hybrid_json_v1_shape`
- `test_lint_widgets_json_v1_routes_through_shared_envelope` — monkeypatch `_shared.envelope.to_json_v1` and assert called
- `test_lint_deluge_env_var_honored` — set `FORGEDS_OUTPUT=json-v1`, expect JSON output
- `test_lint_cli_flag_overrides_env` — env says json-v1, flag says text → text wins
- `test_lint_invalid_format_exits_2` — unknown value → stderr message + exit 2, no stdout
- `test_lint_text_default_unchanged` — snapshot-style: known fixture's text output is unchanged after the patch

### 2.2 Implement

For each of `lint_deluge.py`, `lint_access.py`, `lint_hybrid.py`:

1. Import at module top:
   ```python
   from forgeds._shared.envelope import to_json_v1
   from forgeds._shared.output_format import resolve_format, UnknownFormatError
   ```
2. In `main()`'s argparse, add:
   ```python
   parser.add_argument("--format", choices=["text", "json-v1"], default=None,
                       help="Output format (default: text; set via FORGEDS_OUTPUT env)")
   ```
   (`default=None` so env-var can win when flag is absent.)
3. Resolve format early:
   ```python
   try:
       fmt = resolve_format(args.format)
   except UnknownFormatError as exc:
       print(str(exc), file=sys.stderr)
       return 2  # or sys.exit(2) depending on main() shape
   ```
4. At output time:
   ```python
   if fmt == "json-v1":
       print(to_json_v1("forgeds-lint", all_diags))
   else:
       # existing text path, unchanged
       for d in sorted_diags: print(d)
   ```
5. For `lint_deluge` / `lint_access`: tool name is the CLI entry-point name (`forgeds-lint`, `forgeds-lint-access`). Double-check they match `pyproject.toml`.

For `lint_widgets.py`:

1. Replace the inline JSON dict construction in `_emit` with:
   ```python
   if fmt == "json-v1":
       print(to_json_v1("forgeds-lint-widgets", diagnostics))
   else:
       for d in diagnostics: print(str(d))
   ```
2. Update `--format` choices from `["text","json"]` to `["text","json-v1"]`.
3. Rename var `json` → `json-v1` everywhere in `lint_widgets.py` logic; update existing test `test_emit_json_envelope_shape` in `tests/test_lint_widgets.py` to use `"json-v1"` for `fmt`.

### 2.3 Fixture projects

- `tests/fixtures/envelope/deluge_sample_bad.dg` — a tiny .dg with a known rule violation (reuse patterns from `tests/fixtures/lint_test_bad.dg` if possible).
- `tests/fixtures/envelope/access_sample_bad.sql` — one `SELECT *` row to trigger AV warning.
- `tests/fixtures/envelope/hybrid_sample_project/` — minimal `forgeds.yaml` + one fixture file to trigger a deterministic hybrid diagnostic (reuse/symlink from existing hybrid fixtures).

### 2.4 Commit

`feat(widgets): promote --format json-v1 to every linter via shared envelope`

---

## Task 3 — Extended custom_apis schema + CFG### diagnostics

**Spec refs:** §6, §9.1.

### 3.1 Failing tests

Create `tests/test_custom_apis_schema.py`:
- `test_config_loader_accepts_form_a_custom_apis` — bare list still works (regression guard)
- `test_config_loader_accepts_form_b_custom_apis` — dict-of-dicts parses
- `test_config_loader_normalizes_form_a_to_form_b_shape` — in-memory, both load to same canonical structure
- `test_config_loader_rejects_mixed_custom_apis_forms` — CFG010 ERROR
- `test_cfg011_info_on_short_form` — one info per Form-A file (once per file, per open question #5)
- `test_cfg013_warn_on_unknown_named_type`
- `test_cfg014_error_on_missing_param_keys` — param dict missing `name` or `type`
- `test_cfg015_error_on_non_list_permissions`
- `test_cfg012_widget_consumes_undeclared_api` — config-time duplicate of WG003

### 3.2 Implement

Extend `_shared/config.py`:

1. Add a public `validate_custom_apis(cfg) -> list[Diagnostic]` function. Does not mutate `cfg`.
2. After `load_config()` parses YAML, detect if `custom_apis` is list-of-strings (Form A) or dict-of-dicts (Form B). Mixed (list containing dict) → CFG010 ERROR.
3. Normalize in-memory:
   - Form A `["a","b"]` → `{"a": {}, "b": {}}` (Form B with empty defaults)
   - Keep the original parsed form accessible via `cfg["_custom_apis_form"]` = `"A" | "B"` for CFG011 guidance.
4. Validate each Form-B entry:
   - `params[].name` and `params[].type` required → CFG014 if missing
   - `permissions` must be list of strings → CFG015
   - `returns` + `params[].type` types: primitives `{string, integer, number, boolean, any}` + `<named>` + `<type>[]`. Unknown named types → CFG013 WARNING.
5. Cross-reference `widgets.<w>.consumes_apis[i]` against `custom_apis` keys → CFG012 ERROR (same wording as WG003, different provenance).

Expose a convenience `load_config_with_diagnostics(start=None) -> tuple[dict, list[Diagnostic]]` so callers (`forgeds-status`, future linters) can surface CFG without re-parsing.

Rule allocation per spec §6.4: CFG010–CFG015 defined; CFG001–CFG009 reserved for future top-level structural errors.

### 3.3 Fixture layout

```
tests/fixtures/custom_apis/
├── form_a_bare_list/forgeds.yaml
├── form_b_extended/forgeds.yaml
├── mixed_forms/forgeds.yaml                # triggers CFG010
├── missing_param_keys/forgeds.yaml         # triggers CFG014
└── unknown_named_type/forgeds.yaml         # triggers CFG013
```

### 3.4 Commit

`feat(widgets): accept extended custom_apis schema with CFG diagnostics`

---

## Task 4 — `forgeds-status` CLI

**Spec refs:** §5, §9.2.

### 4.1 Failing tests

Create `tests/test_status_checks.py`:
- `test_db_freshness_detects_missing_db` — STA002
- `test_db_freshness_detects_stale_db` — STA003 (mtime > 30 days)
- `test_config_sanity_runs_validate_custom_apis` — surfaces CFG diagnostics
- `test_config_sanity_aborts_on_broken_yaml` — STA001 fatal
- `test_toolchain_reports_node_missing` — STA004 (mock `shutil.which`)
- `test_toolchain_reports_eslint_missing` — STA005
- `test_lint_summary_spawns_each_linter_in_json_v1` — mock subprocess.run

Create `tests/test_status_cli.py`:
- `test_status_text_report_section_order` — §5.2 exact order
- `test_status_json_envelope_shape` — closed-set category values
- `test_status_exit_code_matrix` — parameterized over fixtures:
    - all_green → 0
    - only warnings → 1
    - config_only_warnings (1 warn) → 1
    - missing_db → 2
    - broken_yaml → 2
- `test_status_aborts_on_broken_yaml_in_text_mode` — only text aborts on step 1; JSON runs all
- `test_status_runs_all_checks_in_json_mode_despite_config_failure`
- `test_status_skip_lint_flag_works`
- `test_status_skip_toolchain_does_not_contribute_to_exit`

### 4.2 Implement

Package skeleton: `src/forgeds/status/__init__.py` (empty docstring), `cli.py`, `report.py`, `checks/` package.

`status/checks/config_sanity.py`:
- Load `forgeds.yaml` via existing `_shared/config.py`. If missing or unparseable → STA001 fail, one-check return.
- Reuse `validate_custom_apis` from Task 3. Each CFG diag becomes a StatusCheck.
- Each widget is a separate check entry (id = `widgets.<w>.<dotted-path>`).

`status/checks/db_freshness.py`:
- Uses `forgeds._shared.config.get_db_dir()`.
- Required DBs: `deluge_lang.db`, `access_vba_lang.db`, `zoho_widget_sdk.db` (post-Phase-1 inclusion is valid).
- Missing → STA002 miss. Age > 30 days → STA003 warn. Documented threshold.

`status/checks/toolchain.py`:
- `shutil.which("python")` (cosmetic), `shutil.which("node")`, `shutil.which("npx")`.
- ESLint: `subprocess.run(["npx","--yes","eslint","--version"], timeout=10)` returncode 0 = ok, else STA005.
- STA004 fires only if any widget is declared (no widgets = skip node check entirely).

`status/checks/lint_summary.py`:
- For each of `forgeds-lint`, `forgeds-lint-access`, `forgeds-lint-hybrid`, `forgeds-lint-widgets`:
  - Skip widget linter if no widgets declared.
  - Spawn in `json-v1` mode via `FORGEDS_OUTPUT` env override (robust vs flag ordering).
  - Parse stdout envelope; count errors/warnings.
  - Non-zero for non-lint reasons → STA006 fail.
- Returns one StatusCheck per linter.

`status/report.py`:
- `render_text(checks: list[StatusCheck]) -> str` — spec §5.2, fixed ASCII tokens, stable order
- `render_json(checks, overall) -> str` — delegates to `_shared/envelope.status_envelope_v1`

`status/cli.py`:
- Argparse: `--format`, `--skip-lint`, `--skip-toolchain`, `-q`. No positional args.
- Order: config_sanity → db_freshness → toolchain → lint_summary (spec §5.5).
- Text mode: early-abort on broken-yaml (STA001). JSON mode: run all, include the STA001 check in output.
- Exit code per §5.4:
    - fail/miss anywhere → 2
    - warn but no fail/miss → 1
    - else → 0
- Register in `pyproject.toml`: `forgeds-status = "forgeds.status.cli:main"`.

### 4.3 Commit

`feat(status): add forgeds-status aggregate health CLI`

---

## Task 5 — pyproject.toml + CLAUDE.md + template updates

### 5.1 Entry point

Add to `[project.scripts]` in `pyproject.toml`:

```
forgeds-status = "forgeds.status.cli:main"
```

Run `pip install -e .` locally to verify resolution.

### 5.2 CLAUDE.md updates

Append the full CFG + STA tables from spec §9 (existing rule-code registry table grows). Add "envelope versioning policy" subsection reflecting §9.3 verbatim. Add note on `_generated/` directory ownership for consumer repos (§7).

### 5.3 templates/forgeds.yaml.example

Append a commented block showing Form-B extended `custom_apis`, per spec §6.1:

```yaml
# Extended form (opt-in, per-project choice; do not mix with bare-list form):
# custom_apis:
#   get_pending_claims:
#     params:
#       - { name: "status", type: "string", required: true }
#       - { name: "limit",  type: "integer", required: false, default: 50 }
#     returns: "PendingClaim[]"
#     permissions: ["api.read"]
#     description: "Lists claims awaiting approval."
```

### 5.4 Commit

`docs(widgets): register forgeds-status entry point + CFG/STA registry + extended custom_apis example`

---

## Task 6 — Final verification

### 6.1 Full test suite

`pytest tests/ --ignore=tests/test_build_ds.py` — must be all green.

### 6.2 CLI smoke

```
forgeds-lint       --format json-v1 tests/fixtures/lint_test_bad.dg
forgeds-lint-access --format json-v1 tests/fixtures/lint_test_access_bad.sql
FORGEDS_OUTPUT=json-v1 forgeds-lint-hybrid
forgeds-status --format json-v1
```

Each prints a valid `{tool, version: "1", ...}` envelope. Exit codes match spec §5.4.

### 6.3 Branch review

Dispatch a `feature-dev:code-reviewer` agent over the complete Phase 2A diff.

Focus:
1. Envelope is sole serializer (no other module calls `json.dumps` for the v1 shape).
2. Default text output is byte-identical to pre-Phase-2A (spec §11 non-goal).
3. CFG/STA ranges stay within allocated bands.
4. `forgeds-status` is read-only (no writes anywhere).
5. No typegen generator implementation (§7 is design-only).
6. Severity strings lowercase in all JSON emissions.

---

## Non-goals reiterated (spec §11)

- No Deluge/Access/Hybrid text-format byte changes
- No `--format yaml`, `sarif`, `junit`
- No new diagnostic fields (`column`, `hint`, `fix`, `code_actions`)
- No typegen implementation — contracts only
- No `types:` block parsing
- No permission-scope enforcement
- No `forgeds-status --fix` / `--suggest`
- No color/Unicode in status text
- No default-format flip
