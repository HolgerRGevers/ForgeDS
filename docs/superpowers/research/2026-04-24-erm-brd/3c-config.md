# ERM Config Ingest

## Custom APIs

| Name | Params (type) | Returns (shape) | Method | Purpose |
|------|---|---|---|---|
| Get_Dashboard_Summary | department (Text, opt), date_from (Date, opt), date_to (Date, opt) | pending_count (Number), approved_count (Number), rejected_count (Number), total_amount_pending (Decimal), total_amount_approved (Decimal) | POST | Return aggregated claim statistics (pending/approved/rejected counts, amounts by dept) |
| Get_Claim_Status | claim_reference (Text, req) | status (Text), amount_zar (Decimal), department (Text), category (Text), submitted_date (Date), last_action (Text) | POST | Query claim status by reference number for external systems |
| Get_ESG_Summary | date_from (Date, opt), date_to (Date, opt), department (Text, opt) | total_carbon_kg (Decimal), claim_count (Number) | POST | Return carbon estimates and ESG category breakdowns for sustainability reporting |
| Get_SLA_Breaches | threshold_days (Number, opt), department (Text, opt) | breached_count (Number), at_risk_count (Number) | POST | Return claims approaching or past SLA deadlines |

**Count: 4 custom APIs**

## Widgets

No widgets declared in `forgeds.yaml`.

**Count: 0 widgets**

## Named Types

No named types declared in `forgeds.yaml`.

**Count: 0 types**

## Roles & Permissions

### Role Definitions

| Role | Parent | Purpose | Can Add Claims | Can View Claims | Can Approve | Notes |
|------|--------|---------|---|---|---|---|
| Employee | -- | Base role for all staff | Self only | Own claims only | No | |
| Line Manager | Employee | Stage 1 approval | Yes | Pending LM claims + own | Yes (Stage 1) | Self-approval prevention applies |
| Head of Department (HoD) | Line Manager | Stage 2 approval & Key 1 | Yes | Pending HoD claims + all | Yes (Stage 2 / Key 1) | Final authority or Key 1 for dual-approval |
| Finance Director | CEO peer | Key 2 dual approval | No | Pending Second Key claims + all | Yes (Key 2 only) | Cannot be same person as Key 1 (King IV P7) |
| Finance Accountant | -- | GL account & export management | No | All claims + GL accounts | No | Full GL account CRUD, export |
| System Administrator | -- | Full system control | Yes (all forms) | All records | -- | Full CRUD + import/export |
| Developer | -- | Development access | No | No | No | Dev access only |

### Customer Portal Roles

| Role | Access |
|------|--------|
| Client Representative | View clients, expense_claims, approval_history |
| Vendor | View clients, expense_claims, approval_history |
| Customer | Default portal profile |

### Field Permissions (CRUD Matrix)

| Field | Employee | Line Manager | HoD | Finance Director | Finance/Admin |
|-------|----------|-------------|-----|-----------------|---------------|
| Status | R | R | R | R | C/R/U/D |
| GL_Code | Hidden | R | R | R | C/R/U/D |
| Rejection_Reason | R | C/R/U | C/R/U | C/R/U | C/R/U/D |
| Amount | C/R/U (create) | R | R | R | R |
| Key_1_Approver | Hidden | Hidden | Hidden | R | Hidden (private) |
| Key_1_Timestamp | Hidden | Hidden | Hidden | R | Hidden (private) |
| Requires_Dual_Approval | Hidden | Hidden | Hidden | R | Hidden (private) |
| Department_Shadow | Hidden | Hidden | Hidden | Hidden | Hidden (private) |
| Client_Shadow | Hidden | Hidden | Hidden | Hidden | Hidden (private) |
| Parent_Claim_ID | Hidden | Hidden | Hidden | Hidden | Hidden (private) |

**Count: 7 roles**

## Email Templates

