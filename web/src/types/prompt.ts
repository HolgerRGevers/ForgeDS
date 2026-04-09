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

/** Props for the PromptInput component. */
export interface PromptInputProps {
  onSubmit: (prompt: string, files: File[]) => void;
  isLoading: boolean;
}
