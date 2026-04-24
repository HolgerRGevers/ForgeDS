# Zia-Generated App vs Original — Structured Diff Report
**Original**: `Expense_Reimbursement_Management-stage.ds` (3,656 lines, 06-Apr-2026)
**Zia-built**: `Expense_Reimbursement_Management-development (1).ds` (2,985 lines, 23-Apr-2026)
**Diff produced**: 2026-04-24

---

## 1. Header-Level Diff

| Attribute | Original | Zia-built | Match |
|---|---|---|---|
| App name | `"Expense Reimbursement Management"` | `"Expense Reimbursement Management"` | exact |
| Version | `1.0` | `1.0` | exact |
| Date format | `dd-MMM-yyyy` | `dd-MMM-yyyy` | exact |
| Time format | `24-hr` | `24-hr` | exact |
| **Timezone** | `Africa/Johannesburg` | **`America/Los_Angeles`** | **WRONG** |

**BRD §1 Ingestion Contract verdict**: Partial. App name, date format, and time format were honored. The timezone was not. The BRD specified `Africa/Johannesburg` (SAST, GMT+2) explicitly, but Zia defaulted to Pacific time (`America/Los_Angeles`). This is a functional defect for any date/time stamping in the approval workflow — timestamps on `approval_history.timestamp` and `expense_claims.Submission_Date` would be off by 9–11 hours relative to South Africa.

---

## 2. Forms Comparison

| original_form | zia_form | status | notes |
|---|---|---|---|
| `approval_history` | `approval_history` | kept | link_name identical |
| `approval_thresholds` | `approval_thresholds` | kept | link_name identical |
| `clients` | `clients` | kept | link_name identical; fields restructured |
| `departments` | `departments` | kept | link_name identical; fields restructured |
| `expense_claims` | `expense_claims` | kept | link_name identical; many fields dropped/changed |
| `gl_accounts` | `gl_accounts` | kept | link_name identical; one type change |

**No forms were dropped. No forms were added by Zia.** All 6 forms present. 6/6 form names matched exactly.

---

## 3. Field-Level Diff (Per Form)

### 3A. `approval_history` (original: 5 fields; Zia: 5 fields)

| original_field (link_name, type) | zia_field (link_name, type) | match_status | notes |
|---|---|---|---|
| `claim` (list → expense_claims) | `claim` (list → expense_claims) | **type_changed** | Zia's `displayformat = [Email]`; original uses `[claim_id]`. Wrong display key. |
| `action_1` (picklist, 12 values) | `action_1` (picklist, 12 values) | **type_changed** | Values identical but: (a) order scrambled; (b) Zia adds `others option = true` (allows freetext not in original); (c) displayname changed from "Action" to "Action 1"; (d) description block dropped |
| `actor` (text, "Actor") | `actor_role` (text, "Actor Role") | **renamed** | link_name changed from `actor` to `actor_role`. Breaks all Deluge scripts referencing `input.actor`. |
| `timestamp` (datetime) | `timestamp` (datetime) | exact | Type and options match |
| `comments` (textarea, 100px) | `notes` (textarea, 100px) | **renamed** | link_name changed from `comments` to `notes`. Breaks all workflow scripts that write to `comments`. |
| — | — | — | Description blocks on all fields dropped by Zia |

**Critical renames**: `actor` → `actor_role`, `comments` → `notes`. The original's Deluge workflows extensively write to both fields by their original link_names; the renamed fields would cause every workflow insert into `approval_history` to silently fail or use wrong fields.

---

### 3B. `approval_thresholds` (original: 8 fields; Zia: 6 fields)

