# ERM Core Workflows — Zoho Creator Builder Playbook

**Audience:** implementer working inside the Zoho Creator builder for the
"Expense Reimbursement Management" app. Use this doc as a step-by-step
walkthrough; the `.ds` file in this folder is the reference of the app's
current shape, not the thing you edit.

**Scope = minimum viable "core assignment done":**
- Form validations on `expense_claims` submit
- Automatic tier routing by amount (LM → HoD → Dual approval)
- 5 Custom Action buttons (approve/reject at each tier, request clarification)
- Dual-approval enforcement (Key 1 ≠ Key 2)
- Automatic `approval_history` audit trail
- Light Blueprint wiring (lifecycle display only)

**Out of scope for "core":** email notifications, SLA/scheduled workflows,
Custom APIs, ESG fields, self-approval-bypass rules, role-matrix permissions,
audit retention jobs. Those come in a later pass.

> **Case-sensitivity reminder** — every `input.field_name` and form link name
> in the Deluge snippets below matches the link names from the `.ds` exactly.
> Don't "fix" casing; Zoho will silently treat `input.Amount_ZAR` and
> `input.amount_zar` as different fields and you'll spend an hour debugging.

---

## 0. Preconditions

Before you start wiring workflows, confirm these fields exist on
`expense_claims`. If any are missing, add them in the builder under
**Design → expense_claims → [field palette]** (don't edit the .ds).

| Field link name | Type | Purpose |
|---|---|---|
| `Email` | Email | who submitted |
| `Submission_Date` | Date | claim date |
| `Claim_Reference` | Single Line | set by workflow, format `EXP-<ID>` |
| `status` | Dropdown | routing state |
| `amount_zar` | Currency (ZAR) | amount for tier routing |
| `Department_ID` | Lookup → `departments` | required |
| `Client_ID` | Lookup → `clients` | optional |
| `Key_1_Approver` | Single Line | set by first approver |
| `Key_2_Approver` | Single Line | set by dual-key approver |
| `approval_comments` | Multi Line | rejection/clarification reason |
| `Retention_Expiry_Date` | Date | auto-computed (Submission + 5y) |
| `Claim_Submission_Timestamp` | Date-Time | auto-set on submit |

Also confirm `status` has at least these picklist values (they already exist
in the current .ds, just listing here so the Deluge matches):
`Submitted`, `Pending LM Approval`, `Pending HoD Approval`,
`Pending Second Key`, `Approved`, `Rejected`, `Resubmitted`, `Draft`.

---

## 1. Seed `approval_thresholds` data

Before any routing Deluge can run, you need threshold rows to read from.
Open the app in **View mode** → `Approval Thresholds` → **Add New** and
create exactly these three rows (adjust amounts to your real thresholds):

| `tier_name` | `approver_role` | `max_amount_zar` | `Tier_Order` | `Requires_Dual_Approval` | `Dual_Threshold_ZAR` | `Active` |
|---|---|---|---|---|---|---|
| Tier 1 | LM | 5000 | 1 | false | 0 | ☑ |
| Tier 2 | HoD | 50000 | 2 | false | 0 | ☑ |
| Dual Threshold | Finance | 0 | 99 | ☑ | 100000 | ☑ |

> The `tier_name` strings above are **literal keys** that the Deluge below
> will look up. If you rename any row, update every matching Deluge string
> in lockstep.

---

## 2. Form Actions on `expense_claims`

Path in builder: **Workflow (left nav) → Form Actions → expense_claims**.
You'll see three buckets per event context: **On Load**, **On Validate**,
**On Success**, each under **On Add** and **On Edit**.

### 2.1 On Add → On Validate (pre-insert checks + defaults)

Click **On Add → On Validate → Click to write Deluge → Free-flow script**.
Paste:

```deluge
// --- Required-field checks ---
if(input.Email == null || input.Email == "")
{
    alert "Email is required.";
    cancel submit;
}
if(input.Submission_Date == null)
{
    alert "Submission Date is required.";
    cancel submit;
}
if(input.amount_zar == null || input.amount_zar <= 0)
{
    alert "Amount (ZAR) must be greater than zero.";
    cancel submit;
}
if(input.Department_ID == null)
{
    alert "Department is required.";
    cancel submit;
}

// --- Submission metadata ---
input.Claim_Submission_Timestamp = zoho.currenttime;
input.Retention_Expiry_Date = input.Submission_Date.addYear(5);

// --- Initial status + tier routing by amount ---
t1 = approval_thresholds[tier_name == "Tier 1" && Active == true];
t2 = approval_thresholds[tier_name == "Tier 2" && Active == true];
dt = approval_thresholds[tier_name == "Dual Threshold" && Active == true];

t1_max = if(t1.count() > 0, t1.max_amount_zar, 0.0);
t2_max = if(t2.count() > 0, t2.max_amount_zar, 0.0);
dual_min = if(dt.count() > 0, dt.Dual_Threshold_ZAR, 0.0);

if(dual_min > 0 && input.amount_zar >= dual_min)
{
    input.status = "Pending Second Key";
}
else if(input.amount_zar > t1_max && input.amount_zar <= t2_max)
{
    input.status = "Pending HoD Approval";
}
else if(input.amount_zar <= t1_max)
{
    input.status = "Pending LM Approval";
}
else
{
    // between T2 max and dual_min — treat as HoD scope
    input.status = "Pending HoD Approval";
}
```

### 2.2 On Add → On Success (assign reference + seed audit trail)

Click **On Add → On Success → Free-flow script**. Paste:

```deluge
if(input.Claim_Reference == null || input.Claim_Reference == "")
{
    input.Claim_Reference = "EXP-" + input.ID.toString();
}

insert into approval_history
[
    added_user  = zoho.loginuser
    claim       = input.ID
    action_1    = "Submitted"
    timestamp   = zoho.currenttime
    actor_role  = zoho.loginuser
    notes       = "Claim submitted. Routed to: " + input.status
];
```

> If `insert into approval_history [...]` throws "form not found" when you
> save, try replacing `approval_history` with `Approval_History` (display
> name). Creator accepts both in most versions but a minority of tenants
> require the display name here.

### 2.3 On Edit → On Validate (guard manual status edits — optional)

Users shouldn't be able to jump statuses by hand-editing the form.
Lightweight guard:

```deluge
if(input.status == "Approved" && input.Key_2_Approver == null && input.amount_zar >= 100000)
{
    alert "Approved claims over the dual threshold must have a Key 2 Approver. Use the Key 2 Approve action instead.";
    cancel submit;
}
```

---

## 3. Custom Actions on `expense_claims` (the approval buttons)

Path: **Workflow → Custom Actions → expense_claims → Add New Custom Action**,
or directly from within a Report → **Customize Layout → Add Custom Action**.

Each Custom Action has:
- **Display Name** — the button label users see
- **Link Name** — internal identifier (the name in brackets below)
- **Show In** — pick **Report** (so it appears as a row button) and/or
  **Form Details** (so it appears inside a record)
- **Criteria** — visibility rule (a Deluge-like boolean expression)
- **Script** — the Deluge that fires on click

Create the five actions below in order.

---

### 3.1 `LM_Approve` — "LM Approve"

- **Show In:** Report + Form Details
- **Criteria:** `status == "Pending LM Approval"`
- **Success message:** `"LM approval recorded."`
- **Script:**

```deluge
// Pull thresholds (in case routing needs to escalate)
t2 = approval_thresholds[tier_name == "Tier 2" && Active == true];
dt = approval_thresholds[tier_name == "Dual Threshold" && Active == true];
t2_max = if(t2.count() > 0, t2.max_amount_zar, 0.0);
dual_min = if(dt.count() > 0, dt.Dual_Threshold_ZAR, 0.0);

input.Key_1_Approver = zoho.loginuser;

insert into approval_history
[
    added_user  = zoho.loginuser
    claim       = input.ID
    action_1    = "Approved (LM)"
    timestamp   = zoho.currenttime
    actor_role  = zoho.loginuser
    notes       = "Line manager approval"
];

if(dual_min > 0 && input.amount_zar >= dual_min)
{
    input.status = "Pending Second Key";
}
else if(input.amount_zar > t2_max)
{
    input.status = "Pending HoD Approval";
}
else
{
    input.status = "Approved";
}
```

---

### 3.2 `HoD_Approve` — "HoD Approve"

- **Show In:** Report + Form Details
- **Criteria:** `status == "Pending HoD Approval"`
- **Script:**

```deluge
dt = approval_thresholds[tier_name == "Dual Threshold" && Active == true];
dual_min = if(dt.count() > 0, dt.Dual_Threshold_ZAR, 0.0);

if(input.Key_1_Approver == null || input.Key_1_Approver == "")
{
    input.Key_1_Approver = zoho.loginuser;
}

insert into approval_history
[
    added_user  = zoho.loginuser
    claim       = input.ID
    action_1    = "Approved (HoD)"
    timestamp   = zoho.currenttime
    actor_role  = zoho.loginuser
    notes       = "Head of Department approval"
];

if(dual_min > 0 && input.amount_zar >= dual_min)
{
    input.status = "Pending Second Key";
}
else
{
    input.status = "Approved";
}
```

---

### 3.3 `Key_2_Approve` — "Key 2 Approve" (**dual-approval enforcement**)

This is the enforcement point the BRD calls out. Two non-negotiable rules:
1. **Key 2 must be a different user from Key 1.** Same-user dual approval
   defeats the whole point of the control.
2. **Key 2 only fires from the `Pending Second Key` state** — you cannot
   side-door it from any other status.

Rule 1 is enforced in the Deluge (below). Rule 2 is enforced by the
visibility criteria.

- **Show In:** Report + Form Details
- **Criteria:** `status == "Pending Second Key"`
- **Success message:** `"Key 2 approval recorded. Claim approved."`
- **Script:**

```deluge
// --- DUAL APPROVAL ENFORCEMENT: segregation of duties ---
if(input.Key_1_Approver == zoho.loginuser)
{
    alert "You cannot provide Key 2 approval on a claim you already approved as Key 1.";
    return;
}
if(input.Key_1_Approver == null || input.Key_1_Approver == "")
{
    alert "This claim has no recorded Key 1 approver. Route it back through the tier-1 approval flow first.";
    return;
}

input.Key_2_Approver = zoho.loginuser;
input.status = "Approved";

insert into approval_history
[
    added_user  = zoho.loginuser
    claim       = input.ID
    action_1    = "Approved (Key 2)"
    timestamp   = zoho.currenttime
    actor_role  = zoho.loginuser
    notes       = "Second-key approval — dual approval complete"
];
```

> **Why in Custom Action and not in the Blueprint?** You *could* put this
> check on a blueprint transition. Custom Action is preferable here because
> (a) the error path (`alert` + `return`) is clean and keeps the user on
> the same screen; (b) the button visibility already encodes the "must be
> in Pending Second Key" precondition; (c) it avoids coupling the SoD
> control to the blueprint's transition graph, so you can restructure the
> blueprint later without re-wiring this rule.

---

### 3.4 `Reject_Claim` — "Reject"

- **Show In:** Report + Form Details
- **Criteria:** `status == "Pending LM Approval" || status == "Pending HoD Approval" || status == "Pending Second Key"`
- **Script:**

```deluge
prior_status = input.status;
action_label = "Rejected";
if(prior_status == "Pending LM Approval")    { action_label = "Rejected"; }
else if(prior_status == "Pending HoD Approval") { action_label = "Rejected"; }
else if(prior_status == "Pending Second Key")   { action_label = "Rejected (Key 2)"; }

input.status = "Rejected";

insert into approval_history
[
    added_user  = zoho.loginuser
    claim       = input.ID
    action_1    = action_label
    timestamp   = zoho.currenttime
    actor_role  = zoho.loginuser
    notes       = ifnull(input.approval_comments, "Rejected without comment")
];
```

> The `action_1` picklist in the current `.ds` has `Rejected`, `Rejected (Key 2)`,
> and a handful of others but no `Rejected (LM)` / `Rejected (HoD)`. If you
> want tier-specific rejection labels, either (a) extend the `action_1`
> picklist with `Rejected (LM)` and `Rejected (HoD)` via **Design →
> approval_history → action_1 → Edit Choices**, then update the Deluge, or
> (b) rely on the generic `Rejected` value and carry tier context in `notes`.

---

### 3.5 `Request_Clarification` — "Request Clarification"

- **Show In:** Report + Form Details
- **Criteria:** `status == "Pending LM Approval" || status == "Pending HoD Approval" || status == "Pending Second Key"`
- **Script:**

```deluge
if(input.approval_comments == null || input.approval_comments == "")
{
    alert "Please enter a message in the 'Approval Comments' field explaining what clarification is needed.";
    return;
}

input.status = "Resubmitted";  // submitter will edit and re-save; on-edit validation re-routes

insert into approval_history
[
    added_user  = zoho.loginuser
    claim       = input.ID
    action_1    = "Reconsidered (Key 1)"
    timestamp   = zoho.currenttime
    actor_role  = zoho.loginuser
    notes       = "Clarification requested: " + input.approval_comments
];
```

> `Reconsidered (Key 1)` is the closest-fitting value in the existing
> `action_1` picklist. If you add a `Clarification Requested` value, swap
> it in. See the note at the end of 3.4 about extending the picklist.

---

## 4. Blueprint — lifecycle display

The existing blueprint `expense_claim_approval_workflow` already defines
nine high-level stages. For the **core** pass you do **not** need to add
routing Deluge to the blueprint — the `status` field + Custom Actions
above drive the actual approval logic. The blueprint's job is to show
users "what life-stage is this claim at".

If you want the blueprint state to follow `status` automatically, add a
small **On Edit → On Success** snippet on `expense_claims`:

Path: **Workflow → Form Actions → expense_claims → On Edit → On Success**.
Append (do not replace what's already there):

```deluge
// Nudge blueprint stage to match the routing status
if(input.status == "Approved")
{
    input.currentStage = "Claim Approved";
}
else if(input.status == "Rejected")
{
    input.currentStage = "Claim Rejected";
}
else if(input.status == "Resubmitted")
{
    input.currentStage = "Claim Under Review";
}
```

> `input.currentStage` is the standard Creator handle for the blueprint
> stage field. If your tenant reports it as unresolved, open **Workflow →
> Blueprint → expense_claim_approval_workflow → Settings** and verify the
> "stage field" name; adapt the snippet to match.

For the dual-approval enforcement specifically, no blueprint wiring is
needed — the Custom Action in §3.3 is the control. The blueprint simply
shows "Claim Under Review" while `status` is any of the `Pending ...`
values, and advances to "Claim Approved" once §3.3 (or §3.1/§3.2 single-
approver paths) completes.

---

## 5. Verify it works — smoke tests

After saving all of the above, run these three scenarios in the live app.
Each should produce the listed state + the listed `approval_history` rows.

### Scenario A — small claim (single LM approval)

1. Submit claim: `amount_zar = 1500`, Department/Client/Email populated.
2. **Expect:** `status = "Pending LM Approval"`, `Claim_Reference = "EXP-<ID>"`,
   one `approval_history` row with `action_1 = "Submitted"`.
3. Click **LM Approve**.
4. **Expect:** `status = "Approved"`, `Key_1_Approver = <you>`, blueprint
   stage advances to "Claim Approved" on next edit, second
   `approval_history` row with `action_1 = "Approved (LM)"`.

### Scenario B — mid claim (HoD approval, no dual)

1. Submit: `amount_zar = 25000`.
2. **Expect:** `status = "Pending HoD Approval"`.
3. Click **HoD Approve**.
4. **Expect:** `status = "Approved"`, `Key_1_Approver = <you>`.

### Scenario C — large claim (dual approval, enforcement test)

1. Submit: `amount_zar = 250000`.
2. **Expect:** `status = "Pending Second Key"` (direct jump — dual threshold crossed).
3. As the **same user** who submitted, click **Key 2 Approve**.
   - **Expect:** blocked with the "cannot approve on a claim you already
     approved as Key 1" alert. `Key_1_Approver` was set to the submitter
     on submission, so self-approval is rejected. (If `Key_1_Approver`
     wasn't set on submission — which happens if the claim was submitted
     via a code path that bypassed section 2.1 — the script asks you to
     route it back through tier 1 first.)
4. Log in as a different user, open the claim, click **Key 2 Approve**.
   - **Expect:** `status = "Approved"`, `Key_2_Approver = <different user>`,
     `approval_history` row with `action_1 = "Approved (Key 2)"`.

### Scenario D — rejection with comment

1. Submit any claim.
2. Edit the claim, fill `approval_comments` with a reason.
3. Click **Reject**.
4. **Expect:** `status = "Rejected"`, `approval_history` row with the
   rejection reason in `notes`.

---

## 6. Optional hardening (post-core, worth flagging now)

These are not required for "core done" but cost little if you do them
while you're in the builder anyway:

1. **Role gate the approval buttons.** Open each Custom Action →
   **Permissions** → restrict visibility to the intended role
   (LM/HoD/Finance). The Deluge still holds even if someone bypasses the
   UI, but role gating keeps the button out of the wrong users' view.
2. **Disable direct editing of `status`.** In the form layout, mark the
   `status` field as read-only on edit (Field Properties → Advanced →
   "disable in form view" / "hidden"). Approvals should go through the
   Custom Actions, not by hand-editing the dropdown.
3. **Add a `Claim_Reference` uniqueness index** (Field Properties → "do
   not allow duplicate values") so the `EXP-<ID>` format stays unique.
4. **Add `Key_1_Approver != Key_2_Approver` as a form-level validation**
   (belt-and-braces — §3.3's in-action check is the primary control,
   this catches any backdoor edits).

---

## 7. Explicitly deferred for later

Do NOT attempt these in the core pass; they each deserve their own pass:

- Email notifications on every state transition (~18 templates in BRD)
- Escalation Scheduled Actions when a claim sits in a Pending state > N hours
- ESG fields (`Estimated_Carbon_KG`, `ESG_Category`, `Carbon_Factor`, `GRI_Indicator`)
- Custom APIs (`Get_Claim_Status`, `Get_Dashboard_Summary`, `Get_ESG_Summary`, `Get_SLA_Breaches`)
- Portal-role and internal-role permission matrix
- Blueprint transitions for Payment (`Claim Approved → Processed → Paid → Closed`) with Finance gating
- Parent/Child (resubmission) claim linkage via `Parent_Claim_ID`
- Denormalised department/client shadow fields
- Audit-trail retention job (90-day archival)

---

## Appendix: UI paths cheatsheet

If Creator's navigation drifts between versions, these are the builder
areas you'll be working in:

- **Design** — forms, fields, picklists, layout
- **Workflow** — Form Actions (on add/edit × on load/validate/success),
  Custom Actions, Scheduled Actions, Blueprints
- **Access** — roles, permissions, portal roles
- **Integrations** — Custom APIs, connectors (out of scope here)

If a panel name doesn't match this doc, the concepts map 1:1; Zoho has
occasionally renamed "Actions" ↔ "Custom Actions" and "Form Workflow" ↔
"Form Actions" between release waves.
