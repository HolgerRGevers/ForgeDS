/** A single section within the AI-refined prompt breakdown. */
export interface RefinedSection {
  id: string;
  title: string;
  icon: string;
  content: string;
  items: string[];
  isEditable: boolean;
}

/** Props for the RefinedPrompt component. */
export interface RefinedPromptProps {
  sections: RefinedSection[];
  onSectionUpdate: (
    sectionId: string,
    updates: Partial<RefinedSection>,
  ) => void;
  onConfirm: () => void;
  onStartOver: () => void;
}

/** A file attached from a GitHub repository. */
export interface RepoFile {
  path: string;
  content: string;
  repoName: string;
}

/** Props for the PromptInput component. */
export interface PromptInputProps {
  onSubmit: (prompt: string, files: File[], repoFiles: RepoFile[]) => void;
  isLoading: boolean;
  mode: "plan" | "code";
  onModeChange: (mode: "plan" | "code") => void;
}

/** A single progress message displayed during build. */
export interface BuildMessage {
  timestamp: string;
  text: string;
  type: "info" | "success" | "error" | "warning";
}

/** Props for the BuildProgress component. */
export interface BuildProgressProps {
  messages: BuildMessage[];
  isBuilding: boolean;
  isComplete: boolean;
  onOpenIDE: () => void;
}

/** A generated code file for preview. */
export interface CodeFile {
  name: string;
  path: string;
  content: string;
  language: string;
}

/** Props for the CodePreview component. */
export interface CodePreviewProps {
  files: CodeFile[];
  activeFileIndex: number;
  onFileSelect: (index: number) => void;
}

/** A saved project generation entry. */
export interface ProjectHistoryItem {
  id: string;
  prompt: string;
  timestamp: number;
  fileCount: number;
}

/** Props for the ProjectHistory component. */
export interface ProjectHistoryProps {
  items: ProjectHistoryItem[];
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onClearAll: () => void;
}
