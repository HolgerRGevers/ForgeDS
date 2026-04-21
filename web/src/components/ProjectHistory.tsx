import { useCallback } from "react";
import type { ProjectHistoryProps } from "../types/prompt";

function formatRelativeTime(timestamp: number): string {
  const now = Date.now();
  const diffMs = now - timestamp;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return "Just now";
  if (diffMin < 60) return `${diffMin} minute${diffMin === 1 ? "" : "s"} ago`;
  if (diffHour < 24) return `${diffHour} hour${diffHour === 1 ? "" : "s"} ago`;
  if (diffDay === 1) return "Yesterday";
  if (diffDay < 30) return `${diffDay} days ago`;
  return new Date(timestamp).toLocaleDateString();
}

function truncatePrompt(prompt: string, max = 50): string {
  if (prompt.length <= max) return prompt;
  return prompt.slice(0, max) + "...";
}

export function ProjectHistory({
  items,
  onSelect,
  onDelete,
  onClearAll,
}: ProjectHistoryProps) {
  const handleDelete = useCallback(
    (e: React.MouseEvent, id: string) => {
      e.stopPropagation();
      onDelete(id);
    },
    [onDelete],
  );

  return (
    <div className="w-full rounded-lg border border-gray-700 bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-700 px-4 py-3">
        <h3 className="text-sm font-semibold text-gray-200">
          Project History
          {items.length > 0 && (
            <span className="ml-2 text-xs font-normal text-gray-500">
              ({items.length})
            </span>
          )}
        </h3>
      </div>

      {/* List */}
      {items.length === 0 ? (
        <p className="px-4 py-6 text-center text-xs text-gray-600">
          No projects yet
        </p>
      ) : (
        <ul className="max-h-96 divide-y divide-gray-800 overflow-y-auto">
          {items.map((item) => (
            <li
              key={item.id}
              onClick={() => onSelect(item.id)}
              className="group flex cursor-pointer items-start gap-3 px-4 py-3 transition-colors hover:bg-gray-800/60"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-gray-300">
                  {truncatePrompt(item.prompt)}
                </p>
                <p className="mt-0.5 text-xs text-gray-500">
                  {formatRelativeTime(item.timestamp)} &middot;{" "}
                  {item.fileCount} file{item.fileCount === 1 ? "" : "s"}
                </p>
              </div>
              <button
                type="button"
                onClick={(e) => handleDelete(e, item.id)}
                className="shrink-0 text-gray-600 opacity-0 transition-opacity hover:text-red-400 group-hover:opacity-100"
                aria-label={`Delete project: ${truncatePrompt(item.prompt, 30)}`}
              >
                &times;
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Clear all */}
      {items.length > 0 && (
        <div className="border-t border-gray-700 px-4 py-2 text-center">
          <button
            type="button"
            onClick={onClearAll}
            className="text-xs text-gray-500 transition-colors hover:text-red-400"
          >
            Clear All
          </button>
        </div>
      )}
    </div>
  );
}
