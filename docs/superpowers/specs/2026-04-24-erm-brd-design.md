# ERM BRD Writing Spec — 2026-04-24

---

## Revision Log (Phase 5 rebuttal cycle — applied 2026-04-24)

| Issue | What changed |
|---|---|
| Issue A | gl_accounts has exactly 7 fields; ESG_Category/Carbon_Factor/GRI_Indicator NOT in .ds; §6.3 rule updated; WF-07/WF-09 Reads/Writes retain advisory suffix; §14 ESG BR added; §15 updated |
| Issue B | Email template count = 18 named + 1 inline ad-hoc; §2, §5 A9, §13, §15, §16 #11 updated; WF-11.A Emails line changed to inline; INLINE-01 row added to §13 contract |
| Issue C | Field count total = 53; per-form breakdown corrected; §2 example, §5 A2, §16 #2, writer step 8 updated |
| R-01 | Report count = 11 (9 list + 1 kanban + 1 pivottable); §2, §5 A7, §8 NOTE, §16 #5, writer step 10 updated |
| R-02 | Email template count fixed everywhere (19 → 18 named + 1 inline); duplicate of Issue B |
| R-03 | Field count fixed everywhere (54 → 53); duplicate of Issue C |
| R-04 | Added explicit 5 `must have` field enumeration to §6 cell encoding rules and §16 new assertion |
| R-05 | action_1 picklist pinned to exactly 12 values in declaration order; §7 and §5 updated |
| R-06 | Developer added as 7th internal role; §9.1 ordering and §5 A16 updated to 8 matrix rows |
| R-07 | §5 A11 and §11 Format paragraph rewritten to specify 17 H3 blocks from 13 parent workflows |
| R-08 | Parent_Claim_ID type kept as `pick list (self-ref)` per .ds; `help` cell carries behavioral note |
| R-09 | Developer anchored as internal role (not portal); portal roles = Client Representative, Vendor, Customer |
| R-10 | §13 cc encoding rule tightened; exactly 2 templates have CC specified; §16 new assertion added |
| R-11 | Employee_Name1_prefix demoted to inline pick{}; removed from §7; named picklists = 5 |
| R-12 | cond_format encoding rule changed to require full hex #rrggbb verbatim; color name option removed |
| R-13 | hod_override trigger added to §10 trigger vocab; transition row added |
| R-14 | invoked_by = external (REST) for all 4 Custom APIs; one-sentence note added to §12 |
| R-15 | §8 cell encoding rule permits sub-bulleted column list when columns > 10 fields |
| R-16 | §15 bullet 6 extended with §14 BR traceability note |
| R-17 | §16 #13 rewritten to anchor append-only at menu/report layer, not form layer |
| Phase 6 sim | Phase 6 sim patches applied 2026-04-24: B-1 (self_ref placement), B-2 (conditional email syntax), B-3 (WF-09 template mapping), B-4 (conditional audit syntax) |

---

## 1. Mission

Produce a single, lossless, maximum-density Business Requirements Document (GFM Markdown, `.md`)
at `C:\Users\User\OneDrive\Documents\GitHub\Expense_Reimbursement_Manager\docs\brd\zia-brd-2026-04-24.md`
that Zoho Zia's app-builder LLM can ingest in one upload and reconstruct the Expense Reimbursement
Management Creator application with full schema fidelity. Hard constraints: single file, GFM tables
only (no HTML, no images), no Deluge code (describe behavior in plain English), every form / field /
lookup / report / picklist / role / workflow / Custom API / email template represented with zero
omission.

---

## 2. Input data sources

| BRD Section | Primary source | Secondary sources | Notes |
|---|---|---|---|
| §1 Ingestion Contract | 4-reconciled-blueprint.md §"Ingestion-contract header" | 0-brief.md §"Target output" | YAML fenced block |
| §2 Application Meta | 3a-ds-schema.md §"Application Header" | 3d-context.md §"Business purpose" | Counts come from all research files |
| §3 Glossary & Notation | 4-reconciled-blueprint.md §"Density tactics locked in" | — | Copy verbatim; writer does NOT invent notation |
| §4 Entity Catalog | 3a-ds-schema.md form headers; 3d-context.md | 3c-config.md §"Field Descriptions" | 6 rows, one per form |
| §5 ER Skeleton | 3a-ds-schema.md §"Relationships / Lookups" | 4-reconciled-blueprint.md §"Ranked risks" risk 3 | 5 edges including self-ref |
| §6 Form Catalog | 3a-ds-schema.md per-form tables | 3c-config.md §"Field Descriptions" | 6 subsections, 53 total field rows |
| §7 Picklist Appendix | 3a-ds-schema.md §"Picklist Appendix" | — | 5 named picklists |
| §8 Reports Catalog | 3a-ds-schema.md §"Reports" | 3c-config.md §"UI Standards" | 11 rows including 1 kanban + 1 pivot |
| §9 Roles & Access Model | 3c-config.md §"Roles & Permissions" | 4-reconciled-blueprint.md CRUD matrix example | 3 sub-parts: defs, matrix, overrides |
| §10 Workflow State Machine | 3a-ds-schema.md status picklist; 3b-deluge.md all transitions | 4-reconciled-blueprint.md §"State machine encoding" | 9 status values, ~13 transition rows |
| §11 Workflow Catalog | 3b-deluge.md all 13 script sections | 4-reconciled-blueprint.md §"Workflow block shape" | 13 workflows (17 H3 blocks with splits), bullet-block format |
| §12 Custom APIs | 3c-config.md §"Custom APIs" | 3c-config.md §"Deluge Manifest" | 4 rows, single wide table |
| §13 Email Templates | 3c-config.md §"Email Templates" | 3b-deluge.md per-script Emails sections | 18 named rows + 1 inline ad-hoc row |
| §14 Business Rules Index | 3d-context.md §"Key business rules"; 3b-deluge.md §"Key Observations" | 3c-config.md §"UI Standards" | Numbered BR-NNN, ~20-25 rules |
| §15 Out of Scope | 0-brief.md §constraints; 4-reconciled-blueprint.md §"Ranked risks" risk 5 | 3c-config.md (compliance_config) | ~10 bullet exclusions |
| §16 Reconstruction Checklist | All research files (counts) | 0-brief.md §"Facts the BRD must surface" | Self-audit count assertions for Zia |

---

## 3. Canonical notation (verbatim from blueprint §Glossary)

The Phase 7 implementer MUST render this section verbatim as §3 of the BRD. No additions,
no substitutions.

```
### Type notation (Zoho-native + compact DSL)
- Native Creator palette types: text, number, decimal, currency(ZAR), date, date time,
  boolean, email, phone, url, image, file upload, rich text (textarea), auto number,
  pick list, multi select, name (compound)
- Relational arrows:
    lookup→<target_form>         e.g.  lookup→expense_claims
    subform→<target_form>        (none in this app)
    self_ref→<target_form>       e.g.  self_ref→expense_claims
- Formulas:           fx:"<expression>"    e.g.  fx:"zoho.currenttime + 5y"
- Shared picklist:    pick list @Picklist:<name>    e.g.  pick list @Picklist:category
- Inline picklist:    pick list pick{a,b,c}          used only when ≤3 values AND single-use
- Pick list (Users module): pick list (users-module)

### Flag string (field flags, one cell)
* = required (must have)
‡ = unique
† = private / hidden from default UI
Concatenate: *‡ = required+unique; †  alone = private only.
— = no flags (empty cell, not blank).

### CRUD cell alphabet (role × form matrix)
Letters: C = Create, R = Read, U = Update, D = Delete.
Concatenate in CRUD order: e.g. CRU, R, CRUD, —.
Scope qualifiers: superscript numerals ¹²³ refer to footnotes beneath the matrix.
Example: C R¹ U¹  means Create unrestricted; Read/Update scoped per footnote 1.

### Workflow Reads / Writes micro-syntax
Reads:  semi-separated tokens — input.<field>; zoho.<var>; <form>[<filter>].<field>
        Multi-field pull: <form>[<filter>].(field1,field2,field3)
Writes: semi-separated assignments — input.<field> := <value>
        Arrow shorthand also accepted: input.<field> → <value>

### State machine transition row
from_status | trigger | condition (guard) | to_status | actor_role | workflow_ref (→ WF-NN)

### Email template contract
Subject column: literal template string with {{var}} tokens.
Variables column: comma-separated {{var}} names.
Body prose: omitted. intent column is one sentence only.
```

---

## 4. Section-by-section writing contract

---

### §1. Ingestion Contract

- **Purpose**: Provide a machine-parseable YAML fenced block that anchors the document version,
  app target, locale, notation reference, and a terse reading directive for Zia's ingestor.
- **Source**: 4-reconciled-blueprint.md §"Reconciled divergences" row "Ingestion-contract header";
  0-brief.md §"Target output"; 3a-ds-schema.md §"Application Header".
- **Format**: Single fenced YAML block, followed by one sentence prose reading directive.
- **Columns**: Not applicable (key:value YAML, not tabular).
- **Cell encoding rules**:
  - `doc_version`: string `"1.0"`.
  - `generated`: ISO date `2026-04-24`.
  - `app_display_name`: verbatim from .ds header — `"Expense Reimbursement Management"`.
  - `app_link_name`: `expense_reimbursement_management` (lower_snake derived from display name;
    .ds does not declare an explicit link_name at application level).
  - `currency`: `ZAR`.
  - `timezone`: `Africa/Johannesburg`.
  - `date_format`: `dd-MMM-yyyy`.
  - `time_format`: `24-hr`.
  - `notation`: `see §3`.
  - `how_to_read`: one sentence — "Reconstruct every artifact listed in §16; treat every table row
    as a schema directive."
