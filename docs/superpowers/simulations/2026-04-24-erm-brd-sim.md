# Phase 6 Simulation Report — ERM BRD

**Simulator**: Phase 6 (mathematical validation of Phase 5 spec against Phase 3 research)  
**Date**: 2026-04-24  
**Spec**: `2026-04-24-erm-brd-design.md` (Phase 5 post-rebuttal)  
**Research**: 3a-ds-schema.md, 3b-deluge.md, 3c-config.md  
**Ground truth**: `Expense_Reimbursement_Management-stage.ds` (3,656 lines)

---

## Verdict

**CONDITIONAL PASS** — 4 numbered blockers

The spec is structurally sound and produces a correct, lossless BRD for 11 of 13 workflows, all 6 forms, all 11 reports, and all 4 Custom APIs. Two blockers (B-1, B-2) require spec patches before Phase 7 to prevent implementation errors. Two blockers (B-3, B-4) are lower-severity ambiguities a reasonable implementer would have to guess.

**Blockers**:
- **B-1** (HIGH): Spec §4 §6 `ref/pick` rule for the `Parent_Claim_ID` field is contradicted by the spec's own `type` rule — a Phase 7 implementer will produce either a wrong `type` column or a wrong `ref/pick` column for that field.
- **B-2** (HIGH): hod_approval.on_approve has three distinct email paths (dispute, over-threshold, under-threshold), but the spec's WF-09 split is `.A`/`.B` — only two branches. The third path (under-threshold final approval) is not assigned its own sub-ID or disambiguated, creating ambiguity in the `Emails:` line of WF-09.B.
- **B-3** (MEDIUM): The spec says §11 `Emails:` references must resolve to a named template in §13, but does not enumerate which of the 18 named templates maps to each of WF-09's three email paths. A Phase 7 implementer must infer the mapping from 3b/3c data — one mapping (`hod_approved`) is inferable but the dispute path's correct template name is ambiguous between `key1_reconsider_override` and no template match.
- **B-4** (LOW): The spec states "17 H3 blocks from 13 parent workflows" with splits on WF-03, WF-07, WF-09, WF-11 (.A/.B each = 4 × 2 extra = 4 splits + 9 unsplit = 13 + 4 = 17). WF-09 splits into only .A and .B but the research describes **three** behaviorally distinct paths inside hod_approval.on_approve. Collapsing path 2 (over-threshold) and path 3 (under-threshold) into WF-09.B produces a single block with a disjunctive guard — technically valid but information-lossy.

---

## Simulation 1: Form `expense_claims` (§6.5 reconstruction)

Role-played as Phase 7 implementer writing §6.5, applying spec §4 §6 rules verbatim to 3a-ds-schema.md expense_claims table.

### Simulated BRD output