| original_field (link_name, type) | zia_field (link_name, type) | match_status | notes |
|---|---|---|---|
| `tier_name` (text) | `tier_name` (text) | exact | |
| `max_amount_zar` (ZAR/currency) | **DROPPED** | **dropped** | Critical omission — this is the threshold amount field. Zia has no financial field on this form at all. |
| `approver_role` (text) | `approver_role` (text) | exact | |
| `Active` (checkbox, initial=true) | `Active` (checkbox, initial=**false**) | **type_changed** | Default inverted: Zia defaults to inactive. Original defaults to active. |
| `Tier_Order` (number, initial=0) | `Tier_Order` (number) | **type_changed** | Zia sets `maxchar = 19` (text width), drops initial value |
| `Requires_Dual_Approval` (checkbox, initial=false) | `Requires_Dual_Approval` (checkbox, initial=false) | exact | |
| `Dual_Approval_Role` (text, "Dual Approval Role") | `Dual_Approval_Role` (text, "Duap Approval Role") | **type_changed** | displayname has a **typo** ("Duap") — copy from BRD source text was corrupted |
| `Dual_Threshold_ZAR` (ZAR/currency) | **DROPPED** | **dropped** | Second ZAR field also dropped; dual-approval threshold amount has no storage field |

**Summary**: 2 fields dropped (both ZAR/currency type), 1 default value inverted, 1 display name typo introduced. The `max_amount_zar` field is load-bearing: all threshold-routing logic in the original approval workflow reads `thresholdRec.max_amount_zar`. Dropping it makes the approval routing configuration table non-functional.

---

### 3C. `clients` (original: 3 fields; Zia: 3 fields)

| original_field (link_name, type) | zia_field (link_name, type) | match_status | notes |
|---|---|---|---|
| `client_id` (autonumber, start=1) | **DROPPED** | **dropped** | Auto-number dropped entirely |
| `name` (text, "Name") | `client_name` (text, "Client Name") | **renamed** | link_name `name` → `client_name`. Breaks expense_claims lookup `displayformat = [" - " + name]` |
| `is_active` (checkbox, "Active", initial=true) | **DROPPED** | **dropped** | Active flag dropped |
| — | `contact_person` (text, "Contact Person") | **added_by_zia** | Not in original |
| — | `email` (email, "Email") | **added_by_zia** | Not in original; different field type |

**Net**: 2 fields dropped (autonumber, checkbox), 1 renamed, 2 invented. The lookup in `expense_claims.client` uses `displayformat = [" - " + name]` — since Zia renamed the field `client_name`, the lookup display would be empty/broken if the original Deluge ran.

---

### 3D. `departments` (original: 3 fields; Zia: 2 fields)

| original_field (link_name, type) | zia_field (link_name, type) | match_status | notes |
|---|---|---|---|
| `department_id` (autonumber, start=1) | **DROPPED** | **dropped** | Auto-number dropped |
| `name` (text, "Name") | `department_name` (text, "Department Name") | **renamed** | link_name `name` → `department_name`. Breaks `expense_claims.department` displayformat `[" - " + name]` |
| `is_active` (checkbox, "Active", initial=true) | **DROPPED** | **dropped** | Active flag dropped |
| — | `manager_name` (text, "Manager Name") | **added_by_zia** | Not in original |

**Net**: 2 fields dropped, 1 renamed, 1 invented. Lookup display broken for same reason as clients.

---

### 3E. `expense_claims` (original: 27 fields; Zia: 10 fields)

