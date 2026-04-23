export interface WorkflowRow {
  id: string;
  name: string;
  status: string;
  createdOn: string;
  filePath: string;
}

interface WorkflowDetailTableProps {
  /** Human label for the current tab (e.g., "Blueprints", "Schedules"). */
  workflowTypeLabel: string;
  rows: WorkflowRow[];
  onRowClick: (row: WorkflowRow) => void;
}

export function WorkflowDetailTable({
  workflowTypeLabel,
  rows,
  onRowClick,
}: WorkflowDetailTableProps) {
  if (rows.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-xs text-gray-500">
        No {workflowTypeLabel.toLowerCase()} found in this app.
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="sticky top-0 grid grid-cols-[1fr_120px_140px] gap-2 border-b border-gray-700 bg-gray-900 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-gray-500">
        <span>Name</span>
        <span>Status</span>
        <span>Created</span>
      </div>
      {rows.map((row) => (
        <button
          key={row.id}
          type="button"
          onClick={() => onRowClick(row)}
          className="grid w-full grid-cols-[1fr_120px_140px] gap-2 border-b border-gray-700/30 px-3 py-1.5 text-left text-xs text-gray-300 hover:bg-gray-700/30"
        >
          <span className="truncate text-indigo-300 hover:text-indigo-200">{row.name}</span>
          <span className="truncate text-gray-400">{row.status}</span>
          <span className="truncate font-mono text-gray-500">{row.createdOn}</span>
        </button>
      ))}
    </div>
  );
}
