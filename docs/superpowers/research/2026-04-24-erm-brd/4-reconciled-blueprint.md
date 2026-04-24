# Reconciled BRD Blueprint — Phase 4 Bisim Output

Both Twin A and Twin B produced independent blueprints (transcripts in conversation log). Convergence reached after 1 round — all load-bearing decisions aligned; ~10 encoding-tactic divergences reconciled below with explicit picks and reasoning.

## Convergences (both twins agreed)
- Forms rendered in dependency order (leaf lookups first, transaction hub next, audit child last).
- Wide CRUD matrix (roles × forms), letter-code cells (`C/R/U/D` or `—`).
- Workflows ordered by lifecycle fire-order (load → validate → success → edit → approvals L1→L2→L3 → scheduled).
- Shared picklists deduplicated via named appendix with cross-references.
- Reports as single wide table.
- Email templates: subject + `{{variable}}` contract, no body prose.
- Field-level CRUD exceptions in dedicated override table (not inlined).
- Reports + Custom APIs + Email Templates + Seed Data are tabulated (homogenous data).
- Terminal §16 Reconstruction Checklist giving Zia self-audit counts.

## Reconciled divergences (with rationale)

| Decision | Twin A | Twin B | **Picked** | Rationale |
|---|---|---|---|---|
| Type names | normalized (`text`, `int`, `decimal(ZAR)`) + glossary remap | Zoho-native (`pick list`, `auto number`, `rich text (textarea)`) | **Zoho-native (B)** | Zia targets Creator; native names map 1:1 to Creator palette, no translation layer. |
| CRUD scope qualifier | `*` asterisk | numbered footnotes (¹²³) | **footnotes (B)** | Unambiguous; avoids glossary round-trip. |
| State machine encoding | ASCII diagram + transitions table | transitions table only | **table only (B)** | ASCII costs tokens, fragile, LLM-optimal form is relational. |
| Workflow block shape | 8-line bulleted block (`- Trigger:`, `- Effect:`, …) | 10-row 2-col GFM table per workflow | **bulleted block (A)** | Denser (~14 lines vs ~18), consistent key prefixes still regex-parseable. |
| Picklist inline threshold | ≤6 values & single-use inline | ≤3 values & single-use inline | **≤3 (B)** | Promotes more picklists to appendix → dedup wins. |
| Include `compliance_config` form | omit; not in .ds | stub with flag | **omit (A)** | Don't reconstruct unverified schema; flag in §15 Out-of-Scope only. |
| Ingestion-contract header | — | YAML front-matter block | **adopt (B)** | Low-cost, high-signal anchor for LLM ingestor. |
| Compliance frame as standalone section | yes (§3 bullets) | folded into BR-NNN | **fold into BR-NNN (B)** | Compliance is enforced by fields/rules — centralize in Business Rules Index. |
| Business Rules Index (BR-NNN) | — (rules scattered per-form) | dedicated numbered index | **adopt (B)** | Stable IDs for cross-referencing; concentrates compliance traceability. |
| Named macros (`@Reset:DualApproval`) | propose | — | **skip (B's implicit)** | Overclever for a document; restate inline. |
| Shared picklist notation | `@Picklist:category` | same | **`@Picklist:name`** | Both agree. |

## Final section order (16 sections)

1. **Ingestion Contract** — YAML-style fenced block: doc version, target app, locale defaults, notation anchor, "how to read" directive. (~15 lines)
2. **Application Meta** — key:value table: name, display, author, version, currency, TZ, date/time fmt, counts. (~14 lines)
3. **Glossary & Notation Legend** — GFM table (Symbol | Meaning | Example) for `lookup→`, `pick{}`, `fx:`, `*`, `‡`, `†`, CRUD letters, footnote scope markers, `@Picklist:`. (~25 lines)
4. **Entity Catalog** — 6-row wide table: form, label, kind (txn/ref/audit/config), purpose, key_field, fk_to, row_count_class. (~10 lines)
5. **Entity-Relationship Skeleton** — edge list table: from_form, field, to_form, cardinality, on_delete, self_ref. (~10 lines)
6. **Form Catalog** — one subsection per form (6 total). Each: 1-line purpose, ONE wide GFM field table (columns: `link_name | label | type | flags | default | ref/pick | help`), then numbered form-level rule block if any. Forms in order: `departments`, `clients`, `gl_accounts`, `approval_thresholds`, `expense_claims`, `approval_history`. (~240 lines)
7. **Picklist Appendix** — H3 per shared picklist, fenced block with values, `Used by:` cross-reference line. (~40 lines)
8. **Reports Catalog** — single wide table: name, display_name, source_form, view_type, filter, sort, columns, grouping, cond_format, menu_perms. (~18 lines)
9. **Roles & Access Model** — (a) role definitions table, (b) record-level CRUD matrix (wide: roles × forms), (c) scope footnotes, (d) field-level overrides table for ~10 exceptions. (~55 lines)
10. **Workflow State Machine** — status enum bullets (terminal/non-terminal classification), transitions table: from_status, trigger, condition, to_status, actor_role, workflow_ref. (~25 lines)
11. **Workflow Catalog** — one subsection per workflow (13 total), using fixed 8-bullet compact template:
    ```
    ### <workflow_id>  <script_name>
    - Trigger: <form>.<event> (<actor_role> | scheduled <freq>)
    - Guard:   <boolean | "always">
    - Effect:  <1-paragraph plain English>
    - Reads:   <semi-separated field refs>
    - Writes:  <semi-separated assignments>
    - APIs:    <Custom API names | "—">
    - Emails:  <template_name → recipient; …>
    - Audit:   <approval_history.action_1 value | "—">
    ```
    Ordered: on_load → on_validate → on_success (× 3) → on_edit → LM approval → HoD approval → Finance approval → scheduled. Multi-branch scripts split into `WF-NN.A` / `WF-NN.B`. (~195 lines)
12. **Custom APIs** — single wide table: name, method, params (typed, req/opt), returns (shape), permissions, invoked_by, purpose. (~10 lines)
13. **Email Templates** — single wide table: id, trigger_workflow_ref, to, cc, subject_template, variables, intent. (~25 lines)
14. **Business Rules Index** — numbered `BR-NNN  (category) statement → enforced_by: <workflow_id | form_validation | role_permission>`. Covers compliance (King IV, SARS, POPIA, ISSB), approval thresholds, SLA, dual-approval, retention. (~50 lines)
15. **Out of Scope / Known Discrepancies** — explicit exclusions (widgets=0, subforms=0, full Deluge code, portal role fine-grained CRUD) + discrepancies (e.g., `compliance_config` in field-descriptions YAML but absent from `.ds` export — advisory only). (~15 lines)
16. **Reconstruction Checklist** — numbered "must"-phrased count assertions Zia can self-verify (6 forms, 54 fields, 5 lookup edges, 9 status values, 7 roles, 19 email templates, 4 Custom APIs, 13 workflows, 10 reports, 6 named picklists). (~18 lines)

## Density tactics locked in

### Type notation (Zoho-native + compact DSL arrows)
- `text`, `number`, `decimal`, `currency(ZAR)`, `date`, `date time`, `boolean`, `email`, `phone`, `url`, `image`, `file upload`, `rich text (textarea)`, `auto number`, `pick list`, `multi select`, `name (compound)` — native Creator palette.
- Relational arrows: `lookup→<target_form>`, `subform→<target_form>`, `self_ref→<target_form>`.
- Formulas: `fx:"<expr>"` with expression verbatim.
- Shared picklists: `pick list @Picklist:<name>`; inline picklists: `pick list pick{a,b,c}`.

### Flag string (field-level)
Compact flags in one cell: `*` = required, `‡` = unique, `†` = private/hidden, concatenated as `*‡`. Defined in §3 Glossary.

### CRUD cell alphabet
- Cell alphabet: `C`, `R`, `U`, `D`, concatenated (e.g. `CRU`, `CRUD`, `R`). `—` = no access.
- Scope qualifiers: numbered superscripts `¹²³` pointing to footnote beneath matrix (e.g. `C R¹ U¹` = scoped to own records per footnote 1).
- Field-level overrides live in §9(d), not cell-level.

### Workflow `Reads/Writes` micro-syntax
- Reads: semi-separated tokens in form `input.<field>`, `zoho.<var>`, `<form>[<filter>].<field>`.
- Writes: semi-separated `input.<field> := <value>` with arrow `→` also accepted (e.g. `status → "Approved"`).
- Lookups with multi-field pulls: `<form>[<filter>].(field1,field2,field3)`.

### State machine transitions
- Row: `from_status | trigger | condition (guard) | to_status | actor_role | workflow_ref (→ WF-NN)`.
- `workflow_ref` FK to §11 workflow IDs; eliminates duplication of side effects.

### Email template body contract
Body column omitted; `variables` column lists all `{{var}}` tokens. `intent` column is 1 sentence. Subject stays as literal template string.

## Worked-example target format (locked)

**Form `approval_thresholds`** in §6 — tabular format from Twin B, adapted for reconciled flag string:

```markdown
### 6.4 approval_thresholds — Approval Thresholds
Configuration table defining tiered approval limits and dual-key authorization rules. Read by WF-07 (lm_approval.on_approve), WF-09 (hod_approval.on_approve), WF-13 (sla_enforcement_daily).

| link_name | label | type | flags | default | ref/pick | help |
|---|---|---|---|---|---|---|
| tier_name | Tier Name | text | — | — | — | e.g. "Tier 1 - Line Manager" |
| max_amount_zar | Max Amount ZAR | currency(ZAR) | — | — | — | cap this tier can approve; over → escalate |
| approver_role | Approver Role | text | — | — | — | Zoho Creator role approving at this tier |
| Active | Active | boolean | — | true | — | only Active tiers participate in routing |
| Tier_Order | Tier Order | number | — | 0 | — | ascending; lowest fires first |
| Requires_Dual_Approval | Requires Dual Approval | boolean | — | false | — | enables two-key gate for this tier |
| Dual_Approval_Role | Dual Approval Role | text | — | — | — | Key 2 role when dual approval active |
| Dual_Threshold_ZAR | Dual Threshold ZAR | currency(ZAR) | — | — | — | amount above which two-key fires |

**Form-level rules**: none (configuration form). Referenced by WF-07, WF-09, WF-13.
```

**Workflow `expense_claim.on_validate`** in §11 — compact bullet format from Twin A:

```markdown
### WF-04  expense_claim.on_validate
- Trigger: expense_claims.on_validate (Employee | pre-save on submit/save)
- Guard:   always
- Effect:  Eight hard-stop gates (temporal, 90-day policy, positive amount, evidence mandate, VAT, duplicate warn, POPIA, success stamps). Any fail blocks save with user alert. See BR-011..BR-018.
- Reads:   input.Expense_Date; input.amount_zar; input.Supporting_Documents; input.VAT_Invoice_Type; input.POPIA_Consent; input.ID; zoho.currentdate; zoho.currenttime; zoho.loginuser; expense_claims[Expense_Date=input.Expense_Date && amount_zar=input.amount_zar && Added_User=zoho.loginuser && ID≠input.ID]
- Writes:  status → "Submitted"; Submission_Date → zoho.currenttime; Retention_Expiry_Date → zoho.currenttime + 5y
- APIs:    —
- Emails:  —
- Audit:   —
```

**Role × form CRUD matrix** in §9(b) — wide, letters, footnoted:

```markdown
#### 9.2 Record-level CRUD matrix

| role \ form | departments | clients | gl_accounts | approval_thresholds | expense_claims | approval_history |
|---|---|---|---|---|---|---|
| Employee | R | R | — | — | C R¹ U¹ | R¹ |
| Line Manager | R | R | R | R | C R² U² | R² |
| Head of Department | R | R | R | R | C R U³ | R³ |
| Finance Director | R | R | R | R | R U⁴ | R U⁴ |
| Finance Accountant | R | R | R | R | R U⁵ | R |
| System Administrator | CRUD | CRUD | CRUD | CRUD | CRUD | CRUD |
| Portal roles (Customer/Developer/Vendor/Client Rep) | R | R | — | — | R⁶ | — |

**Footnotes**:  
¹ Employee: own records only (`Added_User == zoho.loginuser`).  
² Line Manager: own + Pending LM Approval queue; U limited to approval-action fields.  
³ HoD: Pending HoD Approval + team visibility; U limited to approval fields + GL code.  
⁴ Finance Director: U limited to Key-2 approval/rejection fields.  
⁵ Finance Accountant: U limited to payment-processing fields.  
⁶ Portal: read-only via customer portal, limited to shared/assigned records.

Field-level overrides: see §9(d).
```

## Expected final BRD size

~750 lines, ~48,000 characters (≈7,500 tokens at 6.5 chars/token). Well inside any realistic Zia single-doc cap; front-loaded structure means attention decay in §14-16 (static checklist/seed/oos) degrades gracefully.

## Ranked risks going into Phase 5

1. **Workflow `Effect:` paragraphs lose conditional branches** (Twin A's risk 1, Twin B's risk 1) — mitigation: split multi-branch scripts into sibling WF-NN.A/WF-NN.B blocks, already planned.
2. **Shared picklist `@Picklist:category`** — Zia may emit two disjoint enums for `expense_claims.category` and `gl_accounts.expense_category`. Mitigation: §7 preamble lists "Shared Picklists" with explicit `used_by: form.field, form.field` rows; §14 BR-NNN contains a "shared enum invariant" rule.
3. **Self-referential lookup on `expense_claims.Parent_Claim_ID`** (Twin B risk 4) — mitigation: BR-NNN rule "expense_claims must be created with Parent_Claim_ID deferred".
4. **CRUD `*` scope markers under-specify field-level rules** — mitigation: §9(d) field-level override table + §14 BR-NNN notes. Phase 6 simulation will stress-test whether Zia reads overrides.
5. **Research discrepancy on `compliance_config`** — mitigation: §15 explicit Out-of-Scope entry: "field-descriptions YAML mentions compliance_config; not present in .ds export; advisory only, do NOT create this form".

## Phase 5 spec writer handoff

Phase 5 consumes this reconciled blueprint and emits the Phase 5 spec — a section-by-section writing contract that the Phase 7 implementer will follow verbatim. Critic (opus) will rebut.