| original_field (link_name, type) | zia_field (link_name, type) | match_status | notes |
|---|---|---|---|
| `Employee_Name1` (name compound, required) | **DROPPED** | **dropped** | Complex name field (prefix/first/last/suffix). Zia cannot generate compound name fields. |
| `Email` (picklist/users module) | `Email` (email type) | **type_changed** | Original is a user-picker (module=users, displayformat=[emailid]); Zia made it a plain email text field. Loses user-system link. |
| `Submission_Date` (datetime, required) | `Submission_Date` (date only) | **type_changed** | Original is datetime with time; Zia is date-only. Loses time-of-day component. |
| `claim_id` (autonumber, start=1) | **DROPPED** | **dropped** | Auto-number dropped |
| `department` (list → departments) | **DROPPED** | **dropped** | Lookup to departments dropped |
| `Claim_Reference` (text, required) | `Claim_Reference` (text) | exact | Required flag dropped |
| `client` (list → clients) | **DROPPED** | **dropped** | Lookup to clients dropped |
| `Expense_Date` (date) | **DROPPED** | **dropped** | |
| `Department_Shadow` (text, private=true) | **DROPPED** | **dropped** | Hidden shadow field for grouping |
| `category` (picklist, 7 values: Travel/Accommodation/Meals & Entertainment/Office Supplies/Communication/Professional Services/Other) | `category` (picklist, 7 values: **Training/Travel/Utilities/Office Supplies/Meals/Marketing/Other**) | **type_changed** | Values entirely different from original. Zia sourced from gl_accounts.expense_category picklist (which also has wrong values — see §3F). Breaks GL code auto-mapping. |
| `Client_Shadow` (text, private=true) | **DROPPED** | **dropped** | Hidden shadow field |
| `amount_zar` (ZAR/currency) | **DROPPED** | **dropped** | Critical — the core claim amount field. No financial amount field exists in Zia's expense_claims. |
| `Supporting_Documents` (upload file, required, max 10) | `Supporting_Documents` (text, "Supporting Documents") | **type_changed** | File upload coerced to plain text field. Cannot store actual file attachments. |
| `description` (textarea, 100px) | **DROPPED** | **dropped** | Business purpose description field dropped |
| `VAT_Invoice_Type` (picklist: None / Abbreviated (< R5,000) / Full Tax Invoice (>= R5,000)) | `VAT_Invoice_Type` (picklist: "Full Tax Invoice (>= R5" / "Partial Tax Invoice (<= R5" / "None" / "000)") | **type_changed** | Values **corrupted** — Zia split the value `"Full Tax Invoice (>= R5,000)"` across two list entries at a parenthesis boundary. The value `"000)"` is a fragment, not a valid picklist entry. |
| `POPIA_Consent` (checkbox, initial=false) | **DROPPED** | **dropped** | Compliance consent field dropped |
| `status` (picklist, 9 values: Draft/Submitted/Pending LM Approval/Pending HoD Approval/Pending Second Key/Key 2 Dispute/Approved/Rejected/Resubmitted) | `status` (picklist, 9 values — same set but reordered, `others option = true` added) | **type_changed** | Values present but: (a) order differs (Zia puts Submitted first, not Draft); (b) `others option = true` allows invalid status values; (c) description dropped |
| `Rejection_Reason` (textarea, 100px) | **DROPPED** | **dropped** | |
| `Version` (number, initial=1) | **DROPPED** | **dropped** | Resubmission version counter dropped |
| `Retention_Expiry_Date` (date, private=true) | `Retention_Expiry_Date` (date) | **type_changed** | `private=true` not honored. SARS retention date is now visible to all users. |
| `Parent_Claim_ID` (picklist → expense_claims.ID, private=true) | **DROPPED** | **dropped** | Self-referential lookup dropped |
| `gl_code` (list → gl_accounts) | `gl_code` (list → gl_accounts) | exact | Lookup preserved |
| `Requires_Dual_Approval` (checkbox, private=true) | **DROPPED** | **dropped** | |
| `Key_1_Approver` (text, private=true) | **DROPPED** | **dropped** | |
| `Key_1_Timestamp` (datetime, private=true) | **DROPPED** | **dropped** | |
| `Key_2_Approver` (text, private=true) | **DROPPED** | **dropped** | |
| `Key_2_Timestamp` (datetime, private=true) | **DROPPED** | **dropped** | |
| — | `Claim_Submission_Timestamp` (datetime) | **added_by_zia** | Separate timestamp field invented by Zia |

**Summary**: Of 27 original fields, only 5 survive with reasonable fidelity (`Claim_Reference`, `gl_code`, `status` [with caveats], `Retention_Expiry_Date` [private flag lost], `VAT_Invoice_Type` [values corrupted]). 17 fields dropped, 4 type-changed significantly, 1 added by Zia. **`amount_zar` was entirely dropped** — the app has no way to store a monetary amount on an expense claim.

---

### 3F. `gl_accounts` (original: 7 fields; Zia: 7 fields)

