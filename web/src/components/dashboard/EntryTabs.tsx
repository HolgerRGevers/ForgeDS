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
