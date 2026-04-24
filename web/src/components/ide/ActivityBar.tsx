import type { ConsoleCategory } from "../../types/ide";

interface ActivityBarProps {
  /** Called for icons A–D (single-panel toggles). */
  onToggle: (panelId: string) => void;
  /** Called for icons E/F (Console Scripts / Dev Tools). */
  onConsoleCategory: (cat: ConsoleCategory) => void;
}

interface IconDef {
  panelId: string | null; // null for console category icons
  category?: ConsoleCategory;
  icon: string; // emoji placeholder (Task 18 swaps for icon set)
  label: string;
}

const ICONS: IconDef[] = [
  { panelId: "repo-explorer", icon: "📁", label: "Repo Explorer" },
  { panelId: "ds-tree", icon: "🌲", label: ".ds Tree" },
  { panelId: "inspector", icon: "🔍", label: "Inspector" },
  { panelId: "source-control", icon: "⇄", label: "Source Control" },
  {
    panelId: null,
    category: "scripts",
    icon: "📜",
    label: "Console — Scripts",
  },
  {
    panelId: null,
    category: "devtools",
    icon: "🛠",
    label: "Console — Dev Tools",
  },
];

export function ActivityBar({
  onToggle,
  onConsoleCategory,
}: ActivityBarProps) {
  return (
    <nav
      aria-label="IDE activity bar"
      className="flex h-full w-12 flex-col items-center gap-1 border-r border-gray-700 bg-gray-900 py-2"
    >
      {ICONS.map((def) => (
        <button
          key={def.label}
          type="button"
          aria-label={def.label}
          title={def.label}
          onClick={() => {
            if (def.panelId) onToggle(def.panelId);
            else if (def.category) onConsoleCategory(def.category);
          }}
          className="flex h-10 w-10 items-center justify-center rounded text-lg text-gray-400 hover:bg-gray-800 hover:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <span aria-hidden="true">{def.icon}</span>
        </button>
      ))}
    </nav>
  );
}