| Template Name | To | CC | Subject | Trigger | Variables |
|---|---|---|---|---|---|
| submit_notify_lm | line_manager | -- | Expense Claim {claim_id} requires your approval | Submission | claim_id, Employee_Name1, amount_zar |
| submit_self_approval_bypass | hod | -- | Expense Claim {claim_id} - Direct HoD Review | Submission by Line Manager | claim_id |
| resubmit_notify_lm | line_manager | -- | RESUBMITTED - Claim {claim_id} (v{Version}) | Resubmission | claim_id, Version |
| resubmit_self_approval_bypass | hod | -- | RESUBMITTED - Claim {claim_id} (v{Version}) - Direct HoD Review | Resubmission by Line Manager | claim_id, Version |
| lm_approved_final | Employee (Email field) | -- | Expense Claim {claim_id} - Approved | LM final approval | claim_id, amount_zar |
| lm_approved_escalate | hod | -- | Expense Claim {claim_id} - Requires HoD Approval | LM approved, amount over threshold | claim_id, amount_zar |
| lm_rejected | Employee (Email field) | -- | Expense Claim {claim_id} - Rejected | LM rejection | claim_id, amount_zar, rejectReason |
| hod_approved | Employee (Email field) | -- | Expense Claim {claim_id} - Final Approval | HoD final approval | claim_id, amount_zar |
| hod_rejected | Employee (Email field) | -- | Expense Claim {claim_id} - Rejected by HoD | HoD rejection | claim_id, amount_zar, rejectReason |
| sla_escalation | hod | -- | SLA BREACH - Claim {claim_id} escalated | LM failed to act within 3 days | claim_id, amount_zar |
| sla_reminder | line_manager | hod | REMINDER - Claim {claim_id} awaiting approval | Pending >2 days | claim_id |
| key1_approved_dual_required | finance_director | -- | TWO-KEY APPROVAL - Claim {claim_id} requires your sign-off | HoD approved (dual approval required) | claim_id, amount_zar |
| key2_approved_final | Employee (Email field) | -- | Expense Claim {claim_id} - Final Approval (Two-Key) | Finance Director (Key 2) approval | claim_id, amount_zar |
| key2_rejected_dispute | hod | -- | TWO-KEY DISPUTE - Claim {claim_id} rejected by Key 2 | Finance Director (Key 2) rejection | claim_id, amount_zar, rejectReason |
| key2_dispute_notify_employee | Employee (Email field) | -- | Expense Claim {claim_id} - Under Review | Two-Key dispute | claim_id, amount_zar |
| key1_reconsider_override | finance_director | -- | TWO-KEY RECONSIDERATION - Claim {claim_id} re-approved by Key 1 | HoD overrides Key 2 rejection | claim_id, amount_zar |
| key2_sla_reminder | finance_director | admin | REMINDER (Key 2) - Claim {claim_id} awaiting approval | Key 2 pending >2 days | claim_id |
| key2_sla_escalation | Admin (zoho.adminuserid) | -- | SLA BREACH (Key 2) - Claim {claim_id} escalated | Finance Director failed to act within 3 days | claim_id, amount_zar |

**Count: 19 email templates**

## Field Descriptions

