# `forgeds-validate-ds` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a recursive descent .ds structural validator that catches placement errors, reference integrity violations, and Deluge field name mismatches before Zoho Creator import.

**Architecture:** Three-layer design — DsReader (line cursor with peek/advance), recursive descent validator (one function per .ds section, collects form schema), Deluge field checker (regex scan of embedded code against collected schema). Single module, stdlib only.

**Tech Stack:** Python >= 3.10, stdlib only. Reuses `Diagnostic`/`Severity` from `forgeds._shared.diagnostics`.

**Spec:** `docs/superpowers/specs/2026-04-10-ds-structural-validator-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| Create: `src/forgeds/core/validate_ds.py` | DsReader, recursive descent validator, Deluge field checker, CLI main() |
| Modify: `pyproject.toml` | Register `forgeds-validate-ds` entry point |
| Create: `tests/fixtures/validate_ds_good.ds` | Minimal valid .ds file (should pass clean) |
| Create: `tests/fixtures/validate_ds_bad.ds` | One example of each DS rule violation |

---

### Task 1: Register CLI Entry Point

**Files:**
- Modify: `pyproject.toml:22-33`

- [ ] **Step 1: Add entry point to pyproject.toml**

In the `[project.scripts]` section, add after the `forgeds-build-ds` line:

```toml
forgeds-validate-ds = "forgeds.core.validate_ds:main"
```

- [ ] **Step 2: Create empty module with main stub**

Create `src/forgeds/core/validate_ds.py`:

```python
#!/usr/bin/env python3
"""
Zoho Creator .ds file structural validator.

Recursive descent parser that catches structural placement errors,
reference integrity violations, and Deluge field name mismatches
before Zoho Creator import.

Usage:
    forgeds-validate-ds app.ds
    forgeds-validate-ds app.ds --errors-only
    forgeds-validate-ds app.ds -q
"""

from __future__ import annotations

import sys


def main() -> None:
    """CLI entry point."""
    print("forgeds-validate-ds: not yet implemented")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify entry point resolves**