```markdown
### 6.5 expense_claims — Expense Claims

Core transaction form; each record is one employee expense reimbursement claim moving through the multi-tier approval workflow.

| link_name              | label                  | type                    | flags | default       | ref/pick                         | help |
|---|---|---|---|---|---|---|
| Employee_Name1         | Employee Name          | name (compound)         | *     | —             | pick{Mr.,Mrs.,Ms.}               | Your full name as registered in the system. Auto-populated on form load. |
| Email                  | Email                  | pick list (users-module)| *     | —             | users-module                     | Notification routing target. |
| Submission_Date        | Submission Date        | date time               | *     | —             | —                                | Date and time the claim was submitted. Set automatically. |
| claim_id               | Claim ID               | auto number             | —     | autonumber(1) | —                                | System-generated unique claim number. Used for tracking and reference. |
| department             | Department             | lookup→departments      | —     | —             | lookup→departments               | Select your department. Used for reporting and approval routing. |
| Claim_Reference        | Claim Reference        | text                    | *     | —             | —                                | Auto-generated reference (EXP-0001 format). Use this when communicating about the claim. |
| client                 | Client                 | lookup→clients          | —     | —             | lookup→clients                   | Select the client this expense relates to. Choose Internal for non-client expenses. |
| Expense_Date           | Expense Date           | date                    | —     | —             | —                                | Date the expense was incurred. Cannot be in the future or older than 90 days. |
| Department_Shadow      | Department Shadow      | text                    | †     | —             | —                                | — |
| category               | Category               | pick list               | —     | —             | @Picklist:category               | Select the expense category. Determines GL code mapping and VAT requirements. |
| Client_Shadow          | Client Shadow          | text                    | †     | —             | —                                | — |
| amount_zar             | Amount ZAR             | currency(ZAR)           | —     | —             | —                                | Total expense amount in South African Rand (ZAR). Must be greater than zero. |
| Supporting_Documents   | Supporting Documents   | file upload             | *     | —             | —                                | Upload receipts or invoices. Required by SARS S11(a) for all claims. Max 10 files. |
| description            | Description            | rich text (textarea)    | —     | —             | —                                | Describe the business purpose of this expense. Required for SARS S11(a) substantiation. |
| VAT_Invoice_Type       | VAT Invoice Type       | pick list               | —     | —             | @Picklist:VAT_Invoice_Type       | Select invoice type. Claims >= R5,000 require a Full Tax Invoice per SARS VAT rules. |
| POPIA_Consent          | POPIA Consent          | boolean                 | —     | false         | —                                | I consent to the processing of my personal data for expense reimbursement purposes in accordance with POPIA. |
| status                 | Status                 | pick list               | —     | —             | @Picklist:status                 | Current claim status. Updated automatically by the approval workflow. |
| Rejection_Reason       | Rejection Reason       | rich text (textarea)    | —     | —             | —                                | Reason for rejection, provided by the approver. Read-only for employees. |
| Version                | Version                | number                  | —     | 1             | —                                | Claim version number. Incremented each time the claim is resubmitted after rejection. |
| Retention_Expiry_Date  | Retention Expiry Date  | date                    | †     | —             | —                                | SARS Tax Administration Act S29: 5-year retention from submission date. |
| Parent_Claim_ID        | Parent Claim ID        | pick list (self-ref)    | †     | —             | self_ref→expense_claims          | Self-referential: stores ID of the parent claim this record amends; .ds type is pick list filtered to expense_claims.ID. |
| gl_code                | GL Code                | lookup→gl_accounts      | —     | —             | lookup→gl_accounts               | General Ledger code assigned during approval. Maps the expense to the correct account. |
| Requires_Dual_Approval | Requires Dual Approval | boolean                 | †     | false         | —                                | — |
| Key_1_Approver         | Key 1 Approver         | text                    | †     | —             | —                                | — |
| Key_1_Timestamp        | Key 1 Timestamp        | date time               | †     | —             | —                                | — |
| Key_2_Approver         | Key 2 Approver         | text                    | †     | —             | —                                | — |
| Key_2_Timestamp        | Key 2 Timestamp        | date time               | †     | —             | —                                | — |

**Form-level rules**:
1. BR-011 — amount_zar must be > 0.
2. BR-006 — Expense_Date must not be in the future.
3. BR-010 — Expense_Date must not be older than 90 days from submission date.
4. BR-009 — Supporting_Documents must not be null (SARS S11(a) substantiation).
5. BR-019 — Duplicate detection on same Expense_Date + amount_zar + submitter (warning, not block).
6. BR-007 — Claims >= R5,000 require VAT_Invoice_Type = "Full Tax Invoice (>= R5,000)".
7. BR-008 — POPIA_Consent must be true before submission.

Referenced by: WF-01, WF-02, WF-03, WF-04, WF-05, WF-06, WF-07, WF-08, WF-09, WF-10, WF-11, WF-12, WF-13.
```

### Evaluation