| Form.Field | Description |
|---|---|
| expense_claims.Employee_Name1 | Your full name as registered in the system. Auto-populated on form load. |
| expense_claims.Email | Notification routing target. |
| expense_claims.Submission_Date | Date and time the claim was submitted. Set automatically. |
| expense_claims.claim_id | System-generated unique claim number. Used for tracking and reference. |
| expense_claims.department | Select your department. Used for reporting and approval routing. |
| expense_claims.Claim_Reference | Auto-generated reference (EXP-0001 format). Use this when communicating about the claim. |
| expense_claims.client | Select the client this expense relates to. Choose Internal for non-client expenses. |
| expense_claims.Expense_Date | Date the expense was incurred. Cannot be in the future or older than 90 days. |
| expense_claims.category | Select the expense category. Determines GL code mapping and VAT requirements. |
| expense_claims.amount_zar | Total expense amount in South African Rand (ZAR). Must be greater than zero. |
| expense_claims.Supporting_Documents | Upload receipts or invoices. Required by SARS S11(a) for all claims. Max 10 files. |
| expense_claims.description | Describe the business purpose of this expense. Required for SARS S11(a) substantiation. |
| expense_claims.VAT_Invoice_Type | Select invoice type. Claims >= R5,000 require a Full Tax Invoice per SARS VAT rules. |
| expense_claims.POPIA_Consent | I consent to the processing of my personal data for expense reimbursement purposes in accordance with POPIA. |
| expense_claims.status | Current claim status. Updated automatically by the approval workflow. |
| expense_claims.Rejection_Reason | Reason for rejection, provided by the approver. Read-only for employees. |
| expense_claims.Version | Claim version number. Incremented each time the claim is resubmitted after rejection. |
| expense_claims.gl_code | General Ledger code assigned during approval. Maps the expense to the correct account. |
| expense_claims.Retention_Expiry_Date | SARS Tax Administration Act S29: 5-year retention from submission date. |
| approval_history.claim | The expense claim this audit record relates to. |
| approval_history.action_1 | The action taken: Submitted, Approved (LM/HoD), Rejected, Escalated, or Resubmitted. |
| approval_history.actor | The person or system that performed the action. |
| approval_history.timestamp | Date and time the action was recorded. |
| approval_history.comments | Details about the action, including amounts, GL codes, or rejection reasons. |
| approval_thresholds.tier_name | Name of the approval tier (e.g., Tier 1 - Line Manager). |
| approval_thresholds.max_amount_zar | Maximum claim amount (ZAR) this tier can approve. Claims above this escalate to the next tier. |
| approval_thresholds.approver_role | The Zoho Creator role that approves claims at this tier. |
| approval_thresholds.Tier_Order | Numeric order of this tier in the escalation chain. Lower numbers approve first. |
| approval_thresholds.Active | Whether this threshold tier is currently active in the approval workflow. |
| approval_thresholds.Requires_Dual_Approval | When enabled, claims exceeding Dual_Threshold_ZAR require two independent approvers (Two-Key). |
| approval_thresholds.Dual_Approval_Role | The Zoho Creator role that serves as Key 2 approver for dual-approval claims. |
| approval_thresholds.Dual_Threshold_ZAR | Claims above this amount require two-key approval when dual approval is enabled. |
| gl_accounts.gl_code | The General Ledger account code (e.g., 6200). Must match your accounting system. |
| gl_accounts.account_name | Descriptive name for this GL account (e.g., Travel - Local Transport). |
| gl_accounts.expense_category | The expense category this GL code maps to. Used for auto-assignment during approval. |
| gl_accounts.receipt_required | Whether a receipt/invoice is required for expenses in this category. Default: Yes (SARS S11(a)). |
| gl_accounts.SARS_Provision | Maps each GL code to SARS deduction provision, e.g. S11(a) + S8(1)(a). Used in compliance reporting. |
| gl_accounts.Risk_Level | ISO 37001: Categories prone to bribery risk receive enhanced scrutiny. |
| gl_accounts.Active | Whether this GL code is currently available for assignment. |
| gl_accounts.ESG_Category | ISSB/GRI sustainability category: Travel Emissions, Energy, Waste, Social, or None. |
| gl_accounts.Carbon_Factor | Estimated kg CO2e per ZAR spent. DEFRA-adapted emission factor for SA energy mix. |
| gl_accounts.GRI_Indicator | GRI Standards indicator code mapped to this GL account (e.g., GRI 305-3). |
| departments.department_id | Auto-generated department identifier. |
| departments.name | Department name as it appears in dropdown selections. |
| departments.is_active | Whether this department is currently active and available for selection. |
| clients.client_id | Auto-generated client identifier. |
| clients.name | Client name as it appears in dropdown selections. |
| clients.is_active | Whether this client is currently active and available for selection. |
| compliance_config.Config_Key | Unique compliance setting name (e.g., ORG_TYPE, ESG_REPORTING). |
| compliance_config.Config_Value | Setting value. Interpretation depends on Config_Key. |
| compliance_config.Description | Human-readable explanation of this compliance setting. |
| compliance_config.Active | Whether this compliance setting is currently active. |

**Count: 54 field descriptions**

## UI Standards