| original_field (link_name, type) | zia_field (link_name, type) | match_status | notes |
|---|---|---|---|
| `gl_code` (text) | `gl_code` (text) | exact | |
| `account_name` (text) | `account_name` (text) | exact | |
| `expense_category` (picklist: Travel/Accommodation/Meals & Entertainment/Office Supplies/Communication/Professional Services/Other) | `expense_category` (picklist: **Training/Travel/Utilities/Office Supplies/Meals/Marketing/Other**) | **type_changed** | Completely different picklist values. Zia invented its own category taxonomy. This breaks GL-auto-mapping logic. |
| `receipt_required` (checkbox, initial=**true**) | `receipt_required` (checkbox, initial=**false**) | **type_changed** | Default inverted (SARS compliance default should be true). |
| `SARS_Provision` (text, with help_text) | `SARS_Provision` (checkbox, initial=false) | **type_changed** | Type changed from text (stores provision codes like "S11(a) + S8(1)(a)") to a boolean checkbox. The field loses its ability to store the provision string. |
| `Risk_Level` (picklist: **Standard/Elevated/High**, initial="Standard") | `Risk_Level` (picklist: **High/Low/Medium**) | **type_changed** | Values changed ("Standard" → "Low", "Elevated" dropped, different order). Default value dropped. |
| `Active` (checkbox, initial=**true**) | `Active` (checkbox, initial=**false**) | **type_changed** | Default inverted again. |

**Summary**: 7/7 fields present by link_name, but 5 of 7 have incorrect defaults or type changes. Most serious: `SARS_Provision` changed from text to checkbox (destroys compliance-tracking capability), and `expense_category` picklist values are completely different from the original (breaks GL auto-assignment).

---

## 4. Reports / Views

**Original had 11 reports** (9 list + 1 kanban + 1 pivot). **Zia generated 8 reports** (6 list + 2 kanban + 0 pivot).

| original_report (link_name, type) | zia_report | match_status | notes |
|---|---|---|---|
| `expense_claims_Report` (list) | `expense_claims_Report` (list) | partial | Zia shows Email/Submission_Date/Claim_Reference/gl_code/category/VAT_Invoice_Type/status/Supporting_Documents — not claim_id/department/client/amount_zar. Reflects missing fields. Zia adds conditional formatting on `VAT_Invoice_Type` using corrupted values ("000)"). |
| `gl_accounts_Report` (list) | `gl_accounts_Report` (list) | partial | Zia shows only 4 of 7 columns (drops SARS_Provision, Risk_Level, Active). |
| `gl_accounts_by_expense_category` (kanban) | `gl_accounts_by_expense_category` (kanban) | partial | Display field is `expense_category` — matches, but with wrong picklist values |
| `approval_history_Report` (list) | `approval_history_Report` (list) | partial | Zia uses renamed fields: `actor_role` instead of `actor`, `notes` instead of `comments`. |
| `approval_thresholds_Report` (list) | `approval_thresholds_Report` (list) | partial | Drops `max_amount_zar` (field absent). Zia report doesn't include Dual_Threshold_ZAR. |
| `clients_Report` (list) | `clients_Report` (list) | partial | Zia shows `client_name`/`contact_person`/`email` (Zia-invented fields). Original shows `client_id`/`name`/`is_active`. |
| `departments_Report` (list) | `departments_Report` (list) | partial | Zia shows `department_name`/`manager_name`. Original shows `department_id`/`name`/`is_active`. |
| `Audit_Trail` (list, filtered, sorted) | **DROPPED** | dropped | |
| `pending_approvals_manager` (list, filtered by status, grouped) | **DROPPED** | dropped | Critical workflow report for approvers |
| `My_Claims` (list, filtered by Added_User) | **DROPPED** | dropped | Employee self-service report |
| `Expense_Summary` (pivottable) | **DROPPED** | dropped | |
| — | `expense_claims_by_status` (kanban) | **added_by_zia** | Zia created a new kanban on status field |

**Summary**: 0 reports are an exact match. All 8 Zia-generated reports are partial matches (wrong columns, renamed fields, or corrupted filter values). 3 original reports were dropped (`Audit_Trail`, `pending_approvals_manager`, `My_Claims`, `Expense_Summary`). 1 new kanban was added by Zia. **0/11 reports preserved accurately.**

---

## 5. Relationships (Lookups)

The original has 5 lookup edges:

| # | original_lookup (form.field → target.ID) | Zia status | notes |
|---|---|---|---|
| 1 | `approval_history.claim → expense_claims.ID` | **preserved** | Both files: `type = list`, `values = expense_claims.ID`. Zia's `displayformat = [Email]` is wrong (original uses `[claim_id]`), but the relationship edge exists. |
| 2 | `expense_claims.department → departments.ID` | **DROPPED** | Field `department` absent from Zia's expense_claims form entirely |
| 3 | `expense_claims.client → clients.ID` | **DROPPED** | Field `client` absent from Zia's expense_claims form entirely |
| 4 | `expense_claims.gl_code → gl_accounts.ID` | **preserved** | Both files: `type = list`, `values = gl_accounts.ID`, `displayformat = [gl_code]` |
| 5 | `expense_claims.Parent_Claim_ID → expense_claims.ID` (self-ref) | **DROPPED** | `Parent_Claim_ID` field absent from Zia's expense_claims entirely |

**Self-referential lookup (`Parent_Claim_ID`)**: Dropped. This field tracked resubmitted claims back to their parent, enabling version lineage. Its loss means the resubmission tracking mechanism cannot function.

**Lookups preserved: 2/5.**

---

## 6. Workflows / Roles / Emails

### Workflows
**Expected (per Zia documentation): 0 workflows generated from BRD.**

Actual: Zia generated **a Blueprint workflow** on both `expense_claims` and `approval_thresholds`. These are not the same as the original's Deluge-scripted approval workflows — they are visual state-machine Blueprints with empty `before`/`after` action blocks (no Deluge code). The Blueprint stages on `expense_claims` ("Claim Submitted", "Claim Under Review", "Claim Rejected", "Claim Approved", etc.) are different from the original's status values and do not match the picklist. The Blueprint on `approval_thresholds` is entirely Zia-invented (19 stages).

**Verdict**: Zero Deluge workflow logic generated (as expected). Zia substituted Blueprint stage scaffolding with no actual automation code. The original's critical workflows (SLA enforcement, approval routing, audit trail writing, self-approval prevention, GL auto-population) are all absent.

### Share Settings / Roles
**Expected (per Zia documentation): roles MAY be generated from BRD.**

Original had 9 named roles: `Read`, `Write`, `Line Manager`, `Administrator`, `Employee`, `Finance Accountant`, `Developer`, `HoD`, `Finance Director`, `System Administrator`, `Client Representative`, `Vendor`, `Customer` — plus a 4-level role hierarchy: `CEO > HoD > Line Manager > Employee`, with `Finance Director` as a separate branch.

Zia generated 9 named roles: `Line Manager`, `Administrator`, `Employee`, `Head of Department (HoD)`, `Finance Administrator`, `Developer`, `Third-Party Auditor`, `Client Representative`, `Customer` — plus a flat `CEO` role (no hierarchy structure below it).

**Differences**:
- `Finance Accountant` (original) → `Finance Administrator` (Zia) — renamed
- `HoD` (original short name) → `Head of Department (HoD)` (Zia full name) — renamed; this breaks any Deluge code that calls `isUserInRole("HoD")`
- `Finance Director` role (original) — **dropped** by Zia. This is the Key 2 approver role for dual-authorization.
- `System Administrator` (original) → not present in Zia
- `Vendor` (original) → not present in Zia
- `Third-Party Auditor` (Zia) → not in original, **added by Zia**
- Role hierarchy: Original has `CEO > HoD > Line Manager > Employee` (with Finance Director separate). Zia has only a flat `CEO` with no hierarchy children defined.

**Verdict**: Roles were generated (contradicting "Zia does not generate roles"), but with name mismatches and structural differences. **The role hierarchy was not reproduced.**

---

## 7. Things Zia Added That the BRD Didn't Specify