- **Ordering**: Keys in order: doc_version, generated, app_display_name, app_link_name, currency,
  timezone, date_format, time_format, notation, how_to_read.
- **Example block**:
  ```yaml
  doc_version: "1.0"
  generated: "2026-04-24"
  app_display_name: "Expense Reimbursement Management"
  app_link_name: expense_reimbursement_management
  currency: ZAR
  timezone: Africa/Johannesburg
  date_format: dd-MMM-yyyy
  time_format: 24-hr
  notation: see §3
  how_to_read: >
    Reconstruct every artifact listed in §16; treat every table row
    as a schema directive.
  ```
- **What NOT to include**: No Deluge code, no author email, no file path to .ds source,
  no platform-version constraints.
- **Cross-refs**: `app_display_name` must match §2 Application Meta `display_name` row.
  `currency` and `timezone` must match §2. Notation anchor points to §3.
- **Success criteria**: Supports SC-1 (every form reconstructible) by establishing locale defaults;
  supports SC-5 (workflow behavior) indirectly via timezone.

---

### §2. Application Meta

- **Purpose**: Single key:value table giving Zia the top-level application identity and count summary
  before any schema detail.
- **Source**: 3a-ds-schema.md §"Application Header" (display name, author, version, date format, TZ);
  all research files for counts.
- **Format**: Two-column GFM table (`Property | Value`).
- **Columns**: `Property | Value`
- **Cell encoding rules**:
  - Every value is a plain string or integer literal. No formulas, no links.
  - Counts must match assertions in §16: 6 forms, 53 fields, 5 lookups, 0 subforms, 11 reports,
    9 status values, 8 roles (7 internal + 1 combined-portal row), 13 workflows,
    4 Custom APIs, 18 named email templates + 1 inline ad-hoc, 0 widgets, 5 named picklists.
  - `Email Templates` value MUST read `18 (named) + 1 inline ad-hoc (see §15)`.
  - `Author` value: `holger.gevers360` (verbatim from .ds header).
  - `Version` value: `1.0`.
  - `Generated` value: `06-Apr-2026 13:04:52` (verbatim from .ds header).
- **Ordering**: display_name, link_name, author, version, generated, currency, timezone,
  date_format, time_format, then counts in order: forms, fields, lookups, subforms, reports,
  status values, roles, workflows, custom APIs, email templates, widgets, named picklists.
- **Example rows**:
  ```
  | Property          | Value                                       |
  |---                |---                                          |
  | Display Name      | Expense Reimbursement Management            |
  | Link Name         | expense_reimbursement_management            |
  | Author            | holger.gevers360                            |
  | Version           | 1.0                                         |
  | Generated         | 06-Apr-2026 13:04:52                        |
  | Currency          | ZAR                                         |
  | Timezone          | Africa/Johannesburg                         |
  | Date Format       | dd-MMM-yyyy                                 |
  | Time Format       | 24-hr                                       |
  | Forms             | 6                                           |
  | Fields            | 53                                          |
  | Lookups           | 5                                           |
  | Subforms          | 0                                           |
  | Reports           | 11 (9 list + 1 kanban + 1 pivottable)       |
  | Status Values     | 9                                           |
  | Roles             | 7 internal + 3 portal (combined row in §9.2)|
  | Workflows         | 13                                          |
  | Custom APIs       | 4                                           |
  | Email Templates   | 18 (named) + 1 inline ad-hoc (see §15)     |
  | Widgets           | 0                                           |
  | Named Picklists   | 5                                           |
  ```
- **What NOT to include**: No business context prose, no compliance frameworks in this section
  (those go in §14), no seed data file counts.
- **Cross-refs**: Every count row must match its corresponding assertion in §16. `Currency` and
  `Timezone` must match §1.
- **Success criteria**: Supports SC-1 (form reconstructibility) by anchoring locale. Supports
  SC-3 (report count). Supports SC-4 (role count). Supports SC-5, SC-6, SC-7 via counts.

---

### §3. Glossary & Notation Legend

- **Purpose**: Define every symbol, abbreviation, and DSL construct the implementer uses throughout
  the BRD so Zia and human reviewers can decode every cell unambiguously.
- **Source**: 4-reconciled-blueprint.md §"Density tactics locked in" (all sub-sections).
  Copy from §3 of this spec (above) verbatim.
- **Format**: GFM table (Symbol | Meaning | Example), then flag-string sub-table, then CRUD
  alphabet sub-table. Follow with a `Reads/Writes micro-syntax` note block.
- **Columns**: `Symbol | Meaning | Example`
- **Cell encoding rules**:
  - Symbol column: the literal character(s) or prefix in backticks.
  - Meaning column: one sentence.
  - Example column: one minimal concrete example drawn from actual ERM fields.
- **Ordering**: Relational arrows first (lookup→, subform→, self_ref→), then formula prefix (fx:),
  then picklist notations, then flag chars, then CRUD letters, then scope superscripts.
- **Example rows**:
  ```
  | Symbol              | Meaning                                  | Example                          |
  |---                  |---                                       |---                               |
  | `lookup→<form>`     | Foreign-key lookup to named form          | `lookup→expense_claims`          |
  | `self_ref→<form>`   | Self-referential lookup                   | `self_ref→expense_claims`        |
  | `fx:"<expr>"`       | Computed/formula field value             | `fx:"zoho.currenttime + 5y"`     |
  | `@Picklist:<name>`  | Reference to named picklist in §7        | `pick list @Picklist:category`   |
  | `pick{a,b,c}`       | Inline picklist (≤3 values, single-use)  | `pick list pick{Standard,High}`  |
  | `*`                 | Required (must have)                     | flags cell: `*`                  |
  | `‡`                 | Unique                                   | flags cell: `‡`                  |
  | `†`                 | Private / hidden from default UI         | flags cell: `†`                  |
  | `—`                 | Empty / not applicable                   | any empty cell                   |
  | `C R U D`           | CRUD record-level access letters         | `CRU` = create+read+update       |
  | `¹²³`               | Scope qualifier footnote                 | `R¹` = read scoped per fn 1      |
  ```
- **What NOT to include**: No business rules, no field definitions, no explanation of approval
  workflow tiers. This section is purely notation reference.
- **Cross-refs**: Every symbol defined here must be used consistently in §6 (fields), §8 (reports),
  §9 (CRUD matrix), §11 (workflows). §9 footnotes referenced here by superscript convention.
- **Success criteria**: Supports all 7 SC by enabling accurate decoding of every encoded cell.

---

### §4. Entity Catalog

- **Purpose**: One-row-per-form summary giving Zia the six forms' identities, roles in the data
  model, primary key, foreign key targets, and approximate size class before field-level detail.
- **Source**: 3a-ds-schema.md form headers and relationship table;
  3d-context.md §"User base" and §"Business purpose".
- **Format**: Single wide GFM table, 6 data rows.
- **Columns**: `form | label | kind | purpose | key_field | fk_to | row_count_class`
- **Cell encoding rules**:
  - `form`: link_name (snake_case) verbatim from .ds.
  - `label`: display name verbatim.
  - `kind`: one of `txn` (transaction hub), `ref` (lookup reference), `audit` (append-only log),
    `config` (configuration table).
  - `purpose`: one sentence ≤15 words.
  - `key_field`: primary display/key field link_name.
  - `fk_to`: comma-separated list of `<form>` targets; `—` if none; `self` for self-ref.
  - `row_count_class`: `small` (<100), `medium` (100-10k), `large` (>10k) — use app domain
    knowledge, not a measured count.
- **Ordering**: Dependency order — leaf refs first, transaction hub, audit child last:
  `departments`, `clients`, `gl_accounts`, `approval_thresholds`, `expense_claims`,
  `approval_history`.
- **Example row**:
  ```
  | form             | label             | kind   | purpose                                             | key_field | fk_to                                          | row_count_class |
  | expense_claims   | Expense Claims    | txn    | One record per employee expense reimbursement claim | claim_id  | departments, clients, gl_accounts, self (Parent_Claim_ID) | large |
  ```
- **What NOT to include**: No field-level detail, no workflow references, no picklist values,
  no CRUD permissions.
- **Cross-refs**: Every `form` value must match a subsection heading in §6. Every `fk_to` value
  must appear as an edge in §5. `kind` values inform §9 CRUD matrix footnotes (audit forms
  are view-only).
- **Success criteria**: Supports SC-1 (form reconstructibility), SC-2 (lookup/subform edges).

---

### §5. Entity-Relationship Skeleton

- **Purpose**: List all 5 lookup edges (the complete relationship graph) so Zia can reconstruct
  every foreign-key wiring without re-deriving it from the field tables.
- **Source**: 3a-ds-schema.md §"Relationships / Lookups" table.
- **Format**: Single GFM table, 5 data rows.
- **Columns**: `from_form | field | to_form | cardinality | on_delete | self_ref`
- **Cell encoding rules**:
  - `from_form`, `to_form`: link_name values matching §4 and §6.
  - `field`: link_name of the lookup field.
  - `cardinality`: `N:1` (many-to-one) for all standard lookups; `N:1` for self-ref since
    Parent_Claim_ID is a single pick pointing to one parent; note self-ref explicitly.
  - `on_delete`: `—` (Creator does not expose cascade rules in .ds; do not invent).
  - `self_ref`: `yes` only for `expense_claims → expense_claims`; `—` otherwise.
- **Ordering**: `approval_history.claim` first (leaf audit child → hub), then
  `expense_claims.department`, `expense_claims.client`, `expense_claims.gl_code`,
  `expense_claims.Parent_Claim_ID` (self-ref last).
- **Example row**:
  ```
  | from_form       | field          | to_form        | cardinality | on_delete | self_ref |
  | expense_claims  | Parent_Claim_ID| expense_claims | N:1         | —         | yes      |
  ```