- **Field Descriptions**: Every user-facing field must have help text covering purpose, format, constraints, compliance context (SARS S11(a), POPIA, VAT rules, retention deadlines). Private/shadow fields and self-referential FKs excluded.
- **Report Design**: Keep reports that serve governance purposes (filtered lists for roles/workflows, full lists with aggregates, Kanban with meaningful categorization, audit trails). Remove boilerplate auto-generated reports.
- **Report Menu Permissions**: Transaction reports get Edit/View Record only. Reference data (departments, clients, GL accounts, thresholds) get View Record only. Audit trails get View Record only. Block Delete, Duplicate, Import, Export, Print from reference/audit menus.
- **Conditional Formatting**: Status-based colouring (Approved = Teal/Green #1bbc9b, Rejected = Red #e84c3d, Pending = Amber/Magenta #bd588b), category-based colouring (Entertainment/high-risk = Purple #765f89, Escalated = Dark teal #107c91). Avoid purely decorative, maintain consistency.
- **Form Layout Order**: Identity (Employee Name, Email, Claim ID) → Event (Expense Date, Category, Description, Amount) → Evidence (Supporting Documents, VAT Invoice Type) → Compliance (POPIA Consent) → Status/Tracking (Status, GL Code, Version, Rejection Reason) → Hidden (shadow fields, Parent Claim ID).
- **Field Visibility by Role**: Status read-only all roles. GL Code hidden for employees, read-only for managers/HoD, editable for finance. Rejection Reason read-only for employees, editable for managers and above. Amount editable on create (employees) only. Shadow fields and retention expiry hidden except finance visibility on retention.
- **Navigation Structure**: Organize by role/workflow, not database tables. Sections: Dashboard (KPI, all roles), Expense Claims (submit/track/approve, employee + manager), Configuration (thresholds, GL codes, admin + finance), Audit & Compliance (audit trail, auditor + admin), Reference Data (departments, clients, admin only).
- **Accessibility Checklist**: Every field has description. Descriptions explain purpose + format + compliance. Boilerplate reports removed. Reference/audit menus restricted. Consistent colour scheme used. Status fields read-only. Shadow/private fields hidden. Navigation by workflow. Lookup allow-new-entries removed (unless intentional).

## Deluge Manifest

Summary of all declared script contexts and locations:

| Script Name | Form | Location | Event/Trigger | Context | Purpose |
|---|---|---|---|---|---|
| expense_claim.on_validate | expense_claims | Form > Workflow > On Validate | Form submission (before save) | form-workflow | Hard-stop validation: future dates, 90-day window, positive amount, mandatory receipt (SARS S11(a)) |
| expense_claim.on_success | expense_claims | Form > Workflow > On Success | After successful form submission | form-workflow | Self-approval prevention (King IV P1), routing, audit trail, LM notification |
| expense_claim.on_edit | expense_claims | Form > Workflow > On Edit | Record edit/save | form-workflow | Resubmission handler: version increment, status reset, self-approval check |
| expense_claim.on_load.auto_populate | expense_claims | Form > Workflow > On Load | Form load (on add) | form-workflow | Auto-populate Employee_Name and Email from logged-in user |
| expense_claim.on_success.generate_ref | expense_claims | Form > Workflow > On Success | After successful form submission | form-workflow | Auto-generate claim reference in EXP-0005 format |
| expense_claim.on_success.fill_shadows | expense_claims | Form > Workflow > On Success | After successful form submission or edit | form-workflow | Populate denormalized shadow text fields for Department and Client |
| lm_approval.on_approve | expense_claims | Approval Process > Line Manager Approval > Level 1 > On Approve | Approver clicks Approve | approval-script | Threshold-based conditional routing. Under threshold = final approval + GL. Over = escalate to HoD. |
| lm_approval.on_reject | expense_claims | Approval Process > Line Manager Approval > Level 1 > On Reject | Approver clicks Reject | approval-script | Set status to Rejected, log audit trail, notify employee |
| hod_approval.on_approve | expense_claims | Approval Process > HoD Approval > Level 1 > On Approve | Approver clicks Approve | approval-script | Final approval, GL code population, audit trail, notification |
| hod_approval.on_reject | expense_claims | Approval Process > HoD Approval > Level 1 > On Reject | Approver clicks Reject | approval-script | Set status to Rejected, log audit trail, notify employee |
| finance_approval.on_approve | expense_claims | Approval Process > Line Manager Approval > Level 3 > On Approve | Approver clicks Approve | approval-script | Two-Key second approval (Key 2). Validates independence, sets final approval. |
| finance_approval.on_reject | expense_claims | Approval Process > Line Manager Approval > Level 3 > On Reject | Approver clicks Reject | approval-script | Two-Key second approval rejection. Routes to Key 2 Dispute for HoD reconsideration. |
| sla_enforcement_daily | expense_claims | Workflow > Schedules > SLA_Enforcement_Daily | Scheduled (daily) | scheduled | SLA enforcement: 2-day reminder, 3-day auto-escalation to HoD |
| get_dashboard_summary | (none) | Microservices > Custom API > Get_Dashboard_Summary | API call (REST/widget) | custom-api | Return aggregated claim statistics (pending/approved/rejected counts, amounts by dept) |
| get_claim_status | (none) | Microservices > Custom API > Get_Claim_Status | API call (REST/widget) | custom-api | Query claim status by reference number for external systems |
| get_esg_summary | (none) | Microservices > Custom API > Get_ESG_Summary | API call (REST/widget) | custom-api | Return carbon estimates and ESG category breakdowns for sustainability reporting |
| get_sla_breaches | (none) | Microservices > Custom API > Get_SLA_Breaches | API call (REST/widget) | custom-api | Return claims approaching or past SLA deadlines |

## Seed Data

Files in `config/seed-data/`:

- access_table_fields.json
- approval_thresholds.json
- clients.json
- compliance_config.json
- departments.json
- field_name_mappings.json
- gl_accounts.json
- type_mappings.json

---

## Summary

| Artifact | Count |
|---|---|
| Custom APIs | 4 |
| Widgets | 0 |
| Named Types | 0 |
| Roles | 7 |
| Email Templates | 19 |
| Field Descriptions | 54 |
| Deluge Scripts | 17 |
| Seed Data Files | 8 |
