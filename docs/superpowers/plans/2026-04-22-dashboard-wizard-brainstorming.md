# Dashboard, Wizard & Brainstorming Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the ForgeDS SPA's entry experience around a Zoho-Creator-style dashboard, a Claude-Design-style prototype wizard with a four-tier brainstorming engine (Light / Mid / Heavy / Dev), and silent background GitHub repo provisioning. Implements [docs/superpowers/specs/2026-04-22-dashboard-wizard-brainstorming-design.md](../specs/2026-04-22-dashboard-wizard-brainstorming-design.md).

**Architecture:** Approach 3 (Hybrid). Add `/dashboard` and `/new/*` routes; route-aware `AppShell`; rename `promptStore` → `wizardStore` with expanded state machine; add `dashboardStore` for repo discovery and activity. Reuse `BuildProgress`, `CodePreview`, `RepoSelector`, `ProjectHistory`, all of `components/ide/*`, `components/database/*`, `components/api/*` without changes. Heavy/Dev tiers add `services/multi-agent.ts`; From Data tab adds `services/data-ingestion.ts`. Eager repo creation reuses `repoStore.createNewRepo` (already exists).

**Tech Stack:** React 19, react-router-dom 6, Zustand 5, TypeScript 5.7, Vite 6, Tailwind 3.4, jszip (already a dep), GitHub REST API, existing Cloudflare Worker Claude API proxy. Vitest added in Phase 0 for the one parser unit test.

---

## File structure

### New files (all under `web/src/`)

| Path | Responsibility |
|---|---|
| `types/wizard.ts` | `WizardStep`, `WizardDepth`, `EntryTab`, `PairedQuestion`, `FreeTextQuestion`, `WizardQuestion`, `DataAnalysis`, related shapes |
| `types/dashboard.ts` | `DashboardApp`, `RepoActivity`, `RepoEvent` |
| `lib/badge-utils.ts` | `deriveBadgeInitials(name)`, `hashToBadgeColor(name)` |
| `lib/sanitize-repo-name.ts` | `sanitizeRepoName(input)`, collision-resolving variant |
| `stores/wizardStore.ts` | Renamed from `promptStore.ts`; expanded state machine for wizard steps |
| `stores/dashboardStore.ts` | Repo discovery + activity feed + pinned list cache |
| `services/brainstorming.ts` | `generateOpener()`, `generateQuestionBatch()`; replaces old `refinePrompt` |
| `services/multi-agent.ts` | `fanoutSpec()`, `personaRoundTable()`, `callAgent()` for Heavy/Dev |
| `services/github-repos.ts` | `checkScopes()`, `dropManifest()`; eager-create wrapper around existing `repoStore.createNewRepo` |
| `services/data-ingestion.ts` | CSV / zip / .ds / .json parsers + Claude analysis call → `DataAnalysis` |
| `services/__tests__/brainstorming.parser.test.ts` | One Vitest unit test for `QuestionBatchResponse` parser |
| `services/__tests__/badge-utils.test.ts` | Unit tests for `deriveBadgeInitials` + `hashToBadgeColor` |
| `services/__tests__/sanitize-repo-name.test.ts` | Unit tests for repo name sanitization |
| `pages/DashboardPage.tsx` | New default landing route at `/dashboard` |
| `pages/IdeaPage.tsx` | Wizard step 2 (`/new/idea`) |
| `pages/DepthPickerPage.tsx` | Wizard step 3 (`/new/depth`) |
| `pages/QuestionPage.tsx` | Wizard step 4 (`/new/q/:n`) |
| `pages/BuildingPage.tsx` | Wizard step 5 (`/new/building`) |
| `components/dashboard/RailWizard.tsx` | Top half of dashboard rail |
| `components/dashboard/EntryTabs.tsx` | "Prototype \| From Data" tab switcher |
| `components/dashboard/RepoActivityFeed.tsx` | Bottom half of dashboard rail |
| `components/dashboard/RepoActivityGroup.tsx` | One repo group with heading + events |
| `components/dashboard/AppCardGrid.tsx` | Right column of dashboard |
| `components/dashboard/AppCard.tsx` | Single app tile |
| `components/dashboard/PinRepoCard.tsx` | Dashed-border "+ Pin a repo" tile |
| `components/dashboard/PinRepoModal.tsx` | Modal wrapping `RepoSelector` for pin flow |
| `components/wizard/WizardLayout.tsx` | Chromeless route layout for `/new/*` |
| `components/wizard/DepthPicker.tsx` | Four depth-tier cards |
| `components/wizard/ConstructiveOpener.tsx` | Renders `{shell + gist}` |
| `components/wizard/PairedQuestion.tsx` | Side-by-side A/B question card |
| `components/wizard/FreeTextQuestion.tsx` | Free-text seed question (Mid only) |
| `components/wizard/DataAnalysisPanel.tsx` | Collapsible "What we found in your data" panel |
| `components/IdeaInput.tsx` | Renamed from `PromptInput.tsx`, mode toggle removed |

### Modified files

| Path | Change |
|---|---|
| `web/src/App.tsx` | New route map (see Task 1.2) |
| `web/src/components/AppShell.tsx` | Route-aware header (see Task 1.3) |
| `web/src/services/claude-api.ts` | Remove `refinePrompt` export and `RefineRequest`/`RefineResponse`/`RefinedSectionRaw` types |
| `web/src/services/index.ts` | Re-exports updated to drop `refinePrompt`, add new services |
| `web/src/stores/index.ts` | Replace `promptStore` export with `wizardStore`; add `dashboardStore` |
| `web/src/components/index.ts` | Drop `PromptInput`, `ModeToggle`, `RefinedPrompt`; add `IdeaInput` |
| `web/src/types/index.ts` | Drop `prompt.ts` re-exports; add `wizard.ts`, `dashboard.ts` |
| `web/package.json` | Add `vitest`, `@vitest/ui`, `jsdom` to devDependencies; add `test` script |
| `web/vite.config.ts` (or new `web/vitest.config.ts`) | Add Vitest config |

### Deleted files

| Path | Reason |
|---|---|
| `web/src/pages/PromptPage.tsx` | Replaced by `DashboardPage` + four wizard pages |
| `web/src/components/ModeToggle.tsx` | Plan/Code mode is gone |
| `web/src/components/PromptInput.tsx` | Renamed to `IdeaInput.tsx` |
| `web/src/components/RefinedPrompt.tsx` | No longer used |
| `web/src/stores/promptStore.ts` | Renamed to `wizardStore.ts` |
| `web/src/types/prompt.ts` | Superseded by `wizard.ts` |

---

## Phase 0 — Test infrastructure

### Task 0.1: Add Vitest to the web package

**Files:**
- Modify: `web/package.json`
- Create: `web/vitest.config.ts`

- [ ] **Step 1: Add dev dependencies**

```bash
cd web && npm install --save-dev vitest@^2 @vitest/ui@^2 jsdom@^25
```

- [ ] **Step 2: Add `test` script to `web/package.json`**

In `scripts`, add:
```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 3: Create `web/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/__tests__/**/*.test.ts"],
  },
});
```

- [ ] **Step 4: Verify Vitest runs (no tests yet)**

Run: `cd web && npm test`
Expected: "No test files found, exiting with code 0" or similar — must exit 0.

- [ ] **Step 5: Commit**

```bash
git add web/package.json web/package-lock.json web/vitest.config.ts
git commit -m "build(web): add vitest for unit tests"
```

---

## Phase 1 — Routing, shell, types

### Task 1.1: Define wizard and dashboard types

**Files:**
- Create: `web/src/types/wizard.ts`
- Create: `web/src/types/dashboard.ts`
- Modify: `web/src/types/index.ts`

- [ ] **Step 1: Write `web/src/types/wizard.ts`**

```ts
export type WizardStep = "idea" | "depth" | "questions" | "building";
export type WizardDepth = "light" | "mid" | "heavy" | "dev";
export type EntryTab = "prototype" | "from-data";

export interface PairedQuestion {
  kind: "paired";
  id: string;
  stem: string;
  context: string;
  optionA: { title: string; reason: string; consequence: string };
  optionB: { title: string; reason: string; consequence: string };
  aiPreference: "A" | "B";
}

export interface FreeTextQuestion {
  kind: "free-text";
  id: string;
  stem: string;
  context: string;
  placeholder: string;
}

export type WizardQuestion = PairedQuestion | FreeTextQuestion;

export interface QuestionBatchResponse {
  questions: WizardQuestion[];
  done: boolean;
}

export interface DataAnalysis {
  entities: Array<{
    name: string;
    sourceFile: string;
    fields: Array<{
      name: string;
      type: string;
      sample: string[];
      nullable: boolean;
    }>;
    inferredRules: string[];
    relationships: Array<{
      kind: "FK" | "lookup";
      toEntity: string;
      viaField: string;
    }>;
  }>;
  observedConstraints: string[];
  gaps: string[];
}

export interface BuildMessage {
  timestamp: string;
  text: string;
  type: "info" | "success" | "error" | "warning";
}

export interface GeneratedFile {
  name: string;
  path: string;
  content: string;
  language: string;
}
```

- [ ] **Step 2: Write `web/src/types/dashboard.ts`**

```ts
export interface RepoEvent {
  kind: "push" | "pr-merged" | "pr-opened" | "release" | "ci-failed" | "scaffold";
  summary: string;
  occurredAt: string;
}

export interface RepoActivity {
  repoFullName: string;
  events: RepoEvent[];
}

