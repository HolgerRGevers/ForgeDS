import { useState } from "react";
import { useRepoStore } from "../../stores/repoStore";

interface CreatePRModalProps {
  onClose: () => void;
}

export function CreatePRModal({ onClose }: CreatePRModalProps) {
  const { selectedRepo, selectedBranch, branches, pendingChanges, createPR } =
    useRepoStore();

  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [baseBranch, setBaseBranch] = useState(
    selectedRepo?.default_branch ?? "main",
  );
  const [draft, setDraft] = useState(false);
  const [creating, setCreating] = useState(false);
  const [prUrl, setPrUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canCreate =
    title.trim() &&
    selectedBranch !== baseBranch &&
    selectedRepo;

  const handleCreate = async () => {
    if (!canCreate) return;
    setCreating(true);
    setError(null);
    try {
      const url = await createPR(title.trim(), body.trim(), baseBranch, draft);
      setPrUrl(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "PR creation failed");
    } finally {
      setCreating(false);
    }
  };

  // Success state
  if (prUrl) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
        <div className="w-full max-w-md rounded-xl border border-gray-700 bg-gray-900 p-6 shadow-2xl">
          <div className="mb-4 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-green-500/20">
              <svg className="h-6 w-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-sm font-semibold text-white">
              Pull Request Created
            </h2>
          </div>
          <a
            href={prUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="mb-4 block truncate rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-center text-xs text-blue-400 hover:text-blue-300"
          >
            {prUrl}
          </a>
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-lg bg-gray-800 px-4 py-2 text-xs font-medium text-white hover:bg-gray-700"
          >
            Done
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-full max-w-lg rounded-xl border border-gray-700 bg-gray-900 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-800 px-5 py-3">
          <h2 className="text-sm font-semibold text-white">
            Create Pull Request
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-500 hover:text-white"
          >
            &times;
          </button>
        </div>

        {/* Body */}
        <div className="space-y-3 px-5 py-4">
          {/* Branch info */}
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <span className="rounded bg-gray-800 px-2 py-0.5 font-mono text-blue-300">
              {selectedBranch}
            </span>
            <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
            <select
              value={baseBranch}
              onChange={(e) => setBaseBranch(e.target.value)}
              className="rounded bg-gray-800 px-2 py-0.5 font-mono text-xs text-green-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {branches
                .filter((b) => b.name !== selectedBranch)
                .map((b) => (
                  <option key={b.name} value={b.name}>
                    {b.name}
                  </option>
                ))}
            </select>
          </div>

          {selectedBranch === baseBranch && (
            <p className="text-xs text-red-400">
              Head and base branch must be different
            </p>
          )}

          {/* Title */}
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="PR title"
            className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />

          {/* Body */}
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Description (markdown supported)"
            rows={5}
            className="w-full resize-y rounded-lg bg-gray-800 px-3 py-2 text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />

          {/* Draft toggle */}
          <label className="flex items-center gap-2 text-xs text-gray-400">
            <input
              type="checkbox"
              checked={draft}
              onChange={(e) => setDraft(e.target.checked)}
              className="rounded border-gray-600 bg-gray-800"
            />
            Create as draft
          </label>

          {/* Pending changes warning */}
          {pendingChanges.size > 0 && (
            <p className="text-xs text-orange-400">
              You have {pendingChanges.size} uncommitted change
              {pendingChanges.size !== 1 ? "s" : ""}. Commit them first.
            </p>
          )}

          {error && (
            <p className="text-xs text-red-400">{error}</p>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 border-t border-gray-800 px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-gray-700 px-3 py-1.5 text-xs text-gray-400 hover:border-gray-500"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleCreate}
            disabled={!canCreate || creating}
            className="rounded bg-green-600 px-4 py-1.5 text-xs font-medium text-white transition-colors hover:bg-green-500 disabled:opacity-50"
          >
            {creating
              ? "Creating..."
              : draft
                ? "Create Draft PR"
                : "Create Pull Request"}
          </button>
        </div>
      </div>
    </div>
  );
}
