import { useState } from "react";
import { useSkillStore } from "../stores/skillStore";
import { MARKETPLACE_REPOS, type MarketplaceRepo } from "../data/marketplace-repos";

interface SkillMarketplaceProps {
  onClose: () => void;
}

export function SkillMarketplace({ onClose }: SkillMarketplaceProps) {
  const {
    installedRepos,
    githubSkills,
    importLoading,
    importError,
    loadSkillsFromRepo,
    removeImportedRepo,
  } = useSkillStore();

  const [tab, setTab] = useState<"featured" | "custom" | "installed">("featured");
  const [customUrl, setCustomUrl] = useState("");
  const [lastImportCount, setLastImportCount] = useState<number | null>(null);

  const handleInstall = async (r: MarketplaceRepo) => {
    setLastImportCount(null);
    const count = await loadSkillsFromRepo(r.owner, r.repo);
    setLastImportCount(count);
  };

  const handleCustomImport = async () => {
    if (!customUrl.trim()) return;
    setLastImportCount(null);

    // Parse "owner/repo" or "owner/repo/path"
    const parts = customUrl.trim().replace(/^https?:\/\/github\.com\//, "").split("/");
    if (parts.length < 2) return;

    const owner = parts[0];
    const repo = parts[1];
    const path = parts.length > 2 ? parts.slice(2).join("/") : "skills";

    const count = await loadSkillsFromRepo(owner, repo, path);
    setLastImportCount(count);
    if (count > 0) setCustomUrl("");
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="flex max-h-[80vh] w-full max-w-2xl flex-col rounded-xl border border-gray-700 bg-gray-900 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-800 px-5 py-3">
          <h2 className="text-sm font-semibold text-white">
            Skills Marketplace
          </h2>
          <button type="button" onClick={onClose} className="text-gray-500 hover:text-white">
            &times;
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-800">
          {(["featured", "custom", "installed"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={`flex-1 px-3 py-2 text-xs font-medium capitalize transition-colors ${
                tab === t
                  ? "border-b-2 border-blue-400 text-white"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              {t}
              {t === "installed" && installedRepos.length > 0 && (
                <span className="ml-1 rounded-full bg-blue-600 px-1.5 text-[9px] text-white">
                  {installedRepos.length}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5">
          {/* Status messages */}
          {importError && (
            <div className="mb-3 rounded border border-red-900/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">
              {importError}
            </div>
          )}
          {lastImportCount !== null && !importError && (
            <div className="mb-3 rounded border border-green-900/50 bg-green-950/30 px-3 py-2 text-xs text-green-400">
              Imported {lastImportCount} skill{lastImportCount !== 1 ? "s" : ""}
            </div>
          )}

          {/* Featured tab */}
          {tab === "featured" && (
            <div className="space-y-3">
              {MARKETPLACE_REPOS.filter((r) => r.featured).map((r) => (
                <RepoCard
                  key={`${r.owner}/${r.repo}`}
                  repo={r}
                  installed={installedRepos.includes(`${r.owner}/${r.repo}`)}
                  loading={importLoading}
                  onInstall={() => handleInstall(r)}
                  onRemove={() => removeImportedRepo(`${r.owner}/${r.repo}`)}
                />
              ))}
              <h3 className="pt-2 text-xs font-semibold text-gray-400">More</h3>
              {MARKETPLACE_REPOS.filter((r) => !r.featured).map((r) => (
                <RepoCard
                  key={`${r.owner}/${r.repo}`}
                  repo={r}
                  installed={installedRepos.includes(`${r.owner}/${r.repo}`)}
                  loading={importLoading}
                  onInstall={() => handleInstall(r)}
                  onRemove={() => removeImportedRepo(`${r.owner}/${r.repo}`)}
                />
              ))}
            </div>
          )}

          {/* Custom import tab */}
          {tab === "custom" && (
            <div className="space-y-4">
              <p className="text-xs text-gray-400">
                Import skills from any GitHub repository. The repo should have a{" "}
                <code className="rounded bg-gray-800 px-1 py-0.5 text-blue-300">
                  skills/
                </code>{" "}
                directory with JSON skill files.
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={customUrl}
                  onChange={(e) => setCustomUrl(e.target.value)}
                  placeholder="owner/repo or owner/repo/custom-path"
                  className="min-w-0 flex-1 rounded-lg bg-gray-800 px-3 py-2 text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleCustomImport();
                  }}
                />
                <button
                  type="button"
                  onClick={handleCustomImport}
                  disabled={!customUrl.trim() || importLoading}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-medium text-white hover:bg-blue-500 disabled:opacity-50"
                >
                  {importLoading ? "Importing..." : "Import"}
                </button>
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-800/50 p-3 text-xs text-gray-500">
                <p className="mb-2 font-semibold text-gray-400">Expected file format:</p>
                <pre className="overflow-x-auto text-[11px] text-gray-400">
{`{
  "id": "my-skill",
  "name": "My Custom Skill",
  "category": "apis",
  "description": "What it does",
  "systemPrompt": "You are a...",
  "tags": ["tag1"]
}`}
                </pre>
              </div>
            </div>
          )}

          {/* Installed tab */}
          {tab === "installed" && (
            <div className="space-y-3">
              {installedRepos.length === 0 ? (
                <p className="py-8 text-center text-xs text-gray-500">
                  No imported skill repositories
                </p>
              ) : (
                installedRepos.map((fullName) => {
                  const skillCount = githubSkills.filter((s) =>
                    s.id.startsWith(`${fullName}/`),
                  ).length;
                  return (
                    <div
                      key={fullName}
                      className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-800/50 px-4 py-3"
                    >
                      <div>
                        <p className="text-xs font-medium text-white">
                          {fullName}
                        </p>
                        <p className="text-[11px] text-gray-500">
                          {skillCount} skill{skillCount !== 1 ? "s" : ""} imported
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeImportedRepo(fullName)}
                        className="text-xs text-red-400 hover:text-red-300"
                      >
                        Remove
                      </button>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end border-t border-gray-800 px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded bg-gray-800 px-4 py-1.5 text-xs font-medium text-white hover:bg-gray-700"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

function RepoCard({
  repo,
  installed,
  loading,
  onInstall,
  onRemove,
}: {
  repo: MarketplaceRepo;
  installed: boolean;
  loading: boolean;
  onInstall: () => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex items-start justify-between rounded-lg border border-gray-800 bg-gray-800/50 p-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h3 className="text-xs font-semibold text-white">{repo.name}</h3>
          <span className="rounded bg-gray-700 px-1.5 py-0.5 text-[10px] text-gray-400">
            {repo.skillCount}
          </span>
          <span className="rounded bg-gray-700/50 px-1.5 py-0.5 text-[10px] text-gray-500">
            {repo.category}
          </span>
        </div>
        <p className="mt-1 text-[11px] text-gray-400">{repo.description}</p>
        <p className="mt-1 font-mono text-[10px] text-gray-600">
          {repo.owner}/{repo.repo}
        </p>
      </div>
      <div className="ml-3 shrink-0">
        {installed ? (
          <button
            type="button"
            onClick={onRemove}
            className="rounded border border-gray-700 px-3 py-1 text-[10px] text-gray-400 hover:border-red-700 hover:text-red-400"
          >
            Remove
          </button>
        ) : (
          <button
            type="button"
            onClick={onInstall}
            disabled={loading}
            className="rounded bg-blue-600 px-3 py-1 text-[10px] font-medium text-white hover:bg-blue-500 disabled:opacity-50"
          >
            {loading ? "..." : "Install"}
          </button>
        )}
      </div>
    </div>
  );
}
