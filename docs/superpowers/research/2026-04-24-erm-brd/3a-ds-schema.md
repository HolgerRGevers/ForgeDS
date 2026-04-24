# ERM .ds Schema Ingest
Source: C:\Users\User\OneDrive\Documents\GitHub\Expense_Reimbursement_Manager\exports\Expense_Reimbursement_Management-stage.ds
Forms: 6
Total fields: 54
Reports: 10
Lookups: 5
Subforms: 0

---

## Application Header

- **App link_name**: (not explicitly declared as a link_name; the application block uses display name directly)
- **App display_name**: `Expense Reimbursement Management`
- **Author**: holger.gevers360
- **Generated on**: 06-Apr-2026 13:04:52
- **Version**: 1.0
- **Date format**: dd-MMM-yyyy
- **Time zone**: Africa/Johannesburg
- **Time format**: 24-hr

---

## approval_history — Approval History

Audit log recording every action taken on an expense claim during the approval workflow.

| link_name | label | type | required | unique | max_len | default | picklist/formula/lookup_target | notes |
|---|---|---|---|---|---|---|---|---|
| claim | Claim | lookup | — | — | — | — | `lookup→expense_claims` (values=expense_claims.ID, displayformat=[claim_id], allow new entries) | sortorder=ascending; help: "The expense claim this audit record relates to." |
| action_1 | Action | pick list | — | — | — | — | pick[…see Picklist Appendix: action_1…] | help: "The action taken: Submitted, Approved (LM/HoD), Rejected, Escalated, or Resubmitted." |
| actor | Actor | text | — | — | — | — | — | help: "The person or system that performed the action." |
| timestamp | Timestamp | date time | — | — | — | — | — | timedisplayoptions="hh:mm:ss"; alloweddays=0-6; help: "Date and time the action was recorded." |
| comments | Comments | rich text (textarea) | — | — | — | — | — | height=100px; help: "Details about the action, including amounts, GL codes, or rejection reasons." |

**Form-level notes**: Has a Level 3 approval process block (Finance Director role) with on_approve and on_reject Deluge scripts embedded in the form's `actions` block. These scripts are workflow automation (not schema fields) and are excluded per instructions.

---

## approval_thresholds — Approval Thresholds

Configuration table defining the tiered approval thresholds and dual-key authorization rules for the workflow.

| link_name | label | type | required | unique | max_len | default | picklist/formula/lookup_target | notes |
|---|---|---|---|---|---|---|---|---|
| tier_name | Tier Name | text | — | — | — | — | — | help: "Name of the approval tier (e.g., Tier 1 - Line Manager)." |
| max_amount_zar | Max Amount ZAR | currency (ZAR) | — | — | — | — | — | help: "Maximum claim amount (ZAR) this tier can approve. Claims above this escalate to the next tier." |
| approver_role | Approver Role | text | — | — | — | — | — | help: "The Zoho Creator role that approves claims at this tier." |
| Active | Active | boolean (checkbox) | — | — | — | true | — | help: "Whether this threshold tier is currently active in the approval workflow." |
| Tier_Order | Tier Order | number | — | — | — | 0 | — | help: "Numeric order of this tier in the escalation chain. Lower numbers approve first." |
| Requires_Dual_Approval | Requires Dual Approval | boolean (checkbox) | — | — | — | false | — | help: "Whether this tier triggers dual-approval (two-key) authorization." |
| Dual_Approval_Role | Dual Approval Role | text | — | — | — | — | — | help: "Role that acts as Key 2 approver when dual-approval is required." |
| Dual_Threshold_ZAR | Dual Threshold ZAR | currency (ZAR) | — | — | — | — | — | help: "Amount threshold (ZAR) above which dual-approval is required." |

---

## clients — Clients

Reference lookup table of clients available for selection on expense claims.

| link_name | label | type | required | unique | max_len | default | picklist/formula/lookup_target | notes |
|---|---|---|---|---|---|---|---|---|
| client_id | Client ID | auto number | — | — | — | start index=1 | — | help: "Auto-generated client identifier." |
| name | Name | text | — | — | — | — | — | help: "Client name as it appears in dropdown selections." |
| is_active | Active | boolean (checkbox) | — | — | — | true | — | help: "Whether this client is currently active and available for selection." |

