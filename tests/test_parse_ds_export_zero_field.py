#!/usr/bin/env python3
"""
Test that DSParser emits zero-field FormDefs instead of skipping them.

Invariant 5 (math-verifier) and critic-claim #14 both require that the
validator sees every form declared in a .ds — including placeholder forms
that have no fields yet — to correctly emit DS021 (unknown form reference)
diagnostics without false negatives.
"""

import textwrap
from forgeds.core.parse_ds_export import DSParser


def test_zero_field_form_emitted():
    """
    Test that a form with no fields declared is still emitted with fields=[].

    Minimal .ds fragment with a form that has:
    - displayname set
    - Section header (skipped, not counted as a field)
    - actions block (skipped, not counted as a field)
    - NO field definitions

    Expected: FormDef is emitted with empty fields list, not skipped entirely.
    """
    ds_content = textwrap.dedent("""
        forms
        {
        		form foo
        		{
        			displayname = "Foo Form"
        			Section (
        				"My Section"
        			)
        			actions
        			(
        			)
        		}
        }
    """).lstrip()

    parser = DSParser(ds_content)
    parser.parse()

    # Verify form was parsed and added
    assert len(parser.forms) == 1, f"Expected 1 form, got {len(parser.forms)}"

    form = parser.forms[0]
    assert form.name == "foo", f"Expected form name 'foo', got '{form.name}'"
    assert form.display_name == "Foo Form", f"Expected display name 'Foo Form', got '{form.display_name}'"
    assert form.fields == [], f"Expected empty fields list, got {form.fields}"


def test_form_with_fields_still_works():
    """
    Regression test: verify that forms with fields are still parsed correctly.
    """
    ds_content = textwrap.dedent("""
        forms
        {
        		form bar
        		{
        			displayname = "Bar Form"
        			name_field
        			(
        				type = Text
        				displayname = "Full Name"
        			)
        			email_field
        			(
        				type = Text
        				displayname = "Email Address"
        			)
        		}
        }
    """).lstrip()

    parser = DSParser(ds_content)
    parser.parse()

    assert len(parser.forms) == 1
    form = parser.forms[0]
    assert form.name == "bar"
    assert form.display_name == "Bar Form"
    assert len(form.fields) == 2

    assert form.fields[0].link_name == "name_field"
    assert form.fields[0].display_name == "Full Name"
    assert form.fields[0].field_type == "Text"

    assert form.fields[1].link_name == "email_field"
    assert form.fields[1].display_name == "Email Address"
    assert form.fields[1].field_type == "Text"


def test_mixed_zero_and_nonzero_field_forms():
    """
    Test parsing multiple forms where some have fields and some don't.
    Both should be emitted.
    """
    ds_content = textwrap.dedent("""
        forms
        {
        		form empty_form
        		{
        			displayname = "Empty Form"
        			Section (
        				"Placeholder"
        			)
        		}
        		form filled_form
        		{
        			displayname = "Filled Form"
        			my_field
        			(
        				type = Number
        				displayname = "My Number"
        			)
        		}
        		form another_empty
        		{
        			displayname = "Another Empty"
        			actions
        			(
        			)
        		}
        }
    """).lstrip()

    parser = DSParser(ds_content)
    parser.parse()

    # All 3 forms should be present
    assert len(parser.forms) == 3, f"Expected 3 forms, got {len(parser.forms)}"

    names = [f.name for f in parser.forms]
    assert "empty_form" in names
    assert "filled_form" in names
    assert "another_empty" in names

    # Verify field counts
    empty_form = next(f for f in parser.forms if f.name == "empty_form")
    assert empty_form.fields == []

    filled_form = next(f for f in parser.forms if f.name == "filled_form")
    assert len(filled_form.fields) == 1

    another_empty = next(f for f in parser.forms if f.name == "another_empty")
    assert another_empty.fields == []


if __name__ == "__main__":
    test_zero_field_form_emitted()
    test_form_with_fields_still_works()
    test_mixed_zero_and_nonzero_field_forms()
    print("All tests passed!")