export interface DashboardApp {
  fullName: string;
  displayName: string;
  badge: string;
  badgeColor: string;
  source: "manifest" | "pinned";
  lastUpdated: string;
  hasManifest: boolean;
}
```

- [ ] **Step 3: Update `web/src/types/index.ts`**

Remove the line re-exporting from `./prompt`; add:
```ts
export * from "./wizard";
export * from "./dashboard";
```

- [ ] **Step 4: Verify tsc compiles**

Run: `cd web && npx tsc -b --noEmit`
Expected: 0 errors. (You may see errors in files that still import from `./prompt` — those are fixed in later tasks. Capture the error list and proceed.)

- [ ] **Step 5: Commit**

```bash
git add web/src/types/wizard.ts web/src/types/dashboard.ts web/src/types/index.ts
git commit -m "feat(web): add wizard and dashboard type definitions"
```

### Task 1.2: New route map in App.tsx

**Files:**
- Modify: `web/src/App.tsx`

- [ ] **Step 1: Replace App.tsx route definitions**

Read the existing file first. Then replace the routes block with:

```tsx
import { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { AuthGuard } from "./components/AuthGuard";
import { useBridgeStore } from "./stores/bridgeStore";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import IdeaPage from "./pages/IdeaPage";
import DepthPickerPage from "./pages/DepthPickerPage";
import QuestionPage from "./pages/QuestionPage";
import BuildingPage from "./pages/BuildingPage";
import IdePage from "./pages/IdePage";
import DatabasePage from "./pages/DatabasePage";
import ApiPage from "./pages/ApiPage";
import PrivacyPage from "./pages/PrivacyPage";
import { ToastContainer } from "./components/ToastContainer";

function App() {
  const connect = useBridgeStore((s) => s.connect);

  useEffect(() => {
    connect();
  }, [connect]);

  return (
    <>
      <ToastContainer />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route
          path="/*"
          element={
            <AuthGuard>
              <AppShell>
                <Routes>
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/new/idea" element={<IdeaPage />} />
                  <Route path="/new/depth" element={<DepthPickerPage />} />
                  <Route path="/new/q/:n" element={<QuestionPage />} />
                  <Route path="/new/building" element={<BuildingPage />} />
                  <Route path="/ide" element={<IdePage />} />
                  <Route path="/database" element={<DatabasePage />} />
                  <Route path="/api" element={<ApiPage />} />
                </Routes>
              </AppShell>
            </AuthGuard>
          }
        />
      </Routes>
    </>
  );
}

export default App;
```

- [ ] **Step 2: Verify tsc errors are now only "Cannot find module './pages/DashboardPage'" etc.**

Run: `cd web && npx tsc -b --noEmit`
Expected: errors only for the new page imports — those are stub‑created in Task 1.4.

- [ ] **Step 3: Commit**

```bash
git add web/src/App.tsx
git commit -m "feat(web): wire dashboard and wizard routes"
```

### Task 1.3: Make AppShell route-aware

**Files:**
- Modify: `web/src/components/AppShell.tsx`

- [ ] **Step 1: Replace AppShell with three header variants**

```tsx
import type { ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { BridgePill } from "./ConnectionStatus";
import { UserMenu } from "./UserMenu";
import { BrandMark } from "./BrandMark";

interface AppShellProps {
  children: ReactNode;
}

const navItems = [
  { to: "/ide", label: "Prompt", phase: 1 },
  { to: "/ide", label: "IDE", phase: 2 },
  { to: "/database", label: "Database", phase: 3 },
  { to: "/api", label: "API", phase: 4 },
];

type HeaderVariant = "minimal" | "wizard" | "full";

function variantFor(pathname: string): HeaderVariant {
  if (pathname.startsWith("/new/")) return "wizard";
  if (pathname.startsWith("/dashboard")) return "minimal";
  return "full";
}

export function AppShell({ children }: AppShellProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const variant = variantFor(location.pathname);

  return (
    <div className="flex h-screen flex-col bg-gray-950 text-gray-100">
      <header className="flex items-center justify-between bg-gray-800 px-4 py-2 shadow-md">
        <NavLink to="/dashboard" className="flex items-center gap-2">
          <BrandMark size={24} />
          <span className="text-lg font-medium tracking-tight">
            <span className="text-gray-100">Forge</span>
            <span className="text-[#c2662d]">DS</span>
          </span>
        </NavLink>

        {variant === "full" && (
          <nav className="flex items-center gap-1">
            {navItems.map((item) => (
              <NavLink
                key={`${item.to}-${item.label}`}
                to={item.to}
                className={({ isActive }) =>
                  `rounded px-3 py-1.5 text-sm font-medium transition-colors ${
                    isActive
                      ? "text-white underline underline-offset-4 decoration-blue-400 decoration-2"
                      : item.phase > 1
                        ? "text-gray-500 hover:text-gray-300"
                        : "text-gray-300 hover:text-white"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        )}

        <div className="flex items-center gap-3">
          {variant === "wizard" && (
            <button
              type="button"
              onClick={() => {
                if (confirm("Cancel this prototype? Your answers will be lost.")) {
                  navigate("/dashboard");
                }
              }}
              className="text-xs text-gray-400 hover:text-white"
            >
              × Cancel
            </button>
          )}
          {variant === "full" && <BridgePill />}
          <UserMenu />
        </div>
      </header>

      <main className="flex-1 overflow-hidden">{children}</main>

      <footer className="flex items-center justify-center border-t border-gray-800 bg-gray-900 px-4 py-1.5">
        <NavLink
          to="/privacy"
          className="text-[10px] text-gray-600 transition-colors hover:text-gray-400"
        >
          Privacy Policy
        </NavLink>
      </footer>
    </div>
  );
}
```

- [ ] **Step 2: Verify tsc**

Run: `cd web && npx tsc -b --noEmit`
Expected: same errors as before (missing page modules) but no new ones.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/AppShell.tsx
git commit -m "feat(web): make AppShell route-aware (minimal/wizard/full)"
```

### Task 1.4: Stub the new pages so the app compiles

**Files:**
- Create: `web/src/pages/DashboardPage.tsx`
- Create: `web/src/pages/IdeaPage.tsx`
- Create: `web/src/pages/DepthPickerPage.tsx`
- Create: `web/src/pages/QuestionPage.tsx`
- Create: `web/src/pages/BuildingPage.tsx`

- [ ] **Step 1: Write each as a stub**

For each new page file, write:

```tsx
// DashboardPage.tsx
export default function DashboardPage() {
  return <div className="p-6 text-gray-300">Dashboard (stub)</div>;
}
```

Repeat with appropriate names: `IdeaPage`, `DepthPickerPage`, `QuestionPage`, `BuildingPage`.

- [ ] **Step 2: Verify the app builds**

Run: `cd web && npx tsc -b --noEmit && npx vite build`
Expected: 0 errors, build succeeds. (The PromptPage is still around and still works at this point — we haven't removed it yet because routes were rewritten in 1.2.)

Note: if `App.tsx` no longer imports `PromptPage`, that file becomes dead code. We delete it in Task 9.1.

- [ ] **Step 3: Run dev server and verify navigation**

Run: `cd web && npm run dev`
Open: `http://localhost:5173/`
Expected: redirects to `/dashboard`, shows "Dashboard (stub)" with minimal header. Manually navigate to `/new/idea`, `/new/depth`, `/new/q/1`, `/new/building`, `/ide` — confirm header switches between minimal, wizard (with × Cancel), and full.

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/DashboardPage.tsx web/src/pages/IdeaPage.tsx web/src/pages/DepthPickerPage.tsx web/src/pages/QuestionPage.tsx web/src/pages/BuildingPage.tsx
git commit -m "feat(web): scaffold dashboard and wizard page stubs"
```

---

## Phase 2 — Stores

### Task 2.1: Create wizardStore (renamed from promptStore)

**Files:**
- Create: `web/src/stores/wizardStore.ts`
- Modify: `web/src/stores/index.ts`

- [ ] **Step 1: Write `web/src/stores/wizardStore.ts`**

```ts
import { create } from "zustand";
import type {
  WizardStep,
  WizardDepth,
  EntryTab,
  WizardQuestion,
  DataAnalysis,
  BuildMessage,
  GeneratedFile,
} from "../types/wizard";

const STORAGE_KEY = "forgeds-wizard-v1";
const LEGACY_HISTORY_KEY = "forgeds-project-history";

interface WizardState {
  // entry
  entryTab: EntryTab;
  projectName: string;
  targetMode: "create-new" | "use-existing";
  targetRepoFullName: string | null;
  attachments: File[];

  // step
  step: WizardStep;
  depth: WizardDepth | null;

  // idea
  coreIdea: string;
  midSeedAnswers: string[];

  // opener
  opener: { gist: string; shell: string } | null;

  // questions
  questions: WizardQuestion[];
  currentQuestionIdx: number;
  answers: Record<string, "A" | "B" | string>;

  // building
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
  repoCreationPromise: Promise<string> | null;

  // actions
  setEntryParams: (
    p: Partial<
      Pick<
        WizardState,
        | "entryTab"
        | "projectName"
        | "targetMode"
        | "targetRepoFullName"
        | "attachments"
      >
    >,
  ) => void;
  setStep: (s: WizardStep) => void;
  setDepth: (d: WizardDepth) => void;
  setCoreIdea: (s: string) => void;
  setMidSeedAnswers: (a: string[]) => void;
  setOpener: (o: { gist: string; shell: string }) => void;
  appendQuestions: (qs: WizardQuestion[]) => void;
  recordAnswer: (qid: string, value: "A" | "B" | string) => void;
  setCurrentQuestionIdx: (i: number) => void;
  addBuildMessage: (msg: BuildMessage) => void;
  setBuildMessages: (msgs: BuildMessage[]) => void;
  setGeneratedFiles: (files: GeneratedFile[]) => void;
  setFanoutDrafts: (d: WizardState["fanoutDrafts"]) => void;
  setPersonaCritiques: (c: WizardState["personaCritiques"]) => void;
  setDataAnalysis: (d: DataAnalysis | null) => void;
  setDataIngestionStatus: (s: WizardState["dataIngestionStatus"]) => void;
  setRepoCreationStatus: (
    s: WizardState["repoCreationStatus"],
    error?: string | null,
  ) => void;
  setRepoCreationPromise: (p: Promise<string> | null) => void;
  setCreatedRepoFullName: (n: string | null) => void;
  reset: () => void;
}

const initialState = {
  entryTab: "prototype" as EntryTab,
  projectName: "",
  targetMode: "create-new" as const,
  targetRepoFullName: null,
  attachments: [],
  step: "idea" as WizardStep,
  depth: null,
  coreIdea: "",
  midSeedAnswers: [],
  opener: null,
  questions: [],
  currentQuestionIdx: 0,
  answers: {},
  buildMessages: [],
  generatedFiles: [],
  fanoutDrafts: [],
  personaCritiques: [],
  dataAnalysis: null,
  dataIngestionStatus: "idle" as const,
  repoCreationStatus: "idle" as const,
  repoCreationError: null,
  createdRepoFullName: null,
  repoCreationPromise: null,
};

function persistedFields(s: WizardState) {
  // Files and Promises do not survive serialization.
  // Persist only string/object/scalar fields the user might want back on refresh.
  return {
    entryTab: s.entryTab,
    projectName: s.projectName,
    targetMode: s.targetMode,
    targetRepoFullName: s.targetRepoFullName,
    step: s.step,
    depth: s.depth,
    coreIdea: s.coreIdea,
    midSeedAnswers: s.midSeedAnswers,
    opener: s.opener,
    questions: s.questions,
    currentQuestionIdx: s.currentQuestionIdx,
    answers: s.answers,
    dataAnalysis: s.dataAnalysis,
  };
}

function loadPersisted(): Partial<WizardState> | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function migrateLegacyHistory() {
  // One-shot: if the old key exists, leave it in place for the dashboard
  // migration sunset (handled by dashboardStore in Task 2.2).
  // We do not delete it here; dashboardStore consumes and clears it after 30 days.
}

export const useWizardStore = create<WizardState>((set, get) => {
  migrateLegacyHistory();
  const persisted = loadPersisted();
  return {
    ...initialState,
    ...(persisted ?? {}),

    setEntryParams: (p) => {
      set(p as Partial<WizardState>);
      persist(get());
    },
    setStep: (step) => {
      set({ step });
      persist(get());
    },
    setDepth: (depth) => {
      set({ depth });
      persist(get());
    },
    setCoreIdea: (coreIdea) => {
      set({ coreIdea });
      persist(get());
    },
    setMidSeedAnswers: (midSeedAnswers) => {
      set({ midSeedAnswers });
      persist(get());
    },
    setOpener: (opener) => {
      set({ opener });
      persist(get());
    },
    appendQuestions: (qs) => {
      set({ questions: [...get().questions, ...qs] });
      persist(get());
    },
    recordAnswer: (qid, value) => {
      set({ answers: { ...get().answers, [qid]: value } });
      persist(get());
    },
    setCurrentQuestionIdx: (i) => {
      set({ currentQuestionIdx: i });
      persist(get());
    },
    addBuildMessage: (msg) => {
      set({ buildMessages: [...get().buildMessages, msg] });
    },
    setBuildMessages: (buildMessages) => set({ buildMessages }),
    setGeneratedFiles: (generatedFiles) => set({ generatedFiles }),
    setFanoutDrafts: (fanoutDrafts) => set({ fanoutDrafts }),
    setPersonaCritiques: (personaCritiques) => set({ personaCritiques }),
    setDataAnalysis: (dataAnalysis) => {
      set({ dataAnalysis });
      persist(get());
    },
    setDataIngestionStatus: (dataIngestionStatus) =>
      set({ dataIngestionStatus }),
    setRepoCreationStatus: (repoCreationStatus, error = null) =>
      set({ repoCreationStatus, repoCreationError: error }),
    setRepoCreationPromise: (repoCreationPromise) =>
      set({ repoCreationPromise }),
    setCreatedRepoFullName: (createdRepoFullName) => {
      set({ createdRepoFullName });
      persist(get());
    },
    reset: () => {
      set(initialState);
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch {
        // ignore
      }
    },
  };

  function persist(state: WizardState) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(persistedFields(state)));
    } catch {
      // ignore quota errors
    }
  }
});

export { LEGACY_HISTORY_KEY };
```

- [ ] **Step 2: Update `web/src/stores/index.ts`**

Read the current file. Replace the `promptStore` re-export with:
```ts
export * from "./wizardStore";
export * from "./dashboardStore";
```
(`dashboardStore` doesn't exist yet — we add it in 2.2; tsc will warn until then.)

- [ ] **Step 3: Verify tsc**

Run: `cd web && npx tsc -b --noEmit`
Expected: errors only for `dashboardStore` (not yet created) and any remaining `usePromptStore` references in `PromptPage.tsx` (still around, but `App.tsx` no longer renders it). The latter we'll fix by deleting `PromptPage.tsx` in Phase 9.

- [ ] **Step 4: Commit**

```bash
git add web/src/stores/wizardStore.ts web/src/stores/index.ts
git commit -m "feat(web): add wizardStore (state machine for prototype wizard)"
```

### Task 2.2: Create dashboardStore

**Files:**
- Create: `web/src/stores/dashboardStore.ts`
- Modify: `web/src/services/github-api.ts` (add three GitHub helpers it needs — see Step 1)

- [ ] **Step 1: Add GitHub helpers in `services/github-api.ts`**

Append (after the existing functions):

```ts
// ── Discovery helpers (used by dashboardStore) ────────────────────────────

export async function listUserRepos(
  token: string,
  pageCap = 5,
): Promise<Array<{
  full_name: string;
  name: string;
  description: string | null;
  updated_at: string;
  private: boolean;
}>> {
  const all: Array<{
    full_name: string;
    name: string;
    description: string | null;
    updated_at: string;
    private: boolean;
  }> = [];
  for (let page = 1; page <= pageCap; page++) {
    const res = await fetch(
      `${API}/user/repos?per_page=100&sort=updated&page=${page}`,
      { headers: headers(token) },
    );
    updateRateLimits(res);
    if (!res.ok) await throwForResponse(res);
    const batch = await res.json();
    if (!Array.isArray(batch) || batch.length === 0) break;
    all.push(...batch);
    if (batch.length < 100) break;
  }
  return all;
}

export async function hasManifest(
  token: string,
  fullName: string,
): Promise<boolean> {
  const [owner, repo] = fullName.split("/");
  const res = await fetch(
    `${API}/repos/${owner}/${repo}/contents/forgeds.yaml`,
    { method: "HEAD", headers: headers(token) },
  );
  updateRateLimits(res);
  return res.status === 200;
}

export async function listRepoEvents(
  token: string,
  fullName: string,
  perPage = 5,
): Promise<Array<{
  type: string;
  created_at: string;
  payload: Record<string, unknown>;
}>> {
  const [owner, repo] = fullName.split("/");
  const res = await fetch(
    `${API}/repos/${owner}/${repo}/events?per_page=${perPage}`,
    { headers: headers(token) },
  );
  updateRateLimits(res);
  if (!res.ok) await throwForResponse(res);
  return res.json();
}

async function throwForResponse(res: Response): Promise<never> {
  if (res.status === 401) throw new TokenExpiredError();
  if (res.status === 403 || res.status === 429) {
    const reset = parseInt(res.headers.get("x-ratelimit-reset") ?? "0", 10);
    if (reset) throw new RateLimitError(reset);
  }
  throw new Error(`GitHub API error ${res.status}`);
}
```

(If `throwForResponse` already exists with a different name in the file, reuse it instead of adding a duplicate.)

- [ ] **Step 2: Write `web/src/stores/dashboardStore.ts`**

```ts
import { create } from "zustand";
import type { DashboardApp, RepoActivity, RepoEvent } from "../types/dashboard";
import {
  listUserRepos,
  hasManifest,
  listRepoEvents,
  TokenExpiredError,
} from "../services/github-api";
import { useAuthStore } from "./authStore";
import { deriveBadgeInitials, hashToBadgeColor } from "../lib/badge-utils";

const PINNED_KEY = "forgeds-pinned-repos";
const TTL_MS = 5 * 60 * 1000; // 5 minutes

interface DashboardState {
  apps: DashboardApp[];
  activity: RepoActivity[];
  pinnedRepos: string[];
  loading: boolean;
  error: string | null;
  lastFetchedAt: number | null;

  refresh: (force?: boolean) => Promise<void>;
  pinRepo: (fullName: string) => Promise<void>;
  unpinRepo: (fullName: string) => Promise<void>;
}

function loadPinned(): string[] {
  try {
    const raw = localStorage.getItem(PINNED_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function savePinned(list: string[]) {
  try {
    localStorage.setItem(PINNED_KEY, JSON.stringify(list));
  } catch {
    // ignore
  }
}

function eventKindFromPayload(type: string): RepoEvent["kind"] {
  if (type === "PushEvent") return "push";
  if (type === "PullRequestEvent") return "pr-opened"; // refined below
  if (type === "ReleaseEvent") return "release";
  if (type === "WorkflowRunEvent") return "ci-failed";
  return "scaffold";
}

function summarizeEvent(ev: {
  type: string;
  payload: Record<string, unknown>;
}): string {
  switch (ev.type) {
    case "PushEvent": {
      const ref = (ev.payload.ref as string | undefined) ?? "";
      const branch = ref.replace("refs/heads/", "");
      return `Pushed to ${branch}`;
    }
    case "PullRequestEvent": {
      const action = ev.payload.action as string;
      const num = (ev.payload.number as number) ?? 0;
      if (action === "closed" && (ev.payload.pull_request as Record<string, unknown> | undefined)?.merged) {
        return `PR #${num} merged`;
      }
      return `PR #${num} ${action}`;
    }
    case "ReleaseEvent": {
      const tag = ((ev.payload.release as Record<string, unknown> | undefined)?.tag_name as string | undefined) ?? "release";
      return `${tag} published`;
    }
    case "WorkflowRunEvent": {
      const conclusion = ((ev.payload.workflow_run as Record<string, unknown> | undefined)?.conclusion as string | undefined) ?? "ran";
      return `CI ${conclusion}`;
    }
    default:
      return ev.type;
  }
}

async function pickBatch<T, R>(
  items: T[],
  size: number,
  fn: (item: T) => Promise<R>,
): Promise<R[]> {
  const out: R[] = [];
  for (let i = 0; i < items.length; i += size) {
    const batch = items.slice(i, i + size);
    const results = await Promise.all(batch.map(fn));
    out.push(...results);
  }
  return out;
}

export const useDashboardStore = create<DashboardState>((set, get) => ({
  apps: [],
  activity: [],
  pinnedRepos: loadPinned(),
  loading: false,
  error: null,
  lastFetchedAt: null,

  refresh: async (force = false) => {
    const last = get().lastFetchedAt;
    if (!force && last && Date.now() - last < TTL_MS) return;

    const token = useAuthStore.getState().token;
    if (!token) return;

    set({ loading: true, error: null });
    try {
      const repos = await listUserRepos(token);

      const manifestFlags = await pickBatch(repos, 10, async (r) => ({
        full_name: r.full_name,
        has: await hasManifest(token, r.full_name).catch(() => false),
        repo: r,
      }));

      const pinned = get().pinnedRepos;
      const surfaced = manifestFlags.filter(
        (m) => m.has || pinned.includes(m.full_name),
      );

      const apps: DashboardApp[] = surfaced.map((m) => ({
        fullName: m.full_name,
        displayName: m.repo.name,
        badge: deriveBadgeInitials(m.repo.name),
        badgeColor: hashToBadgeColor(m.full_name),
        source: m.has ? "manifest" : "pinned",
        lastUpdated: m.repo.updated_at,
        hasManifest: m.has,
      }));

      apps.sort((a, b) => b.lastUpdated.localeCompare(a.lastUpdated));

      const activityRaw = await pickBatch(apps, 10, async (a) => ({
        repoFullName: a.fullName,
        events: (await listRepoEvents(token, a.fullName).catch(() => [])).map((ev) => ({
          kind: eventKindFromPayload(ev.type),
          summary: summarizeEvent(ev),
          occurredAt: ev.created_at,
        })),
      }));

      set({
        apps,
        activity: activityRaw,
        loading: false,
        lastFetchedAt: Date.now(),
      });
    } catch (err) {
      if (err instanceof TokenExpiredError) {
        useAuthStore.getState().handleTokenExpired();
      }
      set({
        loading: false,
        error: err instanceof Error ? err.message : "Refresh failed",
      });
    }
  },

  pinRepo: async (fullName) => {
    const list = Array.from(new Set([...get().pinnedRepos, fullName]));
    set({ pinnedRepos: list });
    savePinned(list);
    await get().refresh(true);
  },

  unpinRepo: async (fullName) => {
    const list = get().pinnedRepos.filter((n) => n !== fullName);
    set({ pinnedRepos: list });
    savePinned(list);
    await get().refresh(true);
  },
}));
```

- [ ] **Step 3: Verify tsc**

Run: `cd web && npx tsc -b --noEmit`
Expected: errors only for `lib/badge-utils` (not yet created — Task 2.3) and the still-removed `prompt.ts` references.

- [ ] **Step 4: Commit**

```bash
git add web/src/stores/dashboardStore.ts web/src/services/github-api.ts
git commit -m "feat(web): add dashboardStore + GitHub discovery helpers"
```

### Task 2.3: Badge utilities (TDD)

**Files:**
- Create: `web/src/lib/badge-utils.ts`
- Create: `web/src/services/__tests__/badge-utils.test.ts`

- [ ] **Step 1: Write failing tests**

```ts
// web/src/services/__tests__/badge-utils.test.ts
import { describe, it, expect } from "vitest";
import { deriveBadgeInitials, hashToBadgeColor } from "../../lib/badge-utils";

describe("deriveBadgeInitials", () => {
  it("returns first letters of words for multi-word names", () => {
    expect(deriveBadgeInitials("expense reimbursement manager")).toBe("ERM");
    expect(deriveBadgeInitials("Invoice Overdue")).toBe("INO");
  });
  it("returns first 3 chars of single words", () => {
    expect(deriveBadgeInitials("travel")).toBe("TRA");
  });
  it("handles hyphens and underscores as word separators", () => {
    expect(deriveBadgeInitials("incident-reports")).toBe("INR");
    expect(deriveBadgeInitials("incident_report_sync")).toBe("IRS");
  });
  it("uppercases output", () => {
    expect(deriveBadgeInitials("foo bar")).toBe("FOB");
  });
  it("returns at most 3 chars", () => {
    expect(deriveBadgeInitials("a b c d e")).toBe("ABC");
  });
});

describe("hashToBadgeColor", () => {
  it("returns one of the palette colors", () => {
    const palette = ["#c2662d", "#7c3aed", "#22c55e", "#0ea5e9", "#ec4899", "#f59e0b"];
    expect(palette).toContain(hashToBadgeColor("foo"));
  });
  it("is deterministic for the same input", () => {
    expect(hashToBadgeColor("foo")).toBe(hashToBadgeColor("foo"));
  });
});
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd web && npm test`
Expected: FAIL with "Cannot find module '../../lib/badge-utils'".

- [ ] **Step 3: Write `web/src/lib/badge-utils.ts`**

```ts
const PALETTE = [
  "#c2662d", // ForgeDS orange
  "#7c3aed", // violet
  "#22c55e", // green
  "#0ea5e9", // sky
  "#ec4899", // pink
  "#f59e0b", // amber
];

export function deriveBadgeInitials(name: string): string {
  const words = name
    .split(/[\s\-_]+/)
    .filter((w) => w.length > 0);

  let initials: string;
  if (words.length >= 2) {
    initials = words.slice(0, 3).map((w) => w[0]).join("");
    if (initials.length < 3 && words[0].length >= 2) {
      initials += words[0].slice(1, 1 + (3 - initials.length));
    }
  } else {
    initials = (words[0] ?? "").slice(0, 3);
  }
  return initials.toUpperCase().slice(0, 3);
}

export function hashToBadgeColor(input: string): string {
  let hash = 0;
  for (let i = 0; i < input.length; i++) {
    hash = (hash * 31 + input.charCodeAt(i)) | 0;
  }
  const idx = Math.abs(hash) % PALETTE.length;
  return PALETTE[idx];
}
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd web && npm test`
Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/badge-utils.ts web/src/services/__tests__/badge-utils.test.ts
git commit -m "feat(web): badge initials + deterministic color hash"
```

### Task 2.4: Repo name sanitization (TDD)

**Files:**
- Create: `web/src/lib/sanitize-repo-name.ts`
- Create: `web/src/services/__tests__/sanitize-repo-name.test.ts`

- [ ] **Step 1: Write failing tests**

```ts
// web/src/services/__tests__/sanitize-repo-name.test.ts
import { describe, it, expect } from "vitest";
import { sanitizeRepoName } from "../../lib/sanitize-repo-name";

describe("sanitizeRepoName", () => {
  it("lowercases", () => {
    expect(sanitizeRepoName("Travel Expense")).toBe("travel-expense");
  });
  it("replaces spaces with hyphens", () => {
    expect(sanitizeRepoName("a b c")).toBe("a-b-c");
  });
  it("strips invalid characters", () => {
    expect(sanitizeRepoName("foo!bar@baz.qux")).toBe("foo-bar-baz.qux");
  });
  it("dedupes consecutive hyphens", () => {
    expect(sanitizeRepoName("foo   bar")).toBe("foo-bar");
    expect(sanitizeRepoName("foo!!bar")).toBe("foo-bar");
  });
  it("trims leading/trailing hyphens", () => {
    expect(sanitizeRepoName("-foo-")).toBe("foo");
  });
  it("caps at 100 chars", () => {
    const long = "a".repeat(150);
    expect(sanitizeRepoName(long)).toHaveLength(100);
  });
  it("returns 'untitled' for empty/all-invalid input", () => {
    expect(sanitizeRepoName("")).toBe("untitled");
    expect(sanitizeRepoName("!!!")).toBe("untitled");
  });
});
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd web && npm test sanitize-repo-name`
Expected: FAIL.

- [ ] **Step 3: Write `web/src/lib/sanitize-repo-name.ts`**

```ts
export function sanitizeRepoName(input: string): string {
  let s = input.toLowerCase();
  s = s.replace(/[^a-z0-9._-]+/g, "-");
  s = s.replace(/-+/g, "-");
  s = s.replace(/^-+|-+$/g, "");
  s = s.slice(0, 100);
  return s || "untitled";
}
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `cd web && npm test sanitize-repo-name`
Expected: all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/sanitize-repo-name.ts web/src/services/__tests__/sanitize-repo-name.test.ts
git commit -m "feat(web): repo name sanitization"
```

---

## Phase 3 — Dashboard UI

### Task 3.1: AppCard, PinRepoCard, AppCardGrid

**Files:**
- Create: `web/src/components/dashboard/AppCard.tsx`
- Create: `web/src/components/dashboard/PinRepoCard.tsx`
- Create: `web/src/components/dashboard/AppCardGrid.tsx`

- [ ] **Step 1: Write `AppCard.tsx`**

```tsx
import { useNavigate } from "react-router-dom";
import { useRepoStore } from "../../stores/repoStore";
import type { DashboardApp } from "../../types/dashboard";

interface AppCardProps {
  app: DashboardApp;
}

export function AppCard({ app }: AppCardProps) {
  const navigate = useNavigate();
  const setSelectedRepoByFullName = useRepoStore(
    (s) => s.setSelectedRepoByFullName,
  );

  const onOpen = async () => {
    await setSelectedRepoByFullName(app.fullName);
    navigate("/ide");
  };

  const meta =
    app.source === "manifest"
      ? `forgeds.yaml · ${formatDate(app.lastUpdated)}`
      : `📌 pinned · ${formatDate(app.lastUpdated)}`;

  return (
    <button
      type="button"
      onClick={onOpen}
      className="flex flex-col gap-2 rounded-lg border border-gray-800 bg-gray-900 p-4 text-left transition-colors hover:border-gray-600 hover:bg-gray-800"
    >
      <div
        className="flex h-9 w-9 items-center justify-center rounded-md font-bold text-white"
        style={{ backgroundColor: app.badgeColor }}
      >
        {app.badge}
      </div>
      <div className="text-sm font-semibold text-white">{app.displayName}</div>
      <div className="text-[10px] text-gray-500">{meta}</div>
    </button>
  );
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}
```

- [ ] **Step 2: Add `setSelectedRepoByFullName` to `repoStore` if missing**

Read `web/src/stores/repoStore.ts`. If it does not already export `setSelectedRepoByFullName`, add this method to the store interface and implementation:

```ts
// In the interface:
setSelectedRepoByFullName: (fullName: string) => Promise<void>;

// In the implementation:
setSelectedRepoByFullName: async (fullName) => {
  // Look up in cached repos; if missing, fetch.
  const existing = get().repos.find((r) => r.full_name === fullName);
  if (existing) {
    set({ selectedRepo: existing });
    return;
  }
  const token = useAuthStore.getState().token;
  if (!token) return;
  const [owner, repo] = fullName.split("/");
  const res = await fetch(
    `https://api.github.com/repos/${owner}/${repo}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (res.ok) {
    const r = await res.json();
    set({ selectedRepo: r });
  }
},
```

(Verify property names against the existing `repoStore` shape — adjust `repos`/`selectedRepo` to whatever the actual fields are.)

- [ ] **Step 3: Write `PinRepoCard.tsx`**

```tsx
interface PinRepoCardProps {
  onClick: () => void;
}

export function PinRepoCard({ onClick }: PinRepoCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex min-h-[110px] items-center justify-center rounded-lg border border-dashed border-[#c2662d]/50 bg-[#c2662d]/5 text-sm font-semibold text-[#c2662d] transition-colors hover:border-[#c2662d] hover:bg-[#c2662d]/10"
    >
      + Pin a repo
    </button>
  );
}
```

- [ ] **Step 4: Write `AppCardGrid.tsx`**

```tsx
import { useState } from "react";
import { AppCard } from "./AppCard";
import { PinRepoCard } from "./PinRepoCard";
import { PinRepoModal } from "./PinRepoModal";
import type { DashboardApp } from "../../types/dashboard";

interface AppCardGridProps {
  apps: DashboardApp[];
  loading: boolean;
}

export function AppCardGrid({ apps, loading }: AppCardGridProps) {
  const [pinModalOpen, setPinModalOpen] = useState(false);

  return (
    <>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {loading && apps.length === 0 ? (
          <div className="col-span-full text-sm text-gray-500">Loading apps…</div>
        ) : (
          <>
            {apps.map((app) => (
              <AppCard key={app.fullName} app={app} />
            ))}
            <PinRepoCard onClick={() => setPinModalOpen(true)} />
          </>
        )}
      </div>
      {pinModalOpen && <PinRepoModal onClose={() => setPinModalOpen(false)} />}
    </>
  );
}
```

- [ ] **Step 5: Verify tsc (PinRepoModal not yet created — expected)**

Run: `cd web && npx tsc -b --noEmit`
Expected: error for missing `PinRepoModal` only.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/dashboard/
git commit -m "feat(web): dashboard AppCard / PinRepoCard / AppCardGrid"
```

### Task 3.2: PinRepoModal

**Files:**
- Create: `web/src/components/dashboard/PinRepoModal.tsx`

- [ ] **Step 1: Inspect existing RepoSelector**

Read `web/src/components/RepoSelector.tsx`. Note its props (likely `onSelect: (repo: GhRepo) => void` and `onClose`).

- [ ] **Step 2: Write `PinRepoModal.tsx`**

```tsx
import { RepoSelector } from "../RepoSelector";
import { useDashboardStore } from "../../stores/dashboardStore";

interface PinRepoModalProps {
  onClose: () => void;
}

export function PinRepoModal({ onClose }: PinRepoModalProps) {
  const pinRepo = useDashboardStore((s) => s.pinRepo);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-lg border border-gray-800 bg-gray-900 p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Pin a repository</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-sm text-gray-400 hover:text-white"
          >
            ×
          </button>
        </div>
        <RepoSelector
          onSelect={async (repo) => {
            await pinRepo(repo.full_name);
            onClose();
          }}
        />
      </div>
    </div>
  );
}
```

(If `RepoSelector`'s prop names differ, adjust accordingly.)

- [ ] **Step 3: Verify tsc**

Run: `cd web && npx tsc -b --noEmit`
Expected: 0 new errors. (Some pre-existing errors from earlier phases may still be present.)

- [ ] **Step 4: Commit**

```bash
git add web/src/components/dashboard/PinRepoModal.tsx
git commit -m "feat(web): PinRepoModal wraps RepoSelector for pinning"
```

### Task 3.3: RepoActivityGroup, RepoActivityFeed

**Files:**
- Create: `web/src/components/dashboard/RepoActivityGroup.tsx`
- Create: `web/src/components/dashboard/RepoActivityFeed.tsx`

- [ ] **Step 1: Write `RepoActivityGroup.tsx`**

```tsx
import type { RepoActivity } from "../../types/dashboard";

interface RepoActivityGroupProps {
  activity: RepoActivity;
  color: string;
  shortName: string;
}

export function RepoActivityGroup({
  activity,
  color,
  shortName,
}: RepoActivityGroupProps) {
  return (
    <div className="space-y-1">
      <div
        className="flex items-center gap-2 border-b border-white/5 pb-1 text-xs font-semibold"
        style={{ color }}
      >
        <span
          className="inline-block h-1.5 w-1.5 rounded-sm"
          style={{ backgroundColor: color }}
        />
        {shortName}
      </div>
      {activity.events.length === 0 ? (
        <div className="ml-3 text-[10px] italic text-gray-600">No recent activity</div>
      ) : (
        activity.events.map((ev, i) => (
          <div
            key={`${ev.kind}-${i}`}
            className="ml-1 border-l border-[#c2662d]/20 pl-3 py-1 text-[11px] text-gray-300"
          >
            <div>{ev.summary}</div>
            <div className="text-[9px] text-gray-500">
              {relative(ev.occurredAt)}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function relative(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const min = Math.floor(ms / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}
```

- [ ] **Step 2: Write `RepoActivityFeed.tsx`**

```tsx
import { RepoActivityGroup } from "./RepoActivityGroup";
import type { DashboardApp, RepoActivity } from "../../types/dashboard";

interface RepoActivityFeedProps {
  apps: DashboardApp[];
  activity: RepoActivity[];
}

export function RepoActivityFeed({ apps, activity }: RepoActivityFeedProps) {
  if (apps.length === 0) {
    return (
      <div className="text-xs text-gray-500">
        Activity will appear here once you have apps with <code>forgeds.yaml</code> or pinned repos.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-gray-500">
        Recent activity
      </div>
      {apps.map((app) => {
        const a = activity.find((x) => x.repoFullName === app.fullName);
        return (
          <RepoActivityGroup
            key={app.fullName}
            activity={a ?? { repoFullName: app.fullName, events: [] }}
            color={app.badgeColor}
            shortName={app.displayName}
          />
        );
      })}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/dashboard/RepoActivityGroup.tsx web/src/components/dashboard/RepoActivityFeed.tsx
git commit -m "feat(web): repo activity feed (rail bottom half)"
```

### Task 3.4: EntryTabs and RailWizard

**Files:**
- Create: `web/src/components/dashboard/EntryTabs.tsx`
- Create: `web/src/components/dashboard/RailWizard.tsx`

- [ ] **Step 1: Write `EntryTabs.tsx`**

```tsx
import type { EntryTab } from "../../types/wizard";

interface EntryTabsProps {
  value: EntryTab;
  onChange: (tab: EntryTab) => void;
}

export function EntryTabs({ value, onChange }: EntryTabsProps) {
  const tabs: Array<{ id: EntryTab; label: string }> = [
    { id: "prototype", label: "Prototype" },
    { id: "from-data", label: "From Data" },
  ];
  return (
    <div className="flex gap-1 rounded-md bg-black/30 p-1">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onChange(t.id)}
          className={`flex-1 rounded px-3 py-1.5 text-xs font-semibold transition-colors ${
            value === t.id
              ? "bg-[#c2662d] text-white"
              : "text-gray-400 hover:text-white"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Write `RailWizard.tsx`**

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useWizardStore } from "../../stores/wizardStore";
import { useRepoStore } from "../../stores/repoStore";
import { EntryTabs } from "./EntryTabs";
import type { EntryTab } from "../../types/wizard";

export function RailWizard() {
  const navigate = useNavigate();
  const setEntryParams = useWizardStore((s) => s.setEntryParams);
  const reset = useWizardStore((s) => s.reset);
  const repos = useRepoStore((s) => s.repos);

  const [tab, setTab] = useState<EntryTab>("prototype");
  const [name, setName] = useState("");
  const [target, setTarget] = useState<"create-new" | "use-existing">("create-new");
  const [existingRepo, setExistingRepo] = useState<string>("");

  const onContinue = () => {
    if (!name.trim()) {
      alert("Please give the prototype a name.");
      return;
    }
    if (target === "use-existing" && !existingRepo) {
      alert("Pick an existing repo or switch to 'Create new repo'.");
      return;
    }
    reset(); // Clear any previous wizard state.
    setEntryParams({
      entryTab: tab,
      projectName: name.trim(),
      targetMode: target,
      targetRepoFullName: target === "use-existing" ? existingRepo : null,
      attachments: [],
    });
    navigate("/new/idea");
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="text-sm font-semibold text-white">New prototype</div>
      <EntryTabs value={tab} onChange={setTab} />

      <label className="mt-1 text-[11px] font-semibold text-gray-300">
        Project name
      </label>
      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="e.g. Travel Expense Tracker"
        className="rounded-md border border-white/10 bg-black/40 px-3 py-2 text-xs text-white placeholder-gray-500"
      />

      <label className="mt-1 text-[11px] font-semibold text-gray-300">
        Where should it go?
      </label>
      <div className="flex flex-col gap-1">
        <label
          className={`flex items-center gap-2 rounded-md border px-3 py-2 text-xs cursor-pointer ${
            target === "create-new"
              ? "border-[#c2662d] bg-[#c2662d]/10 text-white"
              : "border-white/10 text-gray-300"
          }`}
        >
          <input
            type="radio"
            name="target"
            checked={target === "create-new"}
            onChange={() => setTarget("create-new")}
            className="accent-[#c2662d]"
          />
          Create new repo
        </label>
        <label
          className={`flex items-center gap-2 rounded-md border px-3 py-2 text-xs cursor-pointer ${
            target === "use-existing"
              ? "border-[#c2662d] bg-[#c2662d]/10 text-white"
              : "border-white/10 text-gray-300"
          }`}
        >
          <input
            type="radio"
            name="target"
            checked={target === "use-existing"}
            onChange={() => setTarget("use-existing")}
            className="accent-[#c2662d]"
          />
          Use an existing repo
        </label>
        {target === "use-existing" && (
          <select
            value={existingRepo}
            onChange={(e) => setExistingRepo(e.target.value)}
            className="mt-1 rounded-md border border-white/10 bg-black/40 px-3 py-2 text-xs text-white"
          >
            <option value="">Select…</option>
            {repos.map((r) => (
              <option key={r.full_name} value={r.full_name}>
                {r.full_name}
              </option>
            ))}
          </select>
        )}
      </div>

      <button
        type="button"
        onClick={onContinue}
        className="mt-2 rounded-md bg-[#c2662d] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[#a8551c]"
      >
        Continue →
      </button>
      <div className="text-center text-[10px] text-gray-500">
        Next: pick depth (Light / Mid / Heavy / Dev)
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/dashboard/EntryTabs.tsx web/src/components/dashboard/RailWizard.tsx
git commit -m "feat(web): RailWizard (always-visible prototype creator)"
```

### Task 3.5: DashboardPage assembly

**Files:**
- Modify: `web/src/pages/DashboardPage.tsx`

- [ ] **Step 1: Replace stub with full DashboardPage**

```tsx
import { useEffect } from "react";
import { useDashboardStore } from "../stores/dashboardStore";
import { useRepoStore } from "../stores/repoStore";
import { RailWizard } from "../components/dashboard/RailWizard";
import { RepoActivityFeed } from "../components/dashboard/RepoActivityFeed";
import { AppCardGrid } from "../components/dashboard/AppCardGrid";

export default function DashboardPage() {
  const apps = useDashboardStore((s) => s.apps);
  const activity = useDashboardStore((s) => s.activity);
  const loading = useDashboardStore((s) => s.loading);
  const refresh = useDashboardStore((s) => s.refresh);
  const fetchRepos = useRepoStore((s) => s.fetchRepos);

  useEffect(() => {
    fetchRepos();
    refresh();
  }, [fetchRepos, refresh]);

  return (
    <div className="flex h-full">
      <aside className="flex w-[320px] flex-col border-r border-gray-800 bg-black/30">
        <div className="flex-1 border-b border-gray-800 p-4">
          <RailWizard />
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <RepoActivityFeed apps={apps} activity={activity} />
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto p-6">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-base font-semibold text-white">My Apps</h1>
          <button
            type="button"
            onClick={() => refresh(true)}
            className="rounded-full bg-white/5 px-3 py-1 text-[11px] text-gray-300 hover:bg-white/10"
          >
            Refresh
          </button>
        </div>
        <AppCardGrid apps={apps} loading={loading} />
      </main>
    </div>
  );
}
```

- [ ] **Step 2: Verify tsc and build**

Run: `cd web && npx tsc -b --noEmit`
Expected: 0 errors related to new files (some pre-existing PromptPage errors may remain).

- [ ] **Step 3: Smoke-test in browser**

Run: `cd web && npm run dev`
Open `http://localhost:5173/`. Confirm:
- Redirects to `/dashboard`.
- Left rail shows the wizard panel and (empty) activity feed.
- Main area shows "Loading apps…" then either the user's manifest repos or the Pin a repo tile only.
- Click "+ Pin a repo" → modal opens, RepoSelector lists repos, picking one closes modal and the repo appears as a card.
- Click a card → navigates to `/ide`.

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/DashboardPage.tsx
git commit -m "feat(web): assemble DashboardPage layout"
```

---

## Phase 4 — Brainstorming service

### Task 4.1: brainstorming.ts service + parser test

**Files:**
- Create: `web/src/services/brainstorming.ts`
- Create: `web/src/services/__tests__/brainstorming.parser.test.ts`

- [ ] **Step 1: Write parser test (failing)**

```ts
// web/src/services/__tests__/brainstorming.parser.test.ts
import { describe, it, expect } from "vitest";
import { parseQuestionBatchResponse } from "../brainstorming";

describe("parseQuestionBatchResponse", () => {
  it("accepts a valid paired-question payload", () => {
    const raw = JSON.stringify({
      questions: [
        {
          kind: "paired",
          id: "q1",
          stem: "Who approves?",
          context: "ctx",
          optionA: { title: "A", reason: "r", consequence: "c" },
          optionB: { title: "B", reason: "r2", consequence: "c2" },
          aiPreference: "A",
        },
      ],
      done: false,
    });
    const out = parseQuestionBatchResponse(raw);
    expect(out.questions).toHaveLength(1);
    expect(out.questions[0].kind).toBe("paired");
    expect(out.done).toBe(false);
  });

  it("accepts a valid free-text-question payload", () => {
    const raw = JSON.stringify({
      questions: [
        { kind: "free-text", id: "q1", stem: "Pain point?", context: "", placeholder: "..." },
      ],
      done: true,
    });
    const out = parseQuestionBatchResponse(raw);
    expect(out.questions[0].kind).toBe("free-text");
    expect(out.done).toBe(true);
  });

  it("throws on missing fields", () => {
    expect(() => parseQuestionBatchResponse("{}")).toThrow();
  });

  it("throws on invalid JSON", () => {
    expect(() => parseQuestionBatchResponse("not json")).toThrow();
  });

  it("throws when paired option lacks required subfields", () => {
    const raw = JSON.stringify({
      questions: [
        { kind: "paired", id: "q1", stem: "?", context: "", optionA: { title: "A" }, optionB: {}, aiPreference: "A" },
      ],
      done: false,
    });
    expect(() => parseQuestionBatchResponse(raw)).toThrow();
  });
});
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd web && npm test brainstorming.parser`
Expected: FAIL.

- [ ] **Step 3: Write `web/src/services/brainstorming.ts`**

```ts
import type {
  QuestionBatchResponse,
  WizardQuestion,
  WizardDepth,
  PairedQuestion,
  FreeTextQuestion,
  DataAnalysis,
} from "../types/wizard";

const CLAUDE_PROXY = import.meta.env.VITE_CLAUDE_API_PROXY ?? "";

export class BrainstormingNotConfiguredError extends Error {
  constructor() {
    super("Claude API proxy is not configured");
    this.name = "BrainstormingNotConfiguredError";
  }
}

function ensureConfigured() {
  if (!CLAUDE_PROXY) throw new BrainstormingNotConfiguredError();
}

export function parseQuestionBatchResponse(raw: string): QuestionBatchResponse {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error("Brainstorming response was not valid JSON");
  }
  if (!parsed || typeof parsed !== "object") {
    throw new Error("Brainstorming response shape invalid");
  }
  const obj = parsed as Record<string, unknown>;
  if (!Array.isArray(obj.questions)) {
    throw new Error("Brainstorming response missing questions array");
  }
  if (typeof obj.done !== "boolean") {
    throw new Error("Brainstorming response missing done flag");
  }
  const questions: WizardQuestion[] = (obj.questions as unknown[]).map((q, i) =>
    parseQuestion(q, i),
  );
  return { questions, done: obj.done };
}

function parseQuestion(q: unknown, idx: number): WizardQuestion {
  if (!q || typeof q !== "object") {
    throw new Error(`Question ${idx} is not an object`);
  }
  const o = q as Record<string, unknown>;
  if (o.kind === "paired") return parsePaired(o, idx);
  if (o.kind === "free-text") return parseFreeText(o, idx);
  throw new Error(`Question ${idx} has unknown kind: ${String(o.kind)}`);
}

function parsePaired(o: Record<string, unknown>, idx: number): PairedQuestion {
  const required = ["id", "stem", "context", "optionA", "optionB", "aiPreference"];
  for (const k of required) {
    if (!(k in o)) throw new Error(`Paired question ${idx} missing ${k}`);
  }
  const a = o.optionA as Record<string, unknown>;
  const b = o.optionB as Record<string, unknown>;
  for (const k of ["title", "reason", "consequence"]) {
    if (typeof a?.[k] !== "string")
      throw new Error(`Paired question ${idx} optionA.${k} invalid`);
    if (typeof b?.[k] !== "string")
      throw new Error(`Paired question ${idx} optionB.${k} invalid`);
  }
  return {
    kind: "paired",
    id: String(o.id),
    stem: String(o.stem),
    context: String(o.context),
    optionA: {
      title: String(a.title),
      reason: String(a.reason),
      consequence: String(a.consequence),
    },
    optionB: {
      title: String(b.title),
      reason: String(b.reason),
      consequence: String(b.consequence),
    },
    aiPreference: o.aiPreference === "B" ? "B" : "A",
  };
}

function parseFreeText(o: Record<string, unknown>, idx: number): FreeTextQuestion {
  for (const k of ["id", "stem", "context", "placeholder"]) {
    if (typeof o[k] !== "string")
      throw new Error(`Free-text question ${idx} ${k} invalid`);
  }
  return {
    kind: "free-text",
    id: String(o.id),
    stem: String(o.stem),
    context: String(o.context),
    placeholder: String(o.placeholder),
  };
}

// ── Public API ────────────────────────────────────────────────────────────

export async function generateOpener(
  token: string,
  coreIdea: string,
  dataAnalysis?: DataAnalysis | null,
): Promise<{ gist: string }> {
  ensureConfigured();
  const res = await fetch(`${CLAUDE_PROXY}/api/brainstorm/opener`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ coreIdea, dataAnalysis }),
  });
  if (!res.ok) throw new Error(`Opener request failed (${res.status})`);
  const json = await res.json();
  return { gist: typeof json.gist === "string" ? json.gist : "" };
}

export async function generateQuestionBatch(params: {
  token: string;
  coreIdea: string;
  depth: WizardDepth;
  midSeedAnswers: string[];
  priorQuestions: WizardQuestion[];
  priorAnswers: Record<string, "A" | "B" | string>;
  dataAnalysis?: DataAnalysis | null;
  needsFreeTextSeed?: boolean;
}): Promise<QuestionBatchResponse> {
  ensureConfigured();
  const { token, ...payload } = params;
  const res = await fetch(`${CLAUDE_PROXY}/api/brainstorm/questions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Question request failed (${res.status})`);
  const text = await res.text();
  return parseQuestionBatchResponse(text);
}
```

> **Note for the implementer:** the proxy endpoints `/api/brainstorm/opener` and `/api/brainstorm/questions` need to be added to the existing Cloudflare Worker. That is a separate worker-repo change scoped to (a) accept the payload above and (b) call Claude with a system prompt that returns the `QuestionBatchResponse` JSON shape. **Out of scope for this plan.** During development, mock these endpoints with a local dev proxy or a vite middleware that returns canned responses matching the parser's contract.

- [ ] **Step 4: Run test, verify it passes**

Run: `cd web && npm test brainstorming.parser`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add web/src/services/brainstorming.ts web/src/services/__tests__/brainstorming.parser.test.ts
git commit -m "feat(web): brainstorming service + JSON response parser"
```

---

## Phase 5 — Wizard pages (Light/Mid path end-to-end)

### Task 5.1: IdeaInput component (rename of PromptInput)

**Files:**
- Create: `web/src/components/IdeaInput.tsx`
- (Delete `web/src/components/PromptInput.tsx` happens in Phase 9)

- [ ] **Step 1: Inspect existing PromptInput**

Read `web/src/components/PromptInput.tsx` to understand its props and structure.

- [ ] **Step 2: Write `IdeaInput.tsx` as a streamlined version**

```tsx
import { useState } from "react";
import type { ChangeEvent, FormEvent } from "react";

interface IdeaInputProps {
  initialValue?: string;
  placeholder?: string;
  acceptAttachments?: boolean;
  onSubmit: (text: string, files: File[]) => void;
  isLoading?: boolean;
}

export function IdeaInput({
  initialValue = "",
  placeholder = "Describe your core idea — what does this app do, and for whom?",
  acceptAttachments = false,
  onSubmit,
  isLoading = false,
}: IdeaInputProps) {
  const [text, setText] = useState(initialValue);
  const [files, setFiles] = useState<File[]>([]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (text.trim().length === 0) return;
    onSubmit(text.trim(), files);
  };

  const handleFiles = (e: ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    setFiles(Array.from(e.target.files));
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex w-full max-w-2xl flex-col gap-3 rounded-lg border border-gray-800 bg-gray-900 p-4"
    >
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={placeholder}
        rows={6}
        className="w-full resize-none rounded-md border border-white/10 bg-black/40 p-3 text-sm text-white placeholder-gray-500"
      />

      {acceptAttachments && (
        <div className="flex items-center gap-3 text-xs text-gray-400">
          <input
            type="file"
            multiple
            onChange={handleFiles}
            accept=".csv,.zip,.accdb,.ds,.json"
            className="text-xs text-gray-300 file:mr-3 file:rounded file:border-0 file:bg-white/10 file:px-3 file:py-1.5 file:text-xs file:text-white"
          />
          {files.length > 0 && <span>{files.length} file(s) attached</span>}
        </div>
      )}

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={isLoading || text.trim().length === 0}
          className="rounded-md bg-[#c2662d] px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-[#a8551c] disabled:cursor-not-allowed disabled:opacity-40"
        >
          {isLoading ? "Submitting…" : "Continue →"}
        </button>
      </div>
    </form>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/IdeaInput.tsx
git commit -m "feat(web): IdeaInput (replaces PromptInput, no mode toggle)"
```

### Task 5.2: IdeaPage

**Files:**
- Modify: `web/src/pages/IdeaPage.tsx`

- [ ] **Step 1: Replace stub**

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useWizardStore } from "../stores/wizardStore";
import { IdeaInput } from "../components/IdeaInput";
import { DataAnalysisPanel } from "../components/wizard/DataAnalysisPanel";

export default function IdeaPage() {
  const navigate = useNavigate();
  const entryTab = useWizardStore((s) => s.entryTab);
  const setCoreIdea = useWizardStore((s) => s.setCoreIdea);
  const setEntryParams = useWizardStore((s) => s.setEntryParams);
  const setStep = useWizardStore((s) => s.setStep);
  const repoCreationStatus = useWizardStore((s) => s.repoCreationStatus);
  const repoCreationError = useWizardStore((s) => s.repoCreationError);
  const dataAnalysis = useWizardStore((s) => s.dataAnalysis);

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setStep("idea");
  }, [setStep]);

  const isFromData = entryTab === "from-data";
  const placeholder = isFromData
    ? "We've parsed your data. Now tell us what pain point this app should solve and who uses it."
    : "Describe your core idea — what does this app do, and for whom?";

  const onSubmit = (text: string, files: File[]) => {
    setError(null);
    setCoreIdea(text);
    if (files.length > 0) {
      setEntryParams({ attachments: files });
    }
    navigate("/new/depth");
  };

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col items-center justify-center gap-6 p-6">
      <h1 className="text-xl font-semibold text-white">
        {isFromData ? "Tell us why" : "What do you want to build?"}
      </h1>

      {repoCreationStatus === "failed" && (
        <div className="w-full max-w-2xl rounded-md border border-red-500/40 bg-red-950/30 px-4 py-3 text-sm text-red-200">
          Background repo creation failed: {repoCreationError ?? "unknown error"}.
          You can edit the project name in the dashboard rail and try again, or switch to "Use existing repo".
        </div>
      )}

      {error && (
        <div className="w-full max-w-2xl rounded-md border border-yellow-500/40 bg-yellow-950/30 px-4 py-3 text-sm text-yellow-200">
          {error}
        </div>
      )}

      <IdeaInput
        placeholder={placeholder}
        acceptAttachments={isFromData}
        onSubmit={onSubmit}
      />

      {isFromData && dataAnalysis && (
        <DataAnalysisPanel analysis={dataAnalysis} />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create stub `DataAnalysisPanel.tsx`**

```tsx
// web/src/components/wizard/DataAnalysisPanel.tsx
import type { DataAnalysis } from "../../types/wizard";

interface DataAnalysisPanelProps {
  analysis: DataAnalysis;
}

export function DataAnalysisPanel({ analysis }: DataAnalysisPanelProps) {
  return (
    <details className="w-full max-w-2xl rounded-md border border-gray-800 bg-gray-900 p-3 text-sm text-gray-300">
      <summary className="cursor-pointer font-semibold text-white">
        What we found in your data ({analysis.entities.length} entities,{" "}
        {analysis.entities.reduce((acc, e) => acc + e.fields.length, 0)} columns)
      </summary>
      <div className="mt-3 space-y-3">
        {analysis.entities.map((e) => (
          <div key={e.name}>
            <div className="font-semibold text-white">{e.name}</div>
            <div className="text-xs text-gray-400">{e.sourceFile}</div>
            <div className="mt-1 text-xs text-gray-300">
              {e.fields.map((f) => f.name).join(", ")}
            </div>
            {e.inferredRules.length > 0 && (
              <ul className="mt-1 list-disc pl-5 text-xs text-gray-400">
                {e.inferredRules.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
        {analysis.gaps.length > 0 && (
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-yellow-400">
              Gaps
            </div>
            <ul className="list-disc pl-5 text-xs text-yellow-200">
              {analysis.gaps.map((g, i) => (
                <li key={i}>{g}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </details>
  );
}
```

- [ ] **Step 3: Smoke-test**

Run: `cd web && npm run dev`. Navigate dashboard → fill name → Continue. Confirm `IdeaPage` renders with prompt, "Continue →" advances to `/new/depth` (stub).

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/IdeaPage.tsx web/src/components/wizard/DataAnalysisPanel.tsx
git commit -m "feat(web): IdeaPage + DataAnalysisPanel"
```

### Task 5.3: DepthPicker + ConstructiveOpener + DepthPickerPage

**Files:**
- Create: `web/src/components/wizard/ConstructiveOpener.tsx`
- Create: `web/src/components/wizard/DepthPicker.tsx`
- Modify: `web/src/pages/DepthPickerPage.tsx`

- [ ] **Step 1: Write `ConstructiveOpener.tsx`**

```tsx
interface ConstructiveOpenerProps {
  shell: string;     // e.g. "Nice — {gist}. How deep do you want to go on this?"
  gist: string;      // AI-generated gist
}

export function ConstructiveOpener({ shell, gist }: ConstructiveOpenerProps) {
  const text = shell.replace("{gist}", gist || "this is a solid starting point");
  return (
    <div className="max-w-2xl rounded-md border border-[#c2662d]/30 bg-[#c2662d]/5 p-4 text-sm text-gray-200">
      {text}
    </div>
  );
}
```

- [ ] **Step 2: Write `DepthPicker.tsx`**

```tsx
import type { WizardDepth } from "../../types/wizard";

interface DepthPickerProps {
  onPick: (d: WizardDepth) => void;
}

const tiers: Array<{
  id: WizardDepth;
  label: string;
  blurb: string;
  est: string;
}> = [
  { id: "light", label: "Light", blurb: "3 quick A/B picks", est: "~2 min" },
  { id: "mid", label: "Mid", blurb: "1-2 short answers + paired picks", est: "~5 min" },
  { id: "heavy", label: "Heavy", blurb: "Thorough Q&A + parallel-agent synthesis", est: "~10 min" },
  { id: "dev", label: "Dev", blurb: "Heavy + persona round-table critique", est: "~15 min" },
];

export function DepthPicker({ onPick }: DepthPickerProps) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
      {tiers.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onPick(t.id)}
          className="flex flex-col gap-2 rounded-lg border border-gray-800 bg-gray-900 p-4 text-left transition-colors hover:border-[#c2662d] hover:bg-[#c2662d]/5"
        >
          <div className="text-base font-semibold text-white">{t.label}</div>
          <div className="text-xs text-gray-300">{t.blurb}</div>
          <div className="text-[10px] uppercase tracking-wider text-[#c2662d]">{t.est}</div>
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Replace `DepthPickerPage.tsx`**

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useWizardStore } from "../stores/wizardStore";
import { useAuthStore } from "../stores/authStore";
import { ConstructiveOpener } from "../components/wizard/ConstructiveOpener";
import { DepthPicker } from "../components/wizard/DepthPicker";
import { generateOpener } from "../services/brainstorming";
import type { WizardDepth } from "../types/wizard";

const SHELL = "Nice — {gist}. How deep do you want to go on this?";

export default function DepthPickerPage() {
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
  const coreIdea = useWizardStore((s) => s.coreIdea);
  const dataAnalysis = useWizardStore((s) => s.dataAnalysis);
  const opener = useWizardStore((s) => s.opener);
  const setOpener = useWizardStore((s) => s.setOpener);
  const setDepth = useWizardStore((s) => s.setDepth);
  const setStep = useWizardStore((s) => s.setStep);

  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setStep("depth");
    if (opener || !coreIdea || !token) return;
    setLoading(true);
    generateOpener(token, coreIdea, dataAnalysis)
      .then(({ gist }) => setOpener({ gist, shell: SHELL }))
      .catch(() => setOpener({ gist: "this is a solid starting point", shell: SHELL }))
      .finally(() => setLoading(false));
  }, [coreIdea, dataAnalysis, opener, setOpener, setStep, token]);

  const onPick = (d: WizardDepth) => {
    setDepth(d);
    navigate("/new/q/1");
  };

  return (
    <div className="mx-auto flex h-full max-w-4xl flex-col items-center justify-center gap-6 p-6">
      {loading ? (
        <div className="text-sm text-gray-500">Reading your idea…</div>
      ) : (
        opener && <ConstructiveOpener shell={opener.shell} gist={opener.gist} />
      )}
      <DepthPicker onPick={onPick} />
    </div>
  );
}
```

- [ ] **Step 4: Smoke-test**

Run dev server. Walk: dashboard → IdeaPage → depth picker. Confirm opener text appears (gist fallback acceptable if proxy not wired) and clicking a tier navigates to `/new/q/1`.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/wizard/ConstructiveOpener.tsx web/src/components/wizard/DepthPicker.tsx web/src/pages/DepthPickerPage.tsx
git commit -m "feat(web): depth picker + constructive opener"
```

### Task 5.4: PairedQuestion + FreeTextQuestion components

**Files:**
- Create: `web/src/components/wizard/PairedQuestion.tsx`
- Create: `web/src/components/wizard/FreeTextQuestion.tsx`

- [ ] **Step 1: Write `PairedQuestion.tsx`**

```tsx
import type { PairedQuestion as PairedQ } from "../../types/wizard";

interface PairedQuestionProps {
  question: PairedQ;
  onAnswer: (choice: "A" | "B") => void;
  onSkip: () => void;
  onBack: () => void;
  progressLabel: string;          // "Light · Question 2 of 3"
  totalDots: number;
  currentDot: number;             // 0-indexed
}

export function PairedQuestion({
  question,
  onAnswer,
  onSkip,
  onBack,
  progressLabel,
  totalDots,
  currentDot,
}: PairedQuestionProps) {
  return (
    <div className="mx-auto w-full max-w-3xl rounded-lg border border-gray-800 bg-gray-900 p-6">
      <div className="mb-4 flex items-center gap-3 text-xs text-gray-500">
        <span className="font-semibold text-gray-300">{progressLabel}</span>
        <div className="flex flex-1 justify-end gap-2">
          {Array.from({ length: totalDots }).map((_, i) => (
            <span
              key={i}
              className={`inline-block h-2 w-2 rounded-full ${
                i < currentDot
                  ? "bg-[#c2662d]"
                  : i === currentDot
                    ? "bg-[#c2662d] ring-2 ring-[#c2662d]/30"
                    : "bg-white/15"
              }`}
            />
          ))}
        </div>
      </div>

      <h2 className="text-lg font-semibold text-white">{question.stem}</h2>
      {question.context && (
        <p className="mt-1 text-sm text-gray-400">{question.context}</p>
      )}

      <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2">
        {(["A", "B"] as const).map((letter) => {
          const opt = letter === "A" ? question.optionA : question.optionB;
          const accent = letter === "A" ? "#c2662d" : "#7c3aed";
          return (
            <button
              key={letter}
              type="button"
              onClick={() => onAnswer(letter)}
              className="flex flex-col gap-3 rounded-lg border border-white/10 bg-white/5 p-4 text-left transition-colors hover:border-[#c2662d]/50 hover:bg-[#c2662d]/5"
            >
              <div className="flex items-center gap-3">
                <span
                  className="flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold text-white"
                  style={{ backgroundColor: accent }}
                >
                  {letter}
                </span>
                <span className="text-sm font-semibold text-white">
                  {opt.title}
                </span>
              </div>
              <div
                className="rounded-md bg-black/30 px-3 py-2 text-xs text-gray-200"
                style={{ borderLeft: `2px solid ${accent}` }}
              >
                <div className="text-[9px] font-semibold uppercase tracking-wider text-gray-400">
                  Reason
                </div>
                <div>{opt.reason}</div>
              </div>
              <div className="rounded-md bg-black/30 px-3 py-2 text-xs text-gray-200 border-l-2 border-green-500">
                <div className="text-[9px] font-semibold uppercase tracking-wider text-gray-400">
                  Consequence
                </div>
                <div>{opt.consequence}</div>
              </div>
            </button>
          );
        })}
      </div>

      <div className="mt-5 flex items-center justify-between text-xs text-gray-500">
        <button type="button" onClick={onBack} className="hover:text-white">
          ← Back
        </button>
        <button type="button" onClick={onSkip} className="hover:text-white">
          Skip — let AI decide →
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write `FreeTextQuestion.tsx`**

```tsx
import { useState } from "react";
import type { FreeTextQuestion as FreeQ } from "../../types/wizard";

interface FreeTextQuestionProps {
  question: FreeQ;
  initialValue?: string;
  onAnswer: (text: string) => void;
  onBack: () => void;
  progressLabel: string;
  totalDots: number;
  currentDot: number;
}

export function FreeTextQuestion({
  question,
  initialValue = "",
  onAnswer,
  onBack,
  progressLabel,
  totalDots,
  currentDot,
}: FreeTextQuestionProps) {
  const [text, setText] = useState(initialValue);
  return (
    <div className="mx-auto w-full max-w-3xl rounded-lg border border-gray-800 bg-gray-900 p-6">
      <div className="mb-4 flex items-center gap-3 text-xs text-gray-500">
        <span className="font-semibold text-gray-300">{progressLabel}</span>
        <div className="flex flex-1 justify-end gap-2">
          {Array.from({ length: totalDots }).map((_, i) => (
            <span
              key={i}
              className={`inline-block h-2 w-2 rounded-full ${
                i < currentDot
                  ? "bg-[#c2662d]"
                  : i === currentDot
                    ? "bg-[#c2662d] ring-2 ring-[#c2662d]/30"
                    : "bg-white/15"
              }`}
            />
          ))}
        </div>
      </div>

      <h2 className="text-lg font-semibold text-white">{question.stem}</h2>
      {question.context && (
        <p className="mt-1 text-sm text-gray-400">{question.context}</p>
      )}

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={question.placeholder}
        rows={4}
        className="mt-4 w-full resize-none rounded-md border border-white/10 bg-black/40 p-3 text-sm text-white placeholder-gray-500"
      />

      <div className="mt-4 flex items-center justify-between text-xs text-gray-500">
        <button type="button" onClick={onBack} className="hover:text-white">
          ← Back
        </button>
        <button
          type="button"
          onClick={() => onAnswer(text.trim())}
          disabled={text.trim().length === 0}
          className="rounded-md bg-[#c2662d] px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
        >
          Continue →
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/wizard/PairedQuestion.tsx web/src/components/wizard/FreeTextQuestion.tsx
git commit -m "feat(web): paired and free-text question components"
```

### Task 5.5: QuestionPage

**Files:**
- Modify: `web/src/pages/QuestionPage.tsx`

- [ ] **Step 1: Replace stub**

```tsx
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useWizardStore } from "../stores/wizardStore";
import { useAuthStore } from "../stores/authStore";
import { PairedQuestion } from "../components/wizard/PairedQuestion";
import { FreeTextQuestion } from "../components/wizard/FreeTextQuestion";
import { generateQuestionBatch } from "../services/brainstorming";
import type { WizardDepth } from "../types/wizard";

function totalDotsFor(depth: WizardDepth | null): number {
  switch (depth) {
    case "light": return 3;
    case "mid": return 7;
    case "heavy": return 10;
    case "dev": return 10;
    default: return 5;
  }
}

export default function QuestionPage() {
  const navigate = useNavigate();
  const { n: nParam } = useParams<{ n: string }>();
  const n = Math.max(1, parseInt(nParam ?? "1", 10));

  const token = useAuthStore((s) => s.token);
  const depth = useWizardStore((s) => s.depth);
  const coreIdea = useWizardStore((s) => s.coreIdea);
  const midSeedAnswers = useWizardStore((s) => s.midSeedAnswers);
  const setMidSeedAnswers = useWizardStore((s) => s.setMidSeedAnswers);
  const dataAnalysis = useWizardStore((s) => s.dataAnalysis);
  const questions = useWizardStore((s) => s.questions);
  const appendQuestions = useWizardStore((s) => s.appendQuestions);
  const answers = useWizardStore((s) => s.answers);
  const recordAnswer = useWizardStore((s) => s.recordAnswer);
  const setStep = useWizardStore((s) => s.setStep);
  const setCurrentQuestionIdx = useWizardStore((s) => s.setCurrentQuestionIdx);

  const [loading, setLoading] = useState(false);
  const [doneFlag, setDoneFlag] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setStep("questions");
    setCurrentQuestionIdx(n - 1);
  }, [n, setCurrentQuestionIdx, setStep]);

  // Lazy-load the next batch when needed.
  useEffect(() => {
    if (questions[n - 1] || !depth || !token) return;
    setLoading(true);
    setError(null);
    generateQuestionBatch({
      token,
      coreIdea,
      depth,
      midSeedAnswers,
      priorQuestions: questions,
      priorAnswers: answers,
      dataAnalysis,
      needsFreeTextSeed: depth === "mid" && questions.length === 0,
    })
      .then((batch) => {
        appendQuestions(batch.questions);
        setDoneFlag(batch.done);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load questions"))
      .finally(() => setLoading(false));
  }, [
    appendQuestions,
    answers,
    coreIdea,
    dataAnalysis,
    depth,
    midSeedAnswers,
    n,
    questions,
    token,
  ]);

  const q = questions[n - 1];
  const totalDots = totalDotsFor(depth);
  const progressLabel = `${depth?.charAt(0).toUpperCase()}${depth?.slice(1)} · Question ${n}`;

  const advance = () => {
    const isLastInBatch = n === questions.length;
    if (doneFlag && isLastInBatch) {
      navigate("/new/building");
    } else {
      navigate(`/new/q/${n + 1}`);
    }
  };

  const goBack = () => {
    if (n === 1) navigate("/new/depth");
    else navigate(`/new/q/${n - 1}`);
  };

  if (error) {
    return (
      <div className="mx-auto flex h-full max-w-2xl items-center justify-center p-6">
        <div className="rounded-md border border-red-500/40 bg-red-950/30 p-4 text-sm text-red-200">
          {error}
        </div>
      </div>
    );
  }

  if (loading || !q) {
    return (
      <div className="mx-auto flex h-full max-w-2xl items-center justify-center p-6 text-sm text-gray-500">
        Generating question…
      </div>
    );
  }

  if (q.kind === "free-text") {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <FreeTextQuestion
          question={q}
          initialValue={(answers[q.id] as string) ?? ""}
          onAnswer={(text) => {
            recordAnswer(q.id, text);
            // Mid-seed answers tracking:
            if (depth === "mid") {
              setMidSeedAnswers([...midSeedAnswers, text]);
            }
            advance();
          }}
          onBack={goBack}
          progressLabel={progressLabel}
          totalDots={totalDots}
          currentDot={n - 1}
        />
      </div>
    );
  }

  return (
    <div className="flex h-full items-center justify-center p-6">
      <PairedQuestion
        question={q}
        onAnswer={(choice) => {
          recordAnswer(q.id, choice);
          advance();
        }}
        onSkip={() => {
          recordAnswer(q.id, q.aiPreference);
          advance();
        }}
        onBack={goBack}
        progressLabel={progressLabel}
        totalDots={totalDots}
        currentDot={n - 1}
      />
    </div>
  );
}
```

- [ ] **Step 2: Smoke-test**

Run dev server. Walk dashboard → idea → depth (Light) → first question. With the proxy unmocked, expect the "Failed to load questions" error — confirm the page renders that gracefully. With a mock proxy returning a paired-question payload, confirm the question renders, A/B picks navigate to `/new/q/2`, Back works.

- [ ] **Step 3: Commit**

```bash
git add web/src/pages/QuestionPage.tsx
git commit -m "feat(web): QuestionPage (paired + free-text routing)"
```

---

## Phase 6 — GitHub repo provisioning + manifest

### Task 6.1: github-repos service

**Files:**
- Create: `web/src/services/github-repos.ts`

- [ ] **Step 1: Write the service**

```ts
import type { WizardDepth } from "../types/wizard";
import { sanitizeRepoName } from "../lib/sanitize-repo-name";
import { useRepoStore } from "../stores/repoStore";
import { useAuthStore } from "../stores/authStore";

export interface ProjectMeta {
  displayName: string;
  createdVia: "forgeds-wizard";
  createdAt: string;
  depthUsed: WizardDepth;
  dataSourceKind: "prototype" | "from-data";
  attachmentNames: string[];
}

export async function checkScopes(): Promise<{
  hasRepoScope: boolean;
  scopes: string[];
}> {
  const token = useAuthStore.getState().token;
  if (!token) return { hasRepoScope: false, scopes: [] };
  const res = await fetch("https://api.github.com/user", {
    headers: { Authorization: `Bearer ${token}` },
  });
  const scopes = (res.headers.get("x-oauth-scopes") ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return { hasRepoScope: scopes.includes("repo"), scopes };
}

export async function eagerCreateRepo(params: {
  projectName: string;
  description: string;
  isPrivate?: boolean;
}): Promise<string> {
  const baseName = sanitizeRepoName(params.projectName);
  const token = useAuthStore.getState().token;
  if (!token) throw new Error("Not authenticated");

  // Resolve collisions by suffixing -2, -3...
  const candidate = await findFreeName(token, baseName);

  await useRepoStore.getState().createNewRepo(
    candidate,
    params.description,
    params.isPrivate ?? true,
    true,
  );

  // Resolve to full_name now that the store has updated.
  const created = useRepoStore.getState().selectedRepo;
  if (!created || created.name !== candidate) {
    throw new Error("Repo creation completed but selectedRepo not set");
  }
  return created.full_name;
}

async function findFreeName(token: string, base: string): Promise<string> {
  for (let i = 0; i < 6; i++) {
    const candidate = i === 0 ? base : `${base}-${i + 1}`;
    const exists = await repoExists(token, candidate);
    if (!exists) return candidate;
  }
  throw new Error("Could not find a free repo name");
}

async function repoExists(token: string, name: string): Promise<boolean> {
  const userRes = await fetch("https://api.github.com/user", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!userRes.ok) return false;
  const user = await userRes.json();
  const res = await fetch(
    `https://api.github.com/repos/${user.login}/${name}`,
    { method: "HEAD", headers: { Authorization: `Bearer ${token}` } },
  );
  return res.status === 200;
}

export async function dropManifest(
  fullName: string,
  meta: ProjectMeta,
): Promise<void> {
  const token = useAuthStore.getState().token;
  if (!token) throw new Error("Not authenticated");
  const yaml = `project:
  name: ${meta.displayName}
  created_via: ${meta.createdVia}
  created_at: ${meta.createdAt}
  depth_used: ${meta.depthUsed}
data_source:
  kind: ${meta.dataSourceKind}
  attachments: [${meta.attachmentNames.map((n) => `"${n}"`).join(", ")}]
`;
  const [owner, repo] = fullName.split("/");
  // Use the existing batchUploadToBranch via repoStore to land the file on main.
  await useRepoStore.getState().batchUploadToBranch(
    "main",
    [{ path: "forgeds.yaml", content: yaml, isBinary: false }],
    "ForgeDS: drop project manifest",
    fullName,
  );
  void owner; void repo; // Variables retained for clarity in case batchUpload signature changes.
}
```

> **Note:** verify the actual signatures of `useRepoStore.createNewRepo` and `batchUploadToBranch` against the live store implementation. Adjust positional arguments / property names where they differ.

- [ ] **Step 2: Tsc check**

Run: `cd web && npx tsc -b --noEmit`
Expected: 0 new errors.

- [ ] **Step 3: Commit**

```bash
git add web/src/services/github-repos.ts
git commit -m "feat(web): github-repos service (eager create, scope check, manifest)"
```

### Task 6.2: Wire eager repo creation into RailWizard

**Files:**
- Modify: `web/src/components/dashboard/RailWizard.tsx`
- Modify: `web/src/pages/DashboardPage.tsx` (call `checkScopes` on mount)

- [ ] **Step 1: Add scope state to dashboardStore**

In `web/src/stores/dashboardStore.ts`, extend the state:

```ts
// Add to interface:
hasRepoScope: boolean | null;
checkScopes: () => Promise<void>;

// Add to implementation (top, near other actions):
hasRepoScope: null,
checkScopes: async () => {
  const { checkScopes } = await import("../services/github-repos");
  const { hasRepoScope } = await checkScopes();
  set({ hasRepoScope });
},
```

- [ ] **Step 2: Update `DashboardPage.tsx` useEffect**

Add `checkScopes` to the mount-effect dependency array and call it.

```tsx
const checkScopes = useDashboardStore((s) => s.checkScopes);
const hasRepoScope = useDashboardStore((s) => s.hasRepoScope);

useEffect(() => {
  fetchRepos();
  refresh();
  checkScopes();
}, [fetchRepos, refresh, checkScopes]);
```

- [ ] **Step 3: Disable "Create new repo" radio if scope missing**

In `RailWizard.tsx`, read `hasRepoScope` and gate the radio:

```tsx
import { useDashboardStore } from "../../stores/dashboardStore";

// inside component:
const hasRepoScope = useDashboardStore((s) => s.hasRepoScope);
const canCreateNew = hasRepoScope !== false; // null = unknown → optimistic enabled

// In the "Create new repo" label, add disabled visual + tooltip when !canCreateNew.
```

When the user picks "Create new repo" and clicks Continue, fire the eager creation:

```tsx
import { eagerCreateRepo } from "../../services/github-repos";

const setRepoCreationStatus = useWizardStore((s) => s.setRepoCreationStatus);
const setRepoCreationPromise = useWizardStore((s) => s.setRepoCreationPromise);
const setCreatedRepoFullName = useWizardStore((s) => s.setCreatedRepoFullName);
const coreIdea = ""; // not yet set when wizard starts; description uses placeholder

// in onContinue, after setEntryParams:
if (target === "create-new") {
  setRepoCreationStatus("pending");
  const promise = eagerCreateRepo({
    projectName: name.trim(),
    description: `ForgeDS prototype: ${name.trim()}`,
    isPrivate: true,
  })
    .then((fullName) => {
      setCreatedRepoFullName(fullName);
      setRepoCreationStatus("ready");
      return fullName;
    })
    .catch((err) => {
      setRepoCreationStatus(
        "failed",
        err instanceof Error ? err.message : "Repo creation failed",
      );
      throw err;
    });
  setRepoCreationPromise(promise);
}
```

- [ ] **Step 4: Smoke-test**

Run dev server. With repo scope: pick Prototype + Create new + a name → Continue → IdeaPage. Open Network tab — confirm a POST to `https://api.github.com/user/repos` happens in the background. After ~1-2s, check the user's GitHub: a new repo exists.

Without repo scope (test by revoking scope manually): Continue should still navigate (to allow the user to keep working in the wizard if they later switch to existing-repo), but `repoCreationStatus` becomes `"failed"`, surfaced as the banner on `IdeaPage`.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/dashboard/RailWizard.tsx web/src/pages/DashboardPage.tsx web/src/stores/dashboardStore.ts
git commit -m "feat(web): wire eager repo creation + scope gating from RailWizard"
```

---

## Phase 7 — BuildingPage + Light/Mid build path

### Task 7.1: BuildingPage (Light/Mid only)

**Files:**
- Modify: `web/src/pages/BuildingPage.tsx`

- [ ] **Step 1: Replace stub**

```tsx
import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useWizardStore } from "../stores/wizardStore";
import { useAuthStore } from "../stores/authStore";
import { useRepoStore } from "../stores/repoStore";
import { useIdeStore } from "../stores/ideStore";
import { useToastStore } from "../stores/toastStore";
import { BuildProgress } from "../components/BuildProgress";
import { buildProject } from "../services/claude-api";
import { dropManifest } from "../services/github-repos";

export default function BuildingPage() {
  const navigate = useNavigate();
  const token = useAuthStore((s) => s.token);
  const setStep = useWizardStore((s) => s.setStep);
  const depth = useWizardStore((s) => s.depth);
  const coreIdea = useWizardStore((s) => s.coreIdea);
  const projectName = useWizardStore((s) => s.projectName);
  const targetMode = useWizardStore((s) => s.targetMode);
  const targetRepoFullName = useWizardStore((s) => s.targetRepoFullName);
  const createdRepoFullName = useWizardStore((s) => s.createdRepoFullName);
  const repoCreationPromise = useWizardStore((s) => s.repoCreationPromise);
  const repoCreationStatus = useWizardStore((s) => s.repoCreationStatus);
  const buildMessages = useWizardStore((s) => s.buildMessages);
  const addBuildMessage = useWizardStore((s) => s.addBuildMessage);
  const setBuildMessages = useWizardStore((s) => s.setBuildMessages);
  const setGeneratedFiles = useWizardStore((s) => s.setGeneratedFiles);
  const entryTab = useWizardStore((s) => s.entryTab);
  const attachments = useWizardStore((s) => s.attachments);
  const questions = useWizardStore((s) => s.questions);
  const answers = useWizardStore((s) => s.answers);
  const midSeedAnswers = useWizardStore((s) => s.midSeedAnswers);
  const dataAnalysis = useWizardStore((s) => s.dataAnalysis);
  const reset = useWizardStore((s) => s.reset);

  const startedRef = useRef(false);

  useEffect(() => {
    setStep("building");
    if (startedRef.current) return;
    startedRef.current = true;
    void run();

    async function run() {
      if (!token || !depth) return;
      setBuildMessages([]);
      const log = (text: string, type: "info" | "success" | "error" | "warning" = "info") => {
        addBuildMessage({
          timestamp: new Date().toLocaleTimeString(),
          text,
          type,
        });
      };

      log("Starting build…");

      // Resolve target repo full name (await background creation if needed).
      let repoFullName = targetMode === "use-existing" ? targetRepoFullName : createdRepoFullName;
      if (targetMode === "create-new" && !repoFullName && repoCreationPromise) {
        log("Waiting for new repo to finish provisioning…");
        try {
          repoFullName = await repoCreationPromise;
        } catch (err) {
          log(
            err instanceof Error ? `Repo creation failed: ${err.message}` : "Repo creation failed",
            "error",
          );
          return;
        }
      }
      if (!repoFullName) {
        log("No target repo — cannot commit.", "error");
        return;
      }

      // Build via existing buildProject service. We pass a richer spec under .prompt
      // until the proxy is updated to read the new shape; sections is filled with a
      // single synthetic block so the existing proxy continues to work.
      const spec = JSON.stringify({
        coreIdea,
        depth,
        entryTab,
        midSeedAnswers,
        questions,
        answers,
        dataAnalysis,
      });

      try {
        const result = await buildProject(
          token,
          {
            sections: [
              {
                id: "spec",
                title: "Wizard Spec",
                icon: "🛠",
                content: spec,
                items: [],
                isEditable: false,
              },
            ],
            prompt: coreIdea,
          },
          (chunk) => {
            if (chunk.message) log(chunk.message, chunk.type ?? "info");
          },
        );

        const files = result.files ?? [];
        setGeneratedFiles(files);

        // Silent commit.
        if (files.length > 0) {
          const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
          const branch = `forgeds/${ts}`;
          await useRepoStore.getState().batchUploadToBranch(
            branch,
            files.map((f) => ({ path: f.path, content: f.content, isBinary: false })),
            `ForgeDS: build ${projectName} (${depth})`,
            repoFullName,
          );
          // Drop manifest if newly-created repo.
          if (targetMode === "create-new") {
            await dropManifest(repoFullName, {
              displayName: projectName,
              createdVia: "forgeds-wizard",
              createdAt: new Date().toISOString(),
              depthUsed: depth,
              dataSourceKind: entryTab,
              attachmentNames: attachments.map((f) => f.name),
            });
          }

          // Open in IDE.
          useIdeStore.getState().loadGeneratedFiles(files);
          useToastStore.getState().success(
            "Build complete",
            `${files.length} file(s) committed to ${branch}`,
          );
          reset();
          navigate("/ide");
        } else {
          log("Build returned no files.", "warning");
        }
      } catch (err) {
        log(err instanceof Error ? err.message : "Build failed", "error");
      }
    }
  }, [
    addBuildMessage,
    answers,
    attachments,
    coreIdea,
    createdRepoFullName,
    dataAnalysis,
    depth,
    entryTab,
    midSeedAnswers,
    navigate,
    projectName,
    questions,
    repoCreationPromise,
    reset,
    setBuildMessages,
    setGeneratedFiles,
    setStep,
    targetMode,
    targetRepoFullName,
    token,
  ]);

  // Suppress unused warning for repoCreationStatus — referenced for re-render only.
  void repoCreationStatus;

  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="w-full max-w-3xl">
        <BuildProgress
          messages={buildMessages}
          isBuilding={true}
          isComplete={false}
          onOpenIDE={() => navigate("/ide")}
        />
      </div>
    </div>
  );
}
```

> **Note:** the proxy may need an update to read the richer spec shape. For Light/Mid in this phase, the JSON string under `sections[0].content` is the workaround. Phase 8 introduces the multi-agent path that builds against a fully-synthesised spec.

- [ ] **Step 2: Smoke-test (mocked or live)**

Run the wizard end-to-end with Light depth. Expect: build messages stream, files commit, redirect to IDE, success toast.

- [ ] **Step 3: Commit**

```bash
git add web/src/pages/BuildingPage.tsx
git commit -m "feat(web): BuildingPage runs Light/Mid build + silent commit"
```

---

## Phase 8 — Multi-agent (Heavy/Dev) and From Data sidecar

These two are independent of each other and can be dispatched in parallel.

### Task 8.1: multi-agent service

**Files:**
- Create: `web/src/services/multi-agent.ts`

- [ ] **Step 1: Write the service**

```ts
import type {
  PairedQuestion,
  WizardDepth,
  DataAnalysis,
} from "../types/wizard";

const CLAUDE_PROXY = import.meta.env.VITE_CLAUDE_API_PROXY ?? "";

export interface FanoutResult {
  drafts: Array<{ agent: string; spec: string; rationale: string }>;
  synthesised: string;
  divergences: string[];
}

export interface RoundTableResult {
  critiques: Array<{ persona: string; notes: string }>;
  revisedSpec: string;
}

export type FanoutProgress = (msg: {
  agent: string;
  phase: "started" | "done";
  preview?: string;
}) => void;

export type RoundTableProgress = (msg: {
  persona: string;
  phase: "started" | "done";
  critique?: string;
}) => void;

async function callAgent(
  token: string,
  role: string,
  prompt: string,
  opts?: { temperature?: number },
): Promise<string> {
  const res = await fetch(`${CLAUDE_PROXY}/api/agent`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      role,
      prompt,
      temperature: opts?.temperature ?? 0.7,
    }),
  });
  if (!res.ok) throw new Error(`Agent call failed: ${role} (${res.status})`);
  const json = await res.json();
  return typeof json.text === "string" ? json.text : "";
}