---

## departments — Departments

Reference lookup table of departments available for selection on expense claims.

| link_name | label | type | required | unique | max_len | default | picklist/formula/lookup_target | notes |
|---|---|---|---|---|---|---|---|---|
| department_id | Department ID | auto number | — | — | — | start index=1 | — | help: "Auto-generated department identifier." |
| name | Name | text | — | — | — | — | — | help: "Department name as it appears in dropdown selections." |
| is_active | Active | boolean (checkbox) | — | — | — | true | — | help: "Whether this department is currently active and available for selection." |

---

## expense_claims — Expense Claims

Core transaction form; each record is one employee expense reimbursement claim moving through the multi-tier approval workflow.

| link_name | label | type | required | unique | max_len | default | picklist/formula/lookup_target | notes |
|---|---|---|---|---|---|---|---|---|
| Employee_Name1 | Employee Name | name (compound) | yes (`must have`) | — | — | — | — | Sub-fields: prefix (hidden, pick[Mr., Mrs., Ms.]), first_name, last_name, suffix (hidden); personal data=true; help: "Your full name as registered in the system." |
| Email | Email | pick list (Users module) | yes (`must have`) | — | — | — | — | module=users, displayformat=[emailid]; personal data=true; help: "Notification routing target." |
| Submission_Date | Submission Date | date time | yes (`must have`) | — | — | — | — | timedisplayoptions="hh:mm:ss"; alloweddays=0-6; help: "Date and time the claim was submitted. Set automatically." |
| claim_id | Claim ID | auto number | — | — | — | start index=1 | — | help: "System-generated unique claim number." |
| department | Department | lookup | — | — | — | — | `lookup→departments` (values=departments.ID, displayformat=[" - " + name]) | sortorder=ascending; help: "Select your department." |
| Claim_Reference | Claim Reference | text | yes (`must have`) | — | — | — | — | help: "Auto-generated reference (EXP-0001 format)." |
| client | Client | lookup | — | — | — | — | `lookup→clients` (values=clients.ID, displayformat=[" - " + name]) | sortorder=ascending; help: "Select the client this expense relates to." |
| Expense_Date | Expense Date | date | — | — | — | — | — | alloweddays=0-6; help: "Date the expense was incurred. Cannot be in the future or older than 90 days." |
| Department_Shadow | Department Shadow | text | — | — | — | — | — | private=true; denormalized text copy of department.name; no help text |
| category | Category | pick list | — | — | — | — | pick[Travel, Accommodation, Meals & Entertainment, Office Supplies, Communication, Professional Services, Other] | help: "Select the expense category. Determines GL code mapping and VAT requirements." |
| Client_Shadow | Client Shadow | text | — | — | — | — | — | private=true; denormalized text copy of client.name; no help text |
| amount_zar | Amount ZAR | currency (ZAR) | — | — | — | — | — | help: "Total expense amount in South African Rand. Must be greater than zero." |
| Supporting_Documents | Supporting Documents | file upload | yes (`must have`) | — | — | — | — | file count=10; browse=local_drive, google_docs, zoho_docs; help: "Upload receipts or invoices. Required by SARS S11(a)." |
| description | Description | rich text (textarea) | — | — | — | — | — | height=100px; help: "Describe the business purpose of this expense. Required for SARS S11(a) substantiation." |
| VAT_Invoice_Type | VAT Invoice Type | pick list | — | — | — | — | pick[None, Abbreviated (< R5,000), Full Tax Invoice (>= R5,000)] | help: "Claims >= R5,000 require a Full Tax Invoice per SARS VAT rules." |
| POPIA_Consent | POPIA Consent | boolean (checkbox) | — | — | — | false | — | help: "I consent to the processing of my personal data for expense reimbursement purposes in accordance with POPIA." |
| status | Status | pick list | — | — | — | — | pick[Draft, Submitted, Pending LM Approval, Pending HoD Approval, Pending Second Key, Key 2 Dispute, Approved, Rejected, Resubmitted] | help: "Current claim status. Updated automatically by the approval workflow." |
| Rejection_Reason | Rejection Reason | rich text (textarea) | — | — | — | — | — | height=100px; help: "Reason for rejection, provided by the approver. Read-only for employees." |
| Version | Version | number | — | — | — | 1 | — | help: "Claim version number. Incremented each time the claim is resubmitted after rejection." |
| Retention_Expiry_Date | Retention Expiry Date | date | — | — | — | — | — | private=true; alloweddays=0-6; help: "SARS Tax Administration Act S29: 5-year retention from submission date." |
| Parent_Claim_ID | Parent Claim ID | pick list (self-ref) | — | — | — | — | `lookup→expense_claims` (values=expense_claims.ID, displayformat=[claim_id]) | private=true; type declared as picklist but references own form; sortorder=ascending |
| gl_code | GL Code | lookup | — | — | — | — | `lookup→gl_accounts` (values=gl_accounts.ID, displayformat=[gl_code]) | sortorder=ascending; help: "General Ledger code assigned during approval." |
| Requires_Dual_Approval | Requires Dual Approval | boolean (checkbox) | — | — | — | false | — | private=true; help not present |
| Key_1_Approver | Key 1 Approver | text | — | — | — | — | — | private=true; stores login user of first Key approver |
| Key_1_Timestamp | Key 1 Timestamp | date time | — | — | — | — | — | private=true; timedisplayoptions="hh:mm:ss"; alloweddays=0-6 |
| Key_2_Approver | Key 2 Approver | text | — | — | — | — | — | private=true; stores login user of second Key approver |
| Key_2_Timestamp | Key 2 Timestamp | date time | — | — | — | — | — | private=true; timedisplayoptions="hh:mm:ss"; alloweddays=0-6 |

