# Building a Verifiable Knowledge Base: Using HRC to Measure AI-Generated Code Against Ground Truth

**Holger Gevers**
*April 2026*

---

## 1. The Problem

AI can generate Zoho Creator applications — forms, fields, Blueprint state machines, transitions — that look structurally correct. The .ds exports parse without errors. The Blueprint diagrams are coherent. The field types make sense.

But the apps don't work.

They are hollow. The Blueprint transitions have empty before/after hooks. There are no validation scripts. No audit trails. No notification logic. No error handling. No compliance checks. The AI produced the skeleton of an application but none of the substance.

The question is: **how do you systematically measure what's missing, and how do you know what "complete" looks like?**

---

## 2. The Approach: Knowledge as Ground Truth

We built a knowledge base from canonical sources — Zoho's official documentation — and used it as the formal definition of "correct." Every pattern, function, API call, and best practice documented by Zoho becomes an axiom in the system.

The knowledge base is not a search index. It is a **weighted relational graph** where every piece of information has identity, provenance, classification, and connections to related knowledge. It is built to be projected onto artifacts (applications) so that the gap between "what is" and "what should be" becomes measurable.

This gap is what the Hologram-Reality Clause (HRC) calls the **residual**. A residual of zero means the artifact is fully grounded to the knowledge base. A positive residual means something is missing — and the framework tells you exactly what.

---

## 3. Constructing the Knowledge Base

### 3.1 Scraping: Capturing the Source of Truth

We scraped 440 documentation pages from 9 Zoho modules:

| Module | Pages | Content |
|--------|-------|---------|
| deluge-functions | 214 | Built-in function reference (text, number, date, list, map, etc.) |
| deluge-integrations | 80 | CRM, Mail, Creator, Books integration tasks |
| deluge-core | 36 | Data types, control flow, criteria, variables |
| deluge-web | 35 | invokeUrl, connections, API calls |
| deluge-data-access | 21 | Record fetching, iteration, field access |
| deluge-encryption | 21 | AES encode/decode, hashing |
| creator-api | 12 | REST API v2.1 (add, get, update, delete records) |
| deluge-notifications | 9 | sendmail, SMS, push notifications |
| catalyst-cli | 3 | Data store import/export operations |

Each page was stored as markdown with YAML frontmatter preserving the source URL, scrape timestamp, ETag, and parent page for provenance. A manifest tracks what was fetched and when, enabling incremental re-scraping.

### 3.2 Tokenisation: Decomposing Knowledge into Atomic Units

Raw markdown pages are not useful for verification. A 2,000-word documentation page about `invokeUrl` contains the function signature, parameter descriptions, usage examples, edge case warnings, related function links, and boilerplate navigation — all mixed together.

We decomposed each page into **atomic knowledge tokens** — the smallest unit of coherent information. Each token is:

- **Classified** by content type: PROSE, CODE_EXAMPLE, SIGNATURE, TABLE_ROW, NOTE, IMPORTANT
- **Identified** by a deterministic SHA-256 hash of (content, page_url, paragraph_number)
- **Positioned** by module, page, section, and paragraph number (preserving reading order)
- **Indexed** for full-text search via SQLite FTS5

This produced **12,173 tokens** stored in a SQLite database.

| Content Type | Count | Purpose |
|-------------|-------|---------|
| PROSE | 7,865 | Explanatory text, parameter descriptions |
| TABLE_ROW | 2,289 | Structured data (API parameters, field types) |
| CODE_EXAMPLE | 1,624 | Working Deluge code samples |
| NOTE | 394 | Warnings, caveats, edge cases |
| IMPORTANT | 1 | Critical requirement (e.g., "never hardcode region URLs") |

### 3.3 Graph Construction: Encoding Relationships

Tokens in isolation are a search engine. Tokens with relationships are a knowledge graph. We inferred **20,053 weighted directed edges** between tokens:

| Edge Type | Count | Weight | Semantic Meaning |
|-----------|-------|--------|-----------------|
| HIERARCHY | 9,017 | 1.0 | Section anchor token → child tokens in the same section |
| NEXT_SIBLING | 9,017 | 0.3 | Adjacent tokens in reading order within a section |
| EXAMPLE_OF | 1,267 | 0.6 | Code example → the prose concept it illustrates |
| CALLOUT_NOTE | 311 | 0.5 | Warning/note → the content it annotates |
| CROSS_MODULE | 251 | 0.9 | Link between modules (e.g., core → functions) |
| CROSS_REFERENCE | 189 | 0.7 | In-text hyperlink to another page in the same module |
| CALLOUT_IMPORTANT | 1 | 0.8 | Critical warning → annotated content |