const PERSPECTIVES = [
  { agent: "simplicity",  system: "You are an architect who optimises for the simplest possible solution that meets the requirements." },
  { agent: "governance",  system: "You are an architect who optimises for governance, audit trail, and regulatory compliance." },
  { agent: "user-friction", system: "You are an architect who optimises for end-user friction — every form field is a tax." },
];

export async function fanoutSpec(params: {
  token: string;
  coreIdea: string;
  depth: WizardDepth;
  midSeedAnswers?: string[];
  questions: PairedQuestion[];
  answers: Record<string, "A" | "B" | string>;
  dataAnalysis?: DataAnalysis | null;
  agentCount?: number;
  onProgress?: FanoutProgress;
}): Promise<FanoutResult> {
  const count = Math.min(params.agentCount ?? 3, PERSPECTIVES.length);
  const perspectives = PERSPECTIVES.slice(0, count);
  const userInputBlock = JSON.stringify({
    coreIdea: params.coreIdea,
    depth: params.depth,
    midSeedAnswers: params.midSeedAnswers ?? [],
    questions: params.questions,
    answers: params.answers,
    dataAnalysis: params.dataAnalysis ?? null,
  });

  const draftPromises = perspectives.map(async (p) => {
    params.onProgress?.({ agent: p.agent, phase: "started" });
    try {
      const text = await callAgent(params.token, p.system, userInputBlock, {
        temperature: 0.9,
      });
      params.onProgress?.({ agent: p.agent, phase: "done", preview: text.slice(0, 80) });
      return { agent: p.agent, spec: text, rationale: "" };
    } catch (err) {
      params.onProgress?.({
        agent: p.agent,
        phase: "done",
        preview: err instanceof Error ? `failed: ${err.message}` : "failed",
      });
      return null;
    }
  });

  const settled = (await Promise.all(draftPromises)).filter(
    (d): d is { agent: string; spec: string; rationale: string } => d !== null,
  );

  if (settled.length < 2) {
    throw new Error(
      `Fanout produced only ${settled.length} draft(s); need at least 2 to synthesise.`,
    );
  }

  // Synthesis pass.
  const synthInput = JSON.stringify({ drafts: settled, original: userInputBlock });
  const synthesised = await callAgent(
    params.token,
    "You are a synthesiser. Given multiple specification drafts written from different perspectives, merge them into one coherent spec. Favour points where drafts agreed; flag divergences explicitly at the end.",
    synthInput,
    { temperature: 0.3 },
  );

  // Naive divergence extraction: lines after a "DIVERGENCES:" marker.
  const divergences = extractDivergences(synthesised);

  return { drafts: settled, synthesised, divergences };
}

