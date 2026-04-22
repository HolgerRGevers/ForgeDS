# ForgeDS Dashboard, Wizard & Brainstorming Engine

**Date:** 2026-04-22
**Status:** Approved
**Scope:** Restructure the ForgeDS SPA's entry experience around a Zoho‑Creator‑style dashboard, a Claude‑Design‑style prototype wizard with a four‑tier brainstorming engine, and silent background repo provisioning.

## Problem

The current SPA drops authenticated users straight onto `PromptPage` (`/`). That page mixes three jobs into one screen: prompt input, plan/code mode toggling, and project history. There is no notion of "an app" — just prompts. New users have no anchor; returning users have to re-find their projects via prompt history alone. Database/API tabs are visible but meaningless until something has been built.

Compounding this, the prompt flow does not adapt to how much planning the user wants. A throwaway scaffold and a governance-critical app go through the same single-shot refinement. A lesson from Zia: when a user pushes data at the system, the data's inferred rules and the user's framing (audience, pressure point) both go missing — the build proceeds on data alone and produces something the user did not ask for.

## Decision

**Approach 3 (Hybrid).** Add `/dashboard` and `/new/*` routes with new components and a route‑aware `AppShell`. Reuse `PromptInput` (renamed `IdeaInput`), `BuildProgress`, `CodePreview`, `RepoSelector`, `ProjectHistory`, and the existing IDE/Database/API pages without modification. Evolve `promptStore` into `wizardStore` (state machine for wizard steps); add `dashboardStore` (repo discovery + activity feed + pinned list).

### Why

- The new entry flow has three distinct surfaces (Dashboard, Wizard, IDE) that do not share UI conventions; collapsing them into one page (Approach 1) would create a thousand‑line component.
- The existing components for build progress, code preview, repo selection, and the IDE itself are working and stable; rewriting them (Approach 2) burns time without product gain.
- One store rename (`promptStore` → `wizardStore`) is a single migration point; the existing localStorage is project history only and is easy to convert into a "Local prompts" group on the new dashboard, sunset after 30 days.

## Design summary

| # | Decision | Choice |
|---|---|---|
| 1 | Dashboard discovery | Hybrid: `forgeds.yaml` auto‑surface + manual pin |
| 2 | Tier mechanics | Light = 3 paired A/B; Mid = 1‑2 free‑text seeds + 3‑5 paired; Heavy = paired + parallel‑agent fanout; Dev = Heavy + persona round‑table |
| 3 | Mid shape | Hybrid (free‑text then paired) |
| 4 | Tier 4 label | "Dev" |
| 5 | Top nav | Hidden on Dashboard & Wizard, visible only in IDE |
| 6 | Scratch path | ForgeDS auto‑creates GitHub repo eagerly |
| 7 | Constructive opener | Hybrid (canned shell + AI gist) |
| 8 | Build flow | Silent background commit, eager repo provisioning, auto‑redirect to IDE |
| 9 | Question screen | Side‑by‑side (responsive stack on narrow) |
| 10 | Dashboard layout | 320px rail (wizard top, repo‑grouped activity bottom) + card grid main |

The Plan/Code mode toggle is removed — the depth picker (Light / Mid / Heavy / Dev) is the new planning intensity dial. Brainstorming is implicit in every wizard run; the tier controls how much.

## Architecture

### Routing & shell behaviour

| URL | Renders | Header chrome |
|---|---|---|
| `/` | redirect → `/dashboard` | n/a |
| `/dashboard` | `DashboardPage` | minimal: BrandMark + UserMenu |
| `/new/idea` | `IdeaPage` | minimal + "× Cancel" |
| `/new/depth` | `DepthPickerPage` | minimal + "× Cancel" |
| `/new/q/:n` | `QuestionPage` (n ∈ 1..N) | minimal + "× Cancel" |
| `/new/building` | `BuildingPage` | minimal (no cancel — build in flight) |
| `/ide` | `IdePage` (unchanged) | full: BrandMark + Prompt/IDE/Database/API tabs + BridgePill + UserMenu |
| `/database`, `/api`, `/login`, `/privacy` | unchanged | as today |