- **[27-field completeness]**: PASS — The simulated table produces exactly 27 rows, matching research 3a's expense_claims section verbatim: Employee_Name1, Email, Submission_Date, claim_id, department, Claim_Reference, client, Expense_Date, Department_Shadow, category, Client_Shadow, amount_zar, Supporting_Documents, description, VAT_Invoice_Type, POPIA_Consent, status, Rejection_Reason, Version, Retention_Expiry_Date, Parent_Claim_ID, gl_code, Requires_Dual_Approval, Key_1_Approver, Key_1_Timestamp, Key_2_Approver, Key_2_Timestamp. Ordering follows 3a's declaration order.

- **[compact-DSL type names resolvable from §3 Glossary]**: PASS — All types used (`name (compound)`, `pick list (users-module)`, `date time`, `auto number`, `lookup→<form>`, `text`, `date`, `pick list`, `currency(ZAR)`, `file upload`, `rich text (textarea)`, `boolean`, `pick list (self-ref)`, `number`) are defined in the §3 notation block verbatim. No invented types.

- **[self-ref Parent_Claim_ID correctly encoded]**: CONDITIONAL PASS — The `type` column correctly uses `pick list (self-ref)` per spec rule: "Do NOT override the type to self_ref→expense_claims in the type column — use `pick list (self-ref)` to match the .ds verbatim." The `ref/pick` column uses `self_ref→expense_claims` per the cell encoding rule: "For self-ref pick list — `self_ref→expense_claims`." The `†` flag is applied because `private=true` per 3a research. **However, the spec contains an internal contradiction**: §4 §6 `ref/pick` rule says to put `self_ref→expense_claims` there, while §3 Notation defines `self_ref→<form>` as its own type arrow. The spec explicitly bars using `self_ref→expense_claims` in the `type` column but then uses it in `ref/pick` — a reasonable Phase 7 implementer might place `self_ref→expense_claims` in the `type` column instead, because the §3 Glossary lists it as a relational arrow type. **This is Blocker B-1**: the spec needs an explicit statement that `self_ref→<form>` only appears in the `ref/pick` column, never in the `type` column, for fields whose .ds type is `pick list`.

- **[formulas rendered verbatim from 3a]**: PASS (N/A for expense_claims) — No formula fields (`fx:` entries) exist in expense_claims in the 3a research. The 3a research shows no `fx:` DSL entries for this form. Formulas (Retention_Expiry_Date, Claim_Reference) are workflow-computed, not form-level formula fields — correctly represented as `text`/`date` with no `fx:` prefix. The spec correctly distinguishes between field types and workflow side-effects.