1. **`clients.contact_person` and `clients.email` fields** (lines 224–239): Zia expanded the Clients form with contact details not in the original.
2. **`departments.manager_name` field** (line 290): Zia added a manager name to Departments.
3. **`expense_claims.Claim_Submission_Timestamp`** (line 427): Separate datetime field for submission, in addition to `Submission_Date`.
4. **`expense_claims_by_status` kanban report** (line 617): Zia invented a kanban view on the status field for expense_claims, which the original did not have.
5. **Blueprint on `approval_thresholds`** (`dual_approval_enforcement_process`, 19 stages, lines 1129–1679): Entirely Zia-invented; original has no Blueprint on this form.
6. **Blueprint on `expense_claims`** (`expense_claim_approval_workflow`, 9 stages): Replaces the original's Deluge approval process with an empty visual workflow with different stage names.
7. **`Third-Party Auditor` role** (line 1865): Zia invented an auditor portal role not in the original.
8. **`Client Representative` role** (Zia keeps it from original but with `Create` permission on `clients` — original had only `Viewall`).
9. **`others option = true` on all picklists**: Zia added free-text fallback to every picklist, which the original intentionally omitted for data integrity.

---

## 8. Fidelity Scorecard

| Dimension | Score | Detail |
|---|---|---|
| **Forms** | **6/6** | All 6 form link_names preserved |
| **Fields** | **~7/53** | See below |
| **Lookups** | **2/5** | `approval_history.claim` and `expense_claims.gl_code` preserved; 3 dropped |
| **Reports** | **0/11** | All 8 generated have structural errors; 3 originals dropped; 0 exact matches |
| **Picklists** | **0/5 verbatim** | See below |
| **Workflows (Deluge)** | **0 generated** (confirmed) | Blueprint scaffolding substituted but has no automation code |
| **Roles** | **generated but mismatched** | 6 role names preserved; 3 dropped/renamed; role hierarchy absent |

**Field preservation detail** (53 original fields, across all 6 forms):
- `approval_history`: 2/5 exact (`timestamp`, partial `action_1`). `actor` renamed, `comments` renamed, lookup display wrong.
- `approval_thresholds`: 3/8 reasonable (`tier_name`, `approver_role`, `Requires_Dual_Approval`). 2 dropped (`max_amount_zar`, `Dual_Threshold_ZAR`), defaults inverted.
- `clients`: 0/3 exact. 1 renamed, 1 dropped, 1 dropped.
- `departments`: 0/3 exact. 1 renamed, 2 dropped.
- `expense_claims`: 2/27 exact (`Claim_Reference` link_name, `gl_code`). 17 dropped, most others type-changed.
- `gl_accounts`: 2/7 exact (`gl_code`, `account_name`). 5 have type changes or wrong defaults.

**Conservative count of fields that match on both link_name AND type (no caveats)**: approximately **7 of 53** (`approval_history.timestamp`, `approval_thresholds.tier_name`, `approval_thresholds.approver_role`, `approval_thresholds.Requires_Dual_Approval`, `expense_claims.Claim_Reference` [type ok, required dropped], `expense_claims.gl_code`, `gl_accounts.gl_code`, `gl_accounts.account_name`). Call it **8/53** generously.

**Picklist verbatim preservation**:
1. `approval_history.action_1` — 12/12 values present but reordered, `others option` added: **not verbatim**
2. `expense_claims.category` — completely different values: **not verbatim**
3. `expense_claims.VAT_Invoice_Type` — values corrupted (split at parentheses): **not verbatim**
4. `expense_claims.status` — values present but reordered, `others option` added: **not verbatim**
5. `gl_accounts.expense_category` — completely different values: **not verbatim**

**0/5 picklists verbatim.**

**Top-line scorecard**: `6/6 forms | 8/53 fields | 2/5 lookups | 0/11 reports | 0/5 picklists | 0 Deluge workflows | roles present but mismatched`

---

## 9. Surprises

### Positive Surprises (Zia did better than expected)

1. **Roles were generated at all.** Zoho's Zia documentation states it does not generate roles from documents. Zia produced 9 named roles with meaningful descriptions and per-form permissions, including a `Third-Party Auditor` portal role. This was unexpected and useful scaffolding.

2. **Blueprint workflows were auto-created.** Again, documentation implies no workflow generation. Zia created two Blueprint state machines (on `expense_claims` and `approval_thresholds`) with named stages and transitions derived from the BRD's approval process description. The stages and transitions are structurally coherent even if empty of Deluge code.

3. **Dashboard pages with charts were auto-generated.** Zia produced a `Dashboard` page with 4 KPI tiles, 2 charts, Quick Links, and an embedded report — plus a separate `Employee_Dashboard` and `Management_Dashboard`. The original only had a `Dashboard` page. Zia created more pages than the original.