`AppShell` reads `useLocation()` and switches between three header variants: minimal (Dashboard), minimal + Cancel (Wizard), full (IDE / Database / API). The "Prompt" tab in the full nav now means "go back to the idea/wizard for this app", reachable only from inside the IDE. From the dashboard, the path forward is the rail's "+ New Prototype" — not a tab.

Browser back/forward inside `/new/*` works naturally because each step is its own route. `wizardStore` holds answers; the URL holds the step.

### State stores

Existing `authStore`, `repoStore`, `ideStore`, `toastStore`, `bridgeStore` are unchanged.

**`wizardStore`** (renamed and expanded from `promptStore`)

```ts
type WizardStep = "idea" | "depth" | "questions" | "building";
type WizardDepth = "light" | "mid" | "heavy" | "dev";
type EntryTab = "prototype" | "from-data";

interface PairedQuestion {
  kind: "paired";
  id: string;
  stem: string;
  context: string;
  optionA: { title: string; reason: string; consequence: string };
  optionB: { title: string; reason: string; consequence: string };
  aiPreference: "A" | "B";
}

interface FreeTextQuestion {
  kind: "free-text";
  id: string;
  stem: string;
  context: string;
  placeholder: string;
}

type WizardQuestion = PairedQuestion | FreeTextQuestion;

interface DataAnalysis {
  entities: Array<{
    name: string;
    sourceFile: string;
    fields: Array<{ name: string; type: string; sample: string[]; nullable: boolean }>;
    inferredRules: string[];
    relationships: Array<{ kind: "FK" | "lookup"; toEntity: string; viaField: string }>;
  }>;
  observedConstraints: string[];
  gaps: string[];
}

interface WizardState {
  // entry params (from dashboard rail)
  entryTab: EntryTab;
  projectName: string;
  targetMode: "create-new" | "use-existing";
  targetRepoFullName: string | null;
  attachments: File[];

  // step state
  step: WizardStep;
  depth: WizardDepth | null;

  // pg2: idea
  coreIdea: string;
  midSeedAnswers: string[];

  // pg3: opener
  opener: { gist: string; shell: string } | null;

  // pg4: questions
  questions: WizardQuestion[];
  currentQuestionIdx: number;
  answers: Record<string, "A" | "B" | string>;  // string when free-text

  // pg5: building
  buildMessages: BuildMessage[];
  generatedFiles: GeneratedFile[];
  fanoutDrafts: Array<{ agent: string; spec: string; rationale: string }>;
  personaCritiques: Array<{ persona: string; notes: string }>;

  // From Data sidecar
  dataAnalysis: DataAnalysis | null;
  dataIngestionStatus: "idle" | "parsing" | "analyzing" | "ready" | "failed";

  // background work
  repoCreationStatus: "idle" | "pending" | "ready" | "failed";
  repoCreationError: string | null;
  createdRepoFullName: string | null;

  // actions
  setEntryParams(p: Partial<Pick<WizardState, "entryTab" | "projectName" | "targetMode" | "targetRepoFullName" | "attachments">>): void;
  setStep(s: WizardStep): void;
  setDepth(d: WizardDepth): void;
  setCoreIdea(s: string): void;
  recordAnswer(qid: string, value: "A" | "B" | string): void;
  appendQuestions(qs: WizardQuestion[]): void;
  reset(): void;
}
```

Persisted to localStorage under `forgeds-wizard-v1`.

**`dashboardStore`** (new)

