import { useState, useEffect } from "react";
import { useRepoStore } from "../../stores/repoStore";
import { CollaboratorsList } from "./CollaboratorsList";
import { BranchManager } from "./BranchManager";
import { CreatePRModal } from "./CreatePRModal";

type Tab = "changes" | "branches" | "team";

export function SourceControlPanel() {
  const {
    selectedRepo,
    pendingChanges,
    commits,
    pullRequests,
    commitChanges,
    discardChanges,
    fetchPullRequests,
  } = useRepoStore();

  const [tab, setTab] = useState<Tab>("changes");
  const [commitMsg, setCommitMsg] = useState("");
  const [isCommitting, setIsCommitting] = useState(false);
  const [showPRModal, setShowPRModal] = useState(false);

  useEffect(() => {
    if (selectedRepo) fetchPullRequests();
  }, [selectedRepo, fetchPullRequests]);

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
      {/* Tab bar */}
      <div className="flex border-b border-gray-800">
        {(["changes", "branches", "team"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`flex-1 px-2 py-1.5 text-center text-[10px] font-medium capitalize transition-colors ${
              tab === t
                ? "border-b-2 border-blue-400 text-white"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {t}
            {t === "changes" && pendingChanges.size > 0 && (
              <span className="ml-1 rounded-full bg-orange-500 px-1 text-[9px] text-white">
                {pendingChanges.size}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto px-3 py-2">
        {/* Changes tab */}
        {tab === "changes" && (
          <div className="space-y-3">
            {/* Pending changes */}
            <div>
              <h3 className="mb-1 font-semibold text-gray-300">
                Changes ({pendingChanges.size})
              </h3>
              {pendingChanges.size === 0 ? (
                <p className="text-gray-500">No pending changes</p>
              ) : (
                <>
                  <div className="max-h-28 space-y-0.5 overflow-y-auto">
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
                          {change.action === "create" ? "+" : change.action === "delete" ? "-" : "~"}
                        </span>
                        <span className="truncate">{change.path}</span>
                      </div>
                    ))}
                  </div>

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
                        className="flex-1 rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-500 disabled:opacity-50"
                      >
                        {isCommitting ? "Committing..." : "Commit & Push"}
                      </button>
                      <button
                        type="button"
                        onClick={discardChanges}
                        className="rounded border border-gray-700 px-2 py-1 text-xs text-gray-400 hover:border-gray-500"
                      >
                        Discard
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Create PR button */}
            <button
              type="button"
              onClick={() => setShowPRModal(true)}
              className="flex w-full items-center justify-center gap-1.5 rounded border border-green-700 bg-green-600/10 px-2 py-1.5 text-xs font-medium text-green-400 transition-colors hover:bg-green-600/20"
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
              </svg>
              Create Pull Request
            </button>

            {/* Open PRs */}
            {pullRequests.length > 0 && (
              <div>
                <h3 className="mb-1 font-semibold text-gray-300">
                  Open PRs ({pullRequests.length})
                </h3>
                <div className="space-y-1">
                  {pullRequests.map((pr) => (
                    <a
                      key={pr.number}
                      href={pr.html_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-start gap-2 rounded px-1 py-1 text-gray-400 hover:bg-gray-800"
                    >
                      <span className="mt-0.5 shrink-0 text-green-400">
                        {pr.draft ? "D" : "#"}{pr.number}
                      </span>
                      <div className="min-w-0">
                        <p className="truncate text-gray-300">{pr.title}</p>
                        <p className="text-[10px] text-gray-500">
                          {pr.headBranch} &rarr; {pr.baseBranch}
                        </p>
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* Recent commits */}
            <div>
              <h3 className="mb-1 font-semibold text-gray-300">Recent Commits</h3>
              {commits.length === 0 ? (
                <p className="text-gray-500">No commits</p>
              ) : (
                <div className="space-y-1.5">
                  {commits.slice(0, 10).map((c) => (
                    <div key={c.sha} className="flex gap-2 text-gray-400">
                      {c.avatar_url && (
                        <img src={c.avatar_url} alt={c.author} className="mt-0.5 h-4 w-4 shrink-0 rounded-full" />
                      )}
                      <div className="min-w-0">
                        <p className="truncate text-gray-300">{c.message}</p>
                        <p className="text-[10px] text-gray-500">
                          {c.author} &middot; {new Date(c.date).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Branches tab */}
        {tab === "branches" && <BranchManager />}

        {/* Team tab */}
        {tab === "team" && <CollaboratorsList />}
      </div>

      {/* PR Modal */}
      {showPRModal && <CreatePRModal onClose={() => setShowPRModal(false)} />}
    </div>
  );
}