These edges serve two purposes:

1. **Retrieval**: When a query finds a token via full-text search, the edges allow expansion to related tokens — the code example that illustrates the concept, the warning that qualifies it, the next paragraph that continues the explanation. This transforms keyword hits into coherent context.

2. **Verification**: The edges encode what "structurally sound knowledge" looks like. An orphan token (no HIERARCHY edge) is a structural violation. A broken CROSS_REFERENCE is a referential violation. These are the projections that validate the knowledge base itself.

### 3.4 Self-Validation: The Knowledge Base Must Be Truth

Before projecting the knowledge base onto anything else, we validated it against itself using four projections:

- **pi_structure**: Every token must be connected to the hierarchy. Found 2,119 orphan tokens (boilerplate headers, navigation fragments — structurally harmless).
- **pi_reference**: Every cross-reference must point to a valid token. Found 0 broken references.
- **pi_completeness**: Every Deluge function in the language database must appear in at least one knowledge token. Found 0 shadow fields — complete coverage.
- **pi_consistency**: Function signatures must not contradict each other. Found 0 inconsistencies.

The HRC formal analysis confirmed: **hrc_consistent = true, hrc_violation_count = 0**.

The knowledge base is internally consistent. It qualifies as ground truth.

---

## 4. Ingesting Applications

### 4.1 The .ds Export Format

Zoho Creator exports applications as `.ds` files — a hierarchical text-based DSL containing forms, fields, Blueprint state machines (stages and transitions), workflow scripts, scheduled tasks, and approval processes.

We built a parser that extracts:
- **Form schemas**: field link names, display names, types, metadata
- **Blueprint definitions**: stages (states) and transitions (edges in the state machine)
- **Deluge scripts**: embedded code from workflows, scheduled tasks, and approval handlers

### 4.2 From App Structure to Knowledge Tokens

Each parsed application is tokenised into the same knowledge graph, using a module name like `app:Expense_Claim_Approval`. The tokens include:

- An **overview token** summarising the app (forms, blueprints, scripts)
- **Form schema tokens** with field tables
- **Blueprint tokens** with stage lists, transition tables, and Mermaid state diagrams
- **Script tokens** with metadata and the actual Deluge code

Graph edges are created within the app (HIERARCHY from overview to forms/blueprints/scripts, NEXT_SIBLING between related tokens, EXAMPLE_OF linking script metadata to code), and **across modules** (CROSS_MODULE edges from app code to documentation tokens when the code references documented functions).

### 4.3 The Six Applications

We ingested six applications:

| Application | Forms | Fields | Blueprints | Transitions | Scripts | Origin |
|------------|-------|--------|------------|-------------|---------|--------|
| Expense Claim Approval | 5 | 44 | 2 | 25 | 0 | AI-generated |
| Purchase Order Processing | 6 | 120 | 2 | 35 | 0 | AI-generated |
| Invoice Overdue Management | 5 | 74 | 2 | 34 | 0 | AI-generated |
| Incident Report Synchronization | 4 | 64 | 2 | 25 | 0 | AI-generated |
| Ten Chargeback Management | 10 | 72 | 0 | 0 | 0 | AI-generated |
| **Expense Reimbursement Mgmt** | **6** | **57** | **0** | **0** | **14** | **Human-refined** |

Five applications were generated by AI. They have correct structure — well-named forms, appropriate field types, complete Blueprint state machines with meaningful transitions. They look right.

One application — Expense Reimbursement Management — was refined by a human. It has fewer forms, fewer fields, no Blueprints, but **14 Deluge scripts** implementing validation, audit trails, notifications, approval routing, self-approval prevention, SLA enforcement, and SARS/POPIA compliance checks.

---

## 5. Projecting the Knowledge Base onto Applications

### 5.1 The Six Projections

We defined six projections that compare an application against what the knowledge base says should exist:

| Projection | What It Checks | Severity |
|-----------|---------------|----------|
| pi_form_validation | Every form with user input needs an on_validate script | CRITICAL (2.0) |
| pi_transition_logic | Every Blueprint transition needs before/after logic | CRITICAL–MEDIUM (1.0–2.0) |
| pi_audit_trail | State changes must create audit history records | CRITICAL–HIGH (1.5–2.0) |
| pi_notification | State changes must trigger notifications | MEDIUM–HIGH (1.0–1.5) |
| pi_error_handling | Scripts must guard nulls and handle edge cases | MEDIUM (1.0) |
| pi_compliance | Financial apps need SARS substantiation, King IV self-approval prevention, POPIA consent, duplicate detection | HIGH–LOW (0.5–1.5) |