```ts
interface DashboardApp {
  fullName: string;          // "user/repo"
  displayName: string;       // from forgeds.yaml or repo name
  badge: string;             // 3-char auto-derived initials
  badgeColor: string;        // deterministic hash → palette
  source: "manifest" | "pinned";
  lastUpdated: string;       // ISO
  hasManifest: boolean;
}

interface RepoActivity {
  repoFullName: string;
  events: Array<{
    kind: "push" | "pr-merged" | "pr-opened" | "release" | "ci-failed" | "scaffold";
    summary: string;
    occurredAt: string;
  }>;
}

interface DashboardState {
  apps: DashboardApp[];
  activity: RepoActivity[];
  pinnedRepos: string[];     // persisted to localStorage
  loading: boolean;
  lastFetchedAt: number | null;
  refresh(): Promise<void>;
  pinRepo(fullName: string): Promise<void>;
  unpinRepo(fullName: string): Promise<void>;
}
```

`pinnedRepos` persists to `forgeds-pinned-repos`. Apps and activity cached in memory with a 5‑minute TTL.

### Dashboard

```
DashboardPage
├── RailWizard                    (top half of left rail, 320px)
│   ├── EntryTabs                 (Prototype | From Data)
│   ├── ProjectNameInput
│   ├── TargetRepoSelector        (radio: create-new vs use-existing)
│   └── ContinueButton            → navigates to /new/idea
└── RepoActivityFeed              (bottom half, scrollable)
    └── RepoActivityGroup × N
        ├── RepoHeading           (color dot + repo name)
        └── RepoEvent × N

DashboardMain                     (right column)
├── DashboardHeader               ("My Apps" + "All Apps ▾")
└── AppCardGrid                   (3-col responsive grid)
    ├── AppCard × N               (badge + name + meta)
    └── PinRepoCard               (dashed-border tile, opens PinRepoModal)
```

**Discovery sequence on `DashboardPage` mount:**

1. `dashboardStore.refresh()` — returns cached if `Date.now() - lastFetchedAt < 5min`.
2. `GET /user/repos?per_page=100&sort=updated` paginated up to 5 pages (500-repo cap).
3. For each repo, `HEAD /repos/:owner/:repo/contents/forgeds.yaml` — 200 = manifest app, 404 = skip. Parallel batches of 10.
4. Union with `pinnedRepos` (manifest takes precedence on dedupe).
5. For each surfaced app, `GET /repos/:owner/:repo/events?per_page=5` in parallel.
6. Sort apps by `lastUpdated` desc.

A user with 500 repos costs ~511 calls per refresh — well under the 5000/hr authenticated GitHub rate limit. The 5‑minute TTL keeps frequency sane.

**Pin flow:** `+ Pin a repo` tile → `PinRepoModal` (reuses `RepoSelector`) → user picks → `pinRepo(fullName)` writes to `pinnedRepos`, fetches events for that one repo, prepends to apps array. No full refresh.

**Click an app card** → set `repoStore.selectedRepo` → `navigate("/ide?repo=<fullName>")`.

**Click Continue on `RailWizard`** → validates name + target → if `create-new`, fires the eager `createRepo` call (non‑blocking), stores promise in `wizardStore.repoCreationStatus = "pending"` → navigates to `/new/idea`.

### Wizard pages

**Page 2: `/new/idea`** (`IdeaPage`)

Single textarea ("Describe your core idea — what does this app do, and for whom?"). Drag‑drop attachment zone shown only when `entryTab === "from-data"`. Submit stores `coreIdea`, navigates to `/new/depth`. If background `repoCreationStatus === "failed"`, surfaces a toast with retry button.

For the **From Data** tab, the prompt copy is *"We've parsed your data. Now tell us what pain point this app should solve and who uses it."* The textarea is still required — never let the data substitute for the user's framing. A collapsible "What we found in your data" panel below shows entity count, column count, flagged gaps from `dataAnalysis`.

**Page 3: `/new/depth`** (`DepthPickerPage`)

On mount, calls `services/brainstorming.ts → generateOpener(coreIdea, dataAnalysis?)`. Returns `{ gist }`. Shell template:

```
"Nice — {gist}. How deep do you want to go on this?"
```

For From Data, the gist references both idea and data (e.g. *"a travel‑expense app on top of your existing 1,200‑row claim history"*).

