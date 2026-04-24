# Spec Rebuttal — 2026-04-24 — ERM BRD

## 1. Verdict

**ACCEPT WITH CHANGES (numbered below)**.

The spec's skeleton, section-by-section writing contract, cell-encoding rules, and assertion grid are fundamentally sound and usable by Phase 7. However, several load-bearing numeric assertions are **demonstrably wrong against the ground-truth `.ds`** and will cause Phase 6 bisimulation to fail every count-based audit unless corrected before the implementer writes. The three writer-escalated issues all resolve concretely against the ground truth (A→8 gl_accounts revised; B→governance alert is inline, template count stays at 18 **not 19**; C→authoritative field total is **53**, not 54). In addition, the spec propagates an undetected error about report count (11, not 10) and carries several smaller drift issues (picklist-value truncation, role-list mismatch, footnote count, workflow-ref for WF-11.A splits). All fixable by targeted edits; no structural rewrite required.

---

## 2. Resolution of writer-escalated issues

### Issue A — ESG fields on gl_accounts (.ds vs. workflow mismatch)

**Ground-truth evidence** (`Expense_Reimbursement_Management-stage.ds`):

- `form gl_accounts` is declared at line 1001 and closes at line 1137.
- Fields inside the form, in declaration order:
  1. `gl_code` (text) — line 1012
  2. `account_name` (text) — line 1025
  3. `expense_category` (picklist) — line 1038
  4. `receipt_required` (checkbox) — line 1052
  5. `SARS_Provision` (text) — line 1066
  6. `Risk_Level` (picklist) — line 1079
  7. `Active` (checkbox) — line 1094
- Line 1107 is a blank line, then `actions` at 1108. **No further fields exist in the form.**

**Verdict**: `ESG_Category`, `Carbon_Factor`, and `GRI_Indicator` are **NOT declared on `gl_accounts` in the .ds export**. They exist only in `config/field-descriptions.yaml` (lines 60–62) and as *read targets* inside `lm_approval.on_approve` / `hod_approval.on_approve` (research 3b, lines 126, 203). The workflow scripts read `gl_accounts[...].ESG_Category` and `.Carbon_Factor`, but the .ds schema has no such columns; those reads will return null in Creator, silently producing empty ESG outputs.

There is an additional detail the spec currently overlooks: `hod_approval.on_approve` *writes* `input.ESG_Category` and `input.Estimated_Carbon_KG` on the `expense_claims` record (3b-deluge.md line 133–134). `expense_claims` has no such fields in the .ds either. Both write targets silently drop.

**Authoritative gl_accounts field count**: **7**. Do not invent ESG columns.

**Writing rule for Phase 7**:
- §6.3 `gl_accounts` table has **exactly 7 rows**: `gl_code`, `account_name`, `expense_category`, `receipt_required`, `SARS_Provision`, `Risk_Level`, `Active`.
- Do NOT add `ESG_Category`, `Carbon_Factor`, or `GRI_Indicator` to §6.3.
- §15 Out-of-Scope MUST contain a single `[DISCREPANCY]` bullet naming all five missing columns collectively: the three `gl_accounts` reads (`ESG_Category`, `Carbon_Factor`, `GRI_Indicator`) **AND** the two `expense_claims` writes (`ESG_Category`, `Estimated_Carbon_KG`) that the HoD/LM approval scripts reference but that no form declares.
- §14 BR must carry one `(compliance)` rule noting: "ESG/carbon reporting is advisory only until the five referenced fields are added to `gl_accounts` and `expense_claims`; current workflow writes silently no-op."
- §11 `WF-07` and `WF-09` `Reads:` / `Writes:` lines may still mention these field names (so the behavioral intent is preserved for Zia), but each mention MUST be suffixed with `(advisory — not .ds-declared)` inline, to prevent Zia from hallucinating the fields back into §6.3.

### Issue B — governance_alert email template count

**Ground-truth evidence** (`config/email-templates.yaml`, enumerated via `^  [a-z][a-zA-Z0-9_]+:$`):

1. submit_notify_lm (line 12)
2. submit_self_approval_bypass (line 17)
3. resubmit_notify_lm (line 23)
4. resubmit_self_approval_bypass (line 28)
5. lm_approved_final (line 34)
6. lm_approved_escalate (line 39)
7. lm_rejected (line 44)
8. hod_approved (line 50)
9. hod_rejected (line 55)
10. sla_escalation (line 61)
11. sla_reminder (line 66)
12. key1_approved_dual_required (line 73)
13. key2_approved_final (line 78)
14. key2_rejected_dispute (line 83)
15. key2_dispute_notify_employee (line 88)
16. key1_reconsider_override (line 93)
17. key2_sla_reminder (line 98)
18. key2_sla_escalation (line 104)

