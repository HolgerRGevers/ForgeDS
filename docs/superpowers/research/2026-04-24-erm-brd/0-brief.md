# Forgeplan brief — ERM BRD for Zoho Zia

## Goal
Produce a single, maximum-density Business Requirements Document (Markdown, `.md`) that fits Zoho Zia's 1-document upload limit and packs 100% of the ERM Creator app's schema so Zia's app-builder can reconstruct the app with full fidelity.

## Target output
Final BRD file path (Phase 7 will write this):
`C:\Users\User\OneDrive\Documents\GitHub\Expense_Reimbursement_Manager\docs\brd\zia-brd-2026-04-24.md`

## Audience
Primary: Zoho Zia's app-builder LLM ingestor.
Secondary: a human reviewer who wants to spot-check fidelity.

## Hard constraints
1. Single Markdown file, GFM tables only (no HTML, no images).
2. No Deluge code — workflows described as behavior (trigger / effect / fields / emails / APIs).
3. No proprietary scrubbing required (repo is a mock; character names and seed data are fine).
4. Every form, every field, every lookup, every report, every picklist value, every role, every workflow, every custom API, every email template must be represented — lossless.

## Success criteria (these are how Phase 6 simulation scores the design)
1. Every form is reconstructible: link_name, label, type, required, unique, default, picklist/formula/lookup/subform target, notes.
2. Every lookup/subform edge is reconstructible.
3. Every report: source form, filter expression, visible columns, visibility.
4. Every role's CRUD across all forms is unambiguous.
5. Every Deluge workflow has (trigger, form, event, plain-English effect, fields read/written, Custom APIs invoked, emails sent). No code.
6. Every Custom API: name, params with types, return shape, permissions.
7. Every email template: trigger, recipients, subject, variables.

## Design direction (locked in Phase 2)
**Direction A** — standard BRD shell with a "Application Overview" meta-header up top, a tabular data-dictionary body, and numbered business-rule entries. Density tactics:
- One-row-per-field in wide tables.
- Compact types (`lookup→users`, `pick[a,b,c]`, `currency(ZAR)`, `formula: <expr>`).
- `—` for empty cells to preserve grid.
- Picklist Appendix at the end (dedup picklist values; reference by name inline).
- GFM tables everywhere, compact cells.

## Research inputs (these are ALREADY written; read them in full)
- `c:\Users\User\OneDrive\Documents\Claude\Projects\VS_Clones\ForgeDS\docs\superpowers\research\2026-04-24-erm-brd\3a-ds-schema.md` (221 lines — 6 forms, 54 fields, 10 reports, 5 lookups)
- `c:\Users\User\OneDrive\Documents\Claude\Projects\VS_Clones\ForgeDS\docs\superpowers\research\2026-04-24-erm-brd\3b-deluge.md` (544 lines — 13 workflows)
- `c:\Users\User\OneDrive\Documents\Claude\Projects\VS_Clones\ForgeDS\docs\superpowers\research\2026-04-24-erm-brd\3c-config.md` (210 lines — 4 Custom APIs, 7 roles, 19 email templates, 54 field descriptions)
- `c:\Users\User\OneDrive\Documents\Claude\Projects\VS_Clones\ForgeDS\docs\superpowers\research\2026-04-24-erm-brd\3d-context.md` (49 lines — business context)

## Facts the BRD must surface (distilled from research)
- App name: "Expense Reimbursement Management" (v1.0, ZAR currency, Africa/Johannesburg TZ)
- 6 forms: approval_history, approval_thresholds, clients, departments, expense_claims, gl_accounts
- 10 reports (1 is a pivot/summary)
- 5 lookups (expense_claims is the hub: → departments, clients, gl_accounts, and self-ref via Parent_Claim_ID; approval_history → expense_claims)
- 7 roles with CRUD matrix
- 19 email templates
- 4 custom APIs
- 0 widgets
- 13 Deluge workflows: 6 approval (LM / HOD / Finance Director tiers, with Key-2 dual-approval), 7 form hooks (validation, auto-populate, routing, shadow denorm, ref generation, resubmission), 1 daily SLA enforcer

## What bisim is measuring
Two architects will independently produce a BRD layout blueprint. We'll compare structural choices (section order, table shapes, workflow encoding, how roles × forms are matrixed). Disagreements will be reconciled in Phase 5.
