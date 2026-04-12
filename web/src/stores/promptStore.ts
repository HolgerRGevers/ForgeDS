import { create } from "zustand";
import type { RefinedSection, BuildMessage, CodeFile } from "../types/prompt";
import type { PromptMode } from "../components/ModeToggle";

type WorkflowStage = "input" | "planning" | "refined" | "building" | "complete";

interface PromptState {
  stage: WorkflowStage;
  isLoading: boolean;
  promptText: string;
  mode: PromptMode;
  sections: RefinedSection[];
  buildMessages: BuildMessage[];
  generatedFiles: CodeFile[];
  activeFileIndex: number;
  planSteps: string[];
  rightPanelOpen: boolean;

  setStage: (stage: WorkflowStage) => void;
  setIsLoading: (loading: boolean) => void;
  setPromptText: (text: string) => void;
  setMode: (mode: PromptMode) => void;
  setSections: (sections: RefinedSection[]) => void;
  updateSection: (sectionId: string, updates: Partial<RefinedSection>) => void;
  addBuildMessage: (msg: BuildMessage) => void;
  setBuildMessages: (msgs: BuildMessage[]) => void;
  setGeneratedFiles: (files: CodeFile[]) => void;
  setActiveFileIndex: (index: number) => void;
  setPlanSteps: (steps: string[]) => void;
  setRightPanelOpen: (open: boolean) => void;
  reset: () => void;
}

export const usePromptStore = create<PromptState>((set, get) => ({
  stage: "input",
  isLoading: false,
  promptText: "",
  mode: "plan",
  sections: [],
  buildMessages: [],
  generatedFiles: [],
  activeFileIndex: 0,
  planSteps: [],
  rightPanelOpen: true,

  setStage: (stage) => set({ stage }),
  setIsLoading: (isLoading) => set({ isLoading }),
  setPromptText: (promptText) => set({ promptText }),
  setMode: (mode) => set({ mode }),
  setSections: (sections) => set({ sections }),
  updateSection: (sectionId, updates) => {
    set({
      sections: get().sections.map((s) =>
        s.id === sectionId ? { ...s, ...updates } : s,
      ),
    });
  },
  addBuildMessage: (msg) => {
    set({ buildMessages: [...get().buildMessages, msg] });
  },
  setBuildMessages: (buildMessages) => set({ buildMessages }),
  setGeneratedFiles: (generatedFiles) => set({ generatedFiles }),
  setActiveFileIndex: (activeFileIndex) => set({ activeFileIndex }),
  setPlanSteps: (planSteps) => set({ planSteps }),
  setRightPanelOpen: (rightPanelOpen) => set({ rightPanelOpen }),
  reset: () =>
    set({
      stage: "input",
      isLoading: false,
      promptText: "",
      sections: [],
      buildMessages: [],
      generatedFiles: [],
      activeFileIndex: 0,
      planSteps: [],
    }),
}));