**There are exactly 18 templates. The research claim of "19" (3c-config.md line 88 and line 207) is wrong** — the config-ingest author miscounted.

**Governance alert evidence** (`.ds` line 176): the finance_approval.on_approve Level-3 block contains an **inline** `sendmail` block in the same-person branch with subject `"GOVERNANCE ALERT - Claim " + input.claim_id + " - Same-Person Key 2 Blocked"`. It is NOT named in `email-templates.yaml`, does NOT map to any of the 18 templates, and does NOT correspond to `sla_escalation` or `key2_sla_escalation` (which fire on SLA timers, not same-person Key-2 conflicts).

**Verdict**: Governance alert is **option (ii) — an inline ad-hoc `sendmail` with no template_id**, NOT a 19th template.

**Writing rule for §13 Email Templates count**:
- §13 has **exactly 18 rows**, one per named template in `email-templates.yaml`.
- §2 Application Meta `Email Templates` row MUST read `18 (named) + 1 inline ad-hoc (see §15)`.
- §16 Reconstruction Checklist assertion #11 MUST read: *"MUST have exactly 18 named email templates PLUS 1 inline `sendmail` block in the finance_approval Level-3 `on approve` `actions` block with subject `GOVERNANCE ALERT - Claim {claim_id} - Same-Person Key 2 Blocked`."*
- §11 `WF-11.A` `Emails:` line MUST be `(inline) Governance Alert → zoho.adminuserid` rather than referencing a template name.
- §15 Out-of-Scope loses the `governance_alert template discrepancy` entry (it is now resolved) but gains `[DISCREPANCY] 3c-config.md summary states 19 email templates; authoritative count from email-templates.yaml is 18.`

### Issue C — field count 53 vs 54

**Ground-truth evidence** (walked `.ds` offset 14–1138):

| Form | Declaration line | Field link_names | Count |
|---|---|---|---|
| approval_history | 14 | claim, action_1, actor, timestamp, comments | **5** |
| approval_thresholds | 266 | tier_name, max_amount_zar, approver_role, Active, Tier_Order, Requires_Dual_Approval, Dual_Approval_Role, Dual_Threshold_ZAR | **8** |
| clients | 414 | client_id, name, is_active | **3** |
| departments | 497 | department_id, name, is_active | **3** |
| expense_claims | 580 | Employee_Name1, Email, Submission_Date, claim_id, department, Claim_Reference, client, Expense_Date, Department_Shadow, category, Client_Shadow, amount_zar, Supporting_Documents, description, VAT_Invoice_Type, POPIA_Consent, status, Rejection_Reason, Version, Retention_Expiry_Date, Parent_Claim_ID, gl_code, Requires_Dual_Approval, Key_1_Approver, Key_1_Timestamp, Key_2_Approver, Key_2_Timestamp | **27** |
| gl_accounts | 1001 | gl_code, account_name, expense_category, receipt_required, SARS_Provision, Risk_Level, Active | **7** |

**Sum = 5 + 8 + 3 + 3 + 27 + 7 = 53**, not 54.

Reconciliation with `field-descriptions.yaml`: described fields total 52 (expense_claims 19 described + approval_history 5 + approval_thresholds 8 + gl_accounts 10 (includes ESG trio that is NOT in .ds) + departments 3 + clients 3 + compliance_config 4 (not in .ds)). Neither 52 nor 54 aligns with the .ds row total. The 3c-config.md "54 field descriptions" claim is an approximate count that mixes advisory fields with declared ones.

Compound name sub-fields: `Employee_Name1` is a single `type = name` field (line 591) with four visual sub-components (`prefix`, `first_name`, `last_name`, `suffix`). The .ds declares it as a single field; Creator reconstructs it as one compound field. It does NOT count as four fields. `Employee_Name1.prefix` is a visible/hidden sub-component, not a top-level field.

**Verdict**: Authoritative field total is **53**. The "54" in research 3a-ds-schema.md header line 4 and in the brief is an off-by-one propagated from 3c-config.md's inflated description count.

