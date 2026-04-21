# Zia Script Prompts - Stress Test Plan

## Context

ForgeDS has a full round-trip pipeline: **build .ds** -> **export from Creator** -> **parse .ds** -> **lint scripts** -> **enhance with more workflows** -> **re-import**. We need 5 Zia prompts (500 char limit each) that generate Deluge scripts inside Zoho Creator's desktop app. These scripts get exported as .ds files, used as training data, then enhanced by ForgeDS-built workflows and re-imported. The prompts must stress-test every stage of this pipeline.

### What Makes These Good Stress Tests

Each prompt targets different:
- **Parser paths**: `_parse_workflows()`, `_parse_schedules()`, `_parse_approvals()` in `parse_ds_export.py`
- **Builder paths**: `emit_workflows()`, `emit_schedules()` in `build_ds.py`
- **Linter rules**: DG001-DG021 across line-scoped, block-scoped, and file-scoped categories
- **Edge cases**: nested parentheses, HTML in strings, deeply nested braces, multiple insert targets

---

## The 5 Zia Prompts

### Prompt 1: Form Workflow - On Add + On Success (Subform + Audit + Sendmail)
**Target**: Form workflow parser/builder path, subform row insertion, HTML emails

```
Create a Zoho Creator form workflow "Process Purchase Order" on the Purchase_Orders form triggered on add, on success. When submitted: validate total > 0, look up vendor = Vendors[Vendor_ID == input.Vendor_ID], null check the result, insert a subform row into Line_Items subform with item and amount fields, insert audit trail into Approval_History with action "Submitted" and Added_User = zoho.loginuser, then sendmail with HTML table to zoho.adminuserid showing order details and line items.
```
**Chars**: ~497 | **Parser**: `_parse_workflows()` | **Builder**: `emit_workflows()`
**Linter rules exercised**: DG004 (field refs), DG005 (null guard), DG006/07 (audit trail), DG009 (insert =), DG010 (sendmail params), DG012 (action values), DG019 (Added_User)
**Edge cases**: Nested parens from `ifnull()` + subform `insert()`, HTML angle brackets in sendmail strings

---

### Prompt 2: Scheduled Task - Record Iteration + invokeUrl + Map
**Target**: Schedule parser/builder path (entirely separate from form workflows)

```
Create a Zoho Creator scheduled task "Daily Overdue Checker" that runs daily. Query all records from Invoices where Status == "Pending" and Due_Date < zoho.currentdate. For each overdue record: calculate days = daysBetween(rec.Due_Date, zoho.currentdate), if days > 30 update rec.Status = "Escalated", call invokeUrl with url "https://api.example.com/notify" type POST parameters map with invoice_id and days_overdue, insert into Audit_Log with action = "Overdue Escalation" and Added_User = zoho.adminuser.
```
**Chars**: ~493 | **Parser**: `_parse_schedules()` / `_parse_schedule_block()` | **Builder**: `emit_schedules()`
**Linter rules exercised**: DG003 (negative test - `daysBetween` is correct, `hoursBetween` would fail), DG010 (invokeUrl params), DG011 (status values), DG018 (zoho.currentdate)
**Edge cases**: `for each` loop creates deeply nested braces, URL strings with `://`, map construction parens, schedule-specific `on start { on load ( ) }` nesting

---

### Prompt 3: Form Workflow - On Edit + On Validate (Threshold + Role Check + Mixed Operators)
**Target**: Validate event path, threshold logic, deliberate DG013 trap

```
Create a Zoho Creator workflow on the Expense_Claims form on edit, on validate. Check if thisapp.permissions.isUserInRole("Finance Manager") and input.total_amount > 0. Query thresholdRec = approval_thresholds[tier_name == "Tier 1" && Active == true]. If thresholdRec != null use thresholdAmount = ifnull(thresholdRec.max_amount_zar, 999.99) else set thresholdAmount = 999.99. If input.total_amount > thresholdAmount && input.status == "Pending" || input.priority == "Urgent" then cancel submit with alert.
```
**Chars**: ~498 | **Parser**: `_parse_workflows()` with `on validate` event | **Builder**: `emit_workflows()` validate path
**Linter rules exercised**: DG005 (null guard), DG011 (status values), DG013 (mixed &&/|| - deliberate trap), DG014 (threshold 999.99 fallback)
**Edge cases**: `&&` inside query brackets, `ifnull()` nested parens, `cancel submit` valid in form context (would be DG021 in API context). Matches scaffold `generate_threshold_check()` and `generate_self_approval_check()` patterns.

---

### Prompt 4: Approval Process - On Approve + On Reject (GL Lookup + Audit + Email)
**Target**: Approval parser path (structurally distinct from workflows and schedules)

