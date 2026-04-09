export type PromptMode = "plan" | "code";

interface ModeToggleProps {
  mode: PromptMode;
  onChange: (mode: PromptMode) => void;
}

/**
 * Plan / Code mode toggle — mirrors Claude's prompt mode selector.
 * Plan mode: AI analyzes and outlines before generating code.
 * Code mode: AI generates Deluge code directly.
 */
export function ModeToggle({ mode, onChange }: ModeToggleProps) {
  return (
    <div className="inline-flex rounded-full border border-gray-700 bg-gray-800 p-0.5">
      <button
        type="button"
        onClick={() => onChange("plan")}
        className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
          mode === "plan"
            ? "bg-blue-600 text-white shadow-sm"
            : "text-gray-400 hover:text-gray-200"
        }`}
      >
        Plan
      </button>
      <button
        type="button"
        onClick={() => onChange("code")}
        className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
          mode === "code"
            ? "bg-blue-600 text-white shadow-sm"
            : "text-gray-400 hover:text-gray-200"
        }`}
      >
        Code
      </button>
    </div>
  );
}
