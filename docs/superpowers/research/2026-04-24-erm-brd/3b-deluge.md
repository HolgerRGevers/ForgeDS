# ERM Deluge Workflow Ingest

**Generated**: 2026-04-24  
**Source**: `C:\Users\User\OneDrive\Documents\GitHub\Expense_Reimbursement_Manager\src\deluge\`  
**Purpose**: Behavioral summary of all Deluge linting, routing, and automation scripts for BRD alignment

---

## Workflow Index

| Script | Trigger | Category | Event | Purpose (1 line) |
|---|---|---|---|---|
| finance_approval.on_approve | Approval Process > Finance Director | Approval (Key 2) | on_approve | Two-key second approval with same-person prevention check |
| finance_approval.on_reject | Approval Process > Finance Director | Approval (Key 2) | on_reject | Create Key 2 dispute, escalate back to HoD for reconsideration |
| hod_approval.on_approve | Approval Process > HoD | Approval (Key 1) | on_approve | Threshold-based routing: under threshold = final approval; over = Key 2; dispute reconsideration |
| hod_approval.on_reject | Approval Process > HoD | Approval (Key 1) | on_reject | Reject claim, log audit trail, notify employee |
| lm_approval.on_approve | Approval Process > Line Manager | Approval (Tier 1) | on_approve | Threshold-based routing: under = final approval + GL; over = escalate to HoD |
| lm_approval.on_reject | Approval Process > Line Manager | Approval (Tier 1) | on_reject | Reject claim, log audit trail, notify employee |
| expense_claim.on_validate | Expense_Claim form | Form lifecycle | on_validate | Hard-stop validation: dates, 90-day policy, amounts, receipts, VAT, POPIA, duplicates |
| expense_claim.on_load.auto_populate | Expense_Claim form | Form lifecycle | on_load | Auto-fill Employee_Name and Email from logged-in user |
| expense_claim.on_success | Expense_Claim form | Form lifecycle | on_success | Self-approval prevention, initial routing to LM, audit trail creation |
| expense_claim.on_success.fill_shadows | Expense_Claim form | Form lifecycle | on_success | Populate denormalized shadow text fields (Department, Client names) |
| expense_claim.on_success.generate_ref | Expense_Claim form | Form lifecycle | on_success | Auto-generate claim reference code "EXP-NNNN" |
| expense_claim.on_edit | Expense_Claim form | Form lifecycle | on_edit | Resubmission handler: increment version, reset approval state, self-approval check |
| sla_enforcement_daily | Scheduled job | Scheduled | daily | SLA escalation: 2-day reminder, 3-day auto-escalate LM → HoD; Key 2 → admin |

**Total**: 13 scripts  
**Approval workflows**: 6  
**Form workflows**: 7  
**Scheduled jobs**: 1

---

## Approval Workflows

### finance_approval.on_approve

**Trigger**: Finance Director clicks Approve on Pending Second Key claim  
**Context**: Two-Key Threshold Authorization (Key 2 / Finance Director)  
**Stage**: Level 3 (final dual-key authorization)

**Effect** (prose):
When a Finance Director (Key 2 approver) approves a claim, the system first validates that the approver is not the same person who gave Key 1 approval. If the same person attempts both approvals, the claim is blocked with a governance alert and status is reset to "Pending Second Key" — this enforces segregation of duties per King IV corporate governance. If the same-person check passes, the claim receives final approval: the Key_2_Approver and Key_2_Timestamp fields are populated, status becomes "Approved", and an approval_history record is logged with full dual-approval chain details (both Key 1 and Key 2 signatories). The employee receives a final approval email confirming dual-key authorization completion.

**Fields read**:
- `input.Key_1_Approver` (previous approver)
- `input.ID` (claim identifier)
- `input.claim_id` (reference number)
- `input.amount_zar` (claim amount)
- `zoho.loginuser` (current approver identity)
- `zoho.currenttime` (timestamp)

**Fields written**:
- `input.status` → "Approved" or "Pending Second Key" (if blocked)
- `input.Key_2_Approver` → current approver ID
- `input.Key_2_Timestamp` → current timestamp

**Custom APIs**: None  

**Emails**:
1. **Governance Alert** (if same-person block): to `zoho.adminuserid`, subject includes claim reference and blocked identity
2. **Final Approval** (on success): to `input.Email` (employee), subject "Expense Claim [REF] - Final Approval (Dual Key)"

**Audit trail**:
- Approval history record inserted with action "Approved (Key 2)" or "Warning" (same-person block)

**Shadows / side effects**: None

---

### finance_approval.on_reject

**Trigger**: Finance Director clicks Reject on Pending Second Key claim  
**Context**: Two-Key Threshold Authorization (Key 2 / Finance Director)  
**Stage**: Level 3 dispute creation

**Effect** (prose):
When a Finance Director (Key 2 approver) rejects a claim, the system does not immediately mark it as "Rejected"; instead, it creates a dispute state and routes the claim back to the Head of Department (Key 1 approver) for reconsideration. This design allows the HoD to either override the Finance Director's objection (by re-approving and sending for a new Key 2 cycle) or accept the rejection. The Finance Director's rejection reason is captured and communicated to both the HoD and the employee. A Key 2 Dispute record is logged in the approval_history.

**Fields read**:
- `input.ID` (claim identifier)
- `input.claim_id` (reference number)
- `input.amount_zar` (claim amount)
- `input.Rejection_Reason` (dispute reason)
- `input.Key_1_Approver` (HoD name)
- `input.Email` (employee email)
- `zoho.loginuser` (current approver)
- `zoho.currenttime` (timestamp)

**Fields written**:
- `input.status` → "Key 2 Dispute"

**Custom APIs**: None

**Emails**:
1. **To HoD**: subject "Expense Claim [REF] - Key 2 Dispute", body includes Finance Director's rejection reason and instructions to re-approve or reject
2. **To Employee**: subject "Expense Claim [REF] - Under Review", generic notification that claim is under additional review

**Audit trail**:
- Approval history record inserted with action "Rejected (Key 2)" and dispute reason

**Shadows / side effects**: None

---

### hod_approval.on_approve

**Trigger**: Head of Department clicks Approve (two scenarios)  
**Context**: Two-Key Threshold Authorization (Key 1 / HoD)  
**Stage**: Level 2 approval (with dual-threshold and dispute reconsideration logic)

**Effect** (prose):
The HoD approval script handles two distinct scenarios. **Scenario 1 (Dispute Reconsideration)**: If the claim status is "Key 2 Dispute", the HoD is overriding the Finance Director's rejection. The status is reset to "Pending Second Key", the HoD's Key 1 approval is recorded, and the claim is routed back to the Finance Director for a new approval cycle. **Scenario 2 (Normal Approval)**: The script reads the dual-approval threshold from the `approval_thresholds` configuration table. It also auto-populates the GL (General Ledger) code based on the expense category, and extracts ESG metadata (ISSB/GRI classification and carbon factor). If the claim amount exceeds the dual-threshold, the status becomes "Pending Second Key" and the Finance Director is notified; the Key 1 approval is recorded with full GL and ESG context. If the claim is under threshold, the HoD gives final approval, status becomes "Approved", and the employee is notified. In both paths, a full audit trail entry captures the threshold logic, GL code, ESG category, and estimated carbon footprint.

**Fields read**:
- `input.status` (current status, to detect dispute scenario)
- `input.ID` (claim identifier)
- `input.claim_id` (reference number)
- `input.amount_zar` (claim amount)
- `input.category` (expense category for GL lookup)
- `zoho.loginuser` (HoD identity)
- `zoho.currenttime` (timestamp)
- `input.Key_1_Approver` (for dispute context)
- `input.Email` (employee email)
- Via lookup: `approval_thresholds[Requires_Dual_Approval == true]` → `Dual_Threshold_ZAR` (fallback 5000.00)
- Via lookup: `gl_accounts[expense_category == input.category]` → `gl_code`, `ESG_Category`, `Carbon_Factor`

**Fields written**:
- `input.status` → "Pending Second Key" (over threshold or dispute override) or "Approved" (under threshold)
- `input.Key_1_Approver` → HoD user ID
- `input.Key_1_Timestamp` → current timestamp
- `input.Requires_Dual_Approval` → true (if over threshold)
- `input.gl_code` → GL account code from lookup
- `input.ESG_Category` → ESG classification from GL record
- `input.Estimated_Carbon_KG` → `amount_zar * carbon_factor`

**Custom APIs**: None (uses Zoho Creator internal form lookups)

**Emails**:
1. **Dispute scenario**: to `"financedirector.demo@yourdomain.com"`, subject "Expense Claim [REF] - HoD Override (Key 2 Dispute)"
2. **Over threshold**: to `"financedirector.demo@yourdomain.com"`, subject "Expense Claim [REF] - Requires Key 2 Approval"
3. **Under threshold**: to `input.Email` (employee), subject "Expense Claim [REF] - Final Approval"

**Audit trail**:
- Approval history record inserted with action "Reconsidered (Key 1)", "Approved (Key 1)", or "Approved (HoD)"; includes threshold comparison, GL code, ESG category, and carbon estimate

**Shadows / side effects**: 
- GL and ESG data written to claim for financial and sustainability reporting

---

### hod_approval.on_reject

**Trigger**: Head of Department clicks Reject on Pending HoD Approval claim  
**Context**: Tier 2 (HoD approval level)  
**Stage**: Level 2 rejection

**Effect** (prose):
When the HoD rejects a claim, the status is set to "Rejected" and an approval_history record is logged with the rejection reason. The employee is notified that their claim has been rejected and is given the opportunity to edit and resubmit it.

**Fields read**:
- `input.ID` (claim identifier)
- `input.claim_id` (reference number)
- `input.amount_zar` (claim amount)
- `input.Rejection_Reason` (reason for rejection)
- `input.Email` (employee email)
- `zoho.loginuser` (HoD identity)
- `zoho.currenttime` (timestamp)

**Fields written**:
- `input.status` → "Rejected"

**Custom APIs**: None

**Emails**:
- **To Employee**: subject "Expense Claim [REF] - Rejected by HoD", body includes rejection reason and edit/resubmit instructions

**Audit trail**:
- Approval history record inserted with action "Rejected"

**Shadows / side effects**: None

---

### lm_approval.on_approve

**Trigger**: Line Manager clicks Approve on Pending LM Approval claim  
**Context**: Tier 1 (Line Manager approval)  
**Stage**: Level 1 approval (first-line gatekeeper)

**Effect** (prose):
When a Line Manager approves a claim, the system reads the tier-1 approval threshold from the `approval_thresholds` configuration table (fallback 999.99 if config missing). The script auto-populates the GL code, ESG category, and carbon estimate using the same lookup logic as HoD approval. If the claim amount is within the tier-1 threshold, the LM gives final approval: status becomes "Approved", and the employee is notified. If the claim exceeds the threshold, it is escalated to the HoD: status becomes "Pending HoD Approval", the HoD is notified, and an audit trail records the LM approval plus threshold explanation. A configuration gap warning is logged if the threshold config is missing.

**Fields read**:
- `input.ID` (claim identifier)
- `input.claim_id` (reference number)
- `input.amount_zar` (claim amount)
- `input.category` (expense category for GL lookup)
- `input.Email` (employee email)
- `zoho.loginuser` (LM identity)
- `zoho.currenttime` (timestamp)
- Via lookup: `approval_thresholds[tier_name == "Tier 1 - Line Manager"]` → `max_amount_zar` (fallback 999.99)
- Via lookup: `gl_accounts[expense_category == input.category]` → `gl_code`, `ESG_Category`, `Carbon_Factor`

**Fields written**:
- `input.status` → "Approved" (under threshold) or "Pending HoD Approval" (over threshold)
- `input.gl_code` → GL account code from lookup
- `input.ESG_Category` → ESG classification
- `input.Estimated_Carbon_KG` → `amount_zar * carbon_factor`

**Custom APIs**: None

**Emails**:
1. **Under threshold**: to `input.Email` (employee), subject "Expense Claim [REF] - Approved"
2. **Over threshold**: to `"hod.demo@yourdomain.com"`, subject "Expense Claim [REF] - Requires HoD Approval"

**Audit trail**:
- Approval history record inserted with action "Approved (LM)" or "Warning" (if config missing); includes threshold comparison, GL code, ESG category, and carbon estimate

**Shadows / side effects**:
- GL and ESG data written to claim for financial and sustainability reporting

---

### lm_approval.on_reject

**Trigger**: Line Manager clicks Reject on Pending LM Approval claim  
**Context**: Tier 1 (Line Manager approval)  
**Stage**: Level 1 rejection

**Effect** (prose):
When a Line Manager rejects a claim, the status is set to "Rejected" and an approval_history record is logged with the rejection reason. The employee is notified and given the opportunity to edit and resubmit.

**Fields read**:
- `input.ID` (claim identifier)
- `input.claim_id` (reference number)
- `input.amount_zar` (claim amount)
- `input.Rejection_Reason` (reason for rejection)
- `input.Email` (employee email)
- `zoho.loginuser` (LM identity)
- `zoho.currenttime` (timestamp)

**Fields written**:
- `input.status` → "Rejected"

**Custom APIs**: None

**Emails**:
- **To Employee**: subject "Expense Claim [REF] - Rejected", body includes rejection reason and edit/resubmit instructions

**Audit trail**:
- Approval history record inserted with action "Rejected"

**Shadows / side effects**: None

---

## Form Workflows

### expense_claim.on_validate

**Trigger**: Employee submits or saves Expense_Claim form (validation phase, before save)  
**Event**: on_validate  
**Purpose**: Hard-stop validation gates: temporal, policy, financial, and compliance checks

**Effect** (prose):
The validation script enforces eight mandatory checks that block submission if violated. **Temporal check**: expense date cannot be in the future. **Policy check**: expenses older than 90 days are rejected unless Finance grants an exception (assumes a manual workaround process). **Financial check**: the claim amount must be positive (greater than zero). **Receipt mandate**: at least one supporting document (receipt or invoice) must be attached; this satisfies SARS substantiation requirements and internal audit controls. **Duplicate detection**: the system scans for claims with the same expense date, amount, and submitter (excluding the current claim by ID) and warns the user if a potential duplicate exists. **VAT enforcement**: claims of R5,000 or more must have a "Full Tax Invoice (>= R5,000)" VAT type; this enforces SARS tax compliance. **POPIA consent**: the employee must acknowledge POPIA (Protection of Personal Information Act) consent before submission. **Final status and dates**: if all checks pass, the claim status is set to "Submitted", the submission timestamp is recorded, and a retention expiry date is calculated (current time + 5 years, for compliance record-keeping).

**Fields read**:
- `input.Expense_Date` (date of expense)
- `input.amount_zar` (claim amount)
- `input.Supporting_Documents` (attachment field)
- `input.VAT_Invoice_Type` (VAT classification)
- `input.POPIA_Consent` (boolean consent flag)
- `input.ID` (claim identifier, for duplicate check self-exclusion)
- `zoho.currentdate` (current date)
- `zoho.currenttime` (current timestamp)
- `zoho.loginuser` (current submitter)
- Via lookup: `expense_claims[Expense_Date == input.Expense_Date && amount_zar == input.amount_zar && Added_User == zoho.loginuser && ID != input.ID]` (duplicate scan)

**Fields written**:
- `input.status` → "Submitted" (if all checks pass)
- `input.Submission_Date` → current timestamp
- `input.Retention_Expiry_Date` → current timestamp + 5 years

**Custom APIs**: None

**Emails**: None

**Audit trail**: None (validation failures are user-facing alerts; no system log for failed validations)

**Shadows / side effects**: None

---

### expense_claim.on_load.auto_populate

**Trigger**: Employee opens the Expense_Claim form to create a new claim (form load)  
**Event**: on_load  
**Purpose**: Auto-populate user identity fields from login credentials

**Effect** (prose):
When the Expense_Claim form loads in "add" mode (new claim), the system automatically populates the Employee_Name field with the logged-in user's display name and the Email field with their login ID. This reduces data entry friction and ensures the claim is correctly associated with the submitter's identity.

**Fields read**:
- `zoho.loginuser` (logged-in user's display name)
- `zoho.loginuserid` (logged-in user's email/ID)

**Fields written**:
- `input.Employee_Name1` → `zoho.loginuser`
- `input.Email` → `zoho.loginuserid`

**Custom APIs**: None

**Emails**: None

**Audit trail**: None

**Shadows / side effects**: None

---

### expense_claim.on_success

**Trigger**: Employee successfully submits the Expense_Claim form (after validation passes)  
**Event**: on_success  
**Purpose**: Self-approval prevention (King IV governance), initial routing, audit trail creation, approver notification

**Effect** (prose):
After successful form submission, the system performs three key actions. **Self-approval prevention**: the script checks whether the submitter holds the "Line Manager" role in the Zoho Creator application. If the submitter is a Line Manager, the claim is routed directly to the Head of Department (HoD) for approval, bypassing the normal Line Manager tier — this prevents a manager from approving their own subordinates' claims. If the submitter is not a Line Manager, the claim is routed to a Line Manager for approval at the standard tier-1 level. **Audit trail**: in all cases, an approval_history record is created capturing the initial submission, with a note indicating whether the normal flow or self-approval bypass was triggered. **Approver notification**: the assigned approver (either HoD or LM) receives an email with claim details (employee name, amount).

**Fields read**:
- `input.ID` (claim identifier)
- `input.claim_id` (reference number)
- `input.amount_zar` (claim amount)
- `input.Employee_Name1` (employee name)
- `zoho.loginuser` (submitter identity)
- `zoho.currenttime` (timestamp)
- Via role check: `thisapp.permissions.isUserInRole("Line Manager")`

**Fields written**:
- `input.status` → "Pending HoD Approval" (if submitter is LM) or "Pending LM Approval" (otherwise)

**Custom APIs**: None

**Emails**:
1. **Self-approval bypass**: to `"hod.demo@yourdomain.com"`, subject "Expense Claim [REF] - Direct HoD Review", with self-approval prevention note
2. **Normal flow**: to `"linemanager.demo@yourdomain.com"`, subject "Expense Claim [REF] requires your approval", with employee name and amount

**Audit trail**:
- Approval history record inserted with action "Submitted" or "Submitted (Self-approval bypass)"

**Shadows / side effects**: None

---

### expense_claim.on_success.fill_shadows

**Trigger**: Employee successfully submits or edits the Expense_Claim form  
**Event**: on_success  
**Purpose**: Populate denormalized shadow text fields for reporting and UI convenience

**Effect** (prose):
After successful form submission or edit, the system populates two shadow text fields (denormalized copies of linked record names) to avoid the need for nested lookups in reports or list views. The Department_Shadow field is populated with the department name from the linked `department` form record, and the Client_Shadow field is populated with the client name from the linked `client` form record. If either linked record is null or missing, the shadow field is set to an empty string.

**Fields read**:
- `input.department.name` (department name via link)
- `input.client.name` (client name via link)

**Fields written**:
- `input.Department_Shadow` → department name or empty string
- `input.Client_Shadow` → client name or empty string

**Custom APIs**: None

**Emails**: None

**Audit trail**: None

**Shadows / side effects**: Denormalized data written for reporting convenience

---

### expense_claim.on_success.generate_ref

**Trigger**: Employee successfully submits the Expense_Claim form  
**Event**: on_success  
**Purpose**: Auto-generate human-friendly claim reference code

**Effect** (prose):
After form submission, the system auto-generates a claim reference code in the format "EXP-NNNN" by taking the auto-generated claim_id (numeric), converting it to a string, and zero-padding it to 4 digits. For example, claim_id 5 becomes "EXP-0005", claim_id 1234 becomes "EXP-1234". This reference is used in all customer-facing communications and provides a memorable identifier for the claim.

**Fields read**:
- `input.claim_id` (numeric auto-generated claim identifier)

**Fields written**:
- `input.Claim_Reference` → "EXP-" + zero-padded claim_id

**Custom APIs**: None

**Emails**: None

**Audit trail**: None

**Shadows / side effects**: None

---

### expense_claim.on_edit

**Trigger**: Employee edits and saves an existing Expense_Claim record with status "Resubmitted"  
**Event**: on_edit  
**Purpose**: Handle resubmission workflow: version increment, approval state reset, self-approval check

**Effect** (prose):
When an employee edits a claim that is in "Resubmitted" status, the system increments the Version number and clears all dual-approval tracking fields (Key_1_Approver, Key_1_Timestamp, Key_2_Approver, Key_2_Timestamp, and the Requires_Dual_Approval flag). The submission timestamp is reset to the current time. The script then applies the same self-approval prevention logic as the initial submission: if the resubmitter holds the Line Manager role, the claim is routed directly to the HoD (bypassing LM tier); otherwise, it is routed back to a Line Manager. An audit history record logs the resubmission as a new version, and the appropriate approver is notified.

**Fields read**:
- `input.status` (to detect "Resubmitted" condition)
- `input.Version` (current version number)
- `input.ID` (claim identifier)
- `input.claim_id` (reference number)
- `zoho.loginuser` (resubmitter identity)
- `zoho.currenttime` (current timestamp)
- Via role check: `thisapp.permissions.isUserInRole("Line Manager")`

**Fields written**:
- `input.Version` → `input.Version + 1`
- `input.Requires_Dual_Approval` → false
- `input.Key_1_Approver` → "" (empty)
- `input.Key_1_Timestamp` → null
- `input.Key_2_Approver` → "" (empty)
- `input.Key_2_Timestamp` → null
- `input.Submission_Date` → current timestamp
- `input.status` → "Pending HoD Approval" (if resubmitter is LM) or "Pending LM Approval" (otherwise)

**Custom APIs**: None

**Emails**:
1. **Self-approval bypass**: to `"hod.demo@yourdomain.com"`, subject "RESUBMITTED - Claim [REF] (v[VERSION]) - Direct HoD Review"
2. **Normal resubmission**: to `"linemanager.demo@yourdomain.com"`, subject "RESUBMITTED - Claim [REF] (v[VERSION])"

**Audit trail**:
- Approval history record inserted with action "Resubmitted" and version number
- Optionally, a second record with action "Submitted (Self-approval bypass)" if LM role detected

**Shadows / side effects**: Approval state reset for fresh routing cycle

---

## Scheduled Jobs

### sla_enforcement_daily

**Cron / Frequency**: Daily (free trial limitation; hourly on paid Zoho Creator plans)  
**Schedule**: Runs once per day at a Zoho-managed schedule  
**Purpose**: Enforcement escalation: 2-day reminder, 3-day auto-escalation for LM tier and Key 2 approval

**Effect** (prose):
This daily scheduled job monitors all expense claims in "Pending LM Approval" and "Pending Second Key" statuses and enforces SLA timeouts via escalation (not approval bypass). **For Line Manager tier**: the job queries all claims awaiting LM approval and calculates the number of days since submission. If 3+ days have elapsed, the claim is automatically escalated to HoD status, a system audit record is logged ("Escalated (SLA Breach)"), and the HoD is notified of the breach. If 2+ days have elapsed but less than 3, a reminder email is sent to the LM (and CC'd to HoD) warning that auto-escalation occurs at 3 days. **For Key 2 tier**: the job applies similar logic to claims awaiting Finance Director (Key 2) approval, measuring days since the Key 1 approval timestamp. If 3+ days have passed, the claim is escalated to an admin/CEO for manual intervention, the Finance Director has failed their SLA. If 2+ days have passed, a reminder is sent to the Finance Director. This design ensures that high-value claims (those requiring dual approval) receive executive-level attention if approval is delayed.

**Fields read**:
- `expense_claims[status == "Pending LM Approval"]` (LM queue)
- `expense_claims[status == "Pending Second Key"]` (Key 2 queue)
- For each claim: `claim.Submission_Date`, `claim.Key_1_Timestamp`, `claim.claim_id`, `claim.amount_zar`, `claim.Key_1_Approver`, `claim.ID`
- `zoho.currentdate` (current date, for day calculations)
- `zoho.currenttime` (current timestamp)
- `zoho.adminuser` (system user for audit records)
- `zoho.adminuserid` (admin email for escalation messages)

**Fields written**:
- `claim.status` → "Pending HoD Approval" (if LM SLA breach) — no write for Key 2 breach (manual intervention)

**Custom APIs**: None

**Emails**:
1. **LM SLA 2-day reminder**: to `"linemanager.demo@yourdomain.com"` (cc `"hod.demo@yourdomain.com"`), subject "REMINDER - Claim [REF] awaiting approval", body includes auto-escalation warning at 3 days
2. **LM SLA 3-day breach**: to `"hod.demo@yourdomain.com"`, subject "SLA BREACH - Claim [REF] escalated", body notifies HoD of LM failure
3. **Key 2 SLA 2-day reminder**: to `"financedirector.demo@yourdomain.com"`, subject "REMINDER - Claim [REF] awaiting Key 2 approval"
4. **Key 2 SLA 3-day breach**: to `zoho.adminuserid`, subject "SLA BREACH - Claim [REF] - Key 2 overdue", body includes full context (Key 1 approver, amount) for manual resolution

**Audit trail**:
- Approval history record inserted with action "Escalated (SLA Breach)" and actor = "SYSTEM" (for LM breaches)
- No history record for Key 2 breaches (manual intervention assumed)

**Shadows / side effects**: Status escalation to HoD (LM tier only); high-visibility admin notification (Key 2 tier)

---

## Key Observations & Governance Patterns

### Segregation of Duties (King IV P1)
- **LM self-approval prevention**: Same person cannot submit and approve at tier 1.
- **Two-Key same-person block**: Same person cannot serve as both Key 1 (HoD) and Key 2 (Finance Director).

### Threshold-Based Escalation
- **Tier 1 (LM)**: Threshold = R999.99 (fallback). Over = escalate to HoD.
- **Tier 2 (HoD)**: Dual-approval threshold = R5,000.00 (fallback). Over = escalate to Key 2.
- **Key 2 Dispute**: Finance Director rejection does not final-reject; instead, HoD can override and re-route for new Key 2 cycle.

### ESG & GL Integration
- Both HoD and LM approval scripts auto-populate GL code, ESG category, and estimated carbon footprint based on expense category lookup.
- This enables sustainability reporting (Scope 3 emissions) and financial segregation by cost center.

### Compliance Enforcement
- **SARS substantiation**: Receipt mandatory; VAT type enforced for R5,000+ claims.
- **POPIA consent**: Mandatory before submission.
- **90-day late-submission policy**: Hard stop unless Finance grants exception.
- **Duplicate detection**: Warning (not block) to catch accidental resubmissions.

### SLA & Escalation
- **LM tier**: 2-day reminder, 3-day auto-escalation to HoD.
- **Key 2 tier**: 2-day reminder, 3-day escalation to admin (CEO/Finance Controller) — higher visibility for high-value claims.

### Audit Trail Comprehensiveness
- Every approval, rejection, dispute, escalation, and resubmission is logged with actor, timestamp, and context (threshold crossed, GL code, ESG data, rejection reason, same-person block).

### Versioning & Resubmission
- Failed claims can be edited and resubmitted. Version number increments, and dual-approval state is reset for a fresh cycle.
- Self-approval prevention applies to resubmissions as well.

---

## Scripts with Unclear Intent

**None identified.** All 13 scripts have clear, documented intent either in their header comments or derived unambiguously from code behavior.

---

## Summary Statistics

| Category | Count |
|---|---|
| Approval workflows (LM/HoD/Finance tiers) | 6 |
| Form workflows (validation, routing, shadows, references) | 7 |
| Scheduled jobs | 1 |
| **Total Deluge scripts** | **13** |
| **Total approval history records created** | ~26 (varies by path) |
| **Total email notifications** | ~35+ (varies by conditions) |
| **Configuration dependencies** | 2 (`approval_thresholds`, `gl_accounts`) |

---

*Document generated for BRD alignment and workflow architecture review.*