function extractDivergences(text: string): string[] {
  const idx = text.toLowerCase().lastIndexOf("divergences:");
  if (idx < 0) return [];
  return text
    .slice(idx + "divergences:".length)
    .split("\n")
    .map((s) => s.replace(/^[-*]\s*/, "").trim())
    .filter((s) => s.length > 0);
}

const DEFAULT_PERSONAS = [
  "End User",
  "Compliance Officer",
  "Technical Architect",
  "Skeptical CFO",
];

export async function personaRoundTable(params: {
  token: string;
  spec: string;
  personas?: string[];
  onProgress?: RoundTableProgress;
}): Promise<RoundTableResult> {
  const personas = params.personas ?? DEFAULT_PERSONAS;
  const critiques: Array<{ persona: string; notes: string }> = [];

  for (const persona of personas) {
    params.onProgress?.({ persona, phase: "started" });
    try {
      const priorBlock =
        critiques.length > 0
          ? `\n\nPRIOR CRITIQUES:\n${critiques
              .map((c) => `- ${c.persona}: ${c.notes}`)
              .join("\n")}`
          : "";
      const prompt = `SPEC:\n${params.spec}${priorBlock}\n\nCritique this spec from your perspective. Be concrete.`;
      const notes = await callAgent(
        params.token,
        `You are a ${persona}. Critique the spec from your perspective only.`,
        prompt,
        { temperature: 0.5 },
      );
      critiques.push({ persona, notes });
      params.onProgress?.({ persona, phase: "done", critique: notes.slice(0, 80) });
    } catch (err) {
      params.onProgress?.({
        persona,
        phase: "done",
        critique: err instanceof Error ? `failed: ${err.message}` : "failed",
      });
      // Abort the round-table; return what we have.
      break;
    }
  }

  // Final synthesis: merge critiques into a revised spec.
  const synthPrompt = `ORIGINAL SPEC:\n${params.spec}\n\nCRITIQUES:\n${critiques
    .map((c) => `- ${c.persona}: ${c.notes}`)
    .join("\n")}\n\nProduce a revised spec that addresses the critiques.`;
  const revisedSpec = await callAgent(
    params.token,
    "You are a synthesiser merging critiques into a revised specification.",
    synthPrompt,
    { temperature: 0.3 },
  );

  return { critiques, revisedSpec };
}
```

> **Note:** the proxy needs an `/api/agent` endpoint that accepts `{role, prompt, temperature}` and returns `{text}`. Out of scope for this plan — same caveat as Task 4.1.

- [ ] **Step 2: Commit**

```bash
git add web/src/services/multi-agent.ts
git commit -m "feat(web): multi-agent service (fanout + persona round-table)"
```

### Task 8.2: BuildingPage Heavy/Dev branches

**Files:**
- Modify: `web/src/pages/BuildingPage.tsx`

- [ ] **Step 1: Refactor build sequence to branch on depth**

Inside the `run()` function in `BuildingPage`, before the `buildProject` call, add:

```ts
import { fanoutSpec, personaRoundTable } from "../services/multi-agent";
import { useWizardStore } from "../stores/wizardStore";
const setFanoutDrafts = useWizardStore.getState().setFanoutDrafts;
const setPersonaCritiques = useWizardStore.getState().setPersonaCritiques;