### Negative Surprises (Zia did worse than expected)

4. **`amount_zar` was completely dropped from `expense_claims`.** The core financial field of an expense reimbursement system is absent. This is the worst single omission — the app literally cannot store how much money is being claimed. Likely caused by Zia's inability to generate currency/ZAR fields (confirmed: 0 occurrences of `type = ZAR` in Zia output vs. 3 in original).

5. **Picklist values were corrupted by parenthesis tokenization.** The `VAT_Invoice_Type` picklist in the BRD contains `"Full Tax Invoice (>= R5,000)"`. Zia split this into three entries: `"Full Tax Invoice (>= R5"`, `"Partial Tax Invoice (<= R5"`, and `"000)"`. The condition `(VAT_Invoice_Type == "000)")` in Zia's conditional formatting (line 599) confirms that Zia was using the corrupted values — even its own dashboard logic references the corrupted form. This is a parsing artifact from how Zia tokenized the BRD's picklist definitions.

6. **Timezone defaulted to America/Los_Angeles.** Despite the BRD explicitly specifying `Africa/Johannesburg`, Zia ignored this. Since the BRD is uploaded as TXT and Zia did read other app metadata correctly (app name, date format), this suggests Zia has a hard-coded default timezone that overrides document specifications, not a parsing failure.

7. **`SARS_Provision` was changed from `type = text` to `type = checkbox`.** The original field stores compliance provision strings (e.g., "S11(a) + S8(1)(a)"). Zia converted it to a boolean. This completely destroys the compliance-reporting utility of the field.

---

## 10. Implications for a Plan B BRD

These are prioritized from highest-to-lowest impact, each grounded in diff evidence.

### Priority 1: Force ZAR currency fields by workaround
**Evidence**: `amount_zar`, `max_amount_zar`, and `Dual_Threshold_ZAR` were all dropped (0 occurrences of `type = ZAR` in Zia output). Zia cannot generate currency fields. **Plan B**: Describe these as `Number` fields explicitly in the BRD (e.g., "Amount ZAR: integer/decimal number field, stores rand amount"). Accept `type = number`; add a note in BRD that ZAR formatting will be applied manually post-import. Do not use the word "currency" or "ZAR" as the field type label.

### Priority 2: Specify timezone with a workaround cue
**Evidence**: Section 1 BRD had `Africa/Johannesburg` but Zia output `America/Los_Angeles` (line 9 of Zia file). **Plan B**: Add an explicit instruction in the BRD: "IMPORTANT: The application timezone MUST be set to Africa/Johannesburg (SAST, UTC+2). This is a South African app. Do NOT use Pacific or US timezones." Test if Zia can honor this when stated as an imperative rather than a metadata specification.

### Priority 3: Spell out picklist values as line-by-line lists, never inline with parentheses
**Evidence**: `VAT_Invoice_Type` values `"Full Tax Invoice (>= R5,000)"` and `"Abbreviated (< R5,000)"` were corrupted to `"Full Tax Invoice (>= R5"` / `"000)"`. The parenthesis + comma combination caused Zia's tokenizer to split at `,0`. **Plan B**: List each picklist value on its own numbered line in the BRD with no special characters: `1. None`, `2. Abbreviated Invoice - under R5000`, `3. Full Tax Invoice - R5000 and above`. Avoid parentheses, angle brackets, and currency symbols inside picklist value names.

### Priority 4: State field link_names explicitly (not just display names)
**Evidence**: `actor` → `actor_role`, `comments` → `notes`, `name` → `client_name`/`department_name`, `is_active` dropped, `client_id`/`department_id` auto-numbers dropped. Zia used its own naming conventions when the BRD described fields by display name only. **Plan B**: For every field, include a "Technical field name (link_name)" column in the BRD's field tables: e.g., "Display: Actor | Link name: actor | Type: Text". This gives Zia an explicit link_name to use.