- **What NOT to include**: No subform edges (there are none). No field-type detail (that is in §6).
  No workflow side-effects. Do not invent ERD diagram or ASCII art.
- **Cross-refs**: Every `from_form` and `to_form` must match §4 form names and §6 subsections.
  Every `field` value must match a row in the corresponding §6 form table with type containing
  `lookup→`. The self-ref edge must trigger BR-020 in §14.
- **Success criteria**: Supports SC-2 (every lookup/subform edge reconstructible).

---

### §6. Form Catalog

- **Purpose**: Provide complete field-level schema for all 6 forms — link_name, label, type,
  flags, default, ref/pick, and help text — so Zia can create every field exactly.
- **Source**: 3a-ds-schema.md per-form tables (primary); 3c-config.md §"Field Descriptions"
  (help text column cross-check).
- **Format**: One H3 subsection per form (6 total). Each subsection: 1-line purpose sentence,
  then one wide GFM field table, then a "Form-level rules" note (numbered bullet list or
  "none" if absent).
- **Columns**: `link_name | label | type | flags | default | ref/pick | help`
- **Cell encoding rules**:
  - `link_name`: verbatim from .ds, case-preserved.
  - `label`: display label verbatim.
  - `type`: Zoho-native type string from §3 notation. For lookups: `lookup→<target_form>`.
    For self-ref pick list: `pick list (self-ref)` — preserve the .ds declaration; note
    behavioral intent in the `help` cell. For currency: `currency(ZAR)`.
    For boolean: `boolean`. For compound name: `name (compound)`.
    For Users-module pick list: `pick list (users-module)`.
    For file upload: `file upload`.
    For auto number: `auto number`.
    For rich text area: `rich text (textarea)`.
  - `flags`: `*` required, `‡` unique, `†` private; concatenate; `—` if none.
    Fields with `private=true` in .ds get `†`.
    Fields with `must have` in .ds get `*`.
    **The .ds declares exactly 5 `must have` fields across the entire app:
    `expense_claims.Employee_Name1`, `expense_claims.Email`, `expense_claims.Submission_Date`,
    `expense_claims.Claim_Reference`, `expense_claims.Supporting_Documents`.
    ONLY these 5 fields carry the `*` flag. No other form has any `must have` fields.**
  - `default`: literal default value or `—`. For auto number "start index=1" write `autonumber(1)`.
    For booleans: `true` or `false`. For numbers: the numeric literal.
  - `ref/pick`: For lookups — `lookup→<target>` (with display format note if meaningful).
    For shared picklists — `@Picklist:<name>`. For inline picklists (≤3 values, single-use) —
    `pick{val1,val2,val3}`. For Users-module — `users-module`.
    For self-ref pick list — `self_ref→expense_claims`. Do NOT use `self_ref→<form>` in the `type` column for this field. The `type` column preserves the .ds declaration `pick list (self-ref)`. `—` if not applicable.
  - `help`: one-sentence help text from 3c-config.md field descriptions, or derived from
    3a-ds-schema.md notes. For private/shadow fields with no help text: `—`.
    For `Parent_Claim_ID`: include a note such as "Self-referential: stores ID of the parent
    claim this record amends; .ds type is pick list filtered to expense_claims.ID."
- **Ordering within each form**: Rows in the exact same order as 3a-ds-schema.md field tables
  (which reflects the .ds declaration order).
- **Form ordering**: `departments` (§6.1), `clients` (§6.2), `gl_accounts` (§6.3),
  `approval_thresholds` (§6.4), `expense_claims` (§6.5), `approval_history` (§6.6).
- **Form-level rules**: If the form has stated validation rules (expense_claims has 7),
  list them as numbered bullets referencing BR-NNN codes from §14. Otherwise write "none".
- **Example subsection** (abbreviated):
  ```markdown
  ### 6.4 approval_thresholds — Approval Thresholds
  Configuration table defining tiered approval limits and dual-key authorization rules.

  | link_name               | label                  | type         | flags | default | ref/pick | help |
  |---                      |---                     |---           |---    |---      |---       |---   |
  | tier_name               | Tier Name              | text         | —     | —       | —        | Name of the approval tier (e.g., Tier 1 - Line Manager). |
  | max_amount_zar          | Max Amount ZAR         | currency(ZAR)| —     | —       | —        | Maximum claim amount (ZAR) this tier can approve; claims above escalate to next tier. |
  | approver_role           | Approver Role          | text         | —     | —       | —        | The Zoho Creator role that approves claims at this tier. |
  | Active                  | Active                 | boolean      | —     | true    | —        | Whether this threshold tier is currently active in the approval workflow. |
  | Tier_Order              | Tier Order             | number       | —     | 0       | —        | Numeric order in escalation chain; lower numbers approve first. |
  | Requires_Dual_Approval  | Requires Dual Approval | boolean      | —     | false   | —        | Whether this tier triggers dual-approval (two-key) authorization. |
  | Dual_Approval_Role      | Dual Approval Role     | text         | —     | —       | —        | Role that acts as Key 2 approver when dual-approval is required. |
  | Dual_Threshold_ZAR      | Dual Threshold ZAR     | currency(ZAR)| —     | —       | —        | Amount threshold (ZAR) above which dual-approval is required. |

  **Form-level rules**: none (configuration form). Referenced by WF-07, WF-09, WF-13.
  ```
- **§6.3 gl_accounts — authoritative field list**: The .ds `form gl_accounts` declares exactly
  **7 fields** in declaration order: `gl_code`, `account_name`, `expense_category`,
  `receipt_required`, `SARS_Provision`, `Risk_Level`, `Active`. Do NOT add `ESG_Category`,
  `Carbon_Factor`, or `GRI_Indicator` to §6.3. These names appear only in workflow read-lists
  and field-descriptions.yaml; they are NOT .ds-declared fields on gl_accounts. See §15 for
  the schema-workflow divergence discrepancy.
- **What NOT to include**: No Deluge code. No picklist value lists in the table body (use
  `@Picklist:<name>` and define values in §7). Do not add fields that are not in the .ds.
  Do not include the `compliance_config` form — it is absent from the .ds and excluded per §15.
- **Cross-refs**: Every `lookup→<target>` must have a matching edge in §5. Every
  `@Picklist:<name>` must have a matching H3 in §7. Every field with `*` flag must be
  consistent with required-field enforcement in §11 WF-04 (on_validate). Form-level BR-NNN
  references must exist in §14.
- **Success criteria**: Directly satisfies SC-1 (every form reconstructible with all field
  attributes). Supports SC-2 (lookup edges visible in type column).

---

### §7. Picklist Appendix

- **Purpose**: Deduplicate all shared picklist enumerations so §6 can reference them by name
  rather than repeating values inline, and ensure Zia creates a single consistent enum for each
  shared picklist.
- **Source**: 3a-ds-schema.md §"Picklist Appendix" (all named picklists with values and
  `Used by` cross-references).
- **Format**: One H3 per named picklist. Each H3: title = `<name>`, then a fenced block listing
  values one per line, then a `Used by:` cross-reference line.
- **Columns**: Not tabular. Fenced value list + prose Used-by line.
- **Cell encoding rules**:
  - H3 title must exactly match the `@Picklist:<name>` token used in §6 field tables.
  - Values: each value on its own line in the fenced block, verbatim from .ds.
  - `Used by:` lists every `<form>.<field>` pair separated by semicolons.
  - `Employee_Name1_prefix` is an inline sub-component enum (3 values: Mr., Mrs., Ms.) on the
    `prefix` sub-component of the compound `Employee_Name1` field (.ds visibility = false).
    It is NOT a top-level Creator picklist. Render it as `pick list pick{Mr.,Mrs.,Ms.}` in
    §6.5 `ref/pick` for the compound name field note, and do NOT include it in §7.
- **Ordering**: Alphabetical by picklist name — exactly 5 named picklists:
  1. `action_1` (approval_history.action_1) — **MUST contain exactly 12 values in this order**:
     Submitted, Submitted (Self-approval bypass), Approved (LM), Approved (HoD),
     Approved (Key 1), Approved (Key 2), Rejected, Rejected (Key 2), Reconsidered (Key 1),
     Escalated (SLA Breach), Resubmitted, Warning.
  2. `category` (expense_claims.category; gl_accounts.expense_category — shared enum)
  3. `Risk_Level` (gl_accounts.Risk_Level)
  4. `status` (expense_claims.status)
  5. `VAT_Invoice_Type` (expense_claims.VAT_Invoice_Type)
- **Example block**:
  ```markdown
  ### status

  ```
  Draft
  Submitted
  Pending LM Approval
  Pending HoD Approval
  Pending Second Key
  Key 2 Dispute
  Approved
  Rejected
  Resubmitted
  ```

  Used by: `expense_claims.status`
  ```
- **What NOT to include**: Do not include `Employee_Name1_prefix` as a named picklist (demoted
  to inline pick{}). No inline picklists that appear only once and have ≤3 values
  (those stay `pick{a,b}` in §6). Do not invent a `gl_accounts.expense_category` separate
  picklist — it shares the `category` enum. Do not add picklist values not found in .ds.
- **Cross-refs**: Every `@Picklist:<name>` in §6 must resolve to an H3 here. The `status`
  picklist values must equal the status nodes in §10 (9 values). The `action_1` values must
  match the action values logged by workflows in §11 Audit lines. §5 A5 asserts exactly
  5 H3 blocks here.
- **Success criteria**: Supports SC-1 (every picklist value reconstructible). Supports SC-5
  (workflow audit actions align with picklist values).

---

### §8. Reports Catalog

- **Purpose**: One row per report giving Zia every report's source, type, filter, sort, columns,
  grouping, conditional formatting, and menu permissions so each report can be rebuilt exactly.