### 5.2 The Results

| Application | Scripts | Gaps | R(app) | Assessment |
|------------|---------|------|--------|------------|
| **Expense Reimbursement (human)** | **14** | **5** | **7.5** | **Mostly grounded** |
| Expense Claim Approval (AI) | 0 | 36 | 55.0 | Hollow scaffold |
| Incident Report Sync (AI) | 0 | 37 | 44.0 | Hollow scaffold |
| Purchase Order Processing (AI) | 0 | 48 | 71.5 | Hollow scaffold |
| Invoice Overdue Management (AI) | 0 | 45 | 68.0 | Hollow scaffold |
| Chargeback Management (AI) | 0 | 17 | 22.0 | Hollow scaffold |

### 5.3 What the Residuals Mean

**The AI-generated apps (R = 22–71.5)** have high residuals because they are structurally complete but operationally empty. Every Blueprint transition is a state change with no logic. Every form accepts input with no validation. No audit trail exists. No notifications fire. The AI produced the architecture of an application but none of the behaviour.

The gaps are dominated by:
- **pi_transition_logic**: 20–35 empty transitions per app, each representing an unguarded state change
- **pi_form_validation**: 4–6 forms per app with no server-side validation
- **pi_compliance**: Missing SARS substantiation, self-approval prevention, duplicate detection
- **pi_audit_trail**: Zero audit logging across all state changes

**The human-refined app (R = 7.5)** has a low residual because the human wrote the scripts that the AI omitted. Its 5 remaining gaps are real and specific:
- 2 lookup forms (`clients`, `departments`) missing validation — these are reference tables where validation is less critical but still a gap
- 1 validation script that changes status without an audit trail record
- 1 scheduled task that fetches records without a null guard
- 1 validation script that changes status without sending a notification

These are genuine, actionable findings — not theoretical concerns.

### 5.4 The Hologram

The difference between R = 7.5 and R = 71.5 is the **hologram** — the gap between what the AI produced and what the knowledge base says a complete application looks like. In HRC terms:

- The knowledge base is the **reality** (what is documented as correct)
- Each application is a **projection** (a subset of patterns actually implemented)
- The hologram is what's **missing** — visible only when you project reality onto the artifact
- The residual **measures** the hologram: R = 0 means no gap, R > 0 means something is missing
- Each gap **localises** the problem: which entity, which projection, what severity, what the KB says should be there

The AI's projections look correct from one angle (structure) but are empty from every other angle (behaviour, compliance, safety). HRC's multi-perspective design catches this — a single-perspective check would pass these apps.

---

## 6. The Principle

The system we built embodies one principle:

**If you can formalise what "correct" means, you can measure how far anything is from correct.**

The knowledge base is the formalisation. The token graph is the structure. The edges are the relationships. The projections are the questions. The residual is the answer.

This is not specific to code. It is not specific to Zoho Creator. It applies to any domain where:

1. A canonical source of truth exists (documentation, regulations, standards, guidelines)
2. Artifacts are produced that should conform to that truth (applications, policies, treatments, financial statements)
3. Conformance can be checked from multiple perspectives (structure, behaviour, compliance, safety)

The HRC theorem guarantees that this measurement is:
- **Sound**: R > 0 means a real gap exists (no false alarms from the framework itself)
- **Localised**: each gap identifies the exact entity and perspective (O(1) diagnostic per error)
- **Anti-hallucinatory**: the closed-world assumption prevents the system from inventing problems that don't exist
- **Monotonic**: adding more perspectives can only reveal more gaps, never hide existing ones

The only assumption is that the knowledge base is truth. That assumption is not hidden — it is the first thing validated.

---

## 7. What This Demonstrates

We took 440 pages of documentation, decomposed them into 12,173 tokens connected by 20,053 edges, validated the graph's internal consistency, ingested 6 real applications, and in under a second computed a single number for each that tells you how complete it is.

The AI-generated apps scored 22–71.5. The human-refined app scored 7.5. The numbers match intuition — but they are not intuition. They are formal measurements derived from a validated knowledge base via defined projections with guaranteed properties.

This is what the Hologram-Reality Clause was built for.