**Form-level validation (on validate workflow)**: (1) Expense_Date must not be in the future; (2) Expense_Date must not be older than 90 days; (3) amount_zar must be > 0; (4) Supporting_Documents must not be null; (5) duplicate detection on same date+amount+user; (6) amount_zar >= 5000 requires VAT_Invoice_Type = "Full Tax Invoice (>= R5,000)"; (7) POPIA_Consent must be true.

---

## gl_accounts — GL Accounts

Reference table mapping General Ledger account codes to expense categories, SARS provisions, and risk levels.

| link_name | label | type | required | unique | max_len | default | picklist/formula/lookup_target | notes |
|---|---|---|---|---|---|---|---|---|
| gl_code | GL Code | text | — | — | — | — | — | help: "The General Ledger account code (e.g., 6200). Must match your accounting system." |
| account_name | Account Name | text | — | — | — | — | — | help: "Descriptive name for this GL account (e.g., Travel - Local Transport)." |
| expense_category | Expense Category | pick list | — | — | — | — | pick[Travel, Accommodation, Meals & Entertainment, Office Supplies, Communication, Professional Services, Other] | help: "The expense category this GL code maps to. Used for auto-assignment during approval." |
| receipt_required | Receipt Required | boolean (checkbox) | — | — | — | true | — | help: "Whether a receipt/invoice is required for expenses in this category. Default: Yes (SARS S11(a))." |
| SARS_Provision | SARS Provision | text | — | — | — | — | — | help: "Maps each GL code to SARS deduction provision, e.g. \"S11(a) + S8(1)(a)\"." |
| Risk_Level | Risk Level | pick list | — | — | — | Standard | pick[Standard, Elevated, High] | help: "ISO 37001: Categories prone to bribery risk receive enhanced scrutiny." |
| Active | Active | boolean (checkbox) | — | — | — | true | — | help: "Whether this GL code is currently available for assignment." |

---

## Reports