### Priority 5: Explicitly list fields that must be `private=true` / hidden
**Evidence**: `Retention_Expiry_Date`, `Parent_Claim_ID`, `Department_Shadow`, `Client_Shadow`, `Key_1/2_Approver/Timestamp`, and `Requires_Dual_Approval` all had `private=true` in the original; all were either dropped or had the flag removed by Zia. **Plan B**: Add a dedicated section "Hidden fields — set private=true and do not display in reports" with a flat list. Mark them as system/audit fields not for end-user display.

### Priority 6: Separate `category` picklists for `expense_claims` and `gl_accounts`
**Evidence**: The original's `expense_claims.category` and `gl_accounts.expense_category` used the same set of 7 values; Zia generated different values for both (Training/Travel/Utilities/Office Supplies/Meals/Marketing/Other instead of Travel/Accommodation/Meals & Entertainment/etc.). The values Zia chose appear to be generic guesses. **Plan B**: List the exact 7 category values in both the expense_claims field specification and the gl_accounts field specification in the BRD, using consistent wording. Do not refer to one as "same as above" — repeat the list verbatim in both places.

### Priority 7: State that `Supporting_Documents` must be a file-upload field
**Evidence**: `Supporting_Documents` changed from `type = upload file` (original, max 10 files, browsable from Drive) to `type = text` (Zia line 412-414). **Plan B**: Explicitly note this is a file attachment field: "Supporting Documents: file upload field, not a text field. Must accept PDF/JPG/PNG attachments. Required." Then accept that Zia may still render it as text and plan to fix it manually post-import — but at least the intent is documented for the second attempt.

### Priority 8: Spell out the role hierarchy as a tree
**Evidence**: Original has a 4-level hierarchy `CEO > HoD > Line Manager > Employee` (plus Finance Director as side branch). Zia generated a flat `CEO` with no children. Role `HoD` was renamed to `Head of Department (HoD)` — breaking all `isUserInRole("HoD")` calls in Deluge. **Plan B**: Add a section "Role hierarchy (must be exact)": `CEO (top) → Head of Department (HoD) → Line Manager → Employee`. Use the exact short names as they will appear in `isUserInRole()` calls. Also declare `Finance Director` as a peer of HoD under CEO.

### Priority 9: Mark auto-number fields explicitly
**Evidence**: `client_id` (clients), `department_id` (departments), `claim_id` (expense_claims) — all auto-number fields — were dropped by Zia. **Plan B**: Add "Auto-number field: system-generated sequential ID, starts at 1, read-only, do not prompt user" for each. Consider whether BRD should describe these as "system fields" since Zia may simply not support `type = autonumber`.

### Priority 10: Address the Blueprint vs. Approval-Process distinction
**Evidence**: Zia generated Blueprint state machines with stage names derived from the BRD, but with empty transition actions. The original used Zoho Creator `approval` type workflows with Deluge scripting. The Blueprint stages (`"Claim Submitted"`, `"Claim Under Review"`, etc.) do not match the status picklist values (`"Submitted"`, `"Pending LM Approval"`, etc.). **Plan B**: Remove all workflow/process description from the BRD's automation section (since Zia cannot generate Deluge code anyway). Instead, direct the BRD's process description into a separate "Manual Implementation Notes" appendix — not in the main structured specification. This prevents Zia from generating conflicting Blueprint scaffolding over the real forms.

### Priority 11: Declare lookup `displayformat` explicitly
**Evidence**: `approval_history.claim` lookup displays `[Email]` in Zia (line 30) instead of `[claim_id]` (original). `expense_claims.department` and `expense_claims.client` use `displayformat = [" - " + name]` referencing the field name `name` — which Zia renamed to `department_name`/`client_name`. **Plan B**: For every lookup field, state: "Display format: show [claim_id] from the linked record" as explicit text in the BRD. This gives Zia a clear instruction on which field to display.

### Priority 12: Request `others option = false` / closed picklists
**Evidence**: Every picklist in Zia's output has `others option = true` (allows free-text entry not in the list). The original had all picklists closed (no `others option`). For status, category, and VAT type fields, open picklists create data integrity problems. **Plan B**: Add a global instruction: "All picklists are closed (no free-text option). Do not allow custom entries." Then list `others option = false` next to each picklist definition.

---

*End of diff report. Prepared against original (3,656 lines) and Zia-built (2,985 lines) .ds files, 2026-04-24.*