Run: `pip install -e .`
Run: `python -m forgeds.core.validate_ds`
Expected: prints "forgeds-validate-ds: not yet implemented" and exits 0

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src/forgeds/core/validate_ds.py
git commit -m "feat: register forgeds-validate-ds entry point (stub)"
```

---

### Task 2: Create Test Fixtures

**Files:**
- Create: `tests/fixtures/validate_ds_good.ds`
- Create: `tests/fixtures/validate_ds_bad.ds`

- [ ] **Step 1: Create minimal valid .ds fixture**

Create `tests/fixtures/validate_ds_good.ds`:

```
/*
 * Test fixture: minimal valid .ds
 */
 application "Test App"
 {
 	date format = "dd-MMM-yyyy"
 	time zone = "America/Los_Angeles"
 	time format = "24-hr"

 	forms
	{
		form test_form
		{
			displayname = "Test Form"
			success message = "Test Form Added Successfully"
			Section
			(
				type = section
				row = 1
				column = 0
				width = medium
			)
			name_field
			(
				type = text
				displayname = "Name"
				row = 1
				column = 1
				width = medium
			)
			status_field
			(
				type = picklist
				displayname = "Status"
				values = {"Open","Closed"}
				row = 1
				column = 1
				width = medium
			)

			actions
			{
				on add
				{
					submit
					(
						type = submit
						displayname = "Submit"
					)
					reset
					(
						type = reset
						displayname = "Reset"
					)
				}
				on edit
				{
					update
					(
						type = submit
						displayname = "Update"
					)
					cancel
					(
						type = cancel
						displayname = "Cancel"
					)
				}
			}
		}
		form second_form
		{
			displayname = "Second Form"
			success message = "Second Form Added Successfully"
			Section
			(
				type = section
				row = 1
				column = 0
				width = medium
			)
			title
			(
				type = text
				displayname = "Title"
				row = 1
				column = 1
				width = medium
			)

			actions
			{
				on add
				{
					submit
					(
						type = submit
						displayname = "Submit"
					)
					reset
					(
						type = reset
						displayname = "Reset"
					)
				}
				on edit
				{
					update
					(
						type = submit
						displayname = "Update"
					)
					cancel
					(
						type = cancel
						displayname = "Cancel"
					)
				}
			}
		}
	}
	reports
	{
		list test_form_Report
		{
			displayName = "All Test Forms"
			show all rows from test_form
			(
				name_field as "Name"
				status_field as "Status"
			)
		}
	}
	pages
	{
		page DashBoard
		{
			displayname = "Dashboard"
			Content="<zml>\n<layout>\n</layout>\n</zml>"
		}
	}


		workflow
		{
		form
		{
			test_workflow as "Test Workflow"
			{
				type =  form
				form = test_form

				record event = on add

				on success
				{
					actions
					{
						custom deluge script
						(
							input.status_field = "Open";
							info input.name_field;
						)
					}
				}

			}
		}
		schedule
		{
			test_schedule as "Test Schedule"
			{
				type =  schedule
				form = test_form
				time zone = "America/Los_Angeles"
				on start
				{
					actions
					{
					on load
					(
						allRecs = test_form[status_field == "Open"];
						info allRecs.count();
					)
					}
				}
			}
		}

	}
	web
	{
		forms
		{
			form test_form
			{
				label placement = left
			}
			form second_form
			{
				label placement = left
			}
		}
		reports
		{
			report test_form_Report
			{
				quickview
				(
					layout
					(
						type = -1
						datablock1
						(
							layout type = -1
							fields
							(
								name_field
								status_field
							)
						)
					)
					menu
					(
						header
						(
							Edit
							Delete
						)
					)
				)

				detailview
				(
					layout
					(
						type = 1
						datablock1
						(
							layout type = -2
							title = "Overview"
							fields
							(
								name_field
								status_field
							)
						)
					)
					menu
					(
						header
						(
							Edit
							Delete
						)
					)
				)
			}
		}
		menu
		{
			space Space
			{
				displayname = "Space"
				icon = "objects-spaceship"
				section Section_1
				{
					displayname = "Test"
					icon = "travel-world"
					form test_form
					{
						icon = "ui-1-bold-add"
					}
					report test_form_Report
					{
						icon = "travel-world"
					}
				}
			}
			preference
			{
				icon
				{
					style = solid
					show = {space,section,component}
				}
			}
		}
		customize
		{
			new theme = 11
			font = "poppins"
			color options
			{
				color = "5"
			}
			logo
			{
				preference = "none"
				placement = "left"
			}
		}
	}
	phone
	{
		forms
		{
			form test_form
			{
				label placement = auto
			}
			form second_form
			{
				label placement = auto
			}
		}
		customize
		{
			layout = slidingpane
			font = "default"
			style = "3"
			color options
			{
				color = green
			}
			logo
			{
				preference = "none"
			}
		}
	}
	tablet
	{
		forms
		{
			form test_form
			{
				label placement = auto
			}
			form second_form
			{
				label placement = auto
			}
		}
		customize
		{
			layout = slidingpane
			font = "default"
			style = "3"
			color options
			{
				color = green
			}
			logo
			{
				preference = "none"
			}
		}
	}
}
```

- [ ] **Step 2: Create bad .ds fixture with one violation per rule**

Create `tests/fixtures/validate_ds_bad.ds`:

```
/*
 * Test fixture: intentional violations for every DS rule
 */
 application "Bad Test App"
 {
 	date format = "dd-MMM-yyyy"
 	time zone = "America/Los_Angeles"
 	time format = "24-hr"

 	forms
	{
		form my_form
		{
			displayname = "My Form"
			success message = "My Form Added Successfully"
			Section
			(
				type = section
				row = 1
				column = 0
				width = medium
			)
			good_field
			(
				type = text
				displayname = "Good Field"
				row = 1
				column = 1
				width = medium
			)
			bad_type_field
			(
				type = invalidtype
				displayname = "Bad Type"
				row = 1
				column = 1
				width = medium
			)
			no_type_field
			(
				displayname = "No Type"
				row = 1
				column = 1
				width = medium
			)

			actions
			{
				on add
				{
					submit
					(
						type = submit
						displayname = "Submit"
					)
					reset
					(
						type = reset
						displayname = "Reset"
					)
				}
				on edit
				{
					update
					(
						type = submit
						displayname = "Update"
					)
					cancel
					(
						type = cancel
						displayname = "Cancel"
					)
				}
			}
		}
	}
	form orphan_form
	{
		displayname = "Orphan"
	}
	reports
	{
		list my_form_Report
		{
			displayName = "All My Forms"
			show all rows from my_form
			(
				good_field as "Good Field"
			)
		}
		list bad_ref_Report
		{
			displayName = "Bad Ref"
			show all rows from nonexistent_form
			(
				some_field as "Some Field"
			)
		}
	}
	list orphan_report
	{
		displayName = "Orphan Report"
		show all rows from my_form
		(
			good_field as "Good"
		)
	}
	pages
	{
		page DashBoard
		{
			displayname = "Dashboard"
			Content="<zml>\n</zml>"
		}
	}

		workflow
		{
		form
		{
			bad_wf as "Bad Workflow"
			{
				type =  form
				form = nonexistent_form

				record event = on add

				on success
				{
					actions
					{
						custom deluge script
						(
							input.Good_Field = "test";
							input.totally_fake = "nope";
							rec = my_form[Good_Field == "x"];
							row = insert into my_form
							[
							    Good_Field = "val"
							    fake_field = "bad"
							];
						)
					}
				}

			}
		}
		schedule
		{
			bad_sched as "Bad Schedule"
			{
				type =  schedule
				form = my_form
				time zone = "America/Los_Angeles"
				on start
				{
					actions
					{
					on load
					(
						recs = my_form[good_field == "Open"];
						info input.good_field;
					)
					}
				}
			}
		}

	}
	web
	{
		forms
		{
			form my_form
			{
				label placement = left
			}
			form ghost_form
			{
				label placement = left
			}
		}
		reports
		{
			report my_form_Report
			{
				quickview
				(
					layout
					(
						type = -1
						datablock1
						(
							layout type = -1
							fields
							(
								good_field
							)
						)
					)
				)

				detailview
				(
					layout
					(
						type = 1
						datablock1
						(
							layout type = -2
							title = "Overview"
							fields
							(
								good_field
							)
						)
					)
				)
			}
			report ghost_report
			{
				quickview
				(
					layout
					(
						type = -1
						datablock1
						(
							layout type = -1
							fields
							(
								good_field
							)
						)
					)
				)

				detailview
				(
					layout
					(
						type = 1
						datablock1
						(
							layout type = -2
							title = "Overview"
							fields
							(
								good_field
							)
						)
					)
				)
			}
		}
	}
}
```

Expected violations in this fixture:
- DS101: `form orphan_form` outside `forms { }` (after forms block closes)
- DS101: `list orphan_report` outside `reports { }` (after reports block closes)
- DS105: `no_type_field` has no `type` attribute
- DS106: `bad_type_field` has `type = invalidtype`
- DS201: `bad_ref_Report` references `nonexistent_form`
- DS202: `bad_wf` workflow references `form = nonexistent_form`
- DS204: web forms lists `ghost_form` which is not in `forms { }`
- DS203: web reports lists `ghost_report` which is not in `reports { }`
- DS301: `input.totally_fake` not a field on the target form
- DS303: `insert into my_form [fake_field]` not a field
- DS304: `input.Good_Field` should be `good_field` (case mismatch)
- DS304: `my_form[Good_Field == ...]` should be `good_field` (case mismatch)

- [ ] **Step 3: Commit fixtures**

```bash
git add tests/fixtures/validate_ds_good.ds tests/fixtures/validate_ds_bad.ds
git commit -m "test: add .ds validator fixtures (good + bad)"
```

---

### Task 3: Implement DsReader (Layer 1)

**Files:**
- Modify: `src/forgeds/core/validate_ds.py`

- [ ] **Step 1: Write DsReader test**

Add to the top of `validate_ds.py` (will be tested via CLI against fixtures):

Run the good fixture through the reader to verify it can iterate all lines:
`python -c "from forgeds.core.validate_ds import DsReader; r = DsReader(open('tests/fixtures/validate_ds_good.ds').read().splitlines(), 'test'); [r.advance() for _ in range(5)]; print(f'Line {r.line_no()}: {r.peek()}')"` — should print line 6 content.

- [ ] **Step 2: Implement DsReader**

Replace the stub in `validate_ds.py` with:

```python
#!/usr/bin/env python3
"""
Zoho Creator .ds file structural validator.

Recursive descent parser that catches structural placement errors,
reference integrity violations, and Deluge field name mismatches
before Zoho Creator import.

Rules:
    DS101  Element outside its parent block
    DS102  Missing required section (forms, pages, web)
    DS103  Unmatched brace/paren within a block
    DS104  Missing required form attribute (displayname, actions)
    DS105  Missing required field attribute (type)
    DS106  Unknown field type
    DS107  Unexpected section keyword
    DS201  Report references undefined form
    DS202  Workflow/schedule references undefined form
    DS203  Web reports references undefined report
    DS204  Web/device forms references undefined form
    DS301  input.field not in workflow target form
    DS302  form[field] uses field not in that form
    DS303  insert into form [field] uses field not in that form
    DS304  Field reference case mismatch

Usage:
    forgeds-validate-ds app.ds
    forgeds-validate-ds app.ds --errors-only
    forgeds-validate-ds app.ds -q
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field

from forgeds._shared.diagnostics import Diagnostic, Severity


# ============================================================
# Valid .ds field types (from build_ds.py TYPE_MAP + Zoho extras)
# ============================================================

VALID_FIELD_TYPES = {
    "text", "textarea", "picklist", "number", "decimal",
    "date", "datetime", "email", "checkbox", "url", "phone",
    "currency", "percent", "richtext", "upload file", "image",
    "audio", "video", "signature", "autonumber", "list",
    "USD", "percentage",
}

# Keywords that look like field names but aren't
NON_FIELD_KEYWORDS = {
    "Section", "actions", "submit", "reset", "update", "cancel",
    "blueprint", "on", "must",
}


# ============================================================
# Layer 1: Line Reader
# ============================================================

class DsReader:
    """Cursor over .ds file lines with peek/advance helpers."""

    def __init__(self, lines: list[str], filename: str) -> None:
        self._lines = lines
        self._pos = 0
        self.filename = filename

    def peek(self) -> str:
        """Current line, stripped of leading/trailing whitespace."""
        if self._pos >= len(self._lines):
            return ""
        return self._lines[self._pos].strip()

    def peek_raw(self) -> str:
        """Current line with original whitespace."""
        if self._pos >= len(self._lines):
            return ""
        return self._lines[self._pos]

    def line_no(self) -> int:
        """1-based line number of current position."""
        return self._pos + 1

    def advance(self) -> str:
        """Consume current line and return it stripped."""
        line = self.peek()
        self._pos += 1
        return line

    def advance_raw(self) -> str:
        """Consume current line and return it with whitespace."""
        line = self.peek_raw()
        self._pos += 1
        return line

    def skip_blank(self) -> None:
        """Skip blank lines and comment lines."""
        while not self.at_end():
            s = self.peek()
            if s == "" or s.startswith("//"):
                self._pos += 1
            else:
                break

    def at_end(self) -> bool:
        return self._pos >= len(self._lines)

    def remaining(self) -> int:
        return len(self._lines) - self._pos
```

- [ ] **Step 3: Verify DsReader works**

Run: `python -c "from forgeds.core.validate_ds import DsReader; r = DsReader(open('tests/fixtures/validate_ds_good.ds').read().splitlines(), 'test'); r.skip_blank(); print(f'Line {r.line_no()}: {r.peek()[:40]}')"`

Expected: `Line 1: /*` (first non-blank line)

- [ ] **Step 4: Commit**

```bash
git add src/forgeds/core/validate_ds.py
git commit -m "feat: implement DsReader line cursor for .ds validator"
```

---

### Task 4: Implement Recursive Descent Validator (Layer 2 — Core)

**Files:**
- Modify: `src/forgeds/core/validate_ds.py`

- [ ] **Step 1: Add schema collection dataclass and block-skip helper**

Append after the DsReader class:

```python
# ============================================================
# Layer 2: Recursive Descent Validator
# ============================================================

@dataclass
class DsSchema:
    """Schema collected during validation pass."""
    form_fields: dict[str, set[str]] = field(default_factory=dict)
    form_names: set[str] = field(default_factory=set)
    report_names: set[str] = field(default_factory=set)
    deluge_blocks: list[tuple[str, str, int, str]] = field(default_factory=list)
    # Each: (target_form, code_text, line_offset, script_name)


def skip_block(reader: DsReader) -> None:
    """Skip a brace-delimited block { ... }, consuming the closing }."""
    depth = 0
    while not reader.at_end():
        line = reader.advance()
        depth += line.count("{") - line.count("}")
        if depth <= 0:
            return


def skip_paren_block(reader: DsReader) -> None:
    """Skip a paren-delimited block ( ... ), consuming the closing )."""
    depth = 0
    while not reader.at_end():
        line = reader.advance()
        depth += line.count("(") - line.count(")")
        if depth <= 0:
            return
```

- [ ] **Step 2: Implement validate_form (parses fields, collects schema)**

```python
def validate_form(reader: DsReader, diags: list[Diagnostic], schema: DsSchema) -> None:
    """Parse a single form block, collecting field names."""
    # Current line is 'form <name>' — extract name
    m = re.match(r"form\s+(\w+)", reader.peek())
    if not m:
        return
    form_name = m.group(1)
    form_line = reader.line_no()
    reader.advance()  # consume 'form <name>'
    schema.form_names.add(form_name)

    # Expect opening brace
    reader.skip_blank()
    if reader.peek() != "{":
        diags.append(Diagnostic(reader.filename, reader.line_no(), "DS103",
                                Severity.ERROR, f"Expected '{{' after 'form {form_name}'"))
        return
    reader.advance()  # consume '{'

    fields: set[str] = set()
    has_displayname = False
    has_actions = False
    depth = 1

    while not reader.at_end() and depth > 0:
        reader.skip_blank()
        line = reader.peek()

        if line == "}":
            depth -= 1
            reader.advance()
            if depth == 0:
                break
            continue

        # Track displayname
        if line.startswith("displayname"):
            has_displayname = True
            reader.advance()
            continue

        # Skip success message, Section block
        if line.startswith("success message"):
            reader.advance()
            continue
        if line == "Section":
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "(":
                skip_paren_block(reader)
            continue

        # Actions block
        if line == "actions":
            has_actions = True
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                skip_block(reader)
            continue

        # Blueprint components
        if line.startswith("blueprint"):
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                skip_block(reader)
            continue

        # Must be a field definition: identifier followed by (
        fm = re.match(r"^(must\s+have\s+)?(\w+)$", line)
        if fm:
            field_name = fm.group(2)
            if field_name in NON_FIELD_KEYWORDS:
                reader.advance()
                continue
            field_line = reader.line_no()
            reader.advance()
            reader.skip_blank()

            if reader.peek() == "(":
                # Parse field attributes
                fields.add(field_name)
                has_type = False
                field_type = ""
                paren_depth = 0
                while not reader.at_end():
                    attr_line = reader.advance()
                    paren_depth += attr_line.count("(") - attr_line.count(")")
                    tm = re.match(r"type\s*=\s*(.+)", attr_line.strip())
                    if tm:
                        has_type = True
                        field_type = tm.group(1).strip()
                    if paren_depth <= 0:
                        break

                if not has_type:
                    diags.append(Diagnostic(reader.filename, field_line, "DS105",
                                            Severity.ERROR,
                                            f"Field '{field_name}' in form '{form_name}' has no 'type' attribute"))

                if has_type and field_type and field_type not in VALID_FIELD_TYPES:
                    diags.append(Diagnostic(reader.filename, field_line, "DS106",
                                            Severity.ERROR,
                                            f"Field '{field_name}' has unknown type '{field_type}'"))
            continue

        # Anything else — advance to avoid infinite loop
        reader.advance()

    if not has_displayname:
        diags.append(Diagnostic(reader.filename, form_line, "DS104",
                                Severity.WARNING,
                                f"Form '{form_name}' missing 'displayname' attribute"))

    if not has_actions:
        diags.append(Diagnostic(reader.filename, form_line, "DS104",
                                Severity.WARNING,
                                f"Form '{form_name}' missing 'actions' block"))

    schema.form_fields[form_name] = fields
```

- [ ] **Step 3: Implement validate_forms (container for form blocks)**

```python
def validate_forms(reader: DsReader, diags: list[Diagnostic], schema: DsSchema) -> None:
    """Parse the forms { } block."""
    reader.advance()  # consume 'forms'
    reader.skip_blank()
    if reader.peek() != "{":
        diags.append(Diagnostic(reader.filename, reader.line_no(), "DS103",
                                Severity.ERROR, "Expected '{' after 'forms'"))
        return
    reader.advance()  # consume '{'

    while not reader.at_end():
        reader.skip_blank()
        line = reader.peek()

        if line == "}":
            reader.advance()
            return

        if line.startswith("form "):
            validate_form(reader, diags, schema)
        else:
            reader.advance()
```

- [ ] **Step 4: Test forms parsing against good fixture**

Run: `python -c "
from forgeds.core.validate_ds import DsReader, DsSchema, validate_forms
text = open('tests/fixtures/validate_ds_good.ds').read()
lines = text.splitlines()
reader = DsReader(lines, 'good.ds')
# Advance to 'forms' line
while not reader.at_end():
    if reader.peek() == 'forms':
        break
    reader.advance()
diags = []
schema = DsSchema()
validate_forms(reader, diags, schema)
print(f'Forms: {schema.form_names}')
for f, fields in schema.form_fields.items():
    print(f'  {f}: {fields}')
print(f'Diagnostics: {len(diags)}')
for d in diags:
    print(f'  {d}')
"`

Expected: 2 forms (`test_form`, `second_form`), correct fields, 0 diagnostics.

- [ ] **Step 5: Commit**

```bash
git add src/forgeds/core/validate_ds.py
git commit -m "feat: implement form/field parsing in .ds validator"
```

---

### Task 5: Implement Remaining Section Validators

**Files:**
- Modify: `src/forgeds/core/validate_ds.py`

- [ ] **Step 1: Implement validate_reports**

```python
def validate_reports(reader: DsReader, diags: list[Diagnostic], schema: DsSchema) -> None:
    """Parse the reports { } block, validate form references."""
    reader.advance()  # consume 'reports'
    reader.skip_blank()
    if reader.peek() != "{":
        diags.append(Diagnostic(reader.filename, reader.line_no(), "DS103",
                                Severity.ERROR, "Expected '{' after 'reports'"))
        return
    reader.advance()  # consume '{'

    while not reader.at_end():
        reader.skip_blank()
        line = reader.peek()

        if line == "}":
            reader.advance()
            return

        # list report_name or kanban report_name
        rm = re.match(r"(list|kanban)\s+(\w+)", line)
        if rm:
            report_name = rm.group(2)
            report_line = reader.line_no()
            schema.report_names.add(report_name)
            reader.advance()
            reader.skip_blank()

            if reader.peek() == "{":
                # Scan for form reference inside report block
                depth = 0
                while not reader.at_end():
                    rline = reader.advance()
                    depth += rline.count("{") - rline.count("}")
                    fm = re.search(r"show all rows from\s+(\w+)", rline)
                    if fm:
                        ref_form = fm.group(1)
                        if ref_form not in schema.form_names:
                            diags.append(Diagnostic(reader.filename, reader.line_no() - 1,
                                                    "DS201", Severity.ERROR,
                                                    f"Report '{report_name}' references undefined form '{ref_form}'"))
                    if depth <= 0:
                        break
            continue

        reader.advance()
```

- [ ] **Step 2: Implement validate_workflow (collects Deluge code blocks)**

```python
def validate_workflow(reader: DsReader, diags: list[Diagnostic], schema: DsSchema) -> None:
    """Parse workflow { } block including form, schedule, and blueprint sub-blocks."""
    reader.advance()  # consume 'workflow'
    reader.skip_blank()
    if reader.peek() != "{":
        diags.append(Diagnostic(reader.filename, reader.line_no(), "DS103",
                                Severity.ERROR, "Expected '{' after 'workflow'"))
        return
    reader.advance()  # consume '{'

    depth = 1
    while not reader.at_end() and depth > 0:
        reader.skip_blank()
        line = reader.peek()

        if line == "}":
            depth -= 1
            reader.advance()
            if depth == 0:
                return
            continue

        if line == "{":
            depth += 1
            reader.advance()
            continue

        # form sub-block (workflows)
        if line == "form":
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                _parse_wf_form_block(reader, diags, schema)
            continue

        # schedule sub-block
        if line == "schedule":
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                _parse_wf_schedule_block(reader, diags, schema)
            continue

        # blueprint sub-block — skip entirely
        if line == "blueprint":
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                skip_block(reader)
            continue

        reader.advance()


def _parse_wf_form_block(reader: DsReader, diags: list[Diagnostic], schema: DsSchema) -> None:
    """Parse workflow > form { } block with individual workflow items."""
    reader.advance()  # consume '{'

    while not reader.at_end():
        reader.skip_blank()
        line = reader.peek()

        if line == "}":
            reader.advance()
            return

        # workflow_name as "Display Name"
        wm = re.match(r'(\w+)\s+as\s+"(.+)"', line)
        if wm:
            wf_name = wm.group(1)
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                _parse_wf_item(reader, diags, schema, wf_name, "workflow")
            continue

        reader.advance()


def _parse_wf_schedule_block(reader: DsReader, diags: list[Diagnostic], schema: DsSchema) -> None:
    """Parse workflow > schedule { } block."""
    reader.advance()  # consume '{'

    while not reader.at_end():
        reader.skip_blank()
        line = reader.peek()

        if line == "}":
            reader.advance()
            return

        sm = re.match(r'(\w+)\s+as\s+"(.+)"', line)
        if sm:
            sched_name = sm.group(1)
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                _parse_wf_item(reader, diags, schema, sched_name, "schedule")
            continue

        reader.advance()


def _parse_wf_item(reader: DsReader, diags: list[Diagnostic], schema: DsSchema,
                   item_name: str, item_type: str) -> None:
    """Parse a single workflow/schedule item, extract form ref and Deluge code."""
    reader.advance()  # consume '{'
    target_form = ""
    depth = 1

    while not reader.at_end() and depth > 0:
        line = reader.peek()
        raw = reader.peek_raw()

        # Extract form reference
        fm = re.match(r"form\s*=\s*(\w+)", line)
        if fm:
            target_form = fm.group(1)
            if target_form not in schema.form_names:
                diags.append(Diagnostic(reader.filename, reader.line_no(), "DS202",
                                        Severity.ERROR,
                                        f"{item_type.title()} '{item_name}' references undefined form '{target_form}'"))

        # Extract Deluge code from 'custom deluge script (' or 'on load ('
        if line in ("custom deluge script", "on load"):
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "(":
                code_start = reader.line_no()
                code_lines = []
                paren_depth = 0
                while not reader.at_end():
                    cl = reader.advance_raw()
                    paren_depth += cl.count("(") - cl.count(")")
                    code_lines.append(cl)
                    if paren_depth <= 0:
                        break
                code_text = "\n".join(code_lines[1:-1])  # strip opening ( and closing )
                schema.deluge_blocks.append((target_form, code_text, code_start, item_name))
            continue

        depth += line.count("{") - line.count("}")
        reader.advance()
```

- [ ] **Step 3: Implement validate_web and validate_device**

```python
def validate_web(reader: DsReader, diags: list[Diagnostic], schema: DsSchema) -> None:
    """Parse web { } block, validate form and report references."""
    reader.advance()  # consume 'web'
    reader.skip_blank()
    if reader.peek() != "{":
        return
    reader.advance()  # consume '{'

    depth = 1
    while not reader.at_end() and depth > 0:
        reader.skip_blank()
        line = reader.peek()

        if line == "}":
            depth -= 1
            reader.advance()
            continue
        if line == "{":
            depth += 1
            reader.advance()
            continue

        # Check form references in web > forms
        fm = re.match(r"form\s+(\w+)", line)
        if fm and fm.group(1) not in ("", ):
            ref = fm.group(1)
            if ref not in schema.form_names:
                diags.append(Diagnostic(reader.filename, reader.line_no(), "DS204",
                                        Severity.WARNING,
                                        f"Web section references undefined form '{ref}'"))

        # Check report references in web > reports
        rm = re.match(r"report\s+(\w+)", line)
        if rm:
            ref = rm.group(1)
            if ref not in schema.report_names:
                diags.append(Diagnostic(reader.filename, reader.line_no(), "DS203",
                                        Severity.WARNING,
                                        f"Web section references undefined report '{ref}'"))

        reader.advance()


def validate_device(reader: DsReader, diags: list[Diagnostic], schema: DsSchema,
                    device: str) -> None:
    """Parse phone/tablet { } blocks, validate form references."""
    reader.advance()  # consume device keyword
    reader.skip_blank()
    if reader.peek() != "{":
        return
    reader.advance()  # consume '{'

    depth = 1
    while not reader.at_end() and depth > 0:
        line = reader.peek()
        if line == "}":
            depth -= 1
        elif line == "{":
            depth += 1

        fm = re.match(r"form\s+(\w+)", line)
        if fm:
            ref = fm.group(1)
            if ref not in schema.form_names:
                diags.append(Diagnostic(reader.filename, reader.line_no(), "DS204",
                                        Severity.WARNING,
                                        f"{device.title()} section references undefined form '{ref}'"))

        reader.advance()
```

- [ ] **Step 4: Implement validate_pages and skip helpers for share_settings/translation**

```python
def validate_pages(reader: DsReader, diags: list[Diagnostic]) -> None:
    """Parse pages { } block — just validates structure."""
    reader.advance()  # consume 'pages'
    reader.skip_blank()
    if reader.peek() != "{":
        return
    skip_block(reader)
```

- [ ] **Step 5: Commit**

```bash
git add src/forgeds/core/validate_ds.py
git commit -m "feat: implement reports, workflow, web, device section validators"
```

---

### Task 6: Implement Top-Level Validator and Orphan Detection

**Files:**
- Modify: `src/forgeds/core/validate_ds.py`

- [ ] **Step 1: Implement validate_application (top-level orchestrator)**

```python
# Known top-level section keywords inside application { }
TOP_LEVEL_SECTIONS = {
    "forms", "reports", "pages", "workflow", "web",
    "phone", "tablet", "share_settings", "translation",
}

# Sections that are required for a valid Zoho Creator import
REQUIRED_SECTIONS = {"forms", "pages", "web"}


def validate_application(reader: DsReader, diags: list[Diagnostic], schema: DsSchema) -> None:
    """Top-level recursive descent: parse application block."""

    # Skip header comment
    while not reader.at_end():
        line = reader.peek()
        if line.startswith("/*"):
            while not reader.at_end():
                if "*/" in reader.advance():
                    break
            continue
        if line == "":
            reader.advance()
            continue
        break

    # Expect 'application "Name"'
    line = reader.peek()
    if not re.match(r'application\s+".*"', line):
        diags.append(Diagnostic(reader.filename, reader.line_no(), "DS107",
                                Severity.ERROR,
                                f"Expected 'application \"Name\"', found: {line[:50]}"))
        return
    reader.advance()

    # Expect opening brace
    reader.skip_blank()
    if reader.peek() != "{":
        diags.append(Diagnostic(reader.filename, reader.line_no(), "DS103",
                                Severity.ERROR, "Expected '{' after application declaration"))
        return
    reader.advance()

    # Skip metadata lines (date format, time zone, time format)
    while not reader.at_end():
        reader.skip_blank()
        line = reader.peek()
        if line.startswith(("date format", "time zone", "time format")):
            reader.advance()
            continue
        break

    # Parse sections
    seen_sections: set[str] = set()

    while not reader.at_end():
        reader.skip_blank()
        line = reader.peek()

        if line == "}":
            reader.advance()
            break

        # Detect orphan elements (form/list/kanban outside their parent block)
        if re.match(r"form\s+\w+", line) and "forms" in seen_sections:
            diags.append(Diagnostic(reader.filename, reader.line_no(), "DS101",
                                    Severity.ERROR,
                                    f"'{line}' found at application level — must be inside 'forms {{ }}' block"))
            # Skip the orphan block
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                skip_block(reader)
            continue

        if re.match(r"(list|kanban)\s+\w+", line) and "reports" in seen_sections:
            diags.append(Diagnostic(reader.filename, reader.line_no(), "DS101",
                                    Severity.ERROR,
                                    f"'{line}' found at application level — must be inside 'reports {{ }}' block"))
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                skip_block(reader)
            continue

        # Match known sections
        keyword = line.split()[0] if line.split() else ""

        if keyword == "forms":
            seen_sections.add("forms")
            validate_forms(reader, diags, schema)
        elif keyword == "reports":
            seen_sections.add("reports")
            validate_reports(reader, diags, schema)
        elif keyword == "workflow":
            seen_sections.add("workflow")
            validate_workflow(reader, diags, schema)
        elif keyword == "pages":
            seen_sections.add("pages")
            validate_pages(reader, diags)
        elif keyword == "web":
            seen_sections.add("web")
            validate_web(reader, diags, schema)
        elif keyword in ("phone", "tablet"):
            seen_sections.add(keyword)
            validate_device(reader, diags, schema, keyword)
        elif keyword in ("share_settings", "translation"):
            seen_sections.add(keyword)
            reader.advance()
            reader.skip_blank()
            if reader.peek() == "{":
                skip_block(reader)
        else:
            diags.append(Diagnostic(reader.filename, reader.line_no(), "DS107",
                                    Severity.WARNING,
                                    f"Unexpected keyword at application level: '{line[:40]}'"))
            reader.advance()

    # Check required sections
    for required in REQUIRED_SECTIONS:
        if required not in seen_sections:
            diags.append(Diagnostic(reader.filename, reader.line_no(), "DS102",
                                    Severity.ERROR,
                                    f"Missing required section: '{required}'"))
```

- [ ] **Step 2: Add the public validation entry function**

```python
def validate_ds_file(path: str) -> list[Diagnostic]:
    """Validate a .ds file, returning all diagnostics."""
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    reader = DsReader(lines, path)
    diags: list[Diagnostic] = []
    schema = DsSchema()

    validate_application(reader, diags, schema)

    # Layer 3: Deluge field reference checks
    check_deluge_refs(diags, schema)

    return diags
```

- [ ] **Step 3: Test against good fixture**

Run: `python -c "from forgeds.core.validate_ds import validate_ds_file; ds = validate_ds_file('tests/fixtures/validate_ds_good.ds'); print(f'{len(ds)} diagnostics'); [print(d) for d in ds]"`

Expected: 0 diagnostics.

- [ ] **Step 4: Test against bad fixture**

Run: `python -c "from forgeds.core.validate_ds import validate_ds_file; ds = validate_ds_file('tests/fixtures/validate_ds_bad.ds'); print(f'{len(ds)} diagnostics'); [print(d) for d in ds]"`

Expected: Multiple diagnostics including DS101, DS105, DS106, DS201, DS202.

- [ ] **Step 5: Commit**

```bash
git add src/forgeds/core/validate_ds.py
git commit -m "feat: implement top-level .ds validator with orphan detection"
```

---

### Task 7: Implement Deluge Field Reference Checker (Layer 3)

**Files:**
- Modify: `src/forgeds/core/validate_ds.py`

- [ ] **Step 1: Implement check_deluge_refs**

```python
# ============================================================
# Layer 3: Deluge Field Reference Checker
# ============================================================

# System fields that are always valid (not defined in form schema)
SYSTEM_FIELDS = {"ID", "Added_User", "Added_Time", "Modified_User", "Modified_Time"}


def check_deluge_refs(diags: list[Diagnostic], schema: DsSchema) -> None:
    """Check field references in embedded Deluge code against form schema."""
    for target_form, code, line_offset, script_name in schema.deluge_blocks:
        code_lines = code.splitlines()

        for i, code_line in enumerate(code_lines):
            abs_line = line_offset + i

            # DS301: input.field_name
            for m in re.finditer(r"input\.(\w+)", code_line):
                _check_field_ref(diags, schema, m.group(1), target_form,
                                 abs_line, script_name, "DS301",
                                 f"input.{m.group(1)}")

            # DS302: form_name[field == value]
            for m in re.finditer(r"(\w+)\[(\w+)\s*[=!<>]", code_line):
                form_ref = m.group(1)
                field_ref = m.group(2)
                if form_ref in schema.form_fields:
                    _check_field_ref(diags, schema, field_ref, form_ref,
                                     abs_line, script_name, "DS302",
                                     f"{form_ref}[{field_ref}]")

            # DS303: insert into form_name [ field = value ]
            insert_m = re.search(r"insert\s+into\s+(\w+)", code_line)
            if insert_m:
                insert_form = insert_m.group(1)
                # Scan subsequent lines for field = value inside [ ]
                for j in range(i, min(i + 20, len(code_lines))):
                    il = code_lines[j].strip()
                    if il == "]" or il.endswith("];"):
                        break
                    fm = re.match(r"(\w+)\s*=\s*", il)
                    if fm and fm.group(1) not in ("insert", "into"):
                        _check_field_ref(diags, schema, fm.group(1), insert_form,
                                         line_offset + j, script_name, "DS303",
                                         f"insert into {insert_form} [{fm.group(1)}]")


def _check_field_ref(diags: list[Diagnostic], schema: DsSchema,
                     field_name: str, form_name: str, line: int,
                     script_name: str, rule: str, context: str) -> None:
    """Check a single field reference. Emit DS301/302/303 or DS304 for case mismatch."""
    if field_name in SYSTEM_FIELDS:
        return

    fields = schema.form_fields.get(form_name, set())
    if not fields:
        return  # form not found — already caught by DS202

    if field_name in fields:
        return  # exact match, all good

    # Check case-insensitive match
    lower_map = {f.lower(): f for f in fields}
    if field_name.lower() in lower_map:
        actual = lower_map[field_name.lower()]
        diags.append(Diagnostic("", line, "DS304", Severity.WARNING,
                                f"Case mismatch in {context}: '{field_name}' should be '{actual}' "
                                f"(in script '{script_name}')"))
    else:
        diags.append(Diagnostic("", line, rule, Severity.WARNING,
                                f"{context} references undefined field in form '{form_name}' "
                                f"(in script '{script_name}')"))
```

- [ ] **Step 2: Test Deluge checking against bad fixture**

Run: `python -c "from forgeds.core.validate_ds import validate_ds_file; ds = validate_ds_file('tests/fixtures/validate_ds_bad.ds'); [print(d) for d in ds if d.rule.startswith('DS3')]"`

Expected: DS304 for `Good_Field` (should be `good_field`), DS301 for `totally_fake`, DS303 for `fake_field`.

- [ ] **Step 3: Test Deluge checking against good fixture produces no warnings**

Run: `python -c "from forgeds.core.validate_ds import validate_ds_file; ds = validate_ds_file('tests/fixtures/validate_ds_good.ds'); [print(d) for d in ds if d.rule.startswith('DS3')]"`

Expected: 0 diagnostics (good fixture uses correct field names).

- [ ] **Step 4: Commit**

```bash
git add src/forgeds/core/validate_ds.py
git commit -m "feat: implement Deluge field reference checker (DS3xx rules)"
```

---

### Task 8: Implement CLI main() and Wire Up

**Files:**
- Modify: `src/forgeds/core/validate_ds.py`

- [ ] **Step 1: Implement main()**

Replace the existing `main()` stub with:

```python
def main() -> None:
    """CLI entry point for forgeds-validate-ds."""
    parser = argparse.ArgumentParser(
        description="Zoho Creator .ds file structural validator",
        epilog="Exit codes: 0=clean, 1=warnings, 2=errors",
    )
    parser.add_argument("paths", nargs="+", help=".ds files to validate")
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="Only show errors and warnings, suppress info",
    )
    parser.add_argument(
        "--errors-only", action="store_true",
        help="Only show ERROR severity",
    )
    parser.add_argument(
        "--summary", action="store_true",
        help="Show only summary counts",
    )
    args = parser.parse_args()

    all_diags: list[Diagnostic] = []
    file_count = 0

    for path in args.paths:
        file_count += 1
        diags = validate_ds_file(path)
        # Set filename on Deluge diagnostics (which have empty file)
        for d in diags:
            if not d.file:
                d.file = path
        all_diags.extend(diags)

    # Filter by severity
    if args.errors_only:
        all_diags = [d for d in all_diags if d.severity == Severity.ERROR]
    elif args.quiet:
        all_diags = [d for d in all_diags if d.severity != Severity.INFO]

    # Sort by file, line, severity
    severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
    all_diags.sort(key=lambda d: (d.file, d.line, severity_order[d.severity]))

    if not args.summary:
        for diag in all_diags:
            print(diag)

    # Summary
    errors = sum(1 for d in all_diags if d.severity == Severity.ERROR)
    warnings = sum(1 for d in all_diags if d.severity == Severity.WARNING)
    infos = sum(1 for d in all_diags if d.severity == Severity.INFO)

    print(
        f"\n--- Validated {file_count} file(s): "
        f"{errors} error(s), {warnings} warning(s), {infos} info(s) ---"
    )

    sys.exit(2 if errors > 0 else 1 if warnings > 0 else 0)
```

- [ ] **Step 2: Test CLI against good fixture**

Run: `python -m forgeds.core.validate_ds tests/fixtures/validate_ds_good.ds`

Expected output:
```
--- Validated 1 file(s): 0 error(s), 0 warning(s), 0 info(s) ---
```
Exit code: 0

- [ ] **Step 3: Test CLI against bad fixture**

Run: `python -m forgeds.core.validate_ds tests/fixtures/validate_ds_bad.ds`

Expected: Multiple diagnostics with DS101, DS105, DS106, DS201, DS202, DS203, DS204, DS301, DS303, DS304 rules printed, followed by summary. Exit code: 2.

- [ ] **Step 4: Test CLI against real Ten Chargeback .ds**

Run: `python -m forgeds.core.validate_ds "c:/Users/User/OneDrive/Documents/GitHub/Ten_Chargeback/ten_chargeback_management.ds"`

This is the real-world acceptance test. Fix any false positives or missed errors.

- [ ] **Step 5: Test --errors-only and --summary flags**

Run: `python -m forgeds.core.validate_ds tests/fixtures/validate_ds_bad.ds --errors-only`
Expected: Only ERROR-severity lines shown.

Run: `python -m forgeds.core.validate_ds tests/fixtures/validate_ds_bad.ds --summary`
Expected: Only summary line, no individual diagnostics.

- [ ] **Step 6: Reinstall and verify CLI command works**

Run: `pip install -e .`
Run: `forgeds-validate-ds tests/fixtures/validate_ds_good.ds`
Expected: Clean validation, exit 0.

- [ ] **Step 7: Commit**

```bash
git add src/forgeds/core/validate_ds.py
git commit -m "feat: implement forgeds-validate-ds CLI with full validation pipeline"
```

---

### Task 9: Test Against Real .ds Files and Fix Edge Cases

**Files:**
- Modify: `src/forgeds/core/validate_ds.py` (if fixes needed)

- [ ] **Step 1: Validate the base Zoho Creator export (should pass clean)**

Run: `forgeds-validate-ds "c:/Users/User/Downloads/Chargeback_Management_System.ds"`

Expected: 0 errors, 0 warnings (the base file imports successfully into Zoho Creator).

If false positives appear, fix the validator — the base .ds is the ground truth for valid structure.

- [ ] **Step 2: Validate the merged Ten Chargeback .ds**

Run: `forgeds-validate-ds "c:/Users/User/OneDrive/Documents/GitHub/Ten_Chargeback/ten_chargeback_management.ds"`

Check that any diagnostics are real issues (not false positives). Fix the validator or the .ds as appropriate.

- [ ] **Step 3: Validate a build_ds generated .ds**

Run from the Ten Chargeback project:
```bash
forgeds-build-ds -o /tmp/test_build.ds
forgeds-validate-ds /tmp/test_build.ds
```

Expected: Clean or minimal warnings (build_ds output should be structurally valid).

- [ ] **Step 4: Commit any fixes**

```bash
git add src/forgeds/core/validate_ds.py
git commit -m "fix: handle edge cases found in real .ds validation"
```

---

### Task 10: Update ForgeDS Documentation

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add forgeds-validate-ds to README CLI table**

Add entry in the CLI commands section of README.md:

```markdown
| `forgeds-validate-ds` | Validate .ds files for structural errors, reference integrity, and Deluge field mismatches |
```

- [ ] **Step 2: Verify CLAUDE.md gotchas section is up to date**

The gotchas section was already added. Verify it still matches the implemented rules.

- [ ] **Step 3: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: add forgeds-validate-ds to CLI documentation"
```
