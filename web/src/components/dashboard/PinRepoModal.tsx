import { useEffect, useState } from "react";
import { useRepoStore } from "../../stores/repoStore";
import { useDashboardStore } from "../../stores/dashboardStore";

interface PinRepoModalProps {
  onClose: () => void;
}

export function PinRepoModal({ onClose }: PinRepoModalProps) {
  const { repos, repoLoading, fetchRepos } = useRepoStore();
  const pinRepo = useDashboardStore((s) => s.pinRepo);
  const pinnedRepos = useDashboardStore((s) => s.pinnedRepos);

  const [query, setQuery] = useState("");
  const [pinning, setPinning] = useState<string | null>(null);

  useEffect(() => {
    if (repos.length === 0) fetchRepos();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const filtered = repos.filter((r) =>
    r.full_name.toLowerCase().includes(query.toLowerCase()),
  );

  const handlePin = async (fullName: string) => {
    setPinning(fullName);
    try {
      await pinRepo(fullName);
      onClose();
    } finally {
      setPinning(null);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-lg border border-gray-800 bg-gray-900 p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Pin a repository</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-sm text-gray-400 hover:text-white"
          >
            ×
          </button>
        </div>

        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter repositories…"
          className="mb-3 w-full rounded-md border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white placeholder-gray-500 outline-none focus:border-gray-500"
          autoFocus
        />

        <div className="max-h-64 overflow-y-auto rounded-md border border-gray-700">
          {repoLoading && (
            <p className="px-3 py-2 text-xs text-gray-500">Loading repos…</p>
          )}
          {!repoLoading && filtered.length === 0 && (
            <p className="px-3 py-2 text-xs text-gray-500">No repositories found.</p>
          )}
          {filtered.map((r) => {
            const alreadyPinned = pinnedRepos.includes(r.full_name);
            const isPinning = pinning === r.full_name;
            return (
              <button
                key={r.full_name}
                type="button"
                disabled={alreadyPinned || isPinning}
                onClick={() => handlePin(r.full_name)}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition-colors hover:bg-gray-700 disabled:cursor-default disabled:opacity-50"
              >
                <span className="shrink-0">{r.private ? "\u{1F512}" : "\u{1F4C2}"}</span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-white">{r.full_name}</p>
                  {r.description && (
                    <p className="truncate text-[10px] text-gray-500">{r.description}</p>
                  )}
                </div>
                {alreadyPinned && (
                  <span className="shrink-0 text-[10px] text-gray-500">pinned</span>
                )}
                {isPinning && (
                  <span className="shrink-0 text-[10px] text-gray-500">pinning…</span>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
