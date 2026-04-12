import { useState, useCallback } from "react";
import type { RefinedPromptProps, RefinedSection } from "../types/prompt";

interface SectionCardProps {
  section: RefinedSection;
  isOpen: boolean;
  onToggle: () => void;
  onUpdate: (updates: Partial<RefinedSection>) => void;
}

function SectionCard({ section, isOpen, onToggle, onUpdate }: SectionCardProps) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editValue, setEditValue] = useState("");

  const startEdit = useCallback(
    (index: number) => {
      setEditingIndex(index);
      setEditValue(section.items[index]);
    },
    [section.items],
  );

  const commitEdit = useCallback(() => {
    if (editingIndex === null) return;
    const trimmed = editValue.trim();
    if (trimmed && trimmed !== section.items[editingIndex]) {
      const updated = [...section.items];
      updated[editingIndex] = trimmed;
      onUpdate({ items: updated });
    }
    setEditingIndex(null);
    setEditValue("");
  }, [editingIndex, editValue, section.items, onUpdate]);

  const deleteItem = useCallback(
    (index: number) => {
      const updated = section.items.filter((_, i) => i !== index);
      onUpdate({ items: updated });
    },
    [section.items, onUpdate],
  );

  const addItem = useCallback(() => {
    const updated = [...section.items, "New item"];
    onUpdate({ items: updated });
    // Auto-edit the new item
    setTimeout(() => {
      setEditingIndex(updated.length - 1);
      setEditValue("New item");
    }, 0);
  }, [section.items, onUpdate]);

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-900">
      {/* Header */}
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-gray-800/50"
      >
        <span className="text-lg">{section.icon}</span>
        <span className="flex-1 text-sm font-semibold text-gray-100">
          {section.title}
        </span>
        <span className="rounded-full bg-gray-700 px-2 py-0.5 text-xs font-medium text-gray-300">
          {section.items.length}
        </span>
        <svg
          className={`h-4 w-4 text-gray-400 transition-transform ${isOpen ? "rotate-180" : ""}`}
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {/* Expanded body */}
      {isOpen && (
        <div className="border-t border-gray-700 px-4 py-3 space-y-3">
          {/* Content */}
          {section.content && (
            <p className="text-sm leading-relaxed text-gray-400 whitespace-pre-line">
              {section.content}
            </p>
          )}

          {/* Items list */}
          <ul className="space-y-1.5">
            {section.items.map((item, index) => (
              <li
                key={`${section.id}-${index}`}
                className="group flex items-center gap-2 rounded px-2 py-1.5 text-sm text-gray-200 hover:bg-gray-800"
              >
                {editingIndex === index ? (
                  <input
                    type="text"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onBlur={commitEdit}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") commitEdit();
                      if (e.key === "Escape") {
                        setEditingIndex(null);
                        setEditValue("");
                      }
                    }}
                    autoFocus
                    className="flex-1 rounded border border-gray-600 bg-gray-800 px-2 py-0.5 text-sm text-gray-100 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                ) : (
                  <>
                    <span className="flex-1">{item}</span>
                    {section.isEditable && (
                      <span className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                        <button
                          type="button"
                          onClick={() => startEdit(index)}
                          className="rounded p-0.5 text-gray-500 hover:text-blue-400"
                          aria-label={`Edit ${item}`}
                          title="Edit"
                        >
                          <svg
                            className="h-3.5 w-3.5"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                          >
                            <path d="M2.695 14.763l-1.262 3.154a.5.5 0 00.65.65l3.155-1.262a4 4 0 001.343-.885L17.5 5.5a2.121 2.121 0 00-3-3L3.58 13.42a4 4 0 00-.885 1.343z" />
                          </svg>
                        </button>
                        <button
                          type="button"
                          onClick={() => deleteItem(index)}
                          className="rounded p-0.5 text-gray-500 hover:text-red-400"
                          aria-label={`Delete ${item}`}
                          title="Delete"
                        >
                          <svg
                            className="h-3.5 w-3.5"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                          >
                            <path
                              fillRule="evenodd"
                              d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.52.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z"
                              clipRule="evenodd"
                            />
                          </svg>
                        </button>
                      </span>
                    )}
                  </>
                )}
              </li>
            ))}
          </ul>

          {/* Add item button */}
          {section.isEditable && (
            <button
              type="button"
              onClick={addItem}
              className="flex items-center gap-1.5 rounded px-2 py-1 text-xs text-gray-400 hover:text-gray-200"
            >
              <svg
                className="h-3.5 w-3.5"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z" />
              </svg>
              Add item
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function RefinedPrompt({
  sections,
  onSectionUpdate,
  onConfirm,
  onStartOver,
}: RefinedPromptProps) {
  const [openSections, setOpenSections] = useState<Set<string>>(
    () => new Set(sections.map((s) => s.id)),
  );

  const toggleSection = useCallback((id: string) => {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  return (
    <div className="w-full space-y-4">
      {/* Section cards */}
      <div className="space-y-3">
        {sections.map((section) => (
          <SectionCard
            key={section.id}
            section={section}
            isOpen={openSections.has(section.id)}
            onToggle={() => toggleSection(section.id)}
            onUpdate={(updates) => onSectionUpdate(section.id, updates)}
          />
        ))}
      </div>

      {/* Action buttons */}
      <div className="flex gap-3 pt-2">
        <button
          type="button"
          onClick={onStartOver}
          className="flex-1 rounded-lg border border-gray-600 bg-transparent px-4 py-3 text-sm font-semibold text-gray-300 transition-colors hover:border-gray-400 hover:text-gray-100"
        >
          Start Over
        </button>
        <button
          type="button"
          onClick={onConfirm}
          className="flex-1 rounded-lg bg-green-600 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-green-500"
        >
          Build This App
        </button>
      </div>
    </div>
  );
}