```
Create a Zoho Creator approval process for Expense_Claims with two scripts. On approve: look up glRec = gl_accounts[expense_category == input.category && Active == true], null check result, set input.gl_code = glRec.gl_code, update input.status = "Approved", insert into approval_history with action_1 = "Approved" claim = input.ID actor = zoho.loginuser timestamp = zoho.currenttime Added_User = zoho.loginuser, sendmail from zoho.adminuserid to input.Email subject "Claim Approved" message with HTML body.
```
**Chars**: ~496 | **Parser**: `_parse_approvals()` / `_parse_approval_block()` | **Builder**: (approval emission not yet built - gap identified)
**Linter rules exercised**: DG005 (null guard), DG006/07 (audit trail), DG009 (insert =), DG010 (sendmail params), DG011 (status), DG012 (action values), DG015/16 (emails)
**Edge cases**: Approval blocks have triple nesting: `approval { Name { on approve { on load ( CODE ) } } }`. Parser at line 358 hardcodes `form="expense_claims"`. GL lookup matches `generate_gl_lookup()` scaffold pattern.

---

### Prompt 5: Multi-Trigger Form Workflow - On Add Or Edit + Try-Catch + invokeUrl + Error Logging
**Target**: Combined trigger, maximum structural complexity for parser

```
Create a Zoho Creator workflow on the Incident_Reports form on add or edit, on success. Use try-catch: in try block build a map params = Map(), params.put("id", input.ID), params.put("type", input.Category), call resp = invokeUrl url "https://api.example.com/incidents" type POST parameters params headers Map(), parse resp as JSON into resultMap. If resultMap.get("status") == "ok" update input.status = "Synced" and insert audit row. In catch block insert into Error_Log with message and zoho.currenttime.
```
**Chars**: ~499 | **Parser**: `_parse_workflows()` with `on add or edit` | **Builder**: `emit_workflows()` combined trigger
**Linter rules exercised**: DG004 (field refs), DG010 (invokeUrl params), DG011 (status), DG018 (zoho vars)
**Edge cases**: Try-catch creates 4+ levels of brace nesting, `Map()` calls add parentheses, `resp.get("status")` has nested parens with quoted strings, multiple `insert into` targets in one script tests linter block extractor.

---

## Coverage Matrix

| Prompt | Trigger | Event | Parser Path | Builder Path | Key Linter Rules |
|--------|---------|-------|-------------|--------------|------------------|
| 1 | on add | on success | `_parse_workflows` | `emit_workflows` | DG004,05,06,07,09,10,12,19 |
| 2 | scheduled | on load | `_parse_schedules` | `emit_schedules` | DG003(neg),10,11,18 |
| 3 | on edit | on validate | `_parse_workflows` | `emit_workflows` | DG005,11,13,14 |
| 4 | approval | on approve | `_parse_approvals` | (not built yet) | DG005,06,07,09,10,11,12,15 |
| 5 | on add or edit | on success | `_parse_workflows` | `emit_workflows` | DG004,10,11,18 |

## Scaffold Pattern Coverage
- `generate_audit_trail()`: Prompts 1, 2, 4
- `generate_sendmail()`: Prompts 1, 4
- `generate_self_approval_check()`: Prompt 3
- `generate_gl_lookup()`: Prompt 4
- `generate_threshold_check()`: Prompt 3

---

## Implementation Steps

### Step 1: Create the prompts file [DONE]
- File: `config/zia-script-prompts.yaml` (new file in the project)
- Contains all 5 prompts with metadata (name, target workflow type, expected patterns)

### Step 2: Write companion Deluge scripts [DONE]
- Create the expected output scripts that each prompt should generate
- Place in `tests/fixtures/zia-stress-test/` as reference .dg files
- These serve as training data ground truth for the round-trip test

### Step 3: Commit and push to branch `claude/zia-script-prompts-Dze5R` [DONE]

### Step 4: Import .ds training exports [PENDING]
- Copy the 4 .ds files from Downloads into the repo
- Files: Expense_Claim_Approval.ds, Invoice_Overdue_Management.ds, Purchase_Order_Processing.ds, Incident_Report_Synchronization.ds

### Step 5: Parse and lint the training data [PENDING]
- Run `forgeds-parse-ds` on each .ds export
- Run `forgeds-lint` on extracted scripts
- Compare against reference .dg files

### Step 6: Enhance and re-import [PENDING]
- Use `forgeds-build-ds` to add more workflows
- Re-import enhanced .ds back into Creator
- Verify round-trip integrity

---

## Design Rule: [] inside {}

All `[]` action blocks (sendmail, insert into, invokeUrl) MUST be wrapped inside `{}` control flow containers (if, on success, workflow blocks). Bare `[]` blocks are unsafe because the compiler traverses them on sight -- they are action primitives, not deterministic control flow.

## Critical Files
- `src/forgeds/core/parse_ds_export.py` - Parser being stress-tested
- `src/forgeds/core/build_ds.py` - Builder being stress-tested
- `src/forgeds/core/lint_deluge.py` - Linter rules being exercised
- `src/forgeds/core/scaffold_deluge.py` - Boilerplate patterns being matched
- `config/zia-script-prompts.yaml` - The 5 Zia prompts
- `tests/fixtures/zia-stress-test/` - Reference scripts and training .ds exports
