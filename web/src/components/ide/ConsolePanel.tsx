import { useEffect, useRef, useState } from "react";
import { useIdeStore } from "../../stores/ideStore";
import type { ConsoleCategory, ConsoleTab, ScriptsTab } from "../../types/ide";
import { CompleteScriptView } from "./CompleteScriptView";
import { WorkflowTabView, type WorkflowType } from "./WorkflowTabView";
import { DevToolsCategory } from "./DevToolsCategory";

const NARROW_THRESHOLD = 400;

const SCRIPTS_TABS: { id: ScriptsTab; label: string }[] = [
  { id: "complete", label: "Complete Script" },
  { id: "form-workflows", label: "Form Workflows" },
  { id: "schedules", label: "Schedules" },
  { id: "approvals", label: "Approvals" },
  { id: "payments", label: "Payments" },
  { id: "blueprints", label: "Blueprints" },
  { id: "batch-workflows", label: "Batch Workflows" },
  { id: "functions", label: "Functions" },
];

const DEVTOOLS_TABS: { id: ConsoleTab; label: string }[] = [
  { id: "lint", label: "Lint" },
  { id: "build", label: "Build" },
  { id: "relationships", label: "Relationships" },
  { id: "ai", label: "AI Chat" },
];

interface ConsolePanelProps {
  /** Test hook — override width detection. Production callers pass dockview's panel width. */
  containerWidth?: number;
}

export function ConsolePanel({ containerWidth }: ConsolePanelProps) {
  const activeConsoleCategory = useIdeStore((s) => s.activeConsoleCategory);
  const activeScriptsTab = useIdeStore((s) => s.activeScriptsTab);
  const activeDevToolsTab = useIdeStore((s) => s.activeDevToolsTab);
  const setActiveConsoleCategory = useIdeStore((s) => s.setActiveConsoleCategory);
  const setActiveScriptsTab = useIdeStore((s) => s.setActiveScriptsTab);
  const setActiveDevToolsTab = useIdeStore((s) => s.setActiveDevToolsTab);

  const rootRef = useRef<HTMLDivElement>(null);
  const [measuredWidth, setMeasuredWidth] = useState<number | null>(null);

  useEffect(() => {
    if (containerWidth !== undefined) return;
    if (!rootRef.current) return;
    const el = rootRef.current;
    const observer = new ResizeObserver((entries) => {
      for (const e of entries) setMeasuredWidth(e.contentRect.width);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [containerWidth]);

  const effectiveWidth = containerWidth ?? measuredWidth ?? 800;
  const narrow = effectiveWidth < NARROW_THRESHOLD;

  return (
    <div ref={rootRef} className="flex h-full flex-col bg-gray-800">
      {narrow ? (
        <NarrowHeader
          category={activeConsoleCategory}
          scriptsTab={activeScriptsTab}
          devToolsTab={activeDevToolsTab}
          onCategoryChange={setActiveConsoleCategory}
          onScriptsTabChange={setActiveScriptsTab}
          onDevToolsTabChange={setActiveDevToolsTab}
        />
      ) : (
        <WideHeader
          category={activeConsoleCategory}
          scriptsTab={activeScriptsTab}
          devToolsTab={activeDevToolsTab}
          onCategoryChange={setActiveConsoleCategory}
          onScriptsTabChange={setActiveScriptsTab}
          onDevToolsTabChange={setActiveDevToolsTab}
        />
      )}
      <div className="min-h-0 flex-1">
        {activeConsoleCategory === "scripts" ? (
          activeScriptsTab === "complete" ? (
            <CompleteScriptView />
          ) : (
            <WorkflowTabView workflowType={activeScriptsTab as WorkflowType} />
          )
        ) : (
          <DevToolsCategory />
        )}
      </div>
    </div>
  );
}

interface HeaderProps {
  category: ConsoleCategory;
  scriptsTab: ScriptsTab;
  devToolsTab: ConsoleTab;
  onCategoryChange: (c: ConsoleCategory) => void;
  onScriptsTabChange: (t: ScriptsTab) => void;
  onDevToolsTabChange: (t: ConsoleTab) => void;
}

function WideHeader(props: HeaderProps) {
  const { category, scriptsTab, devToolsTab, onCategoryChange, onScriptsTabChange, onDevToolsTabChange } = props;
  const subTabs = category === "scripts" ? SCRIPTS_TABS : DEVTOOLS_TABS;
  const active = category === "scripts" ? scriptsTab : devToolsTab;

  return (
    <div>
      <div role="tablist" className="flex items-center gap-1 border-b border-gray-700 px-2 py-1">
        <CategoryTab
          active={category === "scripts"}
          onClick={() => onCategoryChange("scripts")}
          label="Scripts"
        />
        <CategoryTab
          active={category === "devtools"}
          onClick={() => onCategoryChange("devtools")}
          label="Dev Tools"
        />
      </div>
      <div role="tablist" className="flex items-center gap-0 overflow-x-auto border-b border-gray-700/50">
        {subTabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={active === t.id}
            onClick={() => {
              if (category === "scripts") onScriptsTabChange(t.id as ScriptsTab);
              else onDevToolsTabChange(t.id as ConsoleTab);
            }}
            className={`whitespace-nowrap border-b-2 px-3 py-1.5 text-xs font-medium transition-colors ${
              active === t.id
                ? "border-indigo-400 text-indigo-300"
                : "border-transparent text-gray-500 hover:text-gray-300"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function CategoryTab({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`rounded px-3 py-1 text-xs font-medium ${
        active ? "bg-gray-700 text-gray-100" : "text-gray-400 hover:bg-gray-700/50 hover:text-gray-200"
      }`}
    >
      {label}
    </button>
  );
}

function NarrowHeader(props: HeaderProps) {
  const { category, scriptsTab, devToolsTab, onCategoryChange, onScriptsTabChange, onDevToolsTabChange } = props;
  const subTabs = category === "scripts" ? SCRIPTS_TABS : DEVTOOLS_TABS;
  const active = category === "scripts" ? scriptsTab : devToolsTab;

  return (
    <div className="flex flex-col gap-1 border-b border-gray-700 px-2 py-1 text-xs">
      <label className="flex items-center gap-2">
        <span className="text-[10px] uppercase tracking-wider text-gray-500">Category</span>
        <select
          aria-label="Category"
          value={category}
          onChange={(e) => onCategoryChange(e.target.value as ConsoleCategory)}
          className="flex-1 rounded bg-gray-700 px-2 py-0.5 text-gray-200"
        >
          <option value="scripts">Scripts</option>
          <option value="devtools">Dev Tools</option>
        </select>
      </label>
      <label className="flex items-center gap-2">
        <span className="text-[10px] uppercase tracking-wider text-gray-500">Sub-tab</span>
        <select
          aria-label="Sub-tab"
          value={active}
          onChange={(e) => {
            if (category === "scripts") onScriptsTabChange(e.target.value as ScriptsTab);
            else onDevToolsTabChange(e.target.value as ConsoleTab);
          }}
          className="flex-1 rounded bg-gray-700 px-2 py-0.5 text-gray-200"
        >
          {subTabs.map((t) => (
            <option key={t.id} value={t.id}>
              {t.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