// (move into the run function, replacing the simple spec construction)
let finalSpec = JSON.stringify({
  coreIdea, depth, entryTab, midSeedAnswers, questions, answers, dataAnalysis,
});

if (depth === "heavy" || depth === "dev") {
  log("Heavy mode: dispatching parallel-agent fanout…");
  try {
    const fanout = await fanoutSpec({
      token,
      coreIdea,
      depth,
      midSeedAnswers,
      questions: questions.filter((q): q is import("../types/wizard").PairedQuestion => q.kind === "paired"),
      answers,
      dataAnalysis,
      onProgress: (msg) => log(`[${msg.agent}] ${msg.phase}${msg.preview ? `: ${msg.preview}` : ""}`),
    });
    setFanoutDrafts(fanout.drafts);
    finalSpec = fanout.synthesised;
    if (fanout.divergences.length > 0) {
      log(`Synthesis flagged ${fanout.divergences.length} divergence(s).`, "warning");
    }
  } catch (err) {
    log(err instanceof Error ? `Fanout failed: ${err.message}` : "Fanout failed", "error");
    return;
  }
}

if (depth === "dev") {
  log("Dev mode: persona round-table critique…");
  try {
    const rt = await personaRoundTable({
      token,
      spec: finalSpec,
      onProgress: (msg) =>
        log(`[${msg.persona}] ${msg.phase}${msg.critique ? `: ${msg.critique}` : ""}`),
    });
    setPersonaCritiques(rt.critiques);
    finalSpec = rt.revisedSpec;
  } catch (err) {
    log(err instanceof Error ? `Round-table partial: ${err.message}` : "Round-table failed", "warning");
  }
}

