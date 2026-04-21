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

type PersistedShape = Pick<
  WizardState,
  | "entryTab"
  | "projectName"
  | "targetMode"
  | "targetRepoFullName"
  | "step"
  | "depth"
  | "coreIdea"
  | "midSeedAnswers"
  | "opener"
  | "questions"
  | "currentQuestionIdx"
  | "answers"
  | "dataAnalysis"
>;

function persistedFields(s: WizardState): PersistedShape {
  // Files and Promises don't survive JSON serialization; persist only the
  // scalar/object/array fields the user would want back on refresh.
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

function persist(state: WizardState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(persistedFields(state)));
  } catch {
    // ignore quota errors
  }
}

const initialState = {
  entryTab: "prototype" as EntryTab,
  projectName: "",
  targetMode: "create-new" as const,
  targetRepoFullName: null,
  attachments: [] as File[],
  step: "idea" as WizardStep,
  depth: null as WizardDepth | null,
  coreIdea: "",
  midSeedAnswers: [] as string[],
  opener: null as { gist: string; shell: string } | null,
  questions: [] as WizardQuestion[],
  currentQuestionIdx: 0,
  answers: {} as Record<string, "A" | "B" | string>,
  buildMessages: [] as BuildMessage[],
  generatedFiles: [] as GeneratedFile[],
  fanoutDrafts: [] as Array<{ agent: string; spec: string; rationale: string }>,
  personaCritiques: [] as Array<{ persona: string; notes: string }>,
  dataAnalysis: null as DataAnalysis | null,
  dataIngestionStatus: "idle" as const,
  repoCreationStatus: "idle" as const,
  repoCreationError: null as string | null,
  createdRepoFullName: null as string | null,
  repoCreationPromise: null as Promise<string> | null,
};

export const useWizardStore = create<WizardState>((set, get) => {
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
});

export { LEGACY_HISTORY_KEY };
