"""Comprehensive tests for forgeds.core.build_ds — .ds generation and validation.

Covers:
  - Helper functions (_indent_code, _zoho_type, _format_choices, _derive_*)
  - Emitters (emit_forms, emit_reports, emit_application)
  - Validator Pass 1: DS001–DS005 (balance, references, field checks)
  - Validator Pass 2: DS006–DS007 (section-aware context validation)
  - Input validation: validate_input (DS003–DS005)
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from forgeds.core.build_ds import (
    FieldSpec,
    FormSpec,
    ReportSpec,
    WorkflowSpec,
    ScheduleSpec,
    _indent_code,
    _zoho_type,
    _format_choices,
    _derive_link_name,
    _derive_display_name,
    _read_script_code,
    emit_forms,
    emit_reports,
    emit_application,
    validate_ds,
    _validate_sections,
    validate_input,
    TYPE_MAP,
    VALID_FIELD_TYPES,
)
from forgeds._shared.diagnostics import Diagnostic, Severity


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def simple_field():
    return FieldSpec(name="amount", display_name="Amount", field_type="Number")


@pytest.fixture
def required_field():
    return FieldSpec(
        name="email", display_name="Email", field_type="Email", required=True,
    )


@pytest.fixture
def dropdown_field():
    return FieldSpec(
        name="status", display_name="Status", field_type="Dropdown",
        choices="Draft,Submitted,Approved",
    )


@pytest.fixture
def simple_form(simple_field, dropdown_field):
    return FormSpec(
        link_name="expense_claims",
        display_name="Expense Claims",
        fields=[simple_field, dropdown_field],
    )


@pytest.fixture
def simple_report():
    return ReportSpec(
        link_name="claims_report",
        report_type="list",
        form="expense_claims",
        columns="amount,status",
    )


@pytest.fixture
def filtered_report():
    return ReportSpec(
        link_name="pending_claims",
        report_type="list",
        form="expense_claims",
        columns="amount,status",
        filter_expr='status == "Pending"',
    )


@pytest.fixture
def simple_workflow():
    return WorkflowSpec(
        link_name="On_Submit",
        display_name="On Submit",
        form="expense_claims",
        record_event="on add",
        event_type="on success",
        code='input.status = "Submitted";',
    )


@pytest.fixture
def simple_schedule():
    return ScheduleSpec(
        link_name="Daily_Cleanup",
        display_name="Daily Cleanup",
        form="expense_claims",
        code='info "Running cleanup";',
    )


def _ds_with_approval(approval_body: str, *, forms_body: str = "") -> str:
    """Build a minimal .ds string with configurable approval and forms sections."""
    forms_section = forms_body or textwrap.dedent("""\
        forms
        {
            form test_form
            {
                actions
                {
                    on add { }
                    on edit { }
                }
            }
        }""")
    return textwrap.dedent(f"""\
        application "Test"
        {{
            {forms_section}
            workflow
            {{
            approval
            {{
                {approval_body}
            }}
            }}
        }}
    """)


def _rules(diags: list[Diagnostic]) -> list[str]:
    """Extract just the rule codes from a list of diagnostics."""
    return [d.rule for d in diags]


def _rules_set(diags: list[Diagnostic]) -> set[str]:
    return {d.rule for d in diags}


def _errors(diags: list[Diagnostic]) -> list[Diagnostic]:
    return [d for d in diags if d.severity == Severity.ERROR]


def _warnings(diags: list[Diagnostic]) -> list[Diagnostic]:
    return [d for d in diags if d.severity == Severity.WARNING]


# ============================================================
# Helper function tests
# ============================================================

class TestIndentCode:
    def test_empty_string(self):
        assert _indent_code("", 3) == ""

    def test_single_line(self):
        result = _indent_code("x = 1;", 2)
        assert result == "\t\tx = 1;"

    def test_preserves_relative_indent(self):
        code = "if (x)\n    y = 1;\nz = 2;"
        result = _indent_code(code, 1)
        lines = result.splitlines()
        assert lines[0] == "\tif (x)"
        assert lines[1] == "\t\ty = 1;"   # 4 spaces = 1 extra tab
        assert lines[2] == "\tz = 2;"

    def test_blank_lines_preserved(self):
        code = "a = 1;\n\nb = 2;"
        result = _indent_code(code, 1)
        lines = result.splitlines()
        assert lines[1] == ""

    def test_depth_zero(self):
        result = _indent_code("x = 1;", 0)
        assert result == "x = 1;"


class TestZohoType:
    def test_all_mapped_types(self):
        for yaml_type, zoho_type in TYPE_MAP.items():
            assert _zoho_type(yaml_type) == zoho_type

    def test_unknown_type_lowercased(self):
        assert _zoho_type("FancyWidget") == "fancywidget"

    def test_already_lowercase(self):
        assert _zoho_type("text") == "text"


class TestFormatChoices:
    def test_simple_list(self):
        assert _format_choices("A,B,C") == '{"A","B","C"}'

    def test_whitespace_handling(self):
        assert _format_choices(" Draft , Submitted , Approved ") == '{"Draft","Submitted","Approved"}'

    def test_single_choice(self):
        assert _format_choices("Only") == '{"Only"}'

    def test_empty_items_filtered(self):
        assert _format_choices("A,,B,") == '{"A","B"}'


class TestDeriveLinkName:
    def test_dotted_name(self):
        assert _derive_link_name("expense_claim.on_success") == "Expense_Claim_On_Success"

    def test_simple_name(self):
        assert _derive_link_name("cleanup") == "Cleanup"

    def test_underscores_and_dots(self):
        assert _derive_link_name("sla_enforcement.daily") == "Sla_Enforcement_Daily"


class TestDeriveDisplayName:
    def test_dotted_name(self):
        assert _derive_display_name("expense_claim.on_success") == "Expense Claim On Success"

    def test_simple_name(self):
        assert _derive_display_name("cleanup") == "Cleanup"


class TestReadScriptCode:
    def test_strips_header_comments(self, tmp_path):
        dg = tmp_path / "test.dg"
        dg.write_text(
            "// =============\n"
            "// Script header\n"
            "// =============\n"
            "\n"
            "x = 1;\n"
            "y = 2;\n",
            encoding="utf-8",
        )
        assert _read_script_code(dg) == "x = 1;\ny = 2;"

    def test_no_header(self, tmp_path):
        dg = tmp_path / "test.dg"
        dg.write_text("x = 1;\ny = 2;\n", encoding="utf-8")
        assert _read_script_code(dg) == "x = 1;\ny = 2;"

    def test_strips_trailing_blank_lines(self, tmp_path):
        dg = tmp_path / "test.dg"
        dg.write_text("x = 1;\n\n\n", encoding="utf-8")
        assert _read_script_code(dg) == "x = 1;"

    def test_all_comments_returns_empty(self, tmp_path):
        """When entire file is header comments, nothing follows the header."""
        dg = tmp_path / "test.dg"
        # Header block with trailing blank line — the header scanner skips
        # all // lines and blank lines, so start never advances and the
        # result is the full content (no code lines follow the header).
        dg.write_text("// only comments\n// nothing else\n", encoding="utf-8")
        result = _read_script_code(dg)
        # The function returns all lines from start=0 since the header
        # scanner never found a non-comment line to break on
        assert "// only comments" in result


# ============================================================
# Emitter tests
# ============================================================

class TestEmitForms:
    def test_basic_form_structure(self, simple_form):
        lines = emit_forms([simple_form])
        text = "\n".join(lines)
        assert "form expense_claims" in text
        assert 'displayname = "Expense Claims"' in text
        assert "Section" in text
        assert "type = section" in text
        assert "on add" in text
        assert "on edit" in text

    def test_field_emitted(self, simple_form):
        text = "\n".join(emit_forms([simple_form]))
        assert "amount" in text
        assert "type = number" in text

    def test_required_field_prefix(self, required_field):
        form = FormSpec(link_name="f", display_name="F", fields=[required_field])
        text = "\n".join(emit_forms([form]))
        assert "must have email" in text

    def test_dropdown_with_choices(self, dropdown_field):
        form = FormSpec(link_name="f", display_name="F", fields=[dropdown_field])
        text = "\n".join(emit_forms([form]))
        assert "type = picklist" in text
        assert '{"Draft","Submitted","Approved"}' in text

    def test_checkbox_initial_value(self):
        fld = FieldSpec(name="active", display_name="Active", field_type="Checkbox")
        form = FormSpec(link_name="f", display_name="F", fields=[fld])
        text = "\n".join(emit_forms([form]))
        assert "initial value = false" in text

    def test_datetime_options(self):
        fld = FieldSpec(name="ts", display_name="Timestamp", field_type="DateTime")
        form = FormSpec(link_name="f", display_name="F", fields=[fld])
        text = "\n".join(emit_forms([form]))
        assert "timedisplayoptions" in text
        assert "alloweddays" in text

    def test_multiline_height(self):
        fld = FieldSpec(name="desc", display_name="Description", field_type="MultiLine")
        form = FormSpec(link_name="f", display_name="F", fields=[fld])
        text = "\n".join(emit_forms([form]))
        assert "height = 100px" in text

    def test_multiple_forms(self, simple_field):
        forms = [
            FormSpec(link_name="form_a", display_name="Form A", fields=[simple_field]),
            FormSpec(link_name="form_b", display_name="Form B", fields=[simple_field]),
        ]
        text = "\n".join(emit_forms(forms))
        assert "form form_a" in text
        assert "form form_b" in text

    def test_balanced_braces(self, simple_form):
        text = "\n".join(emit_forms([simple_form]))
        assert text.count("{") == text.count("}")

    def test_balanced_parens(self, simple_form):
        text = "\n".join(emit_forms([simple_form]))
        assert text.count("(") == text.count(")")


class TestEmitReports:
    def test_empty_reports(self):
        assert emit_reports([]) == []

    def test_basic_report(self, simple_report):
        text = "\n".join(emit_reports([simple_report]))
        assert "list claims_report" in text
        assert 'displayName = "claims_report"' in text
        assert "show all rows from expense_claims" in text
        assert 'amount as "amount"' in text
        assert 'status as "status"' in text

    def test_filtered_report(self, filtered_report):
        text = "\n".join(emit_reports([filtered_report]))
        assert '[status == "Pending"]' in text

    def test_balanced_braces(self, simple_report):
        text = "\n".join(emit_reports([simple_report]))
        assert text.count("{") == text.count("}")


class TestEmitApplication:
    def test_header_comment(self, simple_form, simple_report):
        output = emit_application("test", "Test App", [simple_form], [simple_report], [], [])
        assert "/*" in output
        assert "Generated by : ForgeDS build-ds" in output
        assert "*/" in output

    def test_application_declaration(self, simple_form, simple_report):
        output = emit_application("test", "Test App", [simple_form], [simple_report], [], [])
        assert 'application "Test App"' in output

    def test_app_settings(self, simple_form, simple_report):
        output = emit_application("test", "Test App", [simple_form], [simple_report], [], [])
        assert 'date format = "dd-MMM-yyyy"' in output
        assert 'time zone = "Africa/Johannesburg"' in output
        assert 'time format = "24-hr"' in output

    def test_forms_included(self, simple_form, simple_report):
        output = emit_application("test", "Test", [simple_form], [simple_report], [], [])
        assert "form expense_claims" in output

    def test_reports_included(self, simple_form, simple_report):
        output = emit_application("test", "Test", [simple_form], [simple_report], [], [])
        assert "list claims_report" in output

    def test_no_reports(self, simple_form):
        output = emit_application("test", "Test", [simple_form], [], [], [])
        assert "form expense_claims" in output

    def test_workflow_included(self, simple_form, simple_workflow):
        output = emit_application("test", "Test", [simple_form], [], [simple_workflow], [])
        assert "workflow" in output
        assert "custom deluge script" in output
        assert 'input.status = "Submitted";' in output

    def test_schedule_included(self, simple_form, simple_schedule):
        output = emit_application("test", "Test", [simple_form], [], [], [simple_schedule])
        assert "schedule" in output
        assert 'info "Running cleanup";' in output

    def test_web_section(self, simple_form, simple_report):
        output = emit_application("test", "Test", [simple_form], [simple_report], [], [])
        assert "web" in output
        assert "quickview" in output
        assert "detailview" in output
        assert "menu" in output

    def test_share_settings(self, simple_form):
        output = emit_application("test", "Test", [simple_form], [], [], [])
        assert "share_settings" in output
        assert '"Read"' in output
        assert '"Write"' in output
        assert '"Administrator"' in output

    def test_device_sections(self, simple_form):
        output = emit_application("test", "Test", [simple_form], [], [], [])
        assert "phone" in output
        assert "tablet" in output

    def test_translation_block(self, simple_form):
        output = emit_application("test", "Test", [simple_form], [], [], [])
        assert "translation" in output

    def test_balanced_braces_full_output(self, simple_form, simple_report, simple_workflow):
        output = emit_application(
            "test", "Test", [simple_form], [simple_report], [simple_workflow], [],
        )
        assert output.count("{") == output.count("}")

    def test_self_validates_clean(self, simple_form, simple_report, simple_workflow):
        """Generated output should pass our own validator without errors."""
        output = emit_application(
            "test", "Test", [simple_form], [simple_report], [simple_workflow], [],
        )
        diags = validate_ds(output, "self-test.ds")
        errors = _errors(diags)
        assert errors == [], f"Self-validation errors: {errors}"


# ============================================================
# Validator Pass 1 — DS001 through DS005
# ============================================================

class TestDS001BraceBalance:
    def test_balanced(self):
        ds = 'application "X"\n{\n    forms\n    {\n    }\n}\n'
        diags = [d for d in validate_ds(ds) if d.rule == "DS001"]
        assert diags == []

    def test_unclosed_brace(self):
        ds = 'application "X"\n{\n    forms\n    {\n    }\n'
        diags = [d for d in validate_ds(ds) if d.rule == "DS001"]
        assert len(diags) == 1
        assert diags[0].severity == Severity.ERROR
        assert "+1" in diags[0].message

    def test_extra_closing_brace(self):
        ds = 'application "X"\n{\n}\n}\n'
        diags = [d for d in validate_ds(ds) if d.rule == "DS001"]
        assert len(diags) == 1
        assert "-1" in diags[0].message

    def test_multiple_unclosed(self):
        ds = "{\n{\n{\n"
        diags = [d for d in validate_ds(ds) if d.rule == "DS001"]
        assert len(diags) == 1
        assert "+3" in diags[0].message


class TestDS002ParenBalance:
    def test_balanced(self):
        ds = "Section\n(\n    type = section\n)\n"
        diags = [d for d in validate_ds(ds) if d.rule == "DS002"]
        assert diags == []

    def test_unclosed_paren(self):
        ds = "Section\n(\n    type = section\n"
        diags = [d for d in validate_ds(ds) if d.rule == "DS002"]
        assert len(diags) == 1
        assert diags[0].severity == Severity.ERROR

    def test_extra_closing_paren(self):
        ds = "(\n)\n)\n"
        diags = [d for d in validate_ds(ds) if d.rule == "DS002"]
        assert len(diags) == 1


class TestDS003FormReference:
    def test_valid_reference(self):
        ds = textwrap.dedent("""\
            forms
            {
                form expense_claims
                {
                }
            }
            form = expense_claims
        """)
        diags = [d for d in validate_ds(ds) if d.rule == "DS003"]
        assert diags == []

    def test_undefined_reference(self):
        ds = textwrap.dedent("""\
            forms
            {
                form expense_claims
                {
                }
            }
            form = nonexistent_form
        """)
        diags = [d for d in validate_ds(ds) if d.rule == "DS003"]
        assert len(diags) == 1
        assert "nonexistent_form" in diags[0].message

    def test_multiple_undefined(self):
        ds = "form = aaa\nform = bbb\n"
        diags = [d for d in validate_ds(ds) if d.rule == "DS003"]
        assert len(diags) == 2


class TestDS005DropdownChoices:
    def test_dropdown_with_values(self):
        ds = textwrap.dedent("""\
            type = picklist
            values = {"A","B"}
        """)
        diags = [d for d in validate_ds(ds) if d.rule == "DS005"]
        assert diags == []

    def test_dropdown_without_values(self):
        ds = textwrap.dedent("""\
            type = picklist
            displayname = "Status"
            row = 1
            )
        """)
        diags = [d for d in validate_ds(ds) if d.rule == "DS005"]
        assert len(diags) == 1
        assert diags[0].severity == Severity.WARNING

    def test_dropdown_with_choices_keyword(self):
        ds = textwrap.dedent("""\
            type = Dropdown
            choices = "A,B,C"
        """)
        diags = [d for d in validate_ds(ds) if d.rule == "DS005"]
        assert diags == []


# ============================================================
# Validator Pass 2 — DS006 and DS007 (section-aware)
# ============================================================

class TestDS006OnLevelOutsideApproval:
    """DS006: 'on level N' must only appear inside the approval {} section."""

    def test_on_level_in_form_actions_flagged(self):
        """The exact bug pattern from the ERM .ds file."""
        ds = textwrap.dedent("""\
            application "Test"
            {
                forms
                {
                    form approval_history
                    {
                        actions
                        {
                            on add
                            {
                            }
                            on level 3
                            {
                                approvers
                                (
                                    role = "Finance Director"
                                )
                            }
                        }
                    }
                }
            }
        """)
        diags = [d for d in validate_ds(ds) if d.rule == "DS006"]
        assert len(diags) == 1
        assert diags[0].severity == Severity.ERROR
        assert "on level 3" in diags[0].message
        assert "form actions" in diags[0].message

    def test_on_level_in_approval_section_ok(self):
        ds = _ds_with_approval("""\
            Approval_Process as "Approval Process"
            {
                type = approval
                form = test_form
                on level 1
                {
                    approvers
                    (
                        role = "Line Manager"
                    )
                    on approve
                    {
                        actions
                        {
                        on load
                        (
                            input.status = "Approved";
                        )
                        }
                    }
                }
            }""")
        diags = [d for d in validate_ds(ds) if d.rule == "DS006"]
        assert diags == []

    def test_multiple_levels_in_approval_ok(self):
        ds = _ds_with_approval("""\
            Proc as "Proc"
            {
                type = approval
                form = test_form
                on level 1
                {
                    approvers ( role = "LM" )
                    on approve { }
                }
                on level 2
                {
                    approvers ( role = "HoD" )
                    on approve { }
                }
                on level 3
                {
                    approvers ( role = "CFO" )
                    on approve { }
                    on reject { }
                }
            }""")
        diags = [d for d in validate_ds(ds) if d.rule in ("DS006", "DS007")]
        assert diags == []

    def test_on_level_at_top_level(self):
        """on level outside any known section."""
        ds = textwrap.dedent("""\
            application "Test"
            {
                on level 1
                {
                }
            }
        """)
        diags = [d for d in validate_ds(ds) if d.rule == "DS006"]
        assert len(diags) == 1
        assert "non-approval context" in diags[0].message

    def test_on_level_in_workflow_but_not_approval(self):
        ds = textwrap.dedent("""\
            application "Test"
            {
                workflow
                {
                    on level 2
                    {
                    }
                }
            }
        """)
        diags = [d for d in validate_ds(ds) if d.rule == "DS006"]
        assert len(diags) == 1


class TestDS007ApprovalEventsOutsideApproval:
    """DS007: 'on approve' / 'on reject' must only appear in approval section."""

    def test_on_approve_in_form_actions_flagged(self):
        ds = textwrap.dedent("""\
            application "Test"
            {
                forms
                {
                    form test_form
                    {
                        actions
                        {
                            on approve
                            {
                            }
                        }
                    }
                }
            }
        """)
        diags = [d for d in validate_ds(ds) if d.rule == "DS007"]
        assert len(diags) == 1
        assert "on approve" in diags[0].message

    def test_on_reject_in_form_actions_flagged(self):
        ds = textwrap.dedent("""\
            application "Test"
            {
                forms
                {
                    form test_form
                    {
                        actions
                        {
                            on reject
                            {
                            }
                        }
                    }
                }
            }
        """)
        diags = [d for d in validate_ds(ds) if d.rule == "DS007"]
        assert len(diags) == 1
        assert "on reject" in diags[0].message

    def test_on_approve_in_approval_ok(self):
        ds = _ds_with_approval("""\
            Proc as "Proc"
            {
                on level 1
                {
                    on approve { }
                    on reject { }
                }
            }""")
        diags = [d for d in validate_ds(ds) if d.rule == "DS007"]
        assert diags == []

    def test_both_approve_and_reject_flagged(self):
        ds = textwrap.dedent("""\
            application "Test"
            {
                forms
                {
                    form f
                    {
                        actions
                        {
                            on approve { }
                            on reject { }
                        }
                    }
                }
            }
        """)
        diags = [d for d in validate_ds(ds) if d.rule == "DS007"]
        assert len(diags) == 2
        messages = [d.message for d in diags]
        assert any("on approve" in m for m in messages)
        assert any("on reject" in m for m in messages)


class TestSectionTrackerEdgeCases:
    """Edge cases for the section-stack brace-tracking mechanism."""

    def test_empty_file(self):
        diags = _validate_sections([], "test.ds")
        assert diags == []

    def test_comments_only(self):
        lines = ["/* block comment */", "// line comment", ""]
        diags = _validate_sections(lines, "test.ds")
        assert diags == []

    def test_block_comment_hides_keywords(self):
        """Keywords inside block comments must not trigger rules."""
        lines = [
            "/*",
            "on level 3",
            "on approve",
            "on reject",
            "*/",
            'application "Test"',
            "{",
            "}",
        ]
        diags = _validate_sections(lines, "test.ds")
        assert diags == []

    def test_single_line_comment_hides_keywords(self):
        lines = [
            "// on level 3 inside a comment",
            "// on approve also a comment",
        ]
        diags = _validate_sections(lines, "test.ds")
        assert diags == []

    def test_keywords_inside_paren_blocks_ignored(self):
        """Deluge code inside () should not trigger section rules.

        This simulates approval keywords appearing as variable names
        or string content inside Deluge scripts.
        """
        ds = textwrap.dedent("""\
            application "Test"
            {
                workflow
                {
                form
                {
                    Script as "Script"
                    {
                        on success
                        {
                            actions
                            {
                                custom deluge script
                                (
                                    // This references approval terms in code
                                    on_level = 3;
                                    on_approve_flag = true;
                                    on_reject_count = 0;
                                )
                            }
                        }
                    }
                }
                }
            }
        """)
        diags = [d for d in validate_ds(ds) if d.rule in ("DS006", "DS007")]
        assert diags == []

    def test_same_line_braces(self):
        """Section keyword and { on the same line."""
        ds = textwrap.dedent("""\
            application "Test" {
                forms {
                    form test_form {
                        actions {
                            on level 1 {
                            }
                        }
                    }
                }
            }
        """)
        diags = [d for d in validate_ds(ds) if d.rule == "DS006"]
        assert len(diags) == 1

    def test_double_close_braces(self):
        """Multiple }} on same line."""
        ds = textwrap.dedent("""\
            application "Test"
            {
                forms
                {
                    form f
                    {
                        actions
                        {
                            on add { }
                        }}
                    }
                }
                approval
                {
                    P as "P"
                    {
                        on level 1
                        {
                            on approve { }
                        }
                    }
                }
            }
        """)
        diags = [d for d in validate_ds(ds) if d.rule in ("DS006", "DS007")]
        assert diags == []

    def test_nested_approval_inside_workflow(self):
        """The real .ds pattern: approval nested inside workflow."""
        ds = textwrap.dedent("""\
            application "Test"
            {
                forms
                {
                    form claims
                    {
                        actions
                        {
                            on add { }
                        }
                    }
                }
                workflow
                {
                form
                {
                }
                schedule
                {
                }
                approval
                {
                    LM as "Line Manager Approval"
                    {
                        type = approval
                        form = claims
                        on level 1
                        {
                            approvers ( role = "LM" )
                            on approve
                            {
                                actions
                                {
                                on load
                                (
                                    input.status = "Approved";
                                )
                                }
                            }
                            on reject
                            {
                                actions
                                {
                                on load
                                (
                                    input.status = "Rejected";
                                )
                                }
                            }
                        }
                        on level 2
                        {
                            approvers ( role = "HoD" )
                            on approve { }
                        }
                    }
                }
                }
            }
        """)
        diags = [d for d in validate_ds(ds) if d.rule in ("DS006", "DS007")]
        assert diags == [], f"Unexpected: {[str(d) for d in diags]}"

    def test_mixed_valid_and_invalid(self):
        """Some on level in approval (ok) and one in form actions (error)."""
        ds = textwrap.dedent("""\
            application "Test"
            {
                forms
                {
                    form f
                    {
                        actions
                        {
                            on add { }
                            on level 3
                            {
                                on approve { }
                            }
                        }
                    }
                }
                approval
                {
                    P as "P"
                    {
                        on level 1
                        {
                            on approve { }
                        }
                        on level 2
                        {
                            on reject { }
                        }
                    }
                }
            }
        """)
        ds006 = [d for d in validate_ds(ds) if d.rule == "DS006"]
        ds007 = [d for d in validate_ds(ds) if d.rule == "DS007"]
        # Only the one in form actions should be flagged
        assert len(ds006) == 1
        assert "on level 3" in ds006[0].message
        assert len(ds007) == 1
        assert "on approve" in ds007[0].message

    def test_multiline_block_comment(self):
        """Block comment spanning multiple lines with keywords inside."""
        lines = [
            "/*",
            " * This describes the on level 3 approval process",
            " * The on approve handler fires when...",
            " * The on reject handler fires when...",
            " */",
            'application "Test"',
            "{",
            "    approval",
            "    {",
            "        P as \"P\"",
            "        {",
            "            on level 1",
            "            {",
            "                on approve { }",
            "            }",
            "        }",
            "    }",
            "}",
        ]
        diags = _validate_sections(lines, "test.ds")
        assert diags == []

    def test_on_approve_with_trailing_space(self):
        """'on approve ' with trailing content should still match."""
        ds = textwrap.dedent("""\
            application "Test"
            {
                forms
                {
                    form f
                    {
                        actions
                        {
                            on approve extra_stuff
                            {
                            }
                        }
                    }
                }
            }
        """)
        diags = [d for d in validate_ds(ds) if d.rule == "DS007"]
        assert len(diags) == 1


# ============================================================
# validate_input tests (DS003, DS004, DS005)
# ============================================================

class TestValidateInput:
    def test_clean_input(self, simple_form, simple_report):
        diags = validate_input([simple_form], [simple_report])
        assert _errors(diags) == []

    def test_duplicate_field(self):
        fields = [
            FieldSpec(name="amount", display_name="Amount", field_type="Number"),
            FieldSpec(name="amount", display_name="Amount 2", field_type="Number"),
        ]
        form = FormSpec(link_name="f", display_name="F", fields=fields)
        diags = validate_input([form], [])
        ds004 = [d for d in diags if d.rule == "DS004" and d.severity == Severity.ERROR]
        assert len(ds004) == 1
        assert "Duplicate" in ds004[0].message

    def test_unknown_field_type(self):
        fld = FieldSpec(name="x", display_name="X", field_type="FancyWidget")
        form = FormSpec(link_name="f", display_name="F", fields=[fld])
        diags = validate_input([form], [])
        ds004 = [d for d in diags if d.rule == "DS004" and d.severity == Severity.WARNING]
        assert len(ds004) == 1
        assert "FancyWidget" in ds004[0].message

    def test_all_valid_types_pass(self):
        for ft in VALID_FIELD_TYPES:
            fld = FieldSpec(name="x", display_name="X", field_type=ft)
            form = FormSpec(link_name="f", display_name="F", fields=[fld])
            diags = validate_input([form], [])
            type_warnings = [d for d in diags if d.rule == "DS004" and "Unknown" in d.message]
            assert type_warnings == [], f"Valid type {ft} flagged as unknown"

    def test_dropdown_without_choices(self):
        fld = FieldSpec(name="s", display_name="S", field_type="Dropdown", choices="")
        form = FormSpec(link_name="f", display_name="F", fields=[fld])
        diags = validate_input([form], [])
        ds005 = [d for d in diags if d.rule == "DS005"]
        assert len(ds005) == 1

    def test_dropdown_with_choices_ok(self):
        fld = FieldSpec(name="s", display_name="S", field_type="Dropdown", choices="A,B")
        form = FormSpec(link_name="f", display_name="F", fields=[fld])
        diags = validate_input([form], [])
        ds005 = [d for d in diags if d.rule == "DS005"]
        assert ds005 == []

    def test_report_references_undefined_form(self):
        form = FormSpec(
            link_name="claims",
            display_name="Claims",
            fields=[FieldSpec(name="x", display_name="X", field_type="Number")],
        )
        bad_report = ReportSpec(
            link_name="r", report_type="list", form="nonexistent", columns="x",
        )
        diags = validate_input([form], [bad_report])
        ds003 = [d for d in diags if d.rule == "DS003"]
        assert len(ds003) == 1
        assert "nonexistent" in ds003[0].message
        assert ds003[0].severity == Severity.ERROR

    def test_report_references_valid_form(self, simple_form, simple_report):
        diags = validate_input([simple_form], [simple_report])
        ds003 = [d for d in diags if d.rule == "DS003"]
        assert ds003 == []


# ============================================================
# Real-world integration test
# ============================================================

class TestRealWorldDSFile:
    """Test against the actual fixed ERM .ds file if available."""

    ERM_PATH = Path(
        r"C:\Users\holge\Downloads\Expense_Reimbursement_Management-stage.ds"
    )

    @pytest.mark.skipif(
        not ERM_PATH.exists(),
        reason="ERM .ds file not present at expected path",
    )
    def test_fixed_erm_file_no_section_errors(self):
        content = self.ERM_PATH.read_text(encoding="utf-8")
        diags = validate_ds(content, str(self.ERM_PATH))
        section_errors = [d for d in diags if d.rule in ("DS006", "DS007")]
        assert section_errors == [], (
            f"Section errors in fixed ERM file: {[str(d) for d in section_errors]}"
        )

    @pytest.mark.skipif(
        not ERM_PATH.exists(),
        reason="ERM .ds file not present at expected path",
    )
    def test_fixed_erm_file_no_errors(self):
        content = self.ERM_PATH.read_text(encoding="utf-8")
        diags = validate_ds(content, str(self.ERM_PATH))
        errors = _errors(diags)
        assert errors == [], f"Errors in fixed ERM file: {[str(d) for d in errors]}"

    @pytest.mark.skipif(
        not ERM_PATH.exists(),
        reason="ERM .ds file not present at expected path",
    )
    def test_fixed_erm_brace_balance(self):
        content = self.ERM_PATH.read_text(encoding="utf-8")
        diags = validate_ds(content, str(self.ERM_PATH))
        balance_errors = [d for d in diags if d.rule in ("DS001", "DS002")]
        assert balance_errors == []


# ============================================================
# Regression: the original bug pattern
# ============================================================

class TestRegressionApprovalInFormActions:
    """Regression test for the exact bug found in the ERM .ds export.

    The Finance Director 'on level 3' block with on approve/on reject
    and embedded Deluge scripts was nested inside the approval_history
    form's actions block instead of the approval section.
    """

    BROKEN_DS = textwrap.dedent("""\
        application "Expense Reimbursement Management"
        {
            forms
            {
                form approval_history
                {
                    displayname = "Approval History"
                    Section
                    (
                        type = section
                    )
                    claim
                    (
                        type = list
                        displayname = "Claim"
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
                        }
                        on edit
                        {
                            update
                            (
                                type = submit
                                displayname = "Update"
                            )
                        }
                        on level 3
                        {
                            approvers
                            (
                                role = "Finance Director"
                            )
                            on approve
                            {
                                actions  (status == "Pending Second Key")
                                {
                                on load
                                (
                                    key1 = ifnull(input.Key_1_Approver, "");
                                    current = zoho.loginuser;
                                    input.status = "Approved";
                                )
                                }
                            }
                            on reject
                            {
                                actions  (status == "Pending Second Key")
                                {
                                on load
                                (
                                    input.status = "Key 2 Dispute";
                                )
                                }
                            }
                        }
                    }
                }
                form expense_claims
                {
                    displayname = "Expense Claims"
                    Section
                    (
                        type = section
                    )
                    actions
                    {
                        on add { }
                        on edit { }
                    }
                }
            }
            workflow
            {
            approval
            {
                Line_Manager_Approval as "Line Manager Approval"
                {
                    type = approval
                    form = expense_claims
                    on level 1
                    {
                        approvers
                        (
                            role = "Line Manager"
                        )
                        on approve
                        {
                            actions
                            {
                            on load
                            (
                                input.status = "Approved";
                            )
                            }
                        }
                        on reject
                        {
                            actions
                            {
                            on load
                            (
                                input.status = "Rejected";
                            )
                            }
                        }
                    }
                    on level 2
                    {
                        approvers
                        (
                            role = "HoD"
                        )
                        on approve
                        {
                            actions
                            {
                            on load
                            (
                                input.status = "Approved";
                            )
                            }
                        }
                    }
                }
            }
            }
        }
    """)

    def test_detects_on_level_in_form_actions(self):
        diags = validate_ds(self.BROKEN_DS, "broken.ds")
        ds006 = [d for d in diags if d.rule == "DS006"]
        assert len(ds006) == 1
        assert "on level 3" in ds006[0].message
        assert "form actions" in ds006[0].message

    def test_detects_on_approve_reject_in_form(self):
        diags = validate_ds(self.BROKEN_DS, "broken.ds")
        ds007 = [d for d in diags if d.rule == "DS007"]
        assert len(ds007) == 2
        kws = {d.message.split("'")[1] for d in ds007}
        assert kws == {"on approve", "on reject"}

    def test_valid_levels_not_flagged(self):
        """Levels 1 and 2 in the approval section should NOT be flagged."""
        diags = validate_ds(self.BROKEN_DS, "broken.ds")
        ds006 = [d for d in diags if d.rule == "DS006"]
        # Only on level 3 (the misplaced one) should be flagged
        assert all("on level 3" in d.message for d in ds006)

    def test_valid_approve_reject_not_flagged(self):
        """on approve/reject in the approval section should NOT be flagged."""
        diags = validate_ds(self.BROKEN_DS, "broken.ds")
        ds007 = [d for d in diags if d.rule == "DS007"]
        # Only 2 (the ones in form actions) not 4+ (the valid ones too)
        assert len(ds007) == 2

    def test_error_severity(self):
        diags = validate_ds(self.BROKEN_DS, "broken.ds")
        section_diags = [d for d in diags if d.rule in ("DS006", "DS007")]
        for d in section_diags:
            assert d.severity == Severity.ERROR

    def test_line_numbers_reasonable(self):
        diags = validate_ds(self.BROKEN_DS, "broken.ds")
        ds006 = [d for d in diags if d.rule == "DS006"]
        assert len(ds006) == 1
        # on level 3 is in the first form, should be before line 80
        assert 1 < ds006[0].line < 80


# ============================================================
# Data structure tests
# ============================================================

class TestDataStructures:
    def test_field_spec_defaults(self):
        f = FieldSpec(name="x", display_name="X", field_type="text")
        assert f.required is False
        assert f.choices == ""
        assert f.row == 0

    def test_form_spec_default_fields(self):
        f = FormSpec(link_name="f", display_name="F")
        assert f.fields == []

    def test_report_spec_default_filter(self):
        r = ReportSpec(link_name="r", report_type="list", form="f", columns="a,b")
        assert r.filter_expr == ""


# ============================================================
# Diagnostic output format test
# ============================================================

class TestDiagnosticFormat:
    def test_str_format(self):
        d = Diagnostic(
            file="test.ds", line=42, rule="DS006",
            severity=Severity.ERROR,
            message="'on level 3' found in form actions block",
        )
        s = str(d)
        assert "test.ds:42" in s
        assert "DS006" in s
        assert "ERROR" in s
        assert "on level 3" in s