**Authoritative numbers Phase 7 MUST assert in §2 and §16**:
- §2 Application Meta `Fields` row: `53`
- §16 assertion #2: *"MUST have exactly 53 fields across all forms (departments: 3, clients: 3, gl_accounts: 7, approval_thresholds: 8, expense_claims: 27, approval_history: 5)."*
- §16 assertion #7 picklist count remains 6 (see additional findings for the `Employee_Name1_prefix` picklist is an inline sub-component enum, not a first-class named picklist — move to note).
- §5 Data completeness assertion A2 MUST be updated: `expense_claims=27, departments=3, clients=3, gl_accounts=7, approval_thresholds=8, approval_history=5. Sum = 53.`

---

## 3. Additional issues found (ranked by severity)

### R-01
- **ID**: R-01
- **Severity**: **blocker**
- **Location**: spec §2 (Application Meta counts), §5 A7, §8 ordering NOTE, §16 assertion #5, §6 writer workflow step 10
- **Issue**: The spec instructs the writer to use "10 reports", citing 3a-ds-schema.md as containing "10 reports". The `.ds` file declares **11 reports** (9 `list` + 1 `kanban` at line 1212 + 1 `pivottable Expense_Summary` at line 1444). Research 3a-ds-schema.md's Reports section actually lists 11 rows (including `Expense_Summary`); only its own header claims 10. The spec's ordering hint even lists 11 names and then tells the writer to "use only what appears in 3a-ds-schema.md §Reports (10 rows). Do not invent an 11th" — this instruction forces the writer to drop a real report.
- **Impact**: Phase 7 will produce either (a) 10 rows missing `Expense_Summary` (the only pivot) — violating SC-3 (every report reconstructible) and breaking assertion A7 which promises "exactly 1 row has view_type = pivot", OR (b) 10 rows missing a list report — both outcomes fail Phase 6 bisimulation.
- **Fix**: Replace the §8 NOTE with: *"The .ds declares 11 reports (9 list, 1 kanban, 1 pivottable). Use all 11; Expense_Summary is the pivot."* Change §2 count to `11 (9 list + 1 kanban + 1 pivottable)`. Change §5 A7 to *"Exactly 11 rows in §8 Reports Catalog; exactly 1 row has `view_type = pivot` (`Expense_Summary`); exactly 1 has `view_type = kanban` (`gl_accounts_by_expense_category`)."* Change §16 #5 to *"MUST have exactly 11 reports: 9 list, 1 kanban (gl_accounts_by_expense_category), 1 pivot/summary (Expense_Summary)."* Update writer workflow step 10 accordingly.

### R-02
- **ID**: R-02
- **Severity**: **blocker**
- **Location**: spec §2, §5 A9, §13, §16 #11
- **Issue**: Email template count asserted as 19; authoritative ground truth is 18 (see Issue B resolution).
- **Impact**: Every A9 audit fails; Phase 6 will reject.
- **Fix**: Everywhere the number `19` appears for email templates, replace with `18 named + 1 inline`. See Issue B for exact replacement strings.

### R-03
- **ID**: R-03
- **Severity**: **blocker**
- **Location**: spec §2, §5 A2, §16 #2, §4 (implicit), writer workflow step 8
- **Issue**: Field count asserted as 54; authoritative ground truth is 53 (see Issue C resolution).
- **Impact**: Every A2 and §16 #2 audit fails.
- **Fix**: Replace `54` with `53` in §2 counts, §5 A2, §16 #2, and all cross-references.

### R-04
- **ID**: R-04
- **Severity**: **major**
- **Location**: spec §3 Glossary (lines ~40–85), §6 `flags` rules, §6 form-level note for expense_claims
- **Issue**: The `*` flag is defined as "required (must have)" and the writer is told to assign it when a field has `must have` in the .ds. The `.ds` marks exactly five fields with `must have`: `Employee_Name1` (591), `Email` (628), `Submission_Date` (643), `Claim_Reference` (689), `Supporting_Documents` (778). The spec nowhere enumerates these, and lines like *"Ensure Department_Shadow and Client_Shadow carry `†` flag"* correctly hint at privacy but never tell the writer which fields carry `*`. A consistent `*` application is material because §11 WF-04 Effect references "Supporting_Documents must not be null" as BR-enforced.
- **Impact**: Phase 7 risks assigning `*` by guesswork (e.g., giving `amount_zar` `*` because "amount is obviously required" when the .ds does not declare it as `must have`), producing a BRD that diverges from the .ds's declared required-field set.
- **Fix**: Add to §6 Cell encoding rules a numbered sub-bullet: *"The .ds declares exactly 5 `must have` fields across the entire app: `expense_claims.Employee_Name1`, `expense_claims.Email`, `expense_claims.Submission_Date`, `expense_claims.Claim_Reference`, `expense_claims.Supporting_Documents`. ONLY these 5 fields carry the `*` flag. No other form has any `must have` fields."* Add a corresponding §16 assertion: *"MUST have exactly 5 required (`must have`) fields — all on `expense_claims`."*

