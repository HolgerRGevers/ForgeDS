"""Project the knowledge base onto an ingested app to reveal holograms.

A "hologram" in HRC terms is the gap between what an app IS and what
the knowledge base says it SHOULD be.  The residual R(app) > 0 means
the app is incomplete; each violation tells you exactly what is missing.

Projections are run against the Reality Database (RB) via the Librarian's
read-only connection.  The gaps discovered here become HologramTokens
in the Holographic Database (HB), created by the Librarian in api.py.

Projections performed:
    π_structural_completeness — App must have blueprints, pages, dashboards
    π_form_validation  — Every form with user input needs on_validate scripts
    π_transition_logic — Every Blueprint transition needs before/after logic
    π_audit_trail      — State changes should create audit history records
    π_notification     — State changes should trigger email/push notifications
    π_error_handling   — Scripts should guard nulls, validate inputs
    π_compliance       — POPIA consent, SARS substantiation, King IV patterns

Each gap is a violation with a severity weight.  The total residual
R(app) = Σ severity tells you how far the app is from being grounded
to the knowledge base.

Usage:
    from forgeds.knowledge.app_projection import project_kb_onto_app
    report = project_kb_onto_app("app:Expense_Claim_Approval", librarian)

CLI:
    forgeds-kb-project app:Expense_Claim_Approval
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from forgeds.knowledge.librarian_io import LibrarianHandle


# ---------------------------------------------------------------------------
# Gap types
# ---------------------------------------------------------------------------

@dataclass
class AppGap:
    """A single hologram — something the app is missing."""
    projection: str          # Which projection detected this
    severity: float          # 0.0-2.0 weight
    entity: str              # Form, transition, or script affected
    message: str             # Human-readable description
    kb_pattern: str = ""     # What the KB says should be here
    remediation: str = ""    # Suggested fix


@dataclass
class ProjectionReport:
    """Result of projecting the KB onto an app."""
    module: str
    app_name: str
    gaps: list[AppGap] = field(default_factory=list)
    residual: float = 0.0
    forms_analyzed: int = 0
    transitions_analyzed: int = 0
    scripts_analyzed: int = 0
    # Per-entity residuals
    entity_residuals: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Severity constants
# ---------------------------------------------------------------------------

CRITICAL = 2.0    # Missing fundamental logic (empty transition, no validation)
HIGH = 1.5        # Missing important pattern (audit trail, notifications)
MEDIUM = 1.0      # Missing good practice (error handling, null guards)
LOW = 0.5         # Missing nice-to-have (compliance annotations, comments)
INFO = 0.2        # Suggestion only


# ---------------------------------------------------------------------------
# π_form_validation — every form needs validation scripts
# ---------------------------------------------------------------------------

def _pi_form_validation(
    conn: sqlite3.Connection, module: str,
) -> list[AppGap]:
    """Check that every form with user-editable fields has on_validate logic."""
    gaps: list[AppGap] = []

    # Get all forms from the app overview token
    form_tokens = conn.execute(
        """SELECT content, page_url FROM tokens
           WHERE module = ? AND page_url LIKE '%/forms/%'""",
        (module,),
    ).fetchall()

    # Get all script tokens to check what validation exists
    script_tokens = conn.execute(
        """SELECT content FROM tokens
           WHERE module = ? AND page_url LIKE '%/scripts/%'""",
        (module,),
    ).fetchall()
    all_script_content = "\n".join(r[0] for r in script_tokens)

    for content, page_url in form_tokens:
        form_name = page_url.rsplit("/", 1)[-1]

        # Check for on_validate script
        has_validate = "on validate" in all_script_content.lower() and \
                       form_name in all_script_content
        has_cancel_submit = "cancel submit" in all_script_content.lower()

        if not has_validate:
            gaps.append(AppGap(
                projection="π_form_validation",
                severity=CRITICAL,
                entity=f"form:{form_name}",
                message=f"Form '{form_name}' has no on_validate script. "
                        f"User input is accepted without server-side validation.",
                kb_pattern="KB shows on_validate should check: required fields, "
                           "date ranges, duplicate detection, amount bounds, "
                           "document requirements.",
                remediation=f"Add an on_validate workflow to form '{form_name}' "
                            f"with input validation rules.",
            ))
        elif not has_cancel_submit:
            gaps.append(AppGap(
                projection="π_form_validation",
                severity=MEDIUM,
                entity=f"form:{form_name}",
                message=f"Form '{form_name}' has validation but no 'cancel submit' "
                        f"guard — invalid records can still be saved.",
                kb_pattern="KB pattern: if(condition) { alert \"...\"; cancel submit; }",
            ))

    return gaps


# ---------------------------------------------------------------------------
# π_transition_logic — Blueprint transitions need before/after scripts
# ---------------------------------------------------------------------------

def _pi_transition_logic(
    conn: sqlite3.Connection, module: str,
) -> list[AppGap]:
    """Check that Blueprint transitions have logic in before/after hooks."""
    gaps: list[AppGap] = []

    # Get blueprint tokens
    bp_tokens = conn.execute(
        """SELECT content, page_url FROM tokens
           WHERE module = ? AND page_url LIKE '%/blueprints/%'""",
        (module,),
    ).fetchall()

    # Get all scripts to check coverage
    script_tokens = conn.execute(
        """SELECT content FROM tokens
           WHERE module = ? AND content_type = 'CODE_EXAMPLE'""",
        (module,),
    ).fetchall()
    all_code = "\n".join(r[0] for r in script_tokens)

    for content, page_url in bp_tokens:
        bp_name = page_url.rsplit("/", 1)[-1]

        # Parse transitions from the token content
        transition_pattern = re.compile(
            r"\|\s*(.+?)\s*\(`(\w+)`\)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|"
        )
        for match in transition_pattern.finditer(content):
            display = match.group(1).strip()
            link_name = match.group(2).strip()
            from_stage = match.group(3).strip()
            to_stage = match.group(4).strip()

            # Check if this transition has any associated script
            has_script = link_name in all_code

            if not has_script:
                # Determine severity based on transition type
                is_approval = any(kw in display.lower() for kw in
                                  ["approve", "reject", "escalate"])
                is_payment = any(kw in display.lower() for kw in
                                 ["payment", "invoice", "process"])
                is_state_change = any(kw in display.lower() for kw in
                                      ["submit", "close", "cancel", "return"])

                if is_approval:
                    sev = CRITICAL
                    pattern = ("KB pattern: approval transitions should validate "
                               "authorization, check thresholds, create audit trail, "
                               "send notification, update status.")
                elif is_payment:
                    sev = CRITICAL
                    pattern = ("KB pattern: payment transitions should validate "
                               "amounts, check GL codes, create audit record, "
                               "send confirmation, handle failure.")
                elif is_state_change:
                    sev = HIGH
                    pattern = ("KB pattern: state transitions should update status, "
                               "log audit trail, notify stakeholders.")
                else:
                    sev = MEDIUM
                    pattern = ("KB pattern: transitions should validate preconditions "
                               "and log state changes.")

                gaps.append(AppGap(
                    projection="π_transition_logic",
                    severity=sev,
                    entity=f"transition:{bp_name}.{link_name}",
                    message=f"Transition '{display}' ({from_stage} → {to_stage}) "
                            f"has no before/after script. State change is unguarded.",
                    kb_pattern=pattern,
                    remediation=f"Add before/after logic for transition '{link_name}' "
                                f"on blueprint '{bp_name}'.",
                ))

    return gaps


# ---------------------------------------------------------------------------
# π_audit_trail — state changes should create audit records
# ---------------------------------------------------------------------------

def _pi_audit_trail(
    conn: sqlite3.Connection, module: str,
) -> list[AppGap]:
    """Check that scripts create audit trail records on state changes."""
    gaps: list[AppGap] = []

    scripts = conn.execute(
        """SELECT content, page_url, page_title FROM tokens
           WHERE module = ? AND content_type = 'CODE_EXAMPLE'""",
        (module,),
    ).fetchall()

    has_any_audit = False
    for content, page_url, title in scripts:
        code = content.lower()
        has_insert = "insert into" in code
        has_history = "approval_history" in code or "audit" in code or "history" in code
        if has_insert and has_history:
            has_any_audit = True

        # Check for status changes without audit logging
        has_status_change = "input.status" in code or ".status =" in code
        if has_status_change and not (has_insert and has_history):
            script_name = page_url.rsplit("/", 1)[-1]
            gaps.append(AppGap(
                projection="π_audit_trail",
                severity=HIGH,
                entity=f"script:{script_name}",
                message=f"Script '{title}' changes status but does not "
                        f"create an audit trail record.",
                kb_pattern="KB pattern: every status change should insert into "
                           "approval_history [claim, action, actor, timestamp, comments].",
                remediation="Add 'insert into approval_history [...]' after "
                            "every status assignment.",
            ))

    # If no scripts at all exist, the whole app lacks audit
    if not scripts and _has_blueprints(conn, module):
        gaps.append(AppGap(
            projection="π_audit_trail",
            severity=CRITICAL,
            entity=f"app:{module}",
            message="App has Blueprint state machines but zero scripts — "
                    "no audit trail exists for any state transition.",
            kb_pattern="KB pattern: King IV Principle 1 requires audit trails "
                       "for all approval and financial workflows.",
            remediation="Add workflow scripts with audit trail logging for "
                        "every state transition.",
        ))

    return gaps


# ---------------------------------------------------------------------------
# π_notification — state changes should trigger notifications
# ---------------------------------------------------------------------------

def _pi_notification(
    conn: sqlite3.Connection, module: str,
) -> list[AppGap]:
    """Check that state changes trigger appropriate notifications."""
    gaps: list[AppGap] = []

    scripts = conn.execute(
        """SELECT content, page_url, page_title FROM tokens
           WHERE module = ? AND content_type = 'CODE_EXAMPLE'""",
        (module,),
    ).fetchall()

    for content, page_url, title in scripts:
        code = content.lower()
        has_status_change = "input.status" in code or ".status =" in code
        has_sendmail = "sendmail" in code
        has_notification = has_sendmail or "zoho.cliq" in code or "pushnotify" in code

        if has_status_change and not has_notification:
            script_name = page_url.rsplit("/", 1)[-1]
            gaps.append(AppGap(
                projection="π_notification",
                severity=MEDIUM,
                entity=f"script:{script_name}",
                message=f"Script '{title}' changes status but sends no notification.",
                kb_pattern="KB pattern: sendmail [ from: zoho.adminuserid; "
                           "to: stakeholder; subject: ...; message: ... ]",
                remediation="Add sendmail notification after status change.",
            ))

    if not scripts and _has_blueprints(conn, module):
        gaps.append(AppGap(
            projection="π_notification",
            severity=HIGH,
            entity=f"app:{module}",
            message="App has state machines but zero notification scripts.",
            kb_pattern="KB documents sendmail, pushnotify, and Cliq integration patterns.",
        ))

    return gaps


# ---------------------------------------------------------------------------
# π_error_handling — scripts should handle edge cases
# ---------------------------------------------------------------------------

def _pi_error_handling(
    conn: sqlite3.Connection, module: str,
) -> list[AppGap]:
    """Check scripts for null guards, error handling, and boundary checks."""
    gaps: list[AppGap] = []

    scripts = conn.execute(
        """SELECT content, page_url, page_title FROM tokens
           WHERE module = ? AND content_type = 'CODE_EXAMPLE'""",
        (module,),
    ).fetchall()

    for content, page_url, title in scripts:
        code = content.lower()
        script_name = page_url.rsplit("/", 1)[-1]

        # Check for record lookups without null checks
        has_lookup = bool(re.search(r'\w+\[.+==.+\]', code))
        has_null_check = "!= null" in code or "ifnull" in code or "!= void" in code

        if has_lookup and not has_null_check:
            gaps.append(AppGap(
                projection="π_error_handling",
                severity=MEDIUM,
                entity=f"script:{script_name}",
                message=f"Script '{title}' fetches records but does not "
                        f"check for null results.",
                kb_pattern="KB pattern: rec = Form[condition]; "
                           "if(rec != null) { ... } else { handle missing; }",
                remediation="Add null guards: if(record != null && record.count() > 0)",
            ))

        # Check for sendmail without from guard
        has_sendmail = "sendmail" in code
        has_from = "zoho.adminuserid" in code or "zoho.adminuser" in code
        if has_sendmail and not has_from:
            gaps.append(AppGap(
                projection="π_error_handling",
                severity=LOW,
                entity=f"script:{script_name}",
                message=f"Script '{title}' uses sendmail without "
                        f"zoho.adminuserid as sender.",
                kb_pattern="KB pattern: from: zoho.adminuserid",
            ))

    return gaps


# ---------------------------------------------------------------------------
# π_compliance — regulatory patterns (POPIA, SARS, King IV)
# ---------------------------------------------------------------------------

def _pi_compliance(
    conn: sqlite3.Connection, module: str,
) -> list[AppGap]:
    """Check for regulatory compliance patterns relevant to SA apps."""
    gaps: list[AppGap] = []

    # Check if this is a financial/approval app
    overview = conn.execute(
        """SELECT content FROM tokens
           WHERE module = ? AND page_url LIKE '%/overview'""",
        (module,),
    ).fetchone()

    if not overview:
        return gaps

    overview_content = overview[0].lower()
    is_financial = any(kw in overview_content for kw in
                       ["expense", "invoice", "payment", "purchase", "claim",
                        "reimbursement", "chargeback"])
    is_approval = "approval" in overview_content or "blueprint" in overview_content

    all_code = "\n".join(r[0] for r in conn.execute(
        "SELECT content FROM tokens WHERE module = ? AND content_type = 'CODE_EXAMPLE'",
        (module,),
    ).fetchall())
    code_lower = all_code.lower()

    if is_financial:
        # SARS: Expense substantiation
        if "receipt" not in code_lower and "document" not in code_lower:
            gaps.append(AppGap(
                projection="π_compliance",
                severity=HIGH,
                entity=f"app:{module}",
                message="Financial app has no document/receipt validation. "
                        "SARS S11(a) requires substantiation of expenses.",
                kb_pattern="KB pattern: if(input.Supporting_Documents == null) "
                           "{ alert '...'; cancel submit; }",
            ))

        # Duplicate detection
        if "duplicate" not in code_lower and module.count("duplicate") == 0:
            gaps.append(AppGap(
                projection="π_compliance",
                severity=MEDIUM,
                entity=f"app:{module}",
                message="Financial app has no duplicate claim detection (COSO fraud risk).",
                kb_pattern="KB pattern: duplicates = Form[Date == input.Date && "
                           "Amount == input.Amount && User == loginuser]; "
                           "if(duplicates.count() > 0) { alert '...'; }",
            ))

    if is_approval:
        # King IV: Self-approval prevention
        if "self" not in code_lower and "same" not in code_lower and \
           "segregation" not in code_lower:
            gaps.append(AppGap(
                projection="π_compliance",
                severity=HIGH,
                entity=f"app:{module}",
                message="Approval workflow has no self-approval prevention "
                        "(King IV Principle 1 — segregation of duties).",
                kb_pattern="KB pattern: if(zoho.loginuser == submitter) "
                           "{ route to next approver; }",
            ))

        # POPIA: Consent
        if "popia" not in code_lower and "consent" not in code_lower:
            gaps.append(AppGap(
                projection="π_compliance",
                severity=LOW,
                entity=f"app:{module}",
                message="No POPIA consent check detected.",
                kb_pattern="KB pattern: if(input.POPIA_Consent == false) "
                           "{ alert '...'; cancel submit; }",
            ))

    return gaps


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# π_structural_completeness — app must have blueprints, pages, dashboards
# ---------------------------------------------------------------------------

def _pi_structural_completeness(
    conn: sqlite3.Connection, module: str,
) -> list[AppGap]:
    """Check that the app has the structural elements required to function.

    The KB documents three structural requirements:
    1. Every form with a Status/picklist field should have a Blueprint
    2. Every app should have at least one Page (dashboard)
    3. Apps without pages cannot load in the Creator browser UI

    These are weighted higher than behavioural gaps because they are
    foundational — an app without a page literally shows a blank screen.
    """
    gaps: list[AppGap] = []

    # Get overview for context
    overview = conn.execute(
        "SELECT content FROM tokens WHERE module = ? AND page_url LIKE '%/overview'",
        (module,),
    ).fetchone()
    overview_content = overview[0].lower() if overview else ""

    # 1. Blueprint check: forms with Status fields should have blueprints
    has_bp = _has_blueprints(conn, module)
    form_tokens = conn.execute(
        "SELECT content, page_url FROM tokens WHERE module = ? AND page_url LIKE '%/forms/%'",
        (module,),
    ).fetchall()

    forms_with_status = 0
    for content, page_url in form_tokens:
        if "status" in content.lower() and ("picklist" in content.lower() or "dropdown" in content.lower()):
            forms_with_status += 1

    if forms_with_status > 0 and not has_bp:
        gaps.append(AppGap(
            projection="π_structural_completeness",
            severity=CRITICAL,
            entity=f"app:{module}",
            message=f"App has {forms_with_status} form(s) with Status fields but no "
                    f"Blueprint state machine. State transitions are unmanaged.",
            kb_pattern="KB pattern: every form with a Status picklist should have a "
                       "Blueprint defining stages and transitions.",
            remediation="Add a Blueprint to each stateful form via Creator > Blueprint "
                        "or use forgeds-build-ds which auto-generates blueprints.",
        ))

    # 2. Page/Dashboard check
    page_tokens = conn.execute(
        "SELECT COUNT(*) FROM tokens WHERE module = ? AND "
        "(page_url LIKE '%/pages/%' OR page_url LIKE '%/dashboard%')",
        (module,),
    ).fetchone()[0]

    # Also check overview text for page references
    has_page_ref = "page" in overview_content or "dashboard" in overview_content

    if page_tokens == 0 and not has_page_ref:
        gaps.append(AppGap(
            projection="π_structural_completeness",
            severity=HIGH,
            entity=f"app:{module}",
            message="App has no pages or dashboards. Creator apps require at least "
                    "one page to load in the browser UI.",
            kb_pattern="KB pattern: every app needs at least one page with a "
                       "dashboard containing report components.",
            remediation="Add a dashboard page via Creator > Pages or use "
                        "forgeds-build-ds which auto-generates a default dashboard.",
        ))

    # 3. Report coverage: are there reports for the main forms?
    report_count = 0
    for content, _ in form_tokens:
        # Check overview for report references
        form_name_match = re.search(r'`(\w+)`', content)
        if form_name_match:
            fname = form_name_match.group(1)
            if fname in overview_content and "report" not in overview_content:
                report_count += 1

    return gaps


def _has_blueprints(conn: sqlite3.Connection, module: str) -> bool:
    """Check if the app has any Blueprint tokens."""
    row = conn.execute(
        "SELECT COUNT(*) FROM tokens WHERE module = ? AND page_url LIKE '%/blueprints/%'",
        (module,),
    ).fetchone()
    return row[0] > 0


def _get_app_name(conn: sqlite3.Connection, module: str) -> str:
    """Get the app display name from the overview token."""
    row = conn.execute(
        "SELECT page_title FROM tokens WHERE module = ? AND page_url LIKE '%/overview' LIMIT 1",
        (module,),
    ).fetchone()
    return row[0] if row else module


# ---------------------------------------------------------------------------
# Main projection function
# ---------------------------------------------------------------------------

def project_kb_onto_app(
    module: str,
    librarian_or_path: LibrarianHandle | str | Path,
) -> ProjectionReport:
    """Project the knowledge base onto an ingested app.

    Runs all projection functions and computes the residual field.
    The residual R(app) = Σ gap.severity measures how far the app
    is from being fully grounded to the KB.

    Each gap is a hologram — a place where the KB says something
    should exist but the app has nothing.

    Accepts either a LibrarianHandle (preferred) or a db_path for
    backward compatibility.
    """
    if isinstance(librarian_or_path, (str, Path)):
        # Legacy path: open read-only connection
        conn = sqlite3.connect(str(librarian_or_path))
        _close_conn = True
    else:
        conn = librarian_or_path.rb_conn
        _close_conn = False

    try:
        app_name = _get_app_name(conn, module)

        all_gaps: list[AppGap] = []
        all_gaps.extend(_pi_structural_completeness(conn, module))
        all_gaps.extend(_pi_form_validation(conn, module))
        all_gaps.extend(_pi_transition_logic(conn, module))
        all_gaps.extend(_pi_audit_trail(conn, module))
        all_gaps.extend(_pi_notification(conn, module))
        all_gaps.extend(_pi_error_handling(conn, module))
        all_gaps.extend(_pi_compliance(conn, module))

        residual = sum(g.severity for g in all_gaps)

        entity_residuals: dict[str, float] = {}
        for g in all_gaps:
            entity_residuals[g.entity] = entity_residuals.get(g.entity, 0) + g.severity

        forms = conn.execute(
            "SELECT COUNT(*) FROM tokens WHERE module = ? AND page_url LIKE '%/forms/%'",
            (module,),
        ).fetchone()[0]
        transitions = len([g for g in all_gaps
                          if g.projection == "π_transition_logic"])
        scripts = conn.execute(
            "SELECT COUNT(*) FROM tokens WHERE module = ? AND content_type = 'CODE_EXAMPLE'",
            (module,),
        ).fetchone()[0]

        return ProjectionReport(
            module=module,
            app_name=app_name,
            gaps=all_gaps,
            residual=residual,
            forms_analyzed=forms,
            transitions_analyzed=transitions,
            scripts_analyzed=scripts,
            entity_residuals=entity_residuals,
        )
    finally:
        if _close_conn:
            conn.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def project_main() -> None:
    """CLI for KB projection onto apps — wired to forgeds-kb-project."""
    import argparse
    import json
    import sys

    from forgeds.knowledge.cli import _db_path

    parser = argparse.ArgumentParser(
        prog="forgeds-kb-project",
        description="Project the knowledge base onto an app to reveal gaps (holograms).",
    )
    parser.add_argument(
        "module",
        help="App module name (e.g., app:Expense_Claim_Approval). "
             "Use 'all' to project onto all ingested apps.",
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Output as JSON.",
    )
    parser.add_argument(
        "--severity", "-s", type=float, default=0.0,
        help="Only show gaps with severity >= threshold (default: show all).",
    )
    parser.add_argument(
        "--remediate", "-r", action="store_true",
        help="Include KB context for remediation of each gap.",
    )
    args = parser.parse_args()

    db_path = _db_path()
    rb_path = db_path.parent / "reality.db"
    hb_path = db_path.parent / "holographic.db"

    if not rb_path.exists() and not db_path.exists():
        print(f"Database not found at {rb_path}.", file=sys.stderr)
        sys.exit(1)

    from forgeds.knowledge.librarian_io import open_librarian
    # Use reality.db if it exists, otherwise fall back to knowledge.db
    actual_rb = rb_path if rb_path.exists() else db_path
    lib = open_librarian(actual_rb, hb_path)

    # Resolve modules
    if args.module == "all":
        conn = lib.rb_conn
        modules = [r[0] for r in conn.execute(
            "SELECT name FROM modules WHERE name LIKE 'app:%' ORDER BY name"
        ).fetchall()]
    else:
        modules = [args.module]

    if not modules:
        print("No app modules found. Run forgeds-kb-ingest first.", file=sys.stderr)
        sys.exit(1)

    all_reports: list[ProjectionReport] = []
    for mod in modules:
        report = project_kb_onto_app(mod, lib)
        all_reports.append(report)

        if not args.as_json:
            # Filter by severity
            gaps = [g for g in report.gaps if g.severity >= args.severity]

            print(f"\n{'='*70}")
            print(f" {report.app_name} ({report.module})")
            print(f" R(app) = {report.residual:.1f}")
            print(f" Forms: {report.forms_analyzed} | "
                  f"Scripts: {report.scripts_analyzed} | "
                  f"Gaps: {len(gaps)}")
            print(f"{'='*70}")

            if not gaps:
                print("  No gaps detected — app is grounded to KB.")
                continue

            # Group by projection
            by_proj: dict[str, list[AppGap]] = {}
            for g in gaps:
                by_proj.setdefault(g.projection, []).append(g)

            for proj, proj_gaps in sorted(by_proj.items()):
                proj_residual = sum(g.severity for g in proj_gaps)
                print(f"\n  {proj} (residual: {proj_residual:.1f})")
                print(f"  {'─'*50}")
                for g in sorted(proj_gaps, key=lambda x: -x.severity):
                    sev_label = {2.0: "CRITICAL", 1.5: "HIGH", 1.0: "MEDIUM",
                                 0.5: "LOW", 0.2: "INFO"}.get(g.severity, f"{g.severity}")
                    print(f"  [{sev_label:>8s}] {g.entity}")
                    print(f"             {g.message}")
                    if g.kb_pattern:
                        print(f"             KB: {g.kb_pattern[:100]}")
                    if g.remediation and args.remediate:
                        print(f"             FIX: {g.remediation}")
                    print()

            # Per-entity summary
            if report.entity_residuals:
                print(f"  Entity Residuals (hotspots):")
                sorted_entities = sorted(report.entity_residuals.items(),
                                         key=lambda x: -x[1])
                for entity, res in sorted_entities[:10]:
                    bar = "█" * int(res * 3)
                    print(f"    {entity:45s} {res:5.1f} {bar}")

    if args.as_json:
        output = []
        for r in all_reports:
            output.append({
                "module": r.module,
                "app_name": r.app_name,
                "residual": r.residual,
                "forms_analyzed": r.forms_analyzed,
                "scripts_analyzed": r.scripts_analyzed,
                "gap_count": len(r.gaps),
                "gaps": [{
                    "projection": g.projection,
                    "severity": g.severity,
                    "entity": g.entity,
                    "message": g.message,
                    "kb_pattern": g.kb_pattern,
                    "remediation": g.remediation,
                } for g in r.gaps],
                "entity_residuals": r.entity_residuals,
            })
        print(json.dumps(output, indent=2, ensure_ascii=False))

    # Summary
    total_residual = sum(r.residual for r in all_reports)
    total_gaps = sum(len(r.gaps) for r in all_reports)
    print(f"\n{'='*70}")
    print(f" TOTAL: {len(all_reports)} app(s), "
          f"{total_gaps} gap(s), R(total) = {total_residual:.1f}")
    print(f"{'='*70}")

    sys.exit(1 if total_residual > 0 else 0)
