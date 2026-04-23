export interface WorkflowFormEntry {
  id: string;
  label: string;
}

interface WorkflowFormSidebarProps {
  /** Forms that have at least one item of the current workflow type. */
  formsWith: WorkflowFormEntry[];
  /** Forms with no items of the current workflow type. */
  formsWithout: WorkflowFormEntry[];
  selectedFormId: string | null;
  onSelect: (id: string) => void;
}

export function WorkflowFormSidebar({
  formsWith,
  formsWithout,
  selectedFormId,
  onSelect,
}: WorkflowFormSidebarProps) {
  if (formsWith.length === 0 && formsWithout.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-3 text-xs text-gray-500">
        No forms available
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-gray-900 text-xs">
      {formsWith.length > 0 && (
        <div className="px-2 py-2">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-500">
            Forms with
          </div>
          {formsWith.map((f) => (
            <FormRow
              key={f.id}
              entry={f}
              selected={f.id === selectedFormId}
              onClick={() => onSelect(f.id)}
            />
          ))}
        </div>
      )}
      {formsWithout.length > 0 && (
        <div className="px-2 py-2 border-t border-gray-700/50">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-500">
            Forms without
          </div>
          {formsWithout.map((f) => (
            <FormRow
              key={f.id}
              entry={f}
              selected={f.id === selectedFormId}
              onClick={() => onSelect(f.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function FormRow({
  entry,
  selected,
  onClick,
}: {
  entry: WorkflowFormEntry;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`block w-full truncate rounded px-2 py-1 text-left text-[11px] hover:bg-gray-700/50 ${
        selected ? "bg-gray-700 text-indigo-300" : "text-gray-300"
      }`}
    >
      {entry.label}
    </button>
  );
}