// Now invoke buildProject with finalSpec embedded in sections[0].content.
```

Adjust the existing `buildProject(...)` call to use `finalSpec` in `sections[0].content`.

- [ ] **Step 2: Commit**

```bash
git add web/src/pages/BuildingPage.tsx
git commit -m "feat(web): BuildingPage Heavy/Dev branches with fanout + round-table"
```

### Task 8.3: data-ingestion service

**Files:**
- Create: `web/src/services/data-ingestion.ts`

- [ ] **Step 1: Write the service**

```ts
import JSZip from "jszip";
import type { DataAnalysis } from "../types/wizard";

const CLAUDE_PROXY = import.meta.env.VITE_CLAUDE_API_PROXY ?? "";

interface ParsedFile {
  filename: string;
  kind: "csv" | "ds" | "json" | "unsupported";
  preview: {
    columns?: string[];
    rows?: Array<Record<string, string>>;
    raw?: string;
  };
}

export async function parseAttachments(files: File[]): Promise<ParsedFile[]> {
  const out: ParsedFile[] = [];
  for (const f of files) {
    const lower = f.name.toLowerCase();
    if (lower.endsWith(".csv")) {
      out.push(await parseCsv(f));
    } else if (lower.endsWith(".zip")) {
      out.push(...(await parseZip(f)));
    } else if (lower.endsWith(".ds")) {
      out.push({
        filename: f.name,
        kind: "ds",
        preview: { raw: (await f.text()).slice(0, 5000) },
      });
    } else if (lower.endsWith(".json")) {
      out.push({
        filename: f.name,
        kind: "json",
        preview: { raw: (await f.text()).slice(0, 5000) },
      });
    } else if (lower.endsWith(".accdb")) {
      out.push({
        filename: f.name,
        kind: "unsupported",
        preview: { raw: "Access database files cannot be parsed in-browser. Please export tables to CSV." },
      });
    }
  }
  return out;
}