| name | source_form | filter_expr | sort | visible_columns | notes |
|---|---|---|---|---|---|
| expense_claims_Report | expense_claims | — | — | claim_id, department, client, category, amount_zar (total/avg/min/max), description, status, gl_code | displayName="All Expense Claims"; list view; conditional formatting on category (Entertainment, Meals, Travel) |
| gl_accounts_Report | gl_accounts | — | — | gl_code, account_name, expense_category, receipt_required | displayName="All Gl Accounts"; list view; conditional formatting on expense_category (Entertainment, Meals, Supplies) |
| gl_accounts_by_expense_category | gl_accounts | — | — | gl_code, account_name, expense_category, receipt_required | displayName="Expense Categories"; kanban view; display field=expense_category |
| approval_history_Report | approval_history | — | — | claim, action_1, actor, timestamp, comments | displayName="All Approval Histories"; list view; conditional formatting on action_1 (Approved, Rejected, Submitted) |
| approval_thresholds_Report | approval_thresholds | — | — | tier_name, max_amount_zar (total/avg/min/max), approver_role | displayName="All Approval Thresholds"; list view |
| clients_Report | clients | — | — | client_id, name, is_active | displayName="All Clients"; list view |
| departments_Report | departments | — | — | department_id, name, is_active | displayName="All Departments"; list view |
| Audit_Trail | approval_history | — | `timestamp ascending` | claim, action_1, actor, timestamp, comments, claim.claim_id | displayName="Audit Trail"; list view; claim displayed with comma delimiter; includes related field claim.claim_id |
| pending_approvals_manager | expense_claims | `status == "Pending LM Approval" \|\| status == "Pending HoD Approval"` | `Submission_Date ascending` | Employee_Name1, Email, Submission_Date, claim_id, Claim_Reference, Expense_Date, department, client, category, amount_zar (total/avg/min/max), Supporting_Documents, description, status, Rejection_Reason, Version, Parent_Claim_ID, gl_code, Department_Shadow | displayName="Pending Approvals Manager"; list view; group by status/Department_Shadow/Employee_Name1/category; conditional formatting on status (Pending LM Approval, Pending HoD Approval via Parent_Claim_ID) |
| My_Claims | expense_claims | `Added_User == zoho.loginuser` | `Submission_Date descending` | Employee_Name1, Email, Submission_Date, claim_id, Claim_Reference, Expense_Date, department, client, category, amount_zar, Supporting_Documents, description, status, Rejection_Reason, Version, Parent_Claim_ID, gl_code | displayName="My Claims"; list view; group by claim_id/Expense_Date/Submission_Date/category/amount_zar/status/Version; conditional formatting on status (Approved, Rejected, Pending LM Approval, Pending HoD Approval, Resubmitted) |
| Expense_Summary | expense_claims | — | — | Email, Submission_Date, claim_id, Parent_Claim_ID.Department_Shadow, Client_Shadow, category, amount_zar, status | displayName="Expense Summary"; pivot table; layout=4; records displayed=all_records; export=false; drilldown=false; based on autoview Autoview_1775232194200_expense_claims |

---

## Relationships

### Lookups

| from_form | field | to_form |
|---|---|---|
| approval_history | claim | expense_claims |
| expense_claims | department | departments |
| expense_claims | client | clients |
| expense_claims | gl_code | gl_accounts |
| expense_claims | Parent_Claim_ID | expense_claims (self-referential) |

### Subforms

No subform relationships declared in this application.

---

## Picklist Appendix

### action_1 (approval_history.action_1)

Values: Submitted, Submitted (Self-approval bypass), Approved (LM), Approved (HoD), Approved (Key 1), Approved (Key 2), Rejected, Rejected (Key 2), Reconsidered (Key 1), Escalated (SLA Breach), Resubmitted, Warning

Used by: `approval_history.action_1`

---

### category / expense_category (shared values)

Values: Travel, Accommodation, Meals & Entertainment, Office Supplies, Communication, Professional Services, Other

Used by:
- `expense_claims.category` (label: "Category")
- `gl_accounts.expense_category` (label: "Expense Category")

---

### status (expense_claims.status)

Values: Draft, Submitted, Pending LM Approval, Pending HoD Approval, Pending Second Key, Key 2 Dispute, Approved, Rejected, Resubmitted

Used by: `expense_claims.status`

---

### VAT_Invoice_Type (expense_claims.VAT_Invoice_Type)

Values: None, Abbreviated (< R5,000), Full Tax Invoice (>= R5,000)

Used by: `expense_claims.VAT_Invoice_Type`

---

### Risk_Level (gl_accounts.Risk_Level)

Values: Standard, Elevated, High

Default: Standard

Used by: `gl_accounts.Risk_Level`

---

### Employee_Name1 prefix sub-field (expense_claims.Employee_Name1 compound name field)

Values: Mr., Mrs., Ms.

Used by: `expense_claims.Employee_Name1` prefix sub-component (visibility=false in form, hidden from default display)