Renders four depth cards with one‑line descriptions and time estimates:

- **Light** — "3 quick A/B picks · ~2 min"
- **Mid** — "1‑2 short answers + paired picks · ~5 min"
- **Heavy** — "thorough Q&A + parallel‑agent synthesis · ~10 min"
- **Dev** — "everything in Heavy + persona round‑table critique · ~15 min"

Selecting → stores `depth`, navigates to `/new/q/1`.

**Page 4: `/new/q/:n`** (`QuestionPage`)

On mount, ensures `wizardStore.questions[n‑1]` exists. If not, calls `generateQuestionBatch()`:

- **Mid + n === 1**: returns `FreeTextQuestion` (1 question if `coreIdea` is detailed, 2 if terse). `QuestionPage` branches on `question.kind` to render either a paired card layout or a single textarea.
- **Otherwise**: one Claude call passing `coreIdea + midSeedAnswers + answers so far + depth + dataAnalysis` and asks for the next batch (Light = 3 upfront, Mid = 5 after seeds, Heavy = 8 initial then top‑up, Dev = same as Heavy).

Question generator response shape (JSON mode enforced):

```ts
type QuestionBatchResponse = {
  questions: WizardQuestion[];
  done: boolean;  // signals "no more questions, ready to build"
};
```

Side‑by‑side `PairedQuestion` layout on desktop, stacked on narrow viewports (responsive CSS). Per‑option Reason and Consequence blocks. "Skip — let AI decide" picks the AI's `aiPreference`. "← Back" navigates to previous question; answers preserved in the store rehydrate the prior page.

On answer click → `recordAnswer(qid, value)` → if `n < total && !done`, navigate to `/new/q/(n+1)`; else navigate to `/new/building`.

**Page 5: `/new/building`** (`BuildingPage`)

On mount, dispatches the build sequence based on depth:

- **Light / Mid:** single `buildProject({ coreIdea, depth, midSeedAnswers, questions, answers, dataAnalysis })`. Streams build messages into `wizardStore.buildMessages`.
- **Heavy:** `multi-agent.ts → fanoutSpec()` first (3 parallel Claude calls). Synthesis call merges drafts. Then `buildProject()` against synthesised spec.
- **Dev:** Heavy's two stages, then `personaRoundTable()` — sequential calls playing End User, Compliance Officer, Technical Architect, Skeptical CFO. Final synthesis pass merges critiques into v2 spec. Then `buildProject()`.

Generated files committed via `repoStore.batchUploadToBranch()` to `forgeds/<timestamp>` on the target repo. Commit happens silently — no UI for "committing now"; the build log just streams.

When `buildProject()` resolves: write to `ideStore.loadGeneratedFiles()`, then `navigate("/ide")` immediately. Toast posts in IDE: *"Build complete · {n} files committed to forgeds/2026‑04‑22 · View log"* (toast click reopens build log inline).

If `wizardStore.repoCreationStatus === "pending"` when `BuildingPage` reaches its first commit, `await`s the in‑flight `createRepo` promise. Only place repo readiness blocks the user.

### Services

**`services/brainstorming.ts`** — wraps the existing Claude API proxy.

```ts
async function generateOpener(coreIdea: string, dataAnalysis?: DataAnalysis | null): Promise<{ gist: string }>;

async function generateQuestionBatch(params: {
  coreIdea: string;
  depth: WizardDepth;
  midSeedAnswers: string[];
  priorQuestions: WizardQuestion[];
  priorAnswers: Record<string, "A" | "B" | string>;
  dataAnalysis?: DataAnalysis | null;
}): Promise<QuestionBatchResponse>;
```

Replaces the old `claude-api.ts → refinePrompt()`. The old `RefinedSection` shape is deleted.

**`services/multi-agent.ts`** — backs Heavy and Dev tiers.

