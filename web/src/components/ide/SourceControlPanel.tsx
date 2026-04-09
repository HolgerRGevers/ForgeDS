import { useState } from "react";
import { useRepoStore } from "../../stores/repoStore";

export function SourceControlPanel() {
  const {
    selectedRepo,
    pendingChanges,
    commits,
    commitChanges,
    discardChanges,
  } = useRepoStore();

  const [commitMsg, setCommitMsg] = useState("");
  const [isCommitting, setIsCommitting] = useState(false);

  const handleCommit = async () => {
    if (!commitMsg.trim() || pendingChanges.size === 0) return;
    setIsCommitting(true);
    try {
      await commitChanges(commitMsg.trim());
      setCommitMsg("");
    } catch (err) {
      console.error("Commit failed:", err);
    } finally {
      setIsCommitting(false);
    }
  };

  if (!selectedRepo) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-xs text-gray-500">No repository selected</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden text-xs">
      {/* Pending changes */}
      <div className="border-b border-gray-800 px-3 py-2">
        <h3 className="mb-2 font-semibold text-gray-300">
          Changes ({pendingChanges.size})
        </h3>

        {pendingChanges.size === 0 ? (
          <p className="text-gray-500">No pending changes</p>
        ) : (
          <>
            <div className="max-h-32 space-y-0.5 overflow-y-auto">
              {Array.from(pendingChanges.values()).map((change) => (
                <div
                  key={change.path}
                  className="flex items-center gap-2 rounded px-1 py-0.5 text-gray-300"
                >
                  <span
                    className={`shrink-0 font-mono font-bold ${
                      change.action === "create"
                        ? "text-green-400"
                        : change.action === "delete"
                          ? "text-red-400"
                          : "text-orange-400"
                    }`}
                  >
                    {change.action === "create"
                      ? "+"
                      : change.action === "delete"
                        ? "-"
                        : "~"}
                  </span>
                  <span className="truncate">{change.path}</span>
                </div>
              ))}
            </div>

            {/* Commit form */}
            <div className="mt-2 space-y-1.5">
              <input
                type="text"
                value={commitMsg}
                onChange={(e) => setCommitMsg(e.target.value)}
                placeholder="Commit message..."
                className="w-full rounded bg-gray-800 px-2 py-1.5 text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleCommit();
                  }
                }}
              />
              <div className="flex gap-1.5">
                <button
                  type="button"
                  onClick={handleCommit}
                  disabled={!commitMsg.trim() || isCommitting}
                  className="flex-1 rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white transition-colors hover:bg-blue-500 disabled:opacity-50"
                >
                  {isCommitting ? "Committing..." : "Commit & Push"}
                </button>
                <button
                  type="button"
                  onClick={discardChanges}
                  className="rounded border border-gray-700 px-2 py-1 text-xs text-gray-400 transition-colors hover:border-gray-500 hover:text-gray-300"
                >
                  Discard
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Recent commits */}
      <div className="flex-1 overflow-y-auto px-3 py-2">
        <h3 className="mb-2 font-semibold text-gray-300">Recent Commits</h3>
        {commits.length === 0 ? (
          <p className="text-gray-500">No commits</p>
        ) : (
          <div className="space-y-2">
            {commits.slice(0, 15).map((c) => (
              <div key={c.sha} className="flex gap-2 text-gray-400">
                {c.avatar_url && (
                  <img
                    src={c.avatar_url}
                    alt={c.author}
                    className="mt-0.5 h-4 w-4 shrink-0 rounded-full"
                  />
                )}
                <div className="min-w-0">
                  <p className="truncate text-gray-300">{c.message}</p>
                  <p className="text-[10px] text-gray-500">
                    {c.author} &middot;{" "}
                    {new Date(c.date).toLocaleDateString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