### R-05
- **ID**: R-05
- **Severity**: **major**
- **Location**: spec §7 Picklist Appendix ordering and examples, §5 A5
- **Issue**: The `action_1` picklist on `approval_history` has **12 values** in the .ds (line 50): `Submitted, Submitted (Self-approval bypass), Approved (LM), Approved (HoD), Approved (Key 1), Approved (Key 2), Rejected, Rejected (Key 2), Reconsidered (Key 1), Escalated (SLA Breach), Resubmitted, Warning`. The spec never enumerates these or pins the count. §11 WF-11.A `Audit:` line uses `"Warning"`, which is present — good — but assertion A13 "Every `Audit:` value ... appears in the `action_1` picklist" needs the picklist values nailed down, and the §7 content contract must state "12 values".
- **Impact**: Phase 7 may truncate (e.g., write 6 "approved-ish" values) or omit `Warning`, breaking A13 when WF-11.A is validated.
- **Fix**: Add an explicit enumeration in §7 and §5 A-series: *"`action_1` picklist MUST contain exactly 12 values in this order: Submitted, Submitted (Self-approval bypass), Approved (LM), Approved (HoD), Approved (Key 1), Approved (Key 2), Rejected, Rejected (Key 2), Reconsidered (Key 1), Escalated (SLA Breach), Resubmitted, Warning."* Add §16 assertion: *"MUST have `approval_history.action_1` picklist with exactly 12 values."*

### R-06
- **ID**: R-06
- **Severity**: **major**
- **Location**: spec §9 Roles (§9.1 ordering, §9.2 matrix rows, §5 A16), §16 #8
- **Issue**: The spec lists 7 internal roles in §16 #8: *"Employee, Line Manager, Head of Department, Finance Director, Finance Accountant, System Administrator, plus portal roles (Client Rep, Vendor, Customer)"*. That sentence contains **6 internal roles** ("plus portal roles" is the 7th slot but the count says 7 and lists 6 names). Research 3c-config.md lists **7 internal roles**: Employee, Line Manager, Head of Department (HoD), Finance Director, Finance Accountant, System Administrator, **Developer**. The spec silently drops `Developer`. Separately, §9.1 ordering instruction also omits `Developer`.
- **Impact**: A16 asserts exactly 7 data rows in §9.2 (6 internal + 1 portal). With Developer added as a 7th internal role, the matrix actually needs **8 rows** (7 internal + 1 combined-portal), or Developer is dropped (losing role fidelity). Either way, spec and assertion contradict.
- **Fix**: Pick one. Recommended: include `Developer` as 7th internal role (kind = `internal`, purpose = "Development access only", §9.2 CRUD = `R` on all forms per 3c-config.md "No/No/No"). Update §9.1 ordering to end with `Developer`, then portal roles. Change §5 A16 to *"The §9.2 CRUD matrix has exactly 8 data rows (7 internal + 1 combined-portal)."* Change §16 #8 to *"MUST have exactly 7 internal roles: Employee, Line Manager, Head of Department, Finance Director, Finance Accountant, System Administrator, Developer. Plus 3 portal roles represented as 1 combined row."*