- **Source**: 3a-ds-schema.md §"Reports" table (11 rows); 3c-config.md §"UI Standards"
  §"Report Menu Permissions" and §"Conditional Formatting".
- **Format**: Single wide GFM table, 11 data rows.
- **Columns**: `name | display_name | source_form | view_type | filter | sort | columns | grouping | cond_format | menu_perms`
- **Cell encoding rules**:
  - `name`: link_name verbatim from .ds.
  - `display_name`: verbatim display name string from .ds.
  - `source_form`: form link_name.
  - `view_type`: `list`, `kanban`, or `pivot`. `gl_accounts_by_expense_category` is `kanban`.
    `Expense_Summary` is `pivot`.
  - `filter`: verbatim filter expression from .ds using `[condition]` notation; `—` if none.
  - `sort`: `<field> asc` or `<field> desc`; `—` if unspecified.
  - `columns`: comma-separated field link_names in display order, verbatim from .ds.
    Aggregate annotations: `amount_zar (total/avg/min/max)` where present.
    **When `columns` exceeds 10 fields (e.g., `pending_approvals_manager` with 18 fields,
    `My_Claims` with 17 fields), the implementer MAY use a sub-bulleted list under the row
    instead of a single cell to preserve readability. Plain text ingest is unaffected.**
  - `grouping`: `group by <field>[,<field>]`; `—` if none.
  - `cond_format`: `<field>:<value>=#rrggbb` pairs; `—` if none.
    **MUST use full 6-digit hex color verbatim from .ds (e.g., `#1bbc9b`, `#e84c3d`,
    `#bd588b`, `#765f89`, `#107c91`). Color names (e.g., "teal", "red") are NOT permitted.**
    Multiple field-value pairs in one cell are semi-colon-separated.
  - `menu_perms`: `Edit+View` for transaction reports; `View` for reference/audit; note any
    blocked actions.
- **Ordering**: In this order (all 11): expense_claims_Report, gl_accounts_Report,
  gl_accounts_by_expense_category, approval_history_Report, approval_thresholds_Report,
  clients_Report, departments_Report, Audit_Trail, pending_approvals_manager, My_Claims,
  Expense_Summary.

  NOTE: The .ds declares **11 reports** (9 list + 1 kanban + 1 pivottable). Use all 11.
  `gl_accounts_by_expense_category` is the kanban. `Expense_Summary` is the pivot.
  The 3a-ds-schema.md Reports header may state "10" — that header is wrong; the body lists 11.
  Do NOT omit Expense_Summary or any other report.
- **Example row**:
  ```
  | name         | display_name  | source_form      | view_type | filter | sort | columns | grouping | cond_format | menu_perms |
  | Expense_Summary | Expense Summary | expense_claims | pivot   | —      | —    | Email, Submission_Date, claim_id, Parent_Claim_ID.Department_Shadow, Client_Shadow, category, amount_zar, status | — | — | View |
  ```
- **What NOT to include**: No report body prose. No screenshot descriptions. Do not include
  the "Autoview" internal reference (autoview_1775232194200) as a user-facing artifact.
  Do not add reports not in the .ds.
- **Cross-refs**: Every `source_form` must match a form in §4/§6. Every `columns` field name
  must exist in the corresponding §6 form table. `status` column conditional format values
  must match §7 `status` picklist values.
- **Success criteria**: Directly satisfies SC-3 (every report: source form, filter, visible
  columns, visibility reconstructible).

---

### §9. Roles & Access Model

- **Purpose**: Define every role and provide unambiguous CRUD access rules at both record level
  and field level so Zia can configure Creator's permission system exactly.
- **Source**: 3c-config.md §"Roles & Permissions" (role defs, field permissions);
  4-reconciled-blueprint.md §"Worked-example target format" (CRUD matrix example).
- **Format**: Four sub-parts:
  - §9.1 Role Definitions table
  - §9.2 Record-level CRUD matrix (wide: roles × forms)
  - §9.3 Scope footnotes (plain text bullets beneath matrix)
  - §9.4 Field-level override table
- **Columns**:
  - §9.1: `role | parent | kind | purpose | notes`
  - §9.2: `role \ form | departments | clients | gl_accounts | approval_thresholds | expense_claims | approval_history`
  - §9.4: `form | field | Employee | Line Manager | HoD | Finance Director | Finance Accountant | System Administrator`
- **Cell encoding rules**:
  - §9.1 `kind`: `internal` or `portal`. Internal roles (7 total per 3c-config.md):
    Employee, Line Manager, Head of Department, Finance Director, Finance Accountant,
    System Administrator, **Developer**. Portal roles (3 total):
    Client Representative, Vendor, Customer.
    **Developer is an internal role — do NOT classify it as portal.**
  - §9.2 cells: CRUD letter strings with superscript scope qualifiers. `—` for no access.
    Portal roles combined into one row `Portal (Client Representative / Vendor / Customer)`.
  - §9.3 footnotes: one sentence each, beginning with the superscript numeral.
  - §9.4 cells: `Hidden`, `R`, `C/R/U`, `C/R/U/D`, `—` as appropriate from 3c-config.md
    §"Field Permissions" table. Use `Hidden` for private fields not visible to a role.
- **Ordering**:
  - §9.1: Employee, Line Manager, Head of Department, Finance Director, Finance Accountant,
    System Administrator, Developer (7 internal), then portal roles (Client Representative,
    Vendor, Customer).
  - §9.2: Same role order as §9.1 — 7 internal role rows + 1 combined portal row = **8 rows total**.
    Form order: dependency order matching §4/§6.
  - §9.4: Rows ordered by form then field, matching §6 form order.
- **Example §9.2 rows** (verbatim from blueprint, adapted — note 8 data rows):
  ```
  | role \ form                           | departments | clients | gl_accounts | approval_thresholds | expense_claims | approval_history |
  | Employee                              | R           | R       | —           | —                   | C R¹ U¹        | R¹               |
  | Line Manager                          | R           | R       | R           | R                   | C R² U²        | R²               |
  | Head of Department                    | R           | R       | R           | R                   | C R U³         | R³               |
  | Finance Director                      | R           | R       | R           | R                   | R U⁴           | R U⁴             |
  | Finance Accountant                    | R           | R       | R           | R                   | R U⁵           | R                |
  | System Administrator                  | CRUD        | CRUD    | CRUD        | CRUD                | CRUD           | CRUD             |
  | Developer                             | R           | R       | R           | R                   | R              | R                |
  | Portal (Client Rep / Vendor / Customer)| R          | R       | —           | —                   | R⁶             | —                |
  ```
- **Example §9.4 row**:
  ```
  | expense_claims | gl_code | Hidden | R | R | R | C/R/U/D | — |
  ```
- **What NOT to include**: Do not describe role hierarchy as inheritance code. Do not include
  workflow-level permission rules (those go in §11). Do not list portal role CRUD at
  field-level granularity (insufficient data — flag in §15).
- **Cross-refs**: Role names in §9.1 must exactly match role references in §11 workflow
  `Trigger` and `Guard` lines. Scope footnotes must map to status values in §10. Field-level
  overrides in §9.4 must be consistent with §6 field `flags` (private fields `†` should
  appear as `Hidden` for non-finance roles).
