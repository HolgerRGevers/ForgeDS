# ERM Business Context Ingest

## Business purpose
Zoho Creator application automating the expense claim lifecycle for South African organizations with built-in governance controls (2-tier approval, SLA enforcement, comprehensive audit trail) aligned to King IV, SARS, POPIA, and ESG reporting frameworks. Digitizes the journey from employee submission through manager and department-head approval to final reimbursement with full compliance traceability.

## User base

| Persona | Typical Action |
|---------|---|
| **Employee** | Submit expense claim with receipt, business purpose, GL code; resubmit if rejected |
| **Line Manager** | Approve/reject claims up to R999.99; receive SLA escalation after 3 days |
| **Head of Department** | Approve/reject claims exceeding R999.99; oversee manager performance |
| **Finance/Compliance Officer** | Configure approval thresholds, org-type controls, ESG tracking; audit approval trail |

## Key business rules
- **Approval thresholds**: Two-tier routing — Line Manager approves up to R999.99; Head of Department approves above that threshold
- **Self-approval prevention**: Users in Line Manager role skip their own tier if eligible; ensures segregation of duties (King IV P1)
- **SLA enforcement**: Claims pending Line Manager action auto-escalate to Head of Department after 3 days; daily scheduled task; system actor attribution
- **Eligible expense categories**: Travel (local/long-distance), Accommodation, Meals & Entertainment, Office Supplies, Communication, Client Entertainment; each mapped to GL codes
- **Receipt requirements**: SARS S11(a) mandatory; VAT invoice type enforced for claims ≥ R5,000
- **Duplicate detection**: COSO internal-control framework; claims flagged if same employee, amount, GL code within configurable window
- **Anti-bribery classification**: High-risk GL accounts (Meals, Client Entertainment) tagged with ISO 37001 Risk_Level for enhanced scrutiny
- **Resubmission versioning**: Rejected claims can be edited and resubmitted; version counter increments; full history retained

## Compliance & audit requirements
ERM enforces compliance as a first-class architectural constraint, not an afterthought. Every state transition (submit, approve, reject, escalate, resubmit) is logged in Approval_History with actor, timestamp, and comments. Organizations configure org-type (Private, JSE-listed, SOE, Multinational) to enable/disable conditional standards (JSE Listings Requirements, B-BBEE Act, PFMA/MFMA).

**Audit trail controls:**
- Every claim state change recorded in Approval_History with `Added_User = zoho.loginuser`
- Approval_History form is view-only (no Edit/Delete/Duplicate) to prevent post-facto tampering
- Claim reference auto-generated for audit cross-reference
- Retention_Expiry_Date auto-calculated (submission + 5 years) per SARS S29

**Data protection & disclosure:**
- POPIA_Consent mandatory checkbox at submission
- Compliance_Config stores org-type, ESG_REPORTING, carbon-tracking flags for auditor verification
- ESG metadata (ESG_Category, Estimated_Carbon_KG, Carbon_Factor) populated on approval for ISSB S1/S2 sustainability disclosure
- Export pipeline supports GRI 305 (Scope 3 emissions) reporting via carbon-weighted GL accounts

## Non-functional expectations
- **Uptime**: Zoho Creator Free Trial tier (targeting Standard plan) — no explicit SLA stated in source documents
- **Approval turnaround**: 3-day SLA before auto-escalation to HoD
- **Data integrity**: Validation on submission; duplicate detection; GL code validation
- **Audit readiness**: Complete traceability for ISSA 5000 sustainability assurance engagements
- **Configuration flexibility**: Approval thresholds, ESG categories, carbon factors, and compliance flags configurable per organization type without code changes
- **Accessibility**: UI standards require help text on all user-facing fields; view-only menus on audit reports

## Out of scope (if stated anywhere)
(Not stated in source documents.)