### R-07
- **ID**: R-07
- **Severity**: **major**
- **Location**: spec §11 workflow ID assignment table (lines ~575–587) vs. §10 workflow_ref and §13 trigger_workflow_ref
- **Issue**: The spec assigns WF-03 to `expense_claim.on_success` with branches `.A normal, .B bypass`. It separately assigns WF-04 to `expense_claim.on_success.fill_shadows` and WF-05 to `expense_claim.on_success.generate_ref`. But `§5 A11` says *"Exactly 13 H3 heading blocks in §11 Workflow Catalog (counting split .A/.B pairs as separate headings but the same parent WF-NN count). The un-split parent count is 13."* With the split on WF-03 (2 branches), WF-07 (2), WF-09 (2), WF-11 (2), there are 13 parents but **17 headings**. The spec's §11 Format sentence says *"13 total H3 blocks (some scripts with two clear branches may expand to 14-15 blocks if split; document the split decision explicitly)"* — this predicts 14-15, but the writer's own ID table specifies 4 splits = 17 blocks. Separately, §13 example references `submit_notify_lm` with `trigger_workflow_ref = WF-03.A`, but WF-03 is `expense_claim.on_success` (which assigns to LM); the *submission* to LM is triggered via `submit_notify_lm`'s `Trigger: Submission` — this maps to WF-03 (the first success branch) normal case. Correct.
- **Impact**: Phase 7 has ambiguous instructions on split count; Phase 6 A11 as-written can be read two ways.
- **Fix**: Rewrite §5 A11 to: *"Exactly 17 H3 heading blocks in §11 Workflow Catalog, corresponding to 13 parent workflows (WF-01..WF-13), with splits on WF-03 (.A, .B), WF-07 (.A, .B), WF-09 (.A, .B), WF-11 (.A, .B)."* Update §11 Format paragraph to say *"17 total H3 blocks from 13 parent scripts."* Update §16 #9 to match.

### R-08
- **ID**: R-08
- **Severity**: **major**
- **Location**: spec §6 writer-workflow step 8 for expense_claims (line 952–954)
- **Issue**: The writer is told to set `Parent_Claim_ID.type = "self_ref→expense_claims"` even though the .ds declares it as `type = picklist` with `values = expense_claims.ID`. The instruction adds *"Note the type discrepancy in the `help` cell or a footnote"*. This departs from the locked Phase 4 decision that types are Zoho-native verbatim from the .ds. A self-referential picklist in Creator is a legitimate Zoho pattern (a filtered single-pick with an in-form values expression); overriding it to `self_ref→expense_claims` in the BRD may cause Zia's builder to generate an actual `lookup` field, which has different behavior than a picklist-filtered self-reference.
- **Impact**: Semantic drift from ground truth. SC-1 (forms reconstructible) at risk.
- **Fix**: Keep the .ds declaration: `type = pick list (self-ref)` in the type column, populate `ref/pick` with `self_ref→expense_claims` (which is the §3 relational-arrow notation — ref/pick is fine for this), and add a 1-sentence `help` note explaining it stores a reference to another claim. Do NOT override the type. Also: since this is a `pick list (self-ref)`, §5 cardinality for the self-ref edge is `N:1` (one parent per claim), and `self_ref: yes` — already stated; unchanged.

### R-09
- **ID**: R-09
- **Severity**: **major**
- **Location**: spec §9.1 and §9.2 (Portal roles), §16 #8
- **Issue**: The spec treats portal roles as `"Client Rep / Vendor / Customer"` — three portals. But research 3c-config.md line 38 lists Developer as an internal role AND line 44–46 lists three portal roles (`Client Representative`, `Vendor`, `Customer`). However, the .ds file's `permissions` block (lines ~3560–3630 based on the earlier grep of `form` occurrences) declares permissions for *all seven* roles across forms. Additionally, the permissions block at lines 3562–3582 (and the shadow copies at 3606–3626) handle portal visibility separately. The spec lists portal roles as Customer/Developer/Vendor/Client Rep in one place (blueprint line 140) and Client Rep/Vendor/Customer elsewhere — `Developer` is mis-classified as portal in the blueprint but is internal per 3c-config.md.
- **Impact**: §9 matrix confusion; portal combined-row undercount or overcount.
- **Fix**: Anchor §9.1 role list to 3c-config.md exactly — 7 internal (including Developer) + 3 portal (Client Representative, Vendor, Customer). §9.2 combined portal row covers exactly those 3. Remove `Developer` from any "portal roles" mention in the spec and in the blueprint-derived example paragraph the spec imports.