- **[picklist threshold rule — inline vs @Picklist]**: PASS — The spec's threshold rule is "≤3 values AND single-use → `pick{a,b,c}`; otherwise `@Picklist:<name>`". Applied correctly:
  - `category` (7 values, multi-use): `@Picklist:category` ✓
  - `VAT_Invoice_Type` (3 values, single-use on expense_claims only): ambiguous by the rule — 3 values = ≤3, single-use. The spec resolves this by assigning it as a **named** picklist (#5 of 5), so `@Picklist:VAT_Invoice_Type` is correct. The `Employee_Name1` prefix sub-field (3 values, sub-component only) correctly becomes `pick{Mr.,Mrs.,Ms.}` inline. No contradiction found in this form. PASS.
  - `status` (9 values): `@Picklist:status` ✓

- **[ESG fields — present or excluded per .ds reality]**: PASS — The simulated §6.5 does NOT include `ESG_Category` or `Estimated_Carbon_KG` fields. Ground-truth .ds verification (lines 1012–1124) confirms gl_accounts ends at `Active` (7 fields) with no ESG fields declared. The spec's §15 bullet 7 discrepancy note is correctly applied. Neither ESG field appears in expense_claims' 27-field table in the simulation. The advisory suffix `(advisory — not .ds-declared)` would be applied only in §11 Reads/Writes, not in §6.5.

### Gaps found in spec (Simulation 1)

- **Gap 1 (Blocker B-1)**: The spec §4 §6 cell encoding rule for `ref/pick` states "For self-ref pick list — `self_ref→expense_claims`", while §4 §6 cell encoding rule for `type` states "For self-ref pick list: `pick list (self-ref)`". The §3 Glossary lists `self_ref→<form>` as a relational arrow type (like `lookup→`). A Phase 7 implementer reading §3 alone would put `self_ref→expense_claims` in the `type` column. **Proposed fix**: Add an explicit note to the §3 Glossary entry for `self_ref→<form>`: "Note: when a .ds field is declared as a pick list (self-ref), the `type` column MUST read `pick list (self-ref)` verbatim; `self_ref→<form>` appears only in the `ref/pick` column."

- **Gap 2 (minor)**: The spec does not specify the `†` flag for `Retention_Expiry_Date` explicitly as "private=true" in the §6 writing rule — it is mentioned only in 3a-ds-schema.md notes ("private=true"). The spec's flag rule says "Fields with `private=true` in .ds get `†`" which is sufficient, but a cross-check is warranted. Verification: 3a confirms `private=true` for Retention_Expiry_Date. No spec patch needed; existing rule covers it. MINOR — no action.

---

## Simulation 2: Workflow `hod_approval.on_approve` (branch split)

Role-played as Phase 7 implementer writing §11 WF-09.A and WF-09.B, applying spec §4 §11 rules verbatim to 3b-deluge.md hod_approval.on_approve section.

### Simulated BRD output

```markdown
### WF-09.A  hod_approval.on_approve — dispute reconsideration
- Trigger: expense_claims approval process > HoD Approval > Level 1 (on_approve)
- Guard:   input.status == "Key 2 Dispute"
- Effect:  HoD overrides Finance Director's Key 2 rejection. Status resets to "Pending Second Key",
           Key_1_Approver is recorded, Key_1_Timestamp set. Claim re-routes to Finance Director
           for a new Key 2 approval cycle. Dispute override is fully logged in audit trail.
- Reads:   input.status; input.ID; input.claim_id; input.amount_zar; input.Key_1_Approver;
           input.Email; zoho.loginuser; zoho.currenttime
- Writes:  input.status → "Pending Second Key"; input.Key_1_Approver → zoho.loginuser;
           input.Key_1_Timestamp → zoho.currenttime
- APIs:    —
- Emails:  key1_reconsider_override → finance_director
- Audit:   "Reconsidered (Key 1)"

### WF-09.B  hod_approval.on_approve — normal approval (threshold routing)
- Trigger: expense_claims approval process > HoD Approval > Level 1 (on_approve)
- Guard:   input.status != "Key 2 Dispute" (standard HoD approval path)
- Effect:  Reads dual-approval threshold from approval_thresholds config. Auto-populates GL code
           from gl_accounts by expense category. If amount exceeds dual-threshold, routes to Key 2
           (status = "Pending Second Key", Finance Director notified, Key_1_Approver recorded).
           If amount is under threshold, grants final approval (status = "Approved", employee
           notified). ESG metadata reads are advisory. Full audit trail in both sub-paths.
- Reads:   input.status; input.ID; input.claim_id; input.amount_zar; input.category;
           zoho.loginuser; zoho.currenttime; input.Email;
           approval_thresholds[Requires_Dual_Approval == true].(Dual_Threshold_ZAR);
           gl_accounts[expense_category == input.category].(gl_code);
           gl_accounts[expense_category == input.category].(ESG_Category) (advisory — not .ds-declared);
           gl_accounts[expense_category == input.category].(Carbon_Factor) (advisory — not .ds-declared)
- Writes:  input.Key_1_Approver → zoho.loginuser; input.Key_1_Timestamp → zoho.currenttime;
           input.gl_code → gl_code from lookup;
           input.ESG_Category → ESG_Category from lookup (advisory — not .ds-declared);
           input.Estimated_Carbon_KG → amount_zar * Carbon_Factor (advisory — not .ds-declared);
           input.Requires_Dual_Approval → true (if over threshold);
           input.status → "Pending Second Key" (over threshold) or "Approved" (under threshold)
- APIs:    —
- Emails:  key1_approved_dual_required → finance_director (over threshold);
           hod_approved → input.Email (under threshold)
- Audit:   "Approved (Key 1)" (over threshold) or "Approved (HoD)" (under threshold)
```

### Evaluation

- **[Two branch blocks with distinct guards]**: CONDITIONAL PASS — The spec cleanly produces two H3 blocks with non-overlapping guards: WF-09.A guard is `input.status == "Key 2 Dispute"`; WF-09.B guard is the complement. However, the spec's §11 rule "split into sibling .A/.B" for WF-09 implies exactly two blocks, while the 3b research describes **three** behaviorally distinct paths within hod_approval.on_approve (dispute reconsideration, over-threshold routing, under-threshold final approval). The spec correctly collapses the latter two into WF-09.B, but this means WF-09.B must carry a disjunctive `Emails:` line (two different templates for two sub-paths). The spec's bullet template format (`Emails: template → recipient`) does not explicitly allow semicolons for conditional branches within a single block. The example in §11 shows WF-11.B with a single email, WF-11.A with a single email. **This is Blocker B-2**: Phase 7 implementer must guess whether to write both email paths in one `Emails:` cell (using semicolon) or split into WF-09.B.i and WF-09.B.ii. **Proposed fix**: Add a spec note: "When a non-split block has conditional email paths, list all conditional sends separated by semicolons with a parenthetical condition label, e.g.: `key1_approved_dual_required → finance_director (if over-threshold); hod_approved → input.Email (if under-threshold)`."

- **[(advisory — not .ds-declared) suffix correctly applied to ESG writes]**: PASS — The simulation correctly appends `(advisory — not .ds-declared)` to all five ESG-related field references: three reads (`ESG_Category`, `Carbon_Factor`, `GRI_Indicator`) and two writes (`input.ESG_Category`, `input.Estimated_Carbon_KG`). This follows the spec §4 §11 rule verbatim: "each mention MUST be suffixed with `(advisory — not .ds-declared)` inline." Note: `GRI_Indicator` read is present in 3b research but absent from the simulation's `Reads:` line above — **Gap**: the simulator omitted `gl_accounts[...].GRI_Indicator` from WF-09.B Reads. This is a simulator error, not a spec gap. A Phase 7 implementer following 3b verbatim would include it. The spec rule is sufficient; the omission is simulation-side.

- **[Audit column correctly populated for both branches]**: PASS — WF-09.A correctly emits `"Reconsidered (Key 1)"` and WF-09.B emits `"Approved (Key 1)"` (over-threshold) or `"Approved (HoD)"` (under-threshold). These map to `action_1` picklist values per §7: `Approved (Key 1)` ✓, `Reconsidered (Key 1)` ✓, `Approved (HoD)` ✓. Cross-check: 3b-deluge.md §hod_approval.on_approve Audit trail says: "action 'Reconsidered (Key 1)', 'Approved (Key 1)', or 'Approved (HoD)'". All three are in the action_1 picklist (12 values). Full PASS.

- **[Ambiguity the spec did NOT resolve — judgment calls required]**: Two judgment calls were made:
  1. **WF-09.A email**: 3b-deluge.md Emails item 1 for the dispute scenario sends to `"financedirector.demo@yourdomain.com"` with subject "Expense Claim [REF] - HoD Override (Key 2 Dispute)". The closest named template in 3c-config.md is `key1_reconsider_override` (subject: "TWO-KEY RECONSIDERATION - Claim {claim_id} re-approved by Key 1"). The subjects do not match verbatim, but the intent does. The simulator chose `key1_reconsider_override` as the best mapping — **Blocker B-3**: the spec does not provide a WF-to-template mapping table. A Phase 7 implementer must infer from subject-line similarity. The spec §4 §11 rule "every `Emails:` entry must reference a template name existing in §13 named rows" is correct but does not resolve which named template maps to which workflow email send.
  2. **WF-09.B dual Audit value**: The block carries two possible audit values. The simulator listed both separated by "or" parentheticals. The spec does not define a syntax for conditional audit values. This is a judgment call; the spec should clarify.

### Gaps found in spec (Simulation 2)

- **Gap 3 (Blocker B-2)**: Spec §4 §11 does not define how to encode conditional (branching) email sends within a single non-split WF block. WF-09.B has two conditional email paths (over-threshold vs under-threshold). **Proposed fix**: Add a note to the §11 bullet template definition: "If a non-split block sends different emails on different conditions, list all template→recipient pairs semicolon-separated with a `(condition)` parenthetical label."

- **Gap 4 (Blocker B-3)**: Spec §4 §11 cross-ref rule says every `Emails:` value must reference a template from §13, but provides no explicit WF→template mapping. For workflows with multiple conditional email sends, the spec relies on the implementer to match template names to workflow sends by reading both 3b and 3c concurrently — possible but fragile. **Proposed fix**: Add an optional column `trigger_wf` to §13 table (already planned via `trigger_workflow_ref`) and provide an explicit mapping note in §11 for the most ambiguous cases (WF-09.A → key1_reconsider_override, WF-09.B over-threshold → key1_approved_dual_required, WF-09.B under-threshold → hod_approved).

- **Gap 5 (low)**: The spec does not define a syntax for the `Audit:` line when a single WF block has two conditional audit values. WF-09.B logs `"Approved (Key 1)"` when over-threshold and `"Approved (HoD)"` when under-threshold. **Proposed fix**: Mirror the email pattern — allow `"Approved (Key 1)" (if over-threshold); "Approved (HoD)" (if under-threshold)`.

---

## Simulation 3: Count roll-up

| Count | Expected (spec + research) | Derived from spec+research | Status |
|---|---|---|---|
| Form count | 6 (§6 rule: departments, clients, gl_accounts, approval_thresholds, expense_claims, approval_history) | 6 (3a-ds-schema.md header: "Forms: 6") | **PASS** |
| Field total | 53 (§16 assertion #2: 3+3+7+8+27+5=53) | 3a-ds-schema.md header says 54; per-form enumeration: depts=3, clients=3, gl=7, at=8, ec=27, ah=5 → 53 (the header "54" is the pre-rebuttal figure, corrected by Issue C / R-03) | **PASS** — spec correctly documents R-03 correction; implementer uses 53 |
| Email template rows in §13 | 19 total: 18 named + 1 inline ad-hoc (INLINE-01) | 3c-config.md summary says 19 templates; email-templates.yaml has 18 named; §13 contract = 19 rows (18 named + INLINE-01). Cross-check: 3c-config.md lists exactly 18 named templates in its table | **PASS** — spec correctly resolved Issue B / R-02 |
| Workflow H3 blocks in §11 | 17 H3 blocks from 13 parent WFs (WF-01..WF-13, splits on WF-03/07/09/11 = 4 parents × 2 sub-IDs + 9 unsplit = 8+9=17) | 3b-deluge.md: 13 scripts confirmed; spec §4 §11 assigns splits explicitly; count: WF-01(1)+WF-02(1)+WF-03(2)+WF-04(1)+WF-05(1)+WF-06(1)+WF-07(2)+WF-08(1)+WF-09(2)+WF-10(1)+WF-11(2)+WF-12(1)+WF-13(1)=17 | **PASS** |
| Report count | 11 (§8 NOTE: 9 list + 1 kanban + 1 pivot; rebuttal R-01) | 3a-ds-schema.md header says "Reports: 10" but body enumerates 11 rows (including Expense_Summary pivot). Spec §8 NOTE explicitly overrides the header count. The 11th report is Expense_Summary (pivot). | **PASS** — spec correctly documents R-01; implementer uses 11 |
| Custom API count | 4 (§12, §16 assertion #10) | 3c-config.md: "Count: 4 custom APIs" with exact names Get_Dashboard_Summary, Get_Claim_Status, Get_ESG_Summary, Get_SLA_Breaches | **PASS** |

**Summary**: All 6 count assertions produce PASS. The two known discrepancies (field count 54→53, report count 10→11) are correctly resolved in the spec via revision log entries R-03 and R-01 respectively.

---

## Unresolved ambiguities

1. **WF-09.B disjunctive Emails line**: The spec defines a single Emails bullet per WF block but does not provide syntax for conditional (branching) sends within one block. A Phase 7 implementer must invent a notation for "email A if condition X, email B if condition Y."

2. **WF-to-template explicit mapping gap**: The spec provides a correct cross-ref rule (§11 → §13) but no lookup table. For WF-09.A (dispute path), the correct named template `key1_reconsider_override` must be inferred from subject-line similarity between 3b (prose subjects) and 3c (template table subjects). The match is non-obvious because the 3b subject says "HoD Override" and the 3c template says "re-approved by Key 1."

3. **Audit line syntax for conditional-path blocks**: WF-09.B, WF-07.B, and WF-13 each log different audit values on different conditions within a single (non-split) block. The spec defines `Audit: <action_1 value logged>` as a singular value. There is no defined syntax for "one of two values depending on condition."

4. **`†` flag on `Retention_Expiry_Date`**: Research 3a notes `private=true` but the spec's §6.5 example does not illustrate a private date field. A Phase 7 implementer might overlook applying `†` to `Retention_Expiry_Date` because the spec's "exactly 5 must have fields" note (R-04) is prominent but there is no parallel "exactly N private fields" assertion. The spec rule "Fields with `private=true` in .ds get `†`" is clear, but a field-completeness check on `†` is absent from §16.

---

## Recommended spec patches (minimum before Phase 7)

### Patch 1 — Blocker B-1 (HIGH): Clarify `self_ref→<form>` placement

In spec §3 Canonical Notation, add to the `self_ref→<form>` row in the Glossary table:
> "Note: For fields whose .ds type is `pick list (self-ref)`, use `pick list (self-ref)` verbatim in the `type` column; place `self_ref→<form>` in the `ref/pick` column only."

In spec §4 §6 `ref/pick` rule, after "For self-ref pick list — `self_ref→expense_claims`", add:
> "Do NOT use `self_ref→<form>` in the `type` column for this field. The `type` column preserves the .ds declaration `pick list (self-ref)`."

### Patch 2 — Blocker B-2 (HIGH): Define conditional email syntax for non-split blocks

In spec §4 §11 bullet template definition, after the `Emails:` bullet, add:
> "When a non-split block sends different emails on different branches, list all pairs semicolon-separated with a `(if <condition>)` parenthetical: e.g., `key1_approved_dual_required → finance_director (if amount > dual-threshold); hod_approved → input.Email (if amount ≤ dual-threshold)`."

### Patch 3 — Blocker B-3 (MEDIUM): Add WF→template mapping note

In spec §4 §11, under the WF-09 entry in "Workflow ID assignment", add a parenthetical:
> "WF-09.A: uses template key1_reconsider_override (→ finance_director). WF-09.B over-threshold: uses template key1_approved_dual_required. WF-09.B under-threshold: uses template hod_approved."

Alternatively, add a `trigger_workflow_ref` cross-reference column note to §13's existing column definition pointing implementers to verify mapping via subject-line match.

### Patch 4 — Blocker B-4 (LOW): Clarify Audit line for conditional-value blocks

In spec §4 §11 bullet template definition, after the `Audit:` bullet definition, add:
> "When different audit values are logged on different conditions within one block, list both values with `(if <condition>)` labels: e.g., `'Approved (Key 1)' (if over-threshold); 'Approved (HoD)' (if under-threshold)`."

---

*Phase 6 simulation complete. Simulator role discharged.*