async function parseCsv(file: File): Promise<ParsedFile> {
  const text = await file.text();
  const lines = text.split(/\r?\n/).filter((l) => l.length > 0);
  const headerLine = lines[0] ?? "";
  const columns = splitCsvLine(headerLine);
  const rows = lines.slice(1, 51).map((line) => {
    const cells = splitCsvLine(line);
    const row: Record<string, string> = {};
    columns.forEach((c, i) => {
      row[c] = cells[i] ?? "";
    });
    return row;
  });
  return { filename: file.name, kind: "csv", preview: { columns, rows } };
}

function splitCsvLine(line: string): string[] {
  // Naive CSV parser; sufficient for preview. Replace with papaparse if quoted commas appear.
  const out: string[] = [];
  let cur = "";
  let inQuote = false;
  for (const ch of line) {
    if (ch === '"') inQuote = !inQuote;
    else if (ch === "," && !inQuote) {
      out.push(cur);
      cur = "";
    } else {
      cur += ch;
    }
  }
  out.push(cur);
  return out;
}

async function parseZip(file: File): Promise<ParsedFile[]> {
  const out: ParsedFile[] = [];
  const zip = await JSZip.loadAsync(file);
  for (const [name, entry] of Object.entries(zip.files)) {
    if (entry.dir) continue;
    if (name.toLowerCase().endsWith(".csv")) {
      const blob = await entry.async("blob");
      const inner = new File([blob], name);
      out.push(await parseCsv(inner));
    }
  }
  return out;
}

