import { useEffect } from "react";
import { useRepoStore } from "../../stores/repoStore";

export function CollaboratorsList() {
  const { selectedRepo, collaborators, fetchCollaborators } = useRepoStore();

  useEffect(() => {
    if (selectedRepo) fetchCollaborators();
  }, [selectedRepo, fetchCollaborators]);

  if (!selectedRepo) return null;

  return (
    <div className="space-y-1.5">
      <h3 className="text-xs font-semibold text-gray-300">Team</h3>
      {collaborators.length === 0 ? (
        <p className="text-[11px] text-gray-500">No collaborators</p>
      ) : (
        <div className="space-y-1">
          {collaborators.map((c) => (
            <a
              key={c.login}
              href={`https://github.com/${c.login}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 rounded px-1 py-0.5 text-xs text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-200"
            >
              <img
                src={c.avatar_url}
                alt={c.login}
                className="h-4 w-4 rounded-full"
              />
              <span className="truncate">{c.login}</span>
              <span
                className={`ml-auto shrink-0 rounded px-1 py-0.5 text-[9px] font-medium ${
                  c.role === "admin"
                    ? "bg-purple-500/20 text-purple-400"
                    : c.role === "write"
                      ? "bg-green-500/20 text-green-400"
                      : "bg-gray-700 text-gray-500"
                }`}
              >
                {c.role}
              </span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