### R-10
- **ID**: R-10
- **Severity**: **major**
- **Location**: spec §13 (Email Templates columns) and §5 A9/A10/A12
- **Issue**: The `email-templates.yaml` `cc_role` is populated for 2 templates: `sla_reminder` has `cc_role: hod`, and `key2_sla_reminder` has `cc_role: admin`. The spec's §13 `cc` column encoding rule says *"role name or `—`"* — good — but the example shows `—` for both sample rows. The writer must not blanket-fill `—`. Additionally, two templates use `to_field` (not `to_role`): `lm_approved_final`, `lm_rejected`, `hod_approved`, `hod_rejected`, `key2_approved_final`, `key2_dispute_notify_employee`, `key2_sla_escalation` — 7 templates go to `input.Email` / `zoho.adminuserid`. The spec's `to` encoding rule permits both but does not enumerate.
- **Impact**: Moderate: the BRD may render CCs as `—` universally and lose SLA-reminder CC chains, weakening SC-7.
- **Fix**: Add to §13 Cell encoding rules: *"`cc` MUST be populated from `email-templates.yaml` `cc_role` field. Exactly 2 templates have CC: `sla_reminder` (cc=hod), `key2_sla_reminder` (cc=admin)."* Add a §16 assertion: *"MUST have CC recipients on exactly 2 email templates: sla_reminder (hod), key2_sla_reminder (admin)."*

### R-11
- **ID**: R-11
- **Severity**: **minor**
- **Location**: spec §7 ordering (line 383–389), §5 A5
- **Issue**: The spec lists 6 named picklists alphabetically: `action_1, category, Employee_Name1_prefix, Risk_Level, status, VAT_Invoice_Type`. But `Employee_Name1_prefix` is an *inline sub-component enum* on the `prefix` sub-component of the compound `Employee_Name1` field (ds line 600): `value = {"Mr.","Mrs.","Ms."}`. It is not a top-level Creator picklist; it is a values list inside a name-component declaration. The .ds has it with `visibility = false`. Treating it as a named picklist creates a picklist in Zia that would not otherwise exist. Per §3 Glossary, `pick list pick{a,b,c}` is specifically for inline picklists with ≤3 values — this prefix enum (3 values) fits perfectly.
- **Impact**: Zia may generate an orphan picklist definition; no consumer references it.
- **Fix**: Demote `Employee_Name1_prefix` to an inline `pick{Mr.,Mrs.,Ms.}` expression in §6.5 `ref/pick` for the compound name's prefix sub-component note, and REMOVE it from §7 Picklist Appendix. §7 now has **5** named picklists: `action_1, category, Risk_Level, status, VAT_Invoice_Type`. Update §5 A5 and §16 #7 to `5` named picklists.

### R-12
- **ID**: R-12
- **Severity**: **minor**
- **Location**: spec §8 Reports Catalog conditional-formatting cell encoding
- **Issue**: The spec's `cond_format` column rule says *"`<field>:<value>=<color>` pairs; `—` if none. Use color name or hex shorthand."* Ground truth .ds uses exact hex values (e.g., `#1bbc9b`, `#e84c3d`, `#bd588b`, `#765f89`, `#107c91`). The spec allowing "color name" invites Phase 7 to output `teal`/`red`/`amber`, which Zia cannot reliably map back to hex.
- **Impact**: Creator reconstruction of conditional formatting degrades to approximate colors; §16 #14 literally asserts specific hex codes.
- **Fix**: Change the cond_format encoding rule to require full hex (`#rrggbb`) verbatim from the .ds. Remove "color name" option. Add: *"Multiple field-value pairs in one cell are semi-separated."*

### R-13
- **ID**: R-13
- **Severity**: **minor**
- **Location**: spec §10 Workflow State Machine `trigger` vocab (line 536)
- **Issue**: The `trigger` column vocab lists `form_submit, lm_approve, lm_reject, hod_approve, hod_reject, fd_approve, fd_reject, sla_timer, on_edit` (9 values). The `.ds` / deluge model also requires a `hod_override` trigger distinct from `hod_approve` for the dispute-reconsideration path (`WF-09.A`): from `"Key 2 Dispute"` → `"Pending Second Key"` by HoD action. The spec's enum has no name for that; using `hod_approve` conflates two semantically different transitions.
- **Impact**: Assertion A20 (every workflow_ref maps) passes, but the state-machine table loses fidelity on the dispute loop.
- **Fix**: Add `hod_override` to the trigger enum; update §10 to include a transition row: *"`"Key 2 Dispute"` | hod_override | always | `"Pending Second Key"` | Head of Department | → WF-09.A"*.