export async function analyzeData(
  token: string,
  parsed: ParsedFile[],
): Promise<DataAnalysis> {
  if (!CLAUDE_PROXY) {
    return { entities: [], observedConstraints: [], gaps: ["Proxy not configured — analysis skipped"] };
  }
  const res = await fetch(`${CLAUDE_PROXY}/api/data-analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ parsed }),
  });
  if (!res.ok) throw new Error(`Data analysis failed (${res.status})`);
  return res.json();
}
```

> **Note:** the proxy needs `/api/data-analyze` returning the `DataAnalysis` shape. Out of scope for this plan.

- [ ] **Step 2: Wire ingestion into RailWizard's onContinue**

In `RailWizard.tsx`, when `tab === "from-data"`, the user must have attached files via the wizard panel. (Add a file input to the rail wizard's "From Data" tab — only visible when that tab is active.)

Update the RailWizard:
- Add a file input below the project name that's visible only when `tab === "from-data"`.
- Capture into local `dataFiles` state.
- On Continue, if from-data, also fire the ingestion sidecar:

```tsx
import { parseAttachments, analyzeData } from "../../services/data-ingestion";
import { useAuthStore } from "../../stores/authStore";

const setDataAnalysis = useWizardStore((s) => s.setDataAnalysis);
const setDataIngestionStatus = useWizardStore((s) => s.setDataIngestionStatus);
const token = useAuthStore((s) => s.token);

// in onContinue, after setEntryParams (which already takes attachments):
if (tab === "from-data" && dataFiles.length > 0 && token) {
  setDataIngestionStatus("parsing");
  void parseAttachments(dataFiles)
    .then((parsed) => {
      setDataIngestionStatus("analyzing");
      return analyzeData(token, parsed);
    })
    .then((analysis) => {
      setDataAnalysis(analysis);
      setDataIngestionStatus("ready");
    })
    .catch(() => {
      setDataIngestionStatus("failed");
    });
}
```

- [ ] **Step 3: Commit**

```bash
git add web/src/services/data-ingestion.ts web/src/components/dashboard/RailWizard.tsx
git commit -m "feat(web): From Data sidecar — parse + analyze attachments"
```

---

## Phase 9 — Migration & cleanup

### Task 9.1: Delete dead files

**Files:**
- Delete: `web/src/pages/PromptPage.tsx`
- Delete: `web/src/components/ModeToggle.tsx`
- Delete: `web/src/components/PromptInput.tsx`
- Delete: `web/src/components/RefinedPrompt.tsx`
- Delete: `web/src/stores/promptStore.ts`
- Delete: `web/src/types/prompt.ts`
- Modify: `web/src/components/index.ts`, `web/src/services/claude-api.ts`, `web/src/services/index.ts`

- [ ] **Step 1: Confirm nothing imports the dead files**

Run: `cd web && npx tsc -b --noEmit`
Capture all errors. If any code still references the deleted modules, fix or rewire before deletion.

- [ ] **Step 2: Update barrel files**

In `web/src/components/index.ts`:
- Remove exports for `ModeToggle`, `PromptInput`, `RefinedPrompt`
- Add `export * from "./IdeaInput";`

In `web/src/services/claude-api.ts`:
- Remove `refinePrompt` export
- Remove `RefineRequest`, `RefineResponse`, `RefinedSectionRaw` types

In `web/src/services/index.ts`:
- Remove `refinePrompt` re-export

In `web/src/types/index.ts`: ensure no `prompt.ts` re-export remains.

- [ ] **Step 3: Delete the files**

```bash
cd web/src && rm pages/PromptPage.tsx components/ModeToggle.tsx components/PromptInput.tsx components/RefinedPrompt.tsx stores/promptStore.ts types/prompt.ts
```

- [ ] **Step 4: Verify build**

Run: `cd web && npx tsc -b --noEmit && npm test && npx vite build`
Expected: 0 errors, all tests pass, build succeeds.

- [ ] **Step 5: Commit**

```bash
git add -A web/
git commit -m "chore(web): remove PromptPage, ModeToggle, PromptInput, RefinedPrompt, promptStore"
```

### Task 9.2: Legacy history migration

**Files:**
- Modify: `web/src/stores/dashboardStore.ts`

- [ ] **Step 1: Add migration logic**

Add to `dashboardStore.ts`, near the top:

```ts
const SUNSET_DAYS = 30;
const SUNSET_KEY = "forgeds-legacy-history-sunset";

interface LegacyHistoryItem {
  id: string;
  prompt: string;
  timestamp: number;
  fileCount: number;
}

function readLegacyHistory(): LegacyHistoryItem[] {
  try {
    const raw = localStorage.getItem("forgeds-project-history");
    if (!raw) return [];
    return JSON.parse(raw) as LegacyHistoryItem[];
  } catch {
    return [];
  }
}

function isSunset(): boolean {
  try {
    const sunset = localStorage.getItem(SUNSET_KEY);
    if (!sunset) {
      // First time we read — set the sunset date now.
      localStorage.setItem(
        SUNSET_KEY,
        String(Date.now() + SUNSET_DAYS * 24 * 3600 * 1000),
      );
      return false;
    }
    const ts = parseInt(sunset, 10);
    if (Date.now() > ts) {
      localStorage.removeItem("forgeds-project-history");
      localStorage.removeItem(SUNSET_KEY);
      return true;
    }
    return false;
  } catch {
    return false;
  }
}
```

Add a derived field to the store:

```ts
// in interface:
legacyPrompts: LegacyHistoryItem[];

// in initial state:
legacyPrompts: isSunset() ? [] : readLegacyHistory(),
```

- [ ] **Step 2: Render legacy prompts at the bottom of the activity feed**

In `RepoActivityFeed.tsx`, append a "Local prompts (sunsetting)" group when `legacyPrompts.length > 0`.

```tsx
import { useDashboardStore } from "../../stores/dashboardStore";

// inside component, after the apps.map():
const legacy = useDashboardStore((s) => s.legacyPrompts);
{legacy.length > 0 && (
  <div className="mt-3 border-t border-white/5 pt-3">
    <div className="text-[10px] font-semibold uppercase tracking-wider text-gray-600">
      Local prompts (will disappear after 30 days)
    </div>
    {legacy.slice(0, 8).map((item) => (
      <div
        key={item.id}
        className="mt-1 truncate text-[10px] text-gray-500"
      >
        {new Date(item.timestamp).toLocaleDateString()} — {item.prompt.slice(0, 50)}
      </div>
    ))}
  </div>
)}
```

- [ ] **Step 3: Commit**

```bash
git add web/src/stores/dashboardStore.ts web/src/components/dashboard/RepoActivityFeed.tsx
git commit -m "feat(web): legacy promptStore history migration with 30-day sunset"
```

---

## Phase 10 — Manual test pass

### Task 10.1: Walk the test plan from the spec

**Files:** none (verification only)

- [ ] **Step 1: Run dev server**

```bash
cd web && npm run dev
```

- [ ] **Step 2: Walk the 10-item checklist from spec § "Manual test plan"**

For each item, log result (pass/fail/notes) inline below this task. If any fail, open a follow-up issue with reproduction steps.

  1. [ ] New user, no manifest repos → empty state + Pin works.
  2. [ ] User with `forgeds.yaml` in 2 repos → both surface, click → IDE.
  3. [ ] Prototype + Create new + Light → repo created, dashboard refresh shows it, IDE loads files.
  4. [ ] Prototype + Use existing + Mid → existing repo gets `forgeds/<ts>` branch.
  5. [ ] From Data + .csv + Heavy → data analysis runs, opener references it, questions reference data, build incorporates rules.
  6. [ ] Dev path → fanout + round-table messages stream.
  7. [ ] Missing `repo` scope → "Create new repo" disabled, re-auth works.
  8. [ ] Mid-wizard browser back/forward → answers preserved.
  9. [ ] Background repo creation fails → IdeaPage banner + retry.
  10. [ ] One fanout agent fails → build still completes.

- [ ] **Step 3: Commit results note**

```bash
echo "see docs/superpowers/plans/2026-04-22-dashboard-wizard-brainstorming.md Task 10.1 for test results" > docs/superpowers/plans/test-pass-2026-04-22.txt
git add docs/superpowers/plans/test-pass-2026-04-22.txt
git commit -m "test: dashboard/wizard manual test pass notes"
```

(Optional — only if you want a separate audit trail.)

---

## Self-review notes

Plan covers all spec requirements:

- **Routing & shell** — Tasks 1.2, 1.3, 1.4
- **Stores** — Tasks 2.1, 2.2
- **Dashboard** — Tasks 3.1–3.5
- **Brainstorming engine** — Tasks 4.1, 5.3, 5.4, 5.5
- **Multi-agent (Heavy/Dev)** — Tasks 8.1, 8.2
- **Repo provisioning** — Tasks 6.1, 6.2
- **From Data sidecar** — Task 8.3
- **Migration & deletions** — Tasks 9.1, 9.2
- **Manual test plan** — Task 10.1
- **Vitest infra** — Task 0.1, parser test in 4.1, badge test in 2.3, sanitize test in 2.4

**Out-of-scope items the implementer needs to know about:**

1. **Cloudflare Worker proxy endpoints** — `/api/brainstorm/opener`, `/api/brainstorm/questions`, `/api/agent`, `/api/data-analyze`. Add these to the worker repo separately. During SPA development, mock with a vite middleware returning canned shapes that satisfy the parsers.
2. **GitHub OAuth `repo` scope** — verify the existing OAuth login app requests `repo` scope. If not, update the OAuth app config and the login flow's `scope` query param. The plan handles the case where it's missing (radio disabled, re-auth link), but the long-term fix is to request it upfront.
3. **`web/src/components/CreateRepoWizard.tsx`** already exists and overlaps somewhat with `RailWizard`. After Phase 3 lands, decide whether to delete it or keep it for the deeper "advanced repo settings" path. Not addressed in this plan to avoid churn.
