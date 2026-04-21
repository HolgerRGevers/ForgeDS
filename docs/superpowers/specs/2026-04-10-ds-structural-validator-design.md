# Design: `forgeds-validate-ds` — .ds Structural Validator

**Date:** 2026-04-10  
**Status:** Draft  
**Motivation:** Zoho Creator's .ds import gives a single generic error ("A problem encountered while creating the application") for any structural issue. Debugging requires binary-search with test files. A local validator that catches structural errors, reference integrity violations, and Deluge field mismatches before import eliminates this guesswork entirely.

## Problem

The current ForgeDS toolchain can **generate** .ds files (`forgeds-build-ds`) and **extract** data from them (`forgeds-parse-ds`), but cannot **reject** invalid .ds files. The parser is tolerant by design — it skips what it doesn't understand. This means:

- Forms inserted outside `forms { }` go undetected
- Reports outside `reports { }` go undetected
- Deluge scripts referencing `input.Merchant_Account` when the field is `merchant_account` go undetected
- Undefined form/report references go undetected (partially caught by existing DS003)

These are exactly the bugs that caused repeated import failures in the Ten Chargeback project.

## Scope

**In scope:**
- .ds block structure validation (recursive descent parser)
- Reference integrity (forms, reports, fields cross-referenced)
- Deluge field reference checking (input.field, form[field], insert into form[field])

**Out of scope:**
- Full Deluge syntax parsing (if/else, loops, variable scoping)
- ZML content validation (dashboard page markup)
- Blueprint transition logic validation
- Indentation enforcement (Zoho is whitespace-tolerant)

## Architecture

One module: `src/forgeds/core/validate_ds.py`

Three layers:

```
┌─────────────────────────────────────────┐
│  Layer 1: Line Reader                    │
│  Reads .ds text, tracks line numbers,    │
│  provides peek/advance/expect helpers    │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Layer 2: Recursive Descent Validator    │
│  One function per .ds section.           │
│  Knows what's legal at each level.       │
│  Collects form_fields schema as it goes. │
│  Emits DS1xx (structural) and            │
│  DS2xx (reference) diagnostics.          │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Layer 3: Deluge Field Checker           │
│  Regex scan of embedded Deluge code.     │
│  Resolves field refs against schema      │
│  collected by Layer 2.                   │
│  Emits DS3xx diagnostics.                │
└─────────────────────────────────────────┘
```

**Dependencies:** stdlib only. Reuses `Diagnostic` and `Severity` from `forgeds._shared.diagnostics`.

## Layer 1: Line Reader

A cursor over the file's lines with helpers:

```python
class DsReader:
    def __init__(self, lines: list[str], filename: str): ...
    def peek(self) -> str: ...            # current line stripped
    def peek_raw(self) -> str: ...        # current line with whitespace
    def line_no(self) -> int: ...         # 1-based line number
    def advance(self) -> str: ...         # consume and return stripped line
    def skip_blank(self) -> None: ...     # skip empty/comment lines
    def at_end(self) -> bool: ...
    def expect(self, pattern: str) -> str | None:  # advance if matches, else None
```

This keeps line tracking out of the validation logic.

## Layer 2: Recursive Descent Validator

Each .ds section maps to a function. The top-level function:

```python
def validate_application(reader, diags):
    expect header comment
    expect 'application "Name"'
    expect '{'
    expect metadata (date format, time zone, time format)
    
    # Parse sections in whatever order they appear
    seen = set()
    while not at closing '}':
        keyword = peek()
        if keyword == 'forms':      validate_forms(reader, diags, schema)
        elif keyword == 'reports':  validate_reports(reader, diags, schema)
        elif keyword == 'workflow': validate_workflow(reader, diags, schema)
        elif keyword == 'pages':    validate_pages(reader, diags)
        elif keyword == 'web':      validate_web(reader, diags, schema)
        elif keyword == 'phone':    validate_device(reader, diags, 'phone')
        elif keyword == 'tablet':   validate_device(reader, diags, 'tablet')
        elif keyword == 'share_settings': skip_block(reader)
        elif keyword == 'translation':    skip_block(reader)
        else: emit DS107 unexpected section
        seen.add(keyword)
    
    # Check required sections
    if 'forms' not in seen:  emit DS102
    if 'pages' not in seen:  emit DS102
    if 'web' not in seen:    emit DS102
```

### Form parsing collects the schema:

```python
form_fields: dict[str, set[str]] = {}

def validate_form(reader, diags, form_fields):
    form_name = extract_form_name(line)
    fields = set()
    expect '{'
    # must have displayname and success message
    # parse Section block
    # parse fields until 'actions' or '}'
    while peek() not in ('actions', 'blueprint', '}'):
        field_name, field_type = parse_field(reader, diags)
        fields.add(field_name)
    # parse actions block
    # parse optional blueprint components
    expect '}'
    form_fields[form_name] = fields
```

