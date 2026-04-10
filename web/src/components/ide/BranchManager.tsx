import { useState } from "react";
import { useRepoStore } from "../../stores/repoStore";

export function BranchManager() {
  const {
    selectedRepo,
    selectedBranch,
    branches,
    selectBranch,
    createBranch,
    deleteBranch,
  } = useRepoStore();

  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  if (!selectedRepo) return null;

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await createBranch(newName.trim());
      setNewName("");
      setShowCreate(false);
    } catch (err) {
      console.error("Branch creation failed:", err);
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (name: string) => {
    try {
      await deleteBranch(name);
      setConfirmDelete(null);
    } catch (err) {
      console.error("Branch deletion failed:", err);
    }
  };

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-gray-300">Branches</h3>
        <button
          type="button"
          onClick={() => setShowCreate((v) => !v)}
          className="text-[10px] text-blue-400 hover:text-blue-300"
        >
          {showCreate ? "Cancel" : "+ New"}
        </button>
      </div>

      {/* New branch form */}
      {showCreate && (
        <div className="flex gap-1">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="branch-name"
            className="min-w-0 flex-1 rounded bg-gray-800 px-2 py-1 text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
            onKeyDown={(e) => {
              if (e.key === "Enter") handleCreate();
            }}
          />
          <button
            type="button"
            onClick={handleCreate}
            disabled={!newName.trim() || creating}
            className="rounded bg-blue-600 px-2 py-1 text-[10px] font-medium text-white hover:bg-blue-500 disabled:opacity-50"
          >
            {creating ? "..." : "Create"}
          </button>
        </div>
      )}

      {/* Branch list */}
      <div className="max-h-40 space-y-0.5 overflow-y-auto">
        {branches.map((b) => (
          <div
            key={b.name}
            className={`flex items-center gap-1 rounded px-1 py-0.5 text-xs ${
              b.name === selectedBranch
                ? "bg-blue-600/20 text-blue-300"
                : "text-gray-400"
            }`}
          >
            <button
              type="button"
              onClick={() => selectBranch(b.name)}
              className="min-w-0 flex-1 truncate text-left hover:text-white"
              title={b.name}
            >
              {b.name === selectedBranch && (
                <span className="mr-1 text-blue-400">&bull;</span>
              )}
              {b.name}
            </button>
            {b.protected && (
              <span className="shrink-0 text-[9px] text-yellow-500" title="Protected">
                lock
              </span>
            )}
            {!b.protected && b.name !== selectedBranch && (
              <>
                {confirmDelete === b.name ? (
                  <button
                    type="button"
                    onClick={() => handleDelete(b.name)}
                    className="shrink-0 text-[9px] font-bold text-red-400 hover:text-red-300"
                  >
                    confirm?
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(b.name)}
                    className="shrink-0 text-[9px] text-gray-600 hover:text-red-400"
                    title="Delete branch"
                  >
                    &times;
                  </button>
                )}
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