### R-14
- **ID**: R-14
- **Severity**: **minor**
- **Location**: spec §12 (Custom APIs `invoked_by`)
- **Issue**: The spec asserts `invoked_by = —` for all 4 APIs. Research 3c-config.md "Deluge Manifest" says Custom APIs are `context = 'custom-api'` — called externally or by widgets. The spec correctly notes widgets=0. However, the table cell being `—` risks Zia interpreting "no caller" as "dead code" and pruning. The research 3d-context.md hints these are used for dashboards and external systems.
- **Impact**: Cosmetic; Zia unlikely to prune but may flag.
- **Fix**: Set `invoked_by = external (REST)` for all 4. Add a one-sentence note in §12 that no internal workflow invokes Custom APIs; external consumers only.

### R-15
- **ID**: R-15
- **Severity**: **minor**
- **Location**: spec §6.5 gotcha about `pending_approvals_manager` and `My_Claims` columns
- **Issue**: The research 3a-ds-schema.md shows `pending_approvals_manager.visible_columns` includes 18 fields and `My_Claims.visible_columns` includes 17 fields (subset). Zia must reconstruct exact column ordering for report fidelity. The spec's §8 Cell encoding rule says *"comma-separated field link_names in display order, verbatim from .ds"* — good — but does not cap cell length. A single cell with 18 comma-separated names + display-name aliases ≈300 chars may hit GFM table rendering issues with many other wide columns on the row.
- **Impact**: Minor rendering risk; does not break Zia ingest (plain text) but may hurt human readability.
- **Fix**: Permit a sub-bulleted list under the row when `columns` exceeds 10 fields. Mention this in §8 Cell encoding rules.

### R-16
- **ID**: R-16
- **Severity**: **minor**
- **Location**: spec §15 Out-of-Scope bullet 6 (compliance_config discrepancy)
- **Issue**: The bullet says `compliance_config` has 4 fields. This is correct. But the bullet fails to note that `config/seed-data/compliance_config.json` exists (per 3c-config.md line 187) and that `WF-02` validation checks can also read config entries (`ORG_TYPE`, `ESG_REPORTING`) per 3d-context.md line 36. A terse `[DISCREPANCY]` is fine, but writers reading this may assume compliance_config is truly irrelevant and drop all references from §14 BR rules — weakening SC-5 traceability.
- **Impact**: Cosmetic; BR-NNN references may be too terse.
- **Fix**: Append to bullet 6: *"Any §14 BR referencing organization-type/ESG toggles must tag `enforced_by: config (compliance_config advisory)` to preserve traceability."*

### R-17
- **ID**: R-17
- **Severity**: **minor**
- **Location**: spec §16 #13 (approval_history append-only)
- **Issue**: Correctly asserts approval_history is append-only (no Edit/Delete/Duplicate). But the .ds `form approval_history` declares BOTH `on add` and `on edit` action buttons at lines 104–131. The append-only posture is enforced at the **menu/report** layer, not the form layer. The spec elsewhere correctly notes "View" menu perms; need to anchor the append-only invariant to menu perms, not form-level.
- **Impact**: Minor; Zia may create Edit UI on form while permissions block it in menu — both could coexist but confuses auditors.
- **Fix**: §16 #13 rewrite: *"MUST configure `approval_history` reports (`approval_history_Report`, `Audit_Trail`) with menu permissions excluding Edit/Delete/Duplicate/Import/Export/Print; the form itself may retain default Edit action (menu enforcement suffices)."*

---

## 4. Passed checks (audit record)