### Section-aware error messages:

When `validate_forms()` encounters a line it doesn't expect, it can say:

```
DS101 ERROR line 663: Found 'form regional_config' outside 'forms { }' block.
      The forms block closed at line 662. Did you insert after the closing brace?
```

This is the kind of message that would have caught our bug in seconds.

## Layer 3: Deluge Field Checker

Does NOT parse Deluge syntax. Runs targeted regex over raw code strings extracted during Layer 2 workflow/schedule parsing.

**Patterns checked:**

| Pattern | What it catches | Rule |
|---------|----------------|------|
| `input\.(\w+)` | Field ref on the workflow's target form | DS301 |
| `(\w+)\[(\w+)\s*==` | Query criteria field on a named form | DS302 |
| `insert into (\w+)\s*\[` then `(\w+)\s*=` | Insert block field names | DS303 |
| Any of above where `field.lower()` matches but `field` doesn't | Case mismatch | DS304 |

**Schema lookup:**

```python
def check_deluge_refs(code: str, target_form: str, form_fields: dict, line_offset: int, diags):
    # input.field_name checks
    for m in re.finditer(r'input\.(\w+)', code):
        field = m.group(1)
        if field in ('ID',):  # system fields, skip
            continue
        if field not in form_fields.get(target_form, set()):
            # Check case mismatch
            lower_fields = {f.lower(): f for f in form_fields.get(target_form, set())}
            if field.lower() in lower_fields:
                emit DS304 with suggestion
            else:
                emit DS301
```

## Validation Rules

### Structural (DS1xx — ERROR)

| Rule | Description |
|------|-------------|
| DS101 | Element outside its parent block (form outside `forms {}`, report outside `reports {}`) |
| DS102 | Missing required section (`forms`, `pages`, `web`) |
| DS103 | Unmatched brace or paren within a specific block (with block name and opening line) |
| DS104 | Missing required form attribute (`displayname`, `actions`) |
| DS105 | Missing required field attribute (`type`) |
| DS106 | Unknown field type (not in valid type list) |
| DS107 | Unexpected section keyword at current nesting level |

### Reference Integrity (DS2xx — ERROR)

| Rule | Description |
|------|-------------|
| DS201 | Report references undefined form (`show all rows from nonexistent_form`) |
| DS202 | Workflow/schedule references undefined form (`form = nonexistent_form`) |
| DS203 | Web reports section references undefined report |
| DS204 | Web/phone/tablet forms section references undefined form |

### Deluge Field References (DS3xx — WARNING)

| Rule | Description |
|------|-------------|
| DS301 | `input.field_name` references field not in the workflow's target form |
| DS302 | `form_name[field == value]` uses field not in that form |
| DS303 | `insert into form [field = value]` uses field not in that form |
| DS304 | Field reference exists but case doesn't match (e.g., `Merchant_Account` vs `merchant_account`) |

## CLI Interface

```bash
# Validate a .ds file
forgeds-validate-ds app.ds

# Output:
# app.ds:663: [DS101] ERROR: 'form regional_config' found outside 'forms { }' block (closed at line 662)
# app.ds:1757: [DS304] WARNING: 'Merchant_Account' in regional_config query - did you mean 'merchant_account'?
#
# --- Validated app.ds: 1 error(s), 1 warning(s) ---

# Machine-readable JSON output
forgeds-validate-ds app.ds --json

# Summary only
forgeds-validate-ds app.ds --summary
```

**Exit codes:** 0 = clean, 1 = warnings only, 2 = errors (matches forgeds-lint convention).

## Registration

In `pyproject.toml`:
```toml
[project.scripts]
forgeds-validate-ds = "forgeds.core.validate_ds:main"
```

## Consumer Project Integration

Consumer projects (Ten Chargeback, ERM) call it as a CLI command after generating .ds files:

```bash
# In Ten Chargeback's workflow:
python splice_ds.py
forgeds-validate-ds ten_chargeback_management.ds
```

Or in Python:
```python
import subprocess
result = subprocess.run(["forgeds-validate-ds", str(OUTPUT)], capture_output=True, text=True)
if result.returncode == 2:
    print(result.stdout)
    sys.exit(1)
```

ForgeDS is a pip-installed dependency. Consumer projects do not import validation internals.

## Testing

Fixture-based, following `forgeds-lint` pattern:

- `tests/fixtures/validate_ds_good.ds` — minimal valid .ds (should pass clean)
- `tests/fixtures/validate_ds_bad.ds` — one example of each DS rule violation
- `tests/test_validate_ds.py` — asserts each rule fires on the bad fixture, no false positives on good fixture

## What This Does NOT Do

- Parse Deluge syntax (if/else, loops, variable scoping, type checking)
- Validate ZML dashboard markup
- Validate blueprint transition logic (reachability, dead states)
- Enforce indentation or whitespace conventions
- Modify or fix the .ds file (validate only, no auto-repair)