- **Success criteria**: Directly satisfies SC-4 (every role's CRUD across all forms unambiguous).

---

### §10. Workflow State Machine

- **Purpose**: Enumerate all valid `expense_claims.status` values and every legal status
  transition so Zia understands the full lifecycle graph before reading individual workflow
  detail in §11.
- **Source**: 3a-ds-schema.md `expense_claims.status` picklist (9 values);
  3b-deluge.md all script "Fields written" sections (transitions);
  3d-context.md §"Key business rules".
- **Format**: Two sub-parts:
  - Status enum bullet list with terminal/non-terminal classification.
  - Transitions table: one row per transition edge.
- **Columns** (transitions table): `from_status | trigger | condition | to_status | actor_role | workflow_ref`
- **Cell encoding rules**:
  - Status enum: bullet each value; mark `(terminal)` for Approved and Rejected (no further
    transitions originate from these except via resubmission edit); mark `(re-entrant)` for
    Resubmitted (it re-enters routing from on_edit).
  - `from_status`: exact picklist value string in double quotes.
  - `trigger`: one of `form_submit`, `lm_approve`, `lm_reject`, `hod_approve`, `hod_reject`,
    `hod_override` (HoD action on Key 2 dispute reconsideration path — distinct from
    `hod_approve` on standard tier), `fd_approve` (Finance Director / Key 2),
    `fd_reject`, `sla_timer`, `on_edit`.
  - `condition`: brief guard clause in plain English or `always`.
  - `to_status`: exact picklist value string in double quotes.
  - `actor_role`: role name matching §9.1, or `SYSTEM` for scheduled.
  - `workflow_ref`: `→ WF-NN` referencing §11 workflow ID.
- **hod_override transition** (must be present): `"Key 2 Dispute"` | hod_override | always |
  `"Pending Second Key"` | Head of Department | → WF-09.A
- **Ordering**: Lifecycle order — initial submission → LM tier → HoD tier → Key 2 tier →
  dispute resolution → resubmission → SLA escalation.
- **Example rows**:
  ```
  | from_status           | trigger    | condition                          | to_status             | actor_role    | workflow_ref |
  | "Submitted"           | form_submit| submitter is LM role               | "Pending HoD Approval"| Employee      | → WF-05      |
  | "Pending LM Approval" | lm_approve | amount ≤ tier-1 threshold          | "Approved"            | Line Manager  | → WF-07      |
  | "Pending LM Approval" | lm_approve | amount > tier-1 threshold          | "Pending HoD Approval"| Line Manager  | → WF-07      |
  | "Pending Second Key"  | fd_reject  | always                             | "Key 2 Dispute"       | Finance Director | → WF-11   |
  | "Key 2 Dispute"       | hod_override | always                           | "Pending Second Key"  | Head of Department | → WF-09.A |
  | "Pending LM Approval" | sla_timer  | days since submission ≥ 3         | "Pending HoD Approval"| SYSTEM        | → WF-13      |
  ```
- **What NOT to include**: No Deluge code, no ASCII state diagram, no email details
  (those are in §11 and §13). Do not list `Draft` as a transition destination (it is a
  pre-submission UI state; the .ds includes it in the picklist but no workflow transitions
  to Draft after submission).
- **Cross-refs**: Every status value in the enum must exist in §7 `@Picklist:status` (9 values).
  Every `workflow_ref` must match a WF-NN ID in §11. Every `actor_role` must match §9.1.
- **Success criteria**: Supports SC-5 (workflow trigger/effect reconstructible) and SC-1
  (status field values). Supports SC-4 (actor role per transition).

---

### §11. Workflow Catalog

- **Purpose**: Describe all 13 Deluge workflows in plain English using a fixed compact bullet
  template so Zia can reconstruct triggers, logic, side-effects, API calls, and emails for
  each workflow without Deluge code.
- **Source**: 3b-deluge.md all 13 script sections (Effect prose, Fields read/written, Emails,
  Audit trail). 3c-config.md §"Deluge Manifest" for trigger location strings.
- **Format**: One H3 subsection per workflow. Fixed 8-bullet compact template (see below).
  Multi-branch scripts split into sibling `.A` / `.B` sub-IDs.
  **This section has exactly 17 H3 heading blocks** from 13 parent workflows (WF-01..WF-13),
  with splits on WF-03 (.A, .B), WF-07 (.A, .B), WF-09 (.A, .B), WF-11 (.A, .B).
- **Workflow ID assignment** (canonical, the implementer MUST use these exactly):
  - WF-01: expense_claim.on_load.auto_populate
  - WF-02: expense_claim.on_validate
  - WF-03: expense_claim.on_success (self-approval branch: WF-03.A normal, WF-03.B bypass)
  - WF-04: expense_claim.on_success.fill_shadows
  - WF-05: expense_claim.on_success.generate_ref
  - WF-06: expense_claim.on_edit
  - WF-07: lm_approval.on_approve (under-threshold branch: WF-07.A; over-threshold: WF-07.B)
  - WF-08: lm_approval.on_reject
  - WF-09: hod_approval.on_approve (split: WF-09.A dispute reconsideration; WF-09.B normal). WF-09.A: uses template key1_reconsider_override (→ finance_director). WF-09.B over-threshold: uses template key1_approved_dual_required. WF-09.B under-threshold: uses template hod_approved.
  - WF-10: hod_approval.on_reject
  - WF-11: finance_approval.on_approve (split: WF-11.A same-person block; WF-11.B approval)
  - WF-12: finance_approval.on_reject
  - WF-13: sla_enforcement_daily
- **Bullet template** (8 keys, exact labels):
  ```
  ### WF-NN  <script_name>
  - Trigger: <form>.<event> (<actor_role> | scheduled <freq>)
  - Guard:   <boolean condition | "always">
  - Effect:  <1-paragraph plain English, ≤80 words>
  - Reads:   <semi-separated field refs using micro-syntax from §3>
  - Writes:  <semi-separated assignments using := or → notation>
  - APIs:    <Custom API names from §12 | "—">
  - Emails:  <template_name → recipient; template_name → recipient | "—">
  - Audit:   <approval_history.action_1 value logged | "—">
  ```
- **Emails bullet**: When a non-split block sends different emails on different branches, list all pairs semicolon-separated with a `(if <condition>)` parenthetical: e.g., `key1_approved_dual_required → finance_director (if amount > dual-threshold); hod_approved → input.Email (if amount ≤ dual-threshold)`.
- **Audit bullet**: When different audit values are logged on different conditions within one block, list both values with `(if <condition>)` labels: e.g., `'Approved (Key 1)' (if over-threshold); 'Approved (HoD)' (if under-threshold)`.
- **ESG fields in Reads/Writes**: WF-07 and WF-09 reference `gl_accounts[...].ESG_Category`,
  `gl_accounts[...].Carbon_Factor`, `gl_accounts[...].GRI_Indicator` (reads), and
  `input.ESG_Category`, `input.Estimated_Carbon_KG` on expense_claims (writes). These MUST
  appear in the workflow `Reads:` and `Writes:` lines to preserve behavioral intent, but each
  mention MUST be suffixed with `(advisory — not .ds-declared)` inline, to prevent Zia from
  hallucinating these fields back into §6.3 or §6.5.
- **WF-11.A Emails line**: MUST read `(inline) Governance Alert → zoho.adminuserid` — this
  is an inline ad-hoc `sendmail` block in the finance_approval Level-3 `on approve` actions
  block. It is NOT a named template from §13 named rows. Reference `INLINE-01` as the id.
- **Ordering**: on_load → on_validate → on_success (×3) → on_edit → LM approve → LM reject →
  HoD approve → HoD reject → Finance approve → Finance reject → scheduled.
- **Example blocks**:
  ```markdown
  ### WF-01  expense_claim.on_load.auto_populate
  - Trigger: expense_claims.on_load (Employee | new record only)
  - Guard:   form is in "add" mode
  - Effect:  Auto-fills Employee Name from zoho.loginuser and Email from zoho.loginuserid to
             reduce data-entry friction and ensure correct submitter association.
  - Reads:   zoho.loginuser; zoho.loginuserid
  - Writes:  input.Employee_Name1 := zoho.loginuser; input.Email := zoho.loginuserid
  - APIs:    —
  - Emails:  —
  - Audit:   —
  ```
  ```markdown
  ### WF-11.A  finance_approval.on_approve — same-person block
  - Trigger: expense_claims approval process > Finance Director (on_approve)
  - Guard:   zoho.loginuser == input.Key_1_Approver (same-person conflict)
  - Effect:  Blocks approval with a governance alert; resets status to "Pending Second Key";
             logs a Warning audit record; notifies admin of attempted same-person dual-key.
  - Reads:   input.Key_1_Approver; zoho.loginuser; input.ID; input.claim_id; input.amount_zar
  - Writes:  input.status → "Pending Second Key"
  - APIs:    —
  - Emails:  (inline) Governance Alert → zoho.adminuserid
  - Audit:   "Warning"
  ```
- **What NOT to include**: No Deluge code fragments. No email body prose (email subjects go
  in §13 via template reference only). Do not invent APIs not listed in §12. Do not reference
  widgets (0 declared). Do not merge two branching workflows into one block if the guard
  conditions and effects diverge significantly — split them.
- **Cross-refs**: Every `Emails:` entry (other than the inline WF-11.A governance alert) must
  reference a template name existing in §13 named rows. The inline WF-11.A entry is
  cross-referenced by INLINE-01 in §13. Every `Audit:` value must be a value in
  §7 `@Picklist:action_1`. Every `APIs:` name must exist in §12. `workflow_ref` values in §10
  must map to WF-NN IDs here. `Writes:` field names must exist in §6 form tables or carry the
  `(advisory — not .ds-declared)` suffix.
- **Success criteria**: Directly satisfies SC-5 (trigger, form, event, plain-English effect,
  fields read/written, Custom APIs invoked, emails sent — all present).

---

### §12. Custom APIs

- **Purpose**: Enumerate all 4 Custom APIs with full parameter specifications, return shapes,
  permissions, and invocation context so Zia can configure Creator's microservices layer.
- **Source**: 3c-config.md §"Custom APIs" table; 3c-config.md §"Deluge Manifest" (context/location).
- **Format**: Single wide GFM table, 4 data rows.
- **Columns**: `name | method | params | returns | permissions | invoked_by | purpose`
- **Cell encoding rules**:
  - `name`: exact API name from config (case-preserved): Get_Dashboard_Summary,
    Get_Claim_Status, Get_ESG_Summary, Get_SLA_Breaches.
  - `method`: `POST` for all 4 (from research).
  - `params`: semi-separated list of `<param_name>:<type>(req|opt)`.
    Example: `department:Text(opt); date_from:Date(opt); date_to:Date(opt)`.
  - `returns`: semi-separated list of `<field>:<type>`.
    Example: `pending_count:Number; approved_count:Number; total_amount_pending:Decimal`.
  - `permissions`: not declared in research — write `—` (do not invent).
  - `invoked_by`: `external (REST)` for all 4. No internal workflow invokes a Custom API;
    all 4 are externally facing (dashboards, external systems). The 13 Deluge workflows in
    §11 all have `APIs: —`.
  - `purpose`: one sentence ≤15 words from 3c-config.md purpose column.
- **Ordering**: Alphabetical: Get_Claim_Status, Get_Dashboard_Summary, Get_ESG_Summary,
  Get_SLA_Breaches.
- **Example row**:
  ```
  | name               | method | params                                              | returns                                                                                        | permissions | invoked_by      | purpose |
  | Get_Claim_Status   | POST   | claim_reference:Text(req)                           | status:Text; amount_zar:Decimal; department:Text; category:Text; submitted_date:Date; last_action:Text | — | external (REST) | Query claim status by reference number for external systems. |
  ```
- **What NOT to include**: No widget references (0 widgets). Do not document the 13 Deluge
  workflow scripts as Custom APIs — they are internal. Do not invent permissions not stated
  in research. Do not include the internal `get_dashboard_summary` Deluge script manifest
  entry as a separate row (it duplicates the Custom API entry).
- **Cross-refs**: `invoked_by` column must be consistent with §11 workflow `APIs:` lines
  (all `—` currently, since no workflow invokes a Custom API per research). §14 BR-NNN should
  include a rule noting that external callers must authenticate via Zoho OAuth.
- **Success criteria**: Directly satisfies SC-6 (every Custom API: name, params with types,
  return shape, permissions).

---

### §13. Email Templates

- **Purpose**: Enumerate all 18 named email templates plus 1 inline ad-hoc sendmail with
  trigger context, recipients, subject template strings, and variable contracts so Zia can
  configure Creator's notification system exactly.
- **Source**: 3c-config.md §"Email Templates" table (18 named rows);
  3b-deluge.md per-script Emails sections (cross-check subjects and recipients).
- **Format**: Single wide GFM table, **19 rows total** (18 named + 1 inline ad-hoc row for
  the Governance Alert).
- **Columns**: `id | trigger_workflow_ref | to | cc | subject_template | variables | intent`
- **Cell encoding rules**:
  - `id`: use template name directly from 3c-config.md for the 18 named rows (e.g.,
    `submit_notify_lm`). For the inline Governance Alert row, use id = `INLINE-01`.
  - `trigger_workflow_ref`: `WF-NN` referencing the workflow in §11 that sends this email;
    use `WF-NN.A` / `WF-NN.B` for split branches.
  - `to`: role name or field reference (`input.Email` for employee's email field);
    verbatim from 3c-config.md `To` column.
  - `cc`: role name or `—`. **MUST be populated from `email-templates.yaml` `cc_role` field.
    Exactly 2 named templates have a non-null CC: `sla_reminder` (cc = hod),
    `key2_sla_reminder` (cc = admin). All other templates have `cc = —`.**
  - `subject_template`: exact subject string with `{{var}}` tokens, verbatim from
    3c-config.md. For INLINE-01: `GOVERNANCE ALERT - Claim {{claim_id}} - Same-Person Key 2 Blocked`.
  - `variables`: comma-separated `{{var}}` tokens that appear in subject or body.
  - `intent`: one sentence from 3c-config.md `Trigger` or derived from workflow context.
    For INLINE-01: `Alert admin of same-person dual-key attempt; no named template — inline sendmail.`
  - For INLINE-01, `template_id = —` (no named template file) to distinguish from the 18.
- **Ordering**: Match the ordering in 3c-config.md §"Email Templates" table (chronological
  by lifecycle event: submission → LM action → HoD action → Key 2 → SLA). Place INLINE-01
  after the 18 named rows as the final row.
- **Named template list** (authoritative — exactly 18, from email-templates.yaml):
  1. submit_notify_lm, 2. submit_self_approval_bypass, 3. resubmit_notify_lm,
  4. resubmit_self_approval_bypass, 5. lm_approved_final, 6. lm_approved_escalate,
  7. lm_rejected, 8. hod_approved, 9. hod_rejected, 10. sla_escalation,
  11. sla_reminder (cc=hod), 12. key1_approved_dual_required, 13. key2_approved_final,
  14. key2_rejected_dispute, 15. key2_dispute_notify_employee, 16. key1_reconsider_override,
  17. key2_sla_reminder (cc=admin), 18. key2_sla_escalation.
- **Example rows**:
  ```
  | id                       | trigger_workflow_ref | to                 | cc    | subject_template                                                | variables                  | intent |
  | submit_notify_lm         | WF-03.A              | line_manager       | —     | Expense Claim {{claim_id}} requires your approval               | {{claim_id}}, {{Employee_Name1}}, {{amount_zar}} | Notify LM of new claim awaiting tier-1 approval. |
  | sla_reminder             | WF-13                | line_manager       | hod   | SLA Reminder: Claim {{claim_id}} pending approval               | {{claim_id}}               | Remind LM of pending approval with HoD CC. |
  | INLINE-01                | WF-11.A              | zoho.adminuserid   | —     | GOVERNANCE ALERT - Claim {{claim_id}} - Same-Person Key 2 Blocked | {{claim_id}}             | Alert admin of same-person dual-key attempt; no named template — inline sendmail. |
  ```
- **What NOT to include**: No email body prose. Do not document email bodies — the BRD contract
  is subject + variables only. Do not invent templates not in 3c-config.md. Do not include
  the compliance_config seed data as a template. Do not count INLINE-01 as one of the 18
  named templates.
- **Cross-refs**: Every named template must be referenced in at least one §11 workflow `Emails:`
  line. INLINE-01 is referenced by WF-11.A `Emails: (inline) Governance Alert → zoho.adminuserid`.
  The count of named rows must equal 18 per §16 assertion. CC column must be populated
  correctly for sla_reminder and key2_sla_reminder.
- **Success criteria**: Directly satisfies SC-7 (every email template: trigger, recipients,
  subject, variables).

---

### §14. Business Rules Index

- **Purpose**: Provide a stable, numbered, cross-referenceable index of every business rule
  enforced by the system (compliance, approval logic, SLA, governance, data integrity) so
  Zia and auditors can trace each rule to its enforcement mechanism.
- **Source**: 3d-context.md §"Key business rules" and §"Compliance & audit requirements";
  3b-deluge.md §"Key Observations & Governance Patterns"; 3c-config.md §"UI Standards".
- **Format**: Numbered list. Each entry format:
  `BR-NNN  (category)  Statement of rule → enforced_by: <workflow_id | form_validation | role_permission | config>`
- **Categories** (use these exact labels):
  - `governance` — King IV, segregation of duties
  - `compliance` — SARS, POPIA, ISO 37001, ISSB, GRI
  - `financial` — threshold, GL, currency
  - `sla` — timing, escalation
  - `data_integrity` — duplicate, versioning, retention
  - `ui` — field visibility, menu permissions
- **Cell encoding rules**:
  - Rule statement: one sentence, imperative, present tense.
  - `enforced_by`: comma-separated list of WF-NN IDs and/or `form_validation`,
    `role_permission`, `config`.
  - **ESG advisory rule**: Include one `(compliance)` rule stating: "ESG/carbon reporting is
    advisory only until the five referenced fields (`gl_accounts.ESG_Category`,
    `gl_accounts.Carbon_Factor`, `gl_accounts.GRI_Indicator`, `expense_claims.ESG_Category`,
    `expense_claims.Estimated_Carbon_KG`) are added to their respective forms; current
    workflow writes silently no-op." → `enforced_by: advisory (see §15)`.
  - **compliance_config rules**: Any §14 BR referencing organization-type or ESG toggles must
    tag `enforced_by: config (compliance_config advisory)` to preserve traceability even
    though compliance_config is absent from the .ds (see §15 bullet 6).
- **Ordering**: Group by category; within category ascending BR number.
  Approximate allocation:
  - BR-001..BR-005: governance (King IV, segregation of duties, self-approval, same-person Key2)
  - BR-006..BR-010: compliance (POPIA, SARS S11(a), VAT, retention, 90-day policy)
  - BR-011..BR-015: financial (positive amount, threshold routing, dual-threshold, GL auto-assign)
  - BR-016..BR-018: sla (2-day reminder, 3-day escalation LM, 3-day escalation Key 2)
  - BR-019..BR-022: data_integrity (duplicate detection, resubmission versioning, self-ref
    deferred, shared picklist invariant)
  - BR-023..BR-025: ui (approval_history view-only, shadow fields hidden, status read-only all)
- **Example entries**:
  ```
  BR-001  (governance)  No user in the Line Manager role may approve their own submitted claim
                         → enforced_by: WF-03, WF-06
  BR-005  (governance)  The Key 2 approver (Finance Director) must not be the same person as
                         Key 1 approver (HoD) → enforced_by: WF-11.A
  BR-007  (compliance)  Claims >= R5,000 require VAT_Invoice_Type = "Full Tax Invoice (>= R5,000)"
                         (SARS VAT Act) → enforced_by: WF-02 (form_validation)
  BR-011  (financial)   claim amount_zar must be > 0 → enforced_by: WF-02 (form_validation)
  BR-019  (data_integrity) Duplicate claims (same employee, date, amount) trigger a warning but
                         do not block submission → enforced_by: WF-02
  ```
- **What NOT to include**: Do not embed Deluge code. Do not duplicate picklist value lists
  (those are in §7). Do not include UI layout preferences (those are advisory only). Do not
  include compliance_config-dependent rules as implemented rules — note them as advisory only.
- **Cross-refs**: Every `enforced_by: WF-NN` reference must match a WF-NN in §11.
  Form-level rules cited in §6 must appear as BR-NNN here. State transitions in §10
  that have guards should reference the BR-NNN that defines the guard logic.
- **Success criteria**: Supports SC-5 (workflows traceable to rules), SC-4 (role permissions
  traceable to governance rules), SC-6 (Custom API authentication rule).

---

### §15. Out of Scope / Known Discrepancies

- **Purpose**: Explicitly list everything that is NOT in this BRD so Zia does not attempt to
  reconstruct artifacts that are absent, fictional, or intentionally excluded.
- **Source**: 0-brief.md §"Hard constraints"; 4-reconciled-blueprint.md §"Ranked risks" risk 5;
  3c-config.md (compliance_config presence in field-descriptions YAML); 3a-ds-schema.md
  §"Subforms" (none).
- **Format**: Numbered bullet list. Each bullet: `[EXCLUSION]` or `[DISCREPANCY]` tag,
  then one-sentence statement.
- **Ordering**: Exclusions first (things not implemented), then discrepancies (data conflicts).
- **Required entries** (minimum — implementer must include all of these):
  ```
  1. [EXCLUSION] Widgets: 0 widgets are declared in forgeds.yaml; do NOT create any widget
     components.
  2. [EXCLUSION] Subforms: 0 subform relationships exist in the .ds; do NOT add any subforms.
  3. [EXCLUSION] Deluge source code: no Deluge script text is included in this BRD by design.
     Reconstruct from §11 plain-English behavioral specs.
  4. [EXCLUSION] Portal role field-level CRUD: insufficient data to specify; apply Creator
     default portal permissions.
  5. [EXCLUSION] Seed data: approval_thresholds.json, clients.json, departments.json,
     gl_accounts.json reference data exists but is not embedded in this BRD. Load separately.
  6. [DISCREPANCY] compliance_config form: field-descriptions YAML mentions
     compliance_config with 4 fields (Config_Key, Config_Value, Description, Active);
     this form is ABSENT from the .ds export. Do NOT create this form. Treat
     compliance_config-dependent rules as advisory only until a .ds export confirms the schema.
     Any §14 BR referencing organization-type/ESG toggles must tag
     enforced_by: config (compliance_config advisory) to preserve traceability.
  7. [DISCREPANCY] Schema-workflow divergence: workflows WF-07 and WF-09 read
     gl_accounts.ESG_Category, gl_accounts.Carbon_Factor, and gl_accounts.GRI_Indicator,
     and WF-09 writes expense_claims.ESG_Category and expense_claims.Estimated_Carbon_KG —
     but NONE of these 5 fields are declared in the .ds schema for their respective forms.
     Treat these workflow reads/writes as advisory (they silently no-op in Creator until the
     fields are added). Do NOT add any of these 5 fields to §6.3 or §6.5.
  8. [DISCREPANCY] Governance Alert email: WF-11.A contains an inline ad-hoc sendmail block
     (subject: "GOVERNANCE ALERT - Claim {claim_id} - Same-Person Key 2 Blocked") that is
     NOT a named template in email-templates.yaml. It is documented in §13 as INLINE-01
     with template_id = — to distinguish it from the 18 named templates.
  9. [DISCREPANCY] 3c-config.md summary states 19 email templates; authoritative count from
     email-templates.yaml is 18 named templates. The 19th was a miscounting artifact; INLINE-01
     is the governance alert inline sendmail, not a 19th named template.
  10. [EXCLUSION] Pivot table internal autoview reference: Expense_Summary is built on
     "Autoview_1775232194200_expense_claims" — this is a Creator-internal artifact. Do NOT
     create it manually; Creator generates it automatically when the pivot report is configured.
  11. [EXCLUSION] Named types (0 declared), external integrations, Zoho Analytics connectors:
     none declared in forgeds.yaml; do NOT add them.
  ```
- **What NOT to include**: Do not list things that ARE in scope. Do not repeat field-level
  detail or workflow detail here. Do not pad with generic disclaimers.
- **Cross-refs**: `compliance_config` discrepancy must not appear as a form in §4 or §6.
  ESG field discrepancy (bullet 7) must be cross-referenced by the relevant BR-NNN in §14
  (advisory). `INLINE-01` governance alert is now resolved as inline ad-hoc; the §13 template
  count of 18 named is authoritative.
- **Success criteria**: Protects SC-1, SC-2, SC-3, SC-5 from Zia hallucinating absent artifacts.
  Ensures §16 Reconstruction Checklist counts are achievable.

---

### §16. Reconstruction Checklist

- **Purpose**: Provide a self-audit count-assertion list Zia can verify after reconstruction
  to confirm fidelity before declaring the app complete.
- **Source**: All research files (counts verified in §2 Application Meta).
- **Format**: Numbered list of "must"-phrased assertions, one per artifact class.
- **Ordering**: Forms, fields, lookup edges, subforms, reports, status values, picklists,
  roles, workflows, Custom APIs, email templates, widgets, business rules, append-only config,
  conditional formatting, auto-generation rules.
- **Cell encoding rules**: Each line: `MUST have exactly N <artifact>: <comma-list of names or
  description>.`
- **Required assertions** (minimum — implementer must include all of these):
  ```
  1.  MUST have exactly 6 forms: departments, clients, gl_accounts, approval_thresholds,
      expense_claims, approval_history.
  2.  MUST have exactly 53 fields across all forms (departments: 3, clients: 3, gl_accounts: 7,
      approval_thresholds: 8, expense_claims: 27, approval_history: 5).
  3.  MUST have exactly 5 lookup edges (see §5 ER Skeleton), including 1 self-referential.
  4.  MUST have 0 subforms.
  5.  MUST have exactly 11 reports: 9 list, 1 kanban (gl_accounts_by_expense_category),
      1 pivot/summary (Expense_Summary).
  6.  MUST have exactly 9 expense_claims.status values: Draft, Submitted, Pending LM Approval,
      Pending HoD Approval, Pending Second Key, Key 2 Dispute, Approved, Rejected, Resubmitted.
  7.  MUST have exactly 5 named picklists (see §7): action_1, category, Risk_Level, status,
      VAT_Invoice_Type. (Employee_Name1_prefix is an inline sub-component, NOT a named picklist.)
  8.  MUST have exactly 7 internal roles: Employee, Line Manager, Head of Department,
      Finance Director, Finance Accountant, System Administrator, Developer.
      Plus 3 portal roles represented as 1 combined row in §9.2:
      Client Representative, Vendor, Customer.
  9.  MUST have exactly 13 Deluge workflows (WF-01 through WF-13); multi-branch scripts have
      sibling .A/.B sub-IDs but count as 1 workflow each. §11 contains exactly 17 H3 blocks.
  10. MUST have exactly 4 Custom APIs: Get_Claim_Status, Get_Dashboard_Summary, Get_ESG_Summary,
      Get_SLA_Breaches.
  11. MUST have exactly 18 named email templates PLUS 1 inline sendmail block (INLINE-01) in
      the finance_approval Level-3 on_approve actions block with subject
      "GOVERNANCE ALERT - Claim {claim_id} - Same-Person Key 2 Blocked".
      Verify template names match §11 Emails: references.
  12. MUST have 0 widgets.
  13. MUST configure approval_history reports (approval_history_Report, Audit_Trail) with
      menu permissions excluding Edit/Delete/Duplicate/Import/Export/Print; the form itself
      may retain a default Edit action button (menu-level enforcement suffices for append-only
      posture; the .ds form declares both on_add and on_edit action hooks).
  14. MUST apply conditional formatting to expense_claims_Report status column using exact
      hex colors from .ds: Approved = #1bbc9b, Rejected = #e84c3d, Pending states = #bd588b.
      Additional pending-variant colors: #765f89, #107c91 as declared in .ds.
  15. MUST auto-generate Claim_Reference in EXP-NNNN format via WF-05.
  16. MUST set Retention_Expiry_Date = Submission_Date + 5 years via WF-02.
  17. MUST have exactly 5 required (`must have`) fields — all on expense_claims:
      Employee_Name1, Email, Submission_Date, Claim_Reference, Supporting_Documents.
  18. MUST have `approval_history.action_1` picklist with exactly 12 values (in order):
      Submitted, Submitted (Self-approval bypass), Approved (LM), Approved (HoD),
      Approved (Key 1), Approved (Key 2), Rejected, Rejected (Key 2), Reconsidered (Key 1),
      Escalated (SLA Breach), Resubmitted, Warning.
  19. MUST have CC recipients on exactly 2 named email templates:
      sla_reminder (cc = hod), key2_sla_reminder (cc = admin). All other templates cc = —.
  20. The §9.2 CRUD matrix MUST have exactly 8 data rows (7 internal + 1 combined-portal)
      and exactly 6 form columns in dependency order.
  ```
- **What NOT to include**: No explanatory prose beyond the assertion. Do not list seed data
  record counts. Do not describe how to configure Creator UI (that is Zia's job).
- **Cross-refs**: Every count must be derivable from §2 Application Meta. Every named artifact
  must appear in the appropriate catalog section (§6, §7, §8, §9, §11, §12, §13).
- **Success criteria**: Supports all 7 SC as a final gate-check. A checklist item failing
  indicates a fidelity gap in Zia's reconstruction.

---

## 5. Data completeness assertions (for the Phase 6 simulator to score)

- **A1**: Exactly 6 form subsections in §6 Form Catalog, one per form, with link_names:
  `departments`, `clients`, `gl_accounts`, `approval_thresholds`, `expense_claims`,
  `approval_history`.
- **A2**: Exactly 53 field rows across all 6 §6 form tables:
  departments=3, clients=3, gl_accounts=7, approval_thresholds=8, expense_claims=27,
  approval_history=5. Sum must equal 53.
- **A3**: Every `lookup→<target>` entry in §6 field tables (5 total, including 1 self-ref)
  has a matching edge row in §5 ER Skeleton.
- **A4**: Every `@Picklist:<name>` reference in §6 resolves to an H3 heading in §7 Picklist
  Appendix with the exact same name string.
- **A5**: Exactly 5 H3 blocks in §7 Picklist Appendix: `action_1`, `category`,
  `Risk_Level`, `status`, `VAT_Invoice_Type`. (`Employee_Name1_prefix` is an inline
  sub-component enum on the compound name field, NOT a named picklist — it must NOT appear
  as a §7 H3 block.)
- **A6**: The `status` picklist in §7 contains exactly 9 values matching the status enum
  in §10 Workflow State Machine.
- **A7**: Exactly 11 rows in §8 Reports Catalog; exactly 1 row has `view_type = pivot`
  (`Expense_Summary`); exactly 1 row has `view_type = kanban`
  (`gl_accounts_by_expense_category`).
- **A8**: Every `source_form` value in §8 matches a form link_name in §4 and §6.
- **A9**: Exactly 18 named rows in §13 Email Templates table, plus 1 inline ad-hoc row
  (INLINE-01). Total rows in §13 table = 19.
- **A10**: Every `trigger_workflow_ref` in §13 is a WF-NN (or WF-NN.A/B) ID that exists
  in §11.
- **A11**: Exactly 17 H3 heading blocks in §11 Workflow Catalog, corresponding to 13 parent
  workflows (WF-01..WF-13), with splits on WF-03 (.A, .B), WF-07 (.A, .B),
  WF-09 (.A, .B), WF-11 (.A, .B).
- **A12**: Every `Emails:` value in a §11 workflow block either (a) references a template name
  that exists in the 18 named rows of §13, or (b) is the inline Governance Alert reference
  for WF-11.A (INLINE-01), or (c) is documented as a discrepancy in §15.
- **A13**: Every `Audit:` value in a §11 workflow block is a string that appears in the
  `action_1` picklist defined in §7 (12 values).
- **A14**: Exactly 4 rows in §12 Custom APIs table.
- **A15**: No form named `compliance_config` exists in §4, §5, or §6.
- **A16**: The §9.2 CRUD matrix has exactly 8 data rows (7 internal role rows + 1 combined
  portal row) and exactly 6 form columns in dependency order.
- **A17**: Every field marked `†` (private) in §6 appears as `Hidden` in at least the
  `Employee` and `Line Manager` columns of the §9.4 field-level override table.
- **A18**: The §16 Reconstruction Checklist assertion #2 (53 fields, with per-form breakdown)
  matches the actual row counts in §6 form tables.
- **A19**: 0 widgets declared anywhere in the BRD (§2 count = 0; no widget section exists;
  §15 exclusion present).
- **A20**: Every `workflow_ref (→ WF-NN)` in §10 transitions table maps to a WF-NN that
  exists in §11.

---

## 6. Phase 7 writer workflow

Execute these steps linearly. Do NOT skip or reorder.

1. Read this spec in full. Then read `4-reconciled-blueprint.md` and all four `3x-*.md`
   research files. Do not proceed until all 5 documents are read.

2. Create the output file (empty) at the target path:
   `C:\Users\User\OneDrive\Documents\GitHub\Expense_Reimbursement_Manager\docs\brd\zia-brd-2026-04-24.md`
   Confirm the directory exists; create it if absent.

3. Write §1 Ingestion Contract. Source: this spec §4 §1 + blueprint §"Ingestion-contract
   header". Write the YAML fenced block using actual ERM values. Add a one-sentence
   reading directive prose line after the block.

4. Write §2 Application Meta. Source: this spec §4 §2 + 3a-ds-schema.md §"Application
   Header". Populate counts from all research files. Double-check counts match §16
   planned assertions before moving on. Use revised counts: 53 fields, 11 reports,
   18 named + 1 inline email templates, 5 named picklists.

5. Write §3 Glossary & Notation Legend. Source: this spec §3 (copy verbatim). Render as
   GFM table (Symbol | Meaning | Example). Follow with Reads/Writes note block.

6. Write §4 Entity Catalog. Source: this spec §4 §4 + 3a-ds-schema.md form headers.
   6 rows; dependency order: departments, clients, gl_accounts, approval_thresholds,
   expense_claims, approval_history.

7. Write §5 ER Skeleton. Source: this spec §4 §5 + 3a-ds-schema.md §Relationships.
   5 rows; include self-ref edge; mark `on_delete = —` for all.

8. Write §6 Form Catalog. Source: this spec §4 §6 + 3a-ds-schema.md per-form tables
   + 3c-config.md §"Field Descriptions".
   - Write §6.1 departments (3 fields).
   - Write §6.2 clients (3 fields).
   - Write §6.3 gl_accounts (7 fields — exactly: gl_code, account_name, expense_category,
     receipt_required, SARS_Provision, Risk_Level, Active). Do NOT include ESG_Category,
     Carbon_Factor, or GRI_Indicator — these are not .ds-declared. Flag in §15.
   - Write §6.4 approval_thresholds (8 fields). Use example from this spec as template.
   - Write §6.5 expense_claims (27 fields). Most complex form. Ensure Department_Shadow
     and Client_Shadow carry `†` flag. Set Parent_Claim_ID type = `pick list (self-ref)`,
     ref/pick = `self_ref→expense_claims`, and add a help note: "Self-referential: stores
     ID of the parent claim this record amends; .ds type is pick list filtered to
     expense_claims.ID." Do NOT override the type to self_ref→expense_claims in the type
     column — use `pick list (self-ref)` to match the .ds verbatim.
   - Write §6.6 approval_history (5 fields).
   After all 6 subsections, count all rows: must equal 53.

9. Write §7 Picklist Appendix. Source: this spec §4 §7 + 3a-ds-schema.md §"Picklist
   Appendix". **5 named picklists** (alphabetical): action_1, category, Risk_Level, status,
   VAT_Invoice_Type. Do NOT include Employee_Name1_prefix as a named picklist.
   Verify `status` has 9 values. Verify `action_1` has exactly 12 values in declared order.

10. Write §8 Reports Catalog. Source: this spec §4 §8 + 3a-ds-schema.md §Reports.
    **11 rows**; verify Expense_Summary has `view_type = pivot`; verify
    gl_accounts_by_expense_category has `view_type = kanban`. Add `menu_perms` column
    using 3c-config.md §"UI Standards" §"Report Menu Permissions". Use full hex colors
    (#rrggbb) in cond_format — no color names.

11. Write §9 Roles & Access Model. Source: this spec §4 §9 + 3c-config.md §Roles.
    - §9.1 Role Definitions (10 rows: 7 internal + 3 portal).
    - §9.2 CRUD matrix (**8 role rows** × 6 form columns): 7 internal rows + 1 combined
      portal row. Include Developer as 7th internal role (R on all forms).
    - §9.3 Scope footnotes (6 footnote bullets ¹–⁶).
    - §9.4 Field-level overrides (~10 rows from 3c-config.md §"Field Permissions").

12. Write §10 Workflow State Machine. Source: this spec §4 §10 + 3a-ds-schema.md status
    picklist + 3b-deluge.md transition paths.
    - Status enum bullets (9 values; classify terminal/non-terminal).
    - Transitions table (~13-15 rows covering all paths including dispute loop, hod_override
      trigger, and SLA escalation).

13. Write §11 Workflow Catalog. Source: this spec §4 §11 + 3b-deluge.md all 13 scripts.
    Use the 8-bullet compact template exactly. Follow the WF-NN assignment table in this spec.
    Split multi-branch scripts (WF-03, WF-07, WF-09, WF-11) into .A/.B sub-blocks.
    **Total = 17 H3 blocks**. This section will be the largest (~195 lines). Write all
    13 parent workflows. WF-07 and WF-09 Reads/Writes for ESG fields must carry the
    `(advisory — not .ds-declared)` suffix. WF-11.A Emails must be
    `(inline) Governance Alert → zoho.adminuserid`.

14. Write §12 Custom APIs. Source: this spec §4 §12 + 3c-config.md §"Custom APIs". 4 rows;
    alphabetical order; `permissions = —` for all (not declared in research);
    `invoked_by = external (REST)` for all 4.

15. Write §13 Email Templates. Source: this spec §4 §13 + 3c-config.md §"Email Templates".
    **18 named rows + 1 inline ad-hoc row (INLINE-01)**; map each to its WF-NN trigger;
    fill `{{var}}` tokens verbatim. Populate CC column from email-templates.yaml cc_role:
    sla_reminder (cc=hod), key2_sla_reminder (cc=admin), all others cc=—.

16. Write §14 Business Rules Index. Source: this spec §4 §14 + 3d-context.md + 3b-deluge.md
    §"Key Observations". ~20-25 BR-NNN entries; group by category; every enforced_by
    reference must exist in §11. Include ESG advisory BR and compliance_config advisory tag.

17. Write §15 Out of Scope / Known Discrepancies. Source: this spec §4 §15. Minimum 11
    entries. compliance_config discrepancy is mandatory. ESG schema-workflow divergence
    discrepancy (5 fields) is mandatory. Governance Alert inline discrepancy is mandatory.
    3c-config.md miscounting discrepancy (19 vs 18) is mandatory.

18. Write §16 Reconstruction Checklist. Source: this spec §4 §16. Minimum 20 assertions.
    Verify every count matches §2 Application Meta. Use corrected counts: 53 fields,
    11 reports, 18 named + 1 inline template, 5 named picklists, 17 H3 workflow blocks,
    8 CRUD matrix rows, 5 required fields, 12 action_1 values, 2 CC templates.

19. **Self-verify pass**: Check every assertion in §5 (A1-A20) against the written BRD:
    - Count form subsections in §6 (expect 6).
    - Count field rows per form in §6 (expect 53 total, check per-form breakdown).
    - Count lookup arrows in §6 vs §5 rows (expect 5 matches).
    - Count §7 H3 headings (expect 5).
    - Count §7 status values (expect 9).
    - Count §7 action_1 values (expect 12).
    - Count §8 rows (expect 11; 1 pivot, 1 kanban).
    - Count §9.2 matrix rows (expect 8).
    - Count §11 H3 headings (expect 17).
    - Count §12 rows (expect 4).
    - Count §13 named rows (expect 18) + inline row (expect 1).
    - Verify `compliance_config` does NOT appear in §4, §5, or §6.
    - Verify widget count = 0 everywhere.
    - Verify Developer appears in §9.1 as internal role.
    - Verify ESG fields NOT in §6.3 or §6.5.
    For any failed assertion: fix in place, then re-check.

20. Record final line count. Target: 700-900 lines. If under 600 lines, a section is likely
    under-specified. If over 1000 lines, check for prose bloat in §11 Effect paragraphs
    (trim to ≤80 words each).

---

## 7. Open Issues

All issues raised in the Phase 5 writer escalations and the Phase 5 critic rebuttal have been
resolved. No open issues remain.