- Verified every `WF-NN` ID in §11 workflow-assignment table (lines 575–587) maps to a distinct Deluge script in 3b-deluge.md.
- Verified §11 example WF-11.A prose is consistent with the actual `.ds` same-person block at lines 153–181 (status → "Pending Second Key", action_1 → "Warning", governance alert email).
- Verified the 9 `status` picklist values in §16 #6 and §7 match the `.ds` line 839 `values = {…}` array exactly.
- Verified §5 lookup edges (5 total, 1 self-ref) match the .ds: `approval_history.claim → expense_claims` (line 29), `expense_claims.department → departments` (line 676), `expense_claims.client → clients` (line 706), `expense_claims.gl_code → gl_accounts` (line 907), `expense_claims.Parent_Claim_ID → expense_claims` (line 895).
- Verified §6.5 `Parent_Claim_ID` is indeed declared `type = picklist` with `values = expense_claims.ID` in the .ds (line 893) — confirming the type-vs-behavior dissonance that R-08 addresses.
- Verified every field in field-descriptions.yaml for `expense_claims` (19 described) maps to a real .ds field.
- Verified `form-level rules` for `expense_claims` (7 validation gates listed at line 115 of 3a) align with `expense_claim.on_validate` script summary in 3b (8 gates — one extra is the positive-amount gate, which is implied in rule 3).
- Verified §3 Glossary notation DSL is internally consistent; every symbol used in downstream sections (`lookup→`, `@Picklist:`, `pick{}`, `fx:`, `*`, `‡`, `†`, CRUD letters) is defined.
- Verified `Audit_Trail` report (line 1293) uses `timestamp ascending` sort — consistent with spec §8 example contract.
- Verified `Expense_Summary` (line 1444) is declared as `pivottable` in .ds with `layout = 4`, `records displayed = all_records`, `allow export = false`, `allow drilldown = false` — exactly what §8 example captures.
- Verified `Submitted` status appears both in `action_1` picklist (12 values) and `status` picklist (9 values) — they are distinct picklists despite sharing a value; spec correctly separates them in §7.
- Verified §11 example WF-04 `Writes:` chain (`status → "Submitted"; Submission_Date → zoho.currenttime; Retention_Expiry_Date → zoho.currenttime + 5y`) matches `expense_claim.on_validate` code path in 3b-deluge.md.
- Verified A14 (4 Custom APIs) matches 3c-config.md line 12.
- Verified A19 (0 widgets) matches 3c-config.md line 18.

---

## 5. Revised assertions

Given the three escalations + additional findings, Phase 7 MUST assert these corrected numbers in §2 Application Meta and §16 Reconstruction Checklist:

| Property | Spec value | **Corrected value** | Source |
|---|---|---|---|
| Forms | 6 | 6 | unchanged |
| Fields (total) | 54 | **53** | Issue C |
| Fields (expense_claims) | 27 | 27 | unchanged |
| Fields (gl_accounts) | 7 | 7 | unchanged |
| Required (`*`) fields | — | **5** (all on expense_claims) | R-04 |
| Lookups | 5 | 5 | unchanged |
| Self-ref edges | 1 | 1 | unchanged |
| Subforms | 0 | 0 | unchanged |
| Reports | 10 | **11** (9 list + 1 kanban + 1 pivot) | R-01 |
| Status values | 9 | 9 | unchanged |
| action_1 values | — | **12** | R-05 |
| Roles (internal) | 6 (listed) | **7** (incl. Developer) | R-06 |
| Roles (portal) | 3 (Client Rep, Vendor, Customer) | 3 | R-09 |
| §9.2 matrix rows | 7 | **8** (7 internal + 1 combined portal) | R-06 |
| Named picklists | 6 | **5** (drop Employee_Name1_prefix) | R-11 |
| Workflows (parent) | 13 | 13 | unchanged |
| Workflow H3 blocks (with splits) | 13-15 | **17** (4 split into .A/.B) | R-07 |
| Custom APIs | 4 | 4 | unchanged |
| Email templates (named) | 19 | **18** | Issue B |
| Email templates (inline ad-hoc) | — | **1** (Governance Alert) | Issue B |
| Templates with CC | — | **2** (sla_reminder, key2_sla_reminder) | R-10 |
| Widgets | 0 | 0 | unchanged |
| Business rules | ~20–25 | ~20–25 (one new BR for ESG advisory) | R-01 plus Issue A |

---

## 6. Bottom line for writer

Three count-based assertions in the current spec are factually wrong against the ground-truth `.ds`: **field total is 53 not 54**, **report total is 11 not 10**, **named email templates are 18 not 19** (plus 1 inline `sendmail` Governance Alert in WF-11.A). Fix these in §2 Application Meta counts, §5 Data Completeness Assertions A2/A7/A9, and §16 Reconstruction Checklist items #2, #5, #11 before the implementer writes anything else; every downstream cross-reference follows from them. Additionally, §9 Roles drops `Developer` (needs to be restored as a 7th internal role) and §7 Picklist Appendix wrongly promotes `Employee_Name1_prefix` from inline sub-component enum to named picklist (remove — 5 named picklists, not 6). Finally, tighten the `Parent_Claim_ID` type rule in §6.5 to preserve the .ds's `pick list (self-ref)` declaration rather than rewriting it as `self_ref→expense_claims`, and add the ESG-fields-missing-from-.ds discrepancy (5 missing fields total: 3 on gl_accounts, 2 on expense_claims) to §15 and §14 (BR `enforced_by: advisory`). With these edits the spec is ready for Phase 7.
