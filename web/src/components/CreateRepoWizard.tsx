import { useState } from "react";
import { useRepoStore } from "../stores/repoStore";

interface CreateRepoWizardProps {
  onSelectExisting: () => void;
  onCreated: () => void;
  onCancel: () => void;
}

function isValidRepoName(name: string): boolean {
  return /^[a-zA-Z0-9._-]+$/.test(name) && name.length <= 100;
}

export function CreateRepoWizard({ onSelectExisting, onCreated, onCancel }: CreateRepoWizardProps) {
  const [step, setStep] = useState<"choose" | "form" | "creating">("choose");
  const [repoName, setRepoName] = useState("");
  const [description, setDescription] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);
  const [autoInit, setAutoInit] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const createNewRepo = useRepoStore((s) => s.createNewRepo);

  const handleCreate = async () => {
    if (!repoName.trim()) {
      setError("Repository name is required");
      return;
    }
    if (!isValidRepoName(repoName)) {
      setError("Name can only contain letters, numbers, hyphens, underscores, and dots");
      return;
    }
    setError(null);
    setStep("creating");
    try {
      await createNewRepo(repoName.trim(), description.trim(), isPrivate, autoInit);
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create repository");
      setStep("form");
    }
  };

  if (step === "choose") {
    return (
      <div className="w-72 space-y-2 p-3">
        <p className="text-xs font-medium text-gray-400">Get started</p>
        <button
          type="button"
          onClick={() => setStep("form")}
          className="flex w-full items-center gap-3 rounded-lg border border-gray-700 bg-gray-800 px-3 py-3 text-left text-sm text-gray-200 transition-colors hover:border-blue-500 hover:bg-gray-700"
        >
          <svg className="h-5 w-5 shrink-0 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          <div>
            <p className="font-medium">Create new repository</p>
            <p className="text-[10px] text-gray-500">Start a fresh project on GitHub</p>
          </div>
        </button>
        <button
          type="button"
          onClick={onSelectExisting}
          className="flex w-full items-center gap-3 rounded-lg border border-gray-700 bg-gray-800 px-3 py-3 text-left text-sm text-gray-200 transition-colors hover:border-blue-500 hover:bg-gray-700"
        >
          <svg className="h-5 w-5 shrink-0 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
          </svg>
          <div>
            <p className="font-medium">Select existing repository</p>
            <p className="text-[10px] text-gray-500">Pick from your GitHub repos</p>
          </div>
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="w-full py-1 text-center text-[10px] text-gray-600 hover:text-gray-400"
        >
          Cancel
        </button>
      </div>
    );
  }

  if (step === "creating") {
    return (
      <div className="flex w-72 flex-col items-center gap-3 p-6">
        <svg className="h-6 w-6 animate-spin text-blue-400" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
        </svg>
        <p className="text-sm text-gray-400">Creating repository...</p>
      </div>
    );
  }

  return (
    <div className="w-72 space-y-3 p-3">
      <p className="text-xs font-medium text-gray-400">New repository</p>

      {error && (
        <p className="rounded bg-red-900/30 px-2 py-1 text-xs text-red-400">{error}</p>
      )}

      <div>
        <label className="mb-1 block text-[11px] text-gray-500">Repository name *</label>
        <input
          type="text"
          value={repoName}
          onChange={(e) => setRepoName(e.target.value)}
          placeholder="my-project"
          className="w-full rounded border border-gray-700 bg-gray-900 px-2 py-1.5 text-xs text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none"
          autoFocus
          onKeyDown={(e) => { if (e.key === "Enter") handleCreate(); }}
        />
      </div>

      <div>
        <label className="mb-1 block text-[11px] text-gray-500">Description</label>
        <input
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Optional description"
          className="w-full rounded border border-gray-700 bg-gray-900 px-2 py-1.5 text-xs text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none"
        />
      </div>

      <div>
        <label className="mb-1 block text-[11px] text-gray-500">Visibility</label>
        <div className="flex rounded-lg border border-gray-700">
          <button
            type="button"
            onClick={() => setIsPrivate(false)}
            className={`flex-1 rounded-l-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              !isPrivate ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:text-gray-300"
            }`}
          >
            Public
          </button>
          <button
            type="button"
            onClick={() => setIsPrivate(true)}
            className={`flex-1 rounded-r-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              isPrivate ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:text-gray-300"
            }`}
          >
            Private
          </button>
        </div>
      </div>

      <label className="flex items-center gap-2 text-xs text-gray-400">
        <input
          type="checkbox"
          checked={autoInit}
          onChange={(e) => setAutoInit(e.target.checked)}
          className="rounded border-gray-600 bg-gray-800"
        />
        Initialize with README
      </label>

      <div className="flex gap-2 pt-1">
        <button
          type="button"
          onClick={() => setStep("choose")}
          className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-xs text-gray-400 transition-colors hover:text-gray-200"
        >
          Back
        </button>
        <button
          type="button"
          onClick={handleCreate}
          className="flex-1 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-500"
        >
          Create
        </button>
      </div>
    </div>
  );
}