```ts
async function fanoutSpec(params: {
  coreIdea: string;
  depth: WizardDepth;
  midSeedAnswers?: string[];
  questions: PairedQuestion[];
  answers: Record<string, "A" | "B" | string>;
  dataAnalysis?: DataAnalysis | null;
  agentCount?: number;            // default 3
  onProgress?: (msg: { agent: string; phase: "started" | "done"; preview?: string }) => void;
}): Promise<{
  drafts: Array<{ agent: string; spec: string; rationale: string }>;
  synthesised: string;
  divergences: string[];
}>;

async function personaRoundTable(params: {
  spec: string;
  personas?: string[];            // default ["End User", "Compliance Officer", "Technical Architect", "Skeptical CFO"]
  onProgress?: (msg: { persona: string; phase: "started" | "done"; critique?: string }) => void;
}): Promise<{
  critiques: Array<{ persona: string; notes: string }>;
  revisedSpec: string;
}>;

async function callAgent(role: string, prompt: string, opts?: { temperature?: number }): Promise<string>;
```

`fanoutSpec` runs `Promise.all` of three `callAgent()` invocations at `temperature: 0.9`, each with a different perspective system prompt (simplicity / governance / end‑user friction). Synthesis call at `temperature: 0.3` favours points of agreement, flags divergences.

`personaRoundTable` runs sequentially (`for…of`) — each persona reads previous critiques. Final synthesis merges into a revised spec.

Both accept `onProgress` callbacks so `BuildingPage` shows agent/persona progress in the existing `BuildProgress` log. No new UI component needed.

**`services/github-repos.ts`** — eager repo provisioning.

```ts
async function createRepo(params: {
  name: string;                   // sanitised from projectName
  description: string;            // first 80 chars of coreIdea
  private: boolean;               // default true
  autoInit: boolean;              // default true
}): Promise<{ fullName: string; htmlUrl: string; defaultBranch: string }>;

async function checkScopes(): Promise<{ hasRepoScope: boolean; missing: string[] }>;
async function dropManifest(repoFullName: string, projectMeta: ProjectMeta): Promise<void>;
```

**Repo name sanitisation:** lowercase, replace spaces and special chars with hyphens, strip leading/trailing hyphens, dedupe consecutive hyphens, max 100 chars. Collision → append `-2`, `-3`, etc., capped at 5 tries.

**Scope handling:** `checkScopes()` runs once on dashboard mount, cached. `RailWizard`'s "Create new repo" radio is disabled with tooltip if `hasRepoScope === false`; "Re‑authenticate to enable" link triggers fresh OAuth flow. "Use existing repo" stays enabled.

**Manifest drop:** after first build's commit lands, `dropManifest()` writes `forgeds.yaml` to main branch:

```yaml
project:
  name: <displayName>
  created_via: forgeds-wizard
  created_at: <ISO>
  depth_used: <light|mid|heavy|dev>
data_source:
  kind: <prototype|from-data>
  attachments: [<filenames>]
```

This makes the new repo auto‑surface on the dashboard next time.

**`services/data-ingestion.ts`** — From Data sidecar.

Triggered when `entryTab === "from-data"` and Continue is clicked. Runs in parallel with route navigation.

1. Parse attachments client‑side:
   - `.csv` → header + 50 sample rows + per‑column type inference (number/date/text/picklist‑if‑low‑cardinality)
   - `.zip` → unpack, recurse into CSVs
   - `.accdb` → cannot parse in‑browser; flag as "needs server export to CSV", surfaced as lint error on `IdeaPage`
   - `.ds` → JS port of `parse_ds_export.py` (or use existing `web/src/lib/ds-parser.ts` from the prior IDE design)
   - `.json` schema → treat as schema definition directly
2. Single Claude analysis call returns `DataAnalysis` shape.
3. Result stored in `wizardStore.dataAnalysis`. `dataIngestionStatus` tracks lifecycle.

`dataAnalysis.inferredRules` and `observedConstraints` are appended to the build spec — generator treats them as preconditions, not comments.

## Migration & deletions

