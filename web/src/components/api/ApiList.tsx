import { useCallback, useState } from "react";
import { useApiStore } from "../../stores/apiStore";
import type { CustomApiDefinition, HttpMethod } from "../../types/api";

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const METHOD_COLORS: Record<HttpMethod, string> = {
  GET: "bg-green-700 text-green-100",
  POST: "bg-blue-700 text-blue-100",
  PUT: "bg-yellow-700 text-yellow-100",
  DELETE: "bg-red-700 text-red-100",
};

function relativeTime(timestamp: number): string {
  const diff = Date.now() - timestamp;
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + "...";
}

/* ------------------------------------------------------------------ */
/*  API Card                                                           */
/* ------------------------------------------------------------------ */

function ApiCard({
  api,
  isSelected,
  onSelect,
  onDelete,
}: {
  api: CustomApiDefinition;
  isSelected: boolean;
  onSelect: () => void;
  onDelete: () => void;
}) {
  const [showConfirm, setShowConfirm] = useState(false);

  const authLabel = api.auth === "oauth2" ? "OAuth2" : "Public Key";
  const scopeLabel = api.userScope.replace(/_/g, " ");

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
      className={`group relative cursor-pointer rounded-lg border p-4 transition-colors ${
        isSelected
          ? "border-blue-500 bg-gray-800"
          : "border-gray-700 bg-gray-900 hover:border-gray-600 hover:bg-gray-800/50"
      }`}
    >
      {/* Top row: name + method badge */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${METHOD_COLORS[api.method]}`}
          >
            {api.method}
          </span>
          <span className="text-sm font-semibold text-white">{api.name}</span>
        </div>

        {/* Delete button (visible on hover or when confirming) */}
        <div className="flex items-center gap-1">
          {showConfirm ? (
            <>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete();
                  setShowConfirm(false);
                }}
                className="rounded bg-red-600 px-2 py-0.5 text-[10px] font-medium text-white hover:bg-red-500"
              >
                Confirm
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowConfirm(false);
                }}
                className="rounded bg-gray-700 px-2 py-0.5 text-[10px] font-medium text-gray-300 hover:bg-gray-600"
              >
                Cancel
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setShowConfirm(true);
              }}
              className="rounded p-1 text-gray-500 opacity-0 transition-opacity hover:bg-gray-700 hover:text-red-400 group-hover:opacity-100"
              title="Delete API"
            >
              {/* Trash icon (SVG) */}
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z"
                  clipRule="evenodd"
                />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Auth + scope badges */}
      <div className="mt-2 flex items-center gap-2">
        <span className="rounded bg-gray-700 px-1.5 py-0.5 text-[10px] font-medium text-gray-300">
          {authLabel}
        </span>
        <span className="text-xs text-gray-400">{scopeLabel}</span>
      </div>

      {/* Description */}
      {api.description && (
        <p className="mt-2 text-xs text-gray-400">
          {truncate(api.description, 120)}
        </p>
      )}

      {/* Timestamp */}
      <p className="mt-2 text-[10px] text-gray-500">
        Updated {relativeTime(api.updatedAt)}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main list component                                                */
/* ------------------------------------------------------------------ */

export function ApiList() {
  const apis = useApiStore((s) => s.apis);
  const selectedApiId = useApiStore((s) => s.selectedApiId);
  const selectApi = useApiStore((s) => s.selectApi);
  const startEdit = useApiStore((s) => s.startEdit);
  const startCreate = useApiStore((s) => s.startCreate);
  const deleteApi = useApiStore((s) => s.deleteApi);

  const handleSelect = useCallback(
    (id: string) => {
      selectApi(id);
      startEdit(id);
    },
    [selectApi, startEdit],
  );

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-lg border border-gray-700 bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-700 px-4 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-white">Custom APIs</h2>
          <span className="rounded-full bg-gray-700 px-2 py-0.5 text-[10px] font-bold text-gray-300">
            {apis.length}
          </span>
        </div>
        <button
          type="button"
          onClick={startCreate}
          className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-500"
        >
          + New API
        </button>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {apis.length === 0 ? (
          <div className="flex h-full items-center justify-center text-center text-sm text-gray-500">
            No APIs configured yet. Click &quot;+ New API&quot; to get started.
          </div>
        ) : (
          apis.map((api) => (
            <ApiCard
              key={api.id}
              api={api}
              isSelected={selectedApiId === api.id}
              onSelect={() => handleSelect(api.id)}
              onDelete={() => deleteApi(api.id)}
            />
          ))
        )}
      </div>
    </div>
  );
}
