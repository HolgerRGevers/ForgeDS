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