- **`promptStore` → `wizardStore` rename.** localStorage key changes from `forgeds-project-history` to `forgeds-wizard-v1`. On first load after deploy, migration reads old key, converts entries into "Local prompts" group at bottom of activity feed, deletes old key. Group disappears after 30 days.
- **No backend migration.** All state changes are client‑side. Claude API proxy and bridge service unchanged.
- **Pinned repos** — net‑new, empty list on first load.

**Deletions**

| File | Replaced by |
|---|---|
| `pages/PromptPage.tsx` | `DashboardPage` + four wizard pages |
| `components/ModeToggle.tsx` | depth picker (Plan/Code mode gone) |
| `components/PromptInput.tsx` | renamed `IdeaInput.tsx`, mode‑toggle prop removed |
| `components/RefinedPrompt.tsx` | deleted entirely (no compat retention) |
| `services/claude-api.ts → refinePrompt()` | `services/brainstorming.ts` |

**Components retained without changes:** `BuildProgress`, `CodePreview`, `RepoSelector`, `RepoFilePicker`, `ProjectHistory` (relocated under activity feed during migration sunset window), `ToastContainer`, all of `components/ide/*`, all of `components/database/*`, all of `components/api/*`. Same with `repoStore`, `ideStore`, `authStore`, `toastStore`, `bridgeStore`.

## Failure modes

- **Repo creation fails** (rate limit, name collision after 5 retries, scope revoked mid‑session) → `wizardStore.repoCreationStatus = "failed"`, error banner on `IdeaPage` with retry/edit‑name button. User can fall back to "Use existing repo".
- **Fanout agent fails** (one of three drafts errors) → if ≥2 succeed, synthesis proceeds; if <2, retry once with `agentCount=2`, surface failure only on total failure.
- **Round‑table fails mid‑sequence** → keep critiques collected so far, abort round‑table, fall back to plain Heavy synthesis. Warning toast in IDE: *"Dev mode partial — round‑table critique skipped"*.
- **Data ingestion fails** (corrupt zip, unsupported format) → inline error in attachment zone, "Continue without data" option appears (degrades to Prototype tab behaviour).
- **GitHub `repo` scope missing** → "Create new repo" radio disabled with re‑auth link.

## Manual test plan

The repo currently has no JS test runner configured. This spec adds one Vitest unit test (the question‑generator response parser — the only piece where a malformed Claude response would silently break the wizard). Everything else is exercised via this checklist before merge:

1. New user, no repos with manifest → dashboard shows empty state, Pin a repo works.
2. Existing user with `forgeds.yaml` in 2 repos → both surface, click‑through to IDE works.
3. Prototype tab, "Create new repo", Light depth, build → repo appears in user's GitHub, dashboard refresh surfaces it, IDE loads with files.
4. Prototype tab, "Use existing repo", Mid depth → existing repo gets `forgeds/<timestamp>` branch with new files.
5. From Data tab, .csv attachment, Heavy depth → data analysis runs, opener gist references it, questions reference data‑specific columns, build incorporates inferred rules.
6. Dev depth path → fanout messages stream in build log, persona round‑table messages stream, build completes.
7. OAuth scope missing for `repo` → "Create new repo" radio disabled, re‑auth prompt works.
8. Mid‑wizard browser back/forward → answers preserved, store rehydrates.
9. Background repo creation fails → IdeaPage banner shown, retry works.
10. One fanout agent fails (simulated by killing one parallel call) → build still completes, divergence note absent.

The existing `tools/lint_deluge.py` already runs against `src/deluge/`. After build, the IDE can optionally run it (already supported via the bridge). No new lint tool added.

## Implementation note

Implementation will be driven via the `superpowers:subagent-driven-development` skill — the spec decomposes into independent tasks (route scaffolding, wizardStore rename, dashboard discovery, brainstorming service, multi-agent service, github-repos service, data-ingestion sidecar, page components) that can be subagent‑dispatched in parallel where they share no state.
