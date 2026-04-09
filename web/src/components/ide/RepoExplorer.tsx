import { useState, useMemo, useEffect } from "react";
import { useRepoStore } from "../../stores/repoStore";
import type { GitTreeNode } from "../../types/github";

/** Map file extensions to display icons. */
function fileIcon(name: string): string {
  if (name.endsWith(".ds")) return "\u{1F4E6}"; // package
  if (name.endsWith(".dg")) return "\u26A1"; // zap
  if (name.endsWith(".yaml") || name.endsWith(".yml")) return "\u2699\uFE0F"; // gear
  if (name.endsWith(".json")) return "\u{1F4CB}"; // clipboard
  if (name.endsWith(".md")) return "\u{1F4DD}"; // memo
  if (name.endsWith(".py")) return "\u{1F40D}"; // snake
  if (name.endsWith(".sql")) return "\u{1F5C4}\uFE0F"; // file cabinet
  if (name.endsWith(".csv")) return "\u{1F4CA}"; // chart
  return "\u{1F4C4}"; // page
}

interface TreeItemProps {
  node: GitTreeNode;
  depth: number;
  expanded: Set<string>;
  onToggle: (path: string) => void;
  onSelect: (node: GitTreeNode) => void;
  selectedPath: string | null;
  filter: string;
  pendingPaths: Set<string>;
}

function TreeItem({
  node,
  depth,
  expanded,
  onToggle,
  onSelect,
  selectedPath,
  filter,
  pendingPaths,
}: TreeItemProps) {
  const isDir = node.type === "tree";
  const isOpen = expanded.has(node.path);
  const isSelected = selectedPath === node.path;
  const isPending = pendingPaths.has(node.path);

  // Filter: hide non-matching files (but always show dirs that have matching children)
  if (filter) {
    const lower = filter.toLowerCase();
    if (!isDir && !node.name.toLowerCase().includes(lower)) return null;
  }

  return (
    <>
      <button
        type="button"
        onClick={() => (isDir ? onToggle(node.path) : onSelect(node))}
        className={`flex w-full items-center gap-1 px-2 py-1 text-left text-xs transition-colors hover:bg-gray-800 ${
          isSelected
            ? "border-l-2 border-blue-400 bg-gray-800/60 text-white"
            : "text-gray-300"
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        title={node.path}
      >
        {/* Expand/collapse indicator for dirs */}
        {isDir ? (
          <span className="w-3 shrink-0 text-gray-500">
            {isOpen ? "\u25BE" : "\u25B8"}
          </span>
        ) : (
          <span className="w-3 shrink-0" />
        )}

        {/* Icon */}
        <span className="shrink-0 text-[11px]">
          {isDir ? (isOpen ? "\u{1F4C2}" : "\u{1F4C1}") : fileIcon(node.name)}
        </span>

        {/* Name */}
        <span className="truncate">{node.name}</span>

        {/* Pending change indicator */}
        {isPending && (
          <span className="ml-auto h-2 w-2 shrink-0 rounded-full bg-orange-400" title="Modified" />
        )}
      </button>

      {/* Children */}
      {isDir && isOpen && node.children && (
        <>
          {node.children.map((child) => (
            <TreeItem
              key={child.path}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              onToggle={onToggle}
              onSelect={onSelect}
              selectedPath={selectedPath}
              filter={filter}
              pendingPaths={pendingPaths}
            />
          ))}
        </>
      )}
    </>
  );
}

interface RepoExplorerProps {
  onFileSelect: (path: string, content: string) => void;
}

export function RepoExplorer({ onFileSelect }: RepoExplorerProps) {
  const {
    repos,
    selectedRepo,
    selectedBranch,
    branches,
    repoTree,
    repoLoading,
    pendingChanges,
    fetchRepos,
    selectRepo,
    selectBranch,
  } = useRepoStore();

  const fetchFileContent = useRepoStore((s) => s.fetchFileContent);

  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [repoPickerOpen, setRepoPickerOpen] = useState(false);

  // Fetch repos on mount
  useEffect(() => {
    if (repos.length === 0) fetchRepos();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-expand first level when tree loads
  useEffect(() => {
    if (repoTree.length > 0) {
      const firstLevel = new Set(
        repoTree.filter((n) => n.type === "tree").map((n) => n.path),
      );
      setExpanded(firstLevel);
    }
  }, [repoTree]);

  const pendingPaths = useMemo(
    () => new Set(pendingChanges.keys()),
    [pendingChanges],
  );

  const toggleExpand = (path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const handleSelect = async (node: GitTreeNode) => {
    setSelectedPath(node.path);
    try {
      const content = await fetchFileContent(node.path);
      onFileSelect(node.path, content);
    } catch (err) {
      console.error("Failed to fetch file:", err);
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Repo + Branch selector */}
      <div className="space-y-1 border-b border-gray-800 px-2 py-2">
        {/* Repo selector */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setRepoPickerOpen((v) => !v)}
            className="flex w-full items-center justify-between rounded bg-gray-800 px-2 py-1.5 text-xs text-gray-300 hover:bg-gray-700"
          >
            <span className="truncate">
              {selectedRepo ? selectedRepo.full_name : "Select repository..."}
            </span>
            <svg className="h-3 w-3 shrink-0 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {repoPickerOpen && (
            <div className="absolute left-0 right-0 z-40 mt-1 max-h-60 overflow-y-auto rounded-lg border border-gray-700 bg-gray-800 shadow-xl">
              {repos.map((r) => (
                <button
                  key={r.full_name}
                  type="button"
                  onClick={() => {
                    selectRepo(r.owner, r.name);
                    setRepoPickerOpen(false);
                  }}
                  className={`flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition-colors hover:bg-gray-700 ${
                    selectedRepo?.full_name === r.full_name
                      ? "bg-gray-700 text-white"
                      : "text-gray-300"
                  }`}
                >
                  {r.private ? "\u{1F512}" : "\u{1F4C2}"}{" "}
                  <span className="truncate">{r.full_name}</span>
                </button>
              ))}
              {repos.length === 0 && (
                <p className="px-3 py-2 text-xs text-gray-500">
                  {repoLoading ? "Loading..." : "No repositories found"}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Branch selector */}
        {selectedRepo && (
          <select
            value={selectedBranch}
            onChange={(e) => selectBranch(e.target.value)}
            className="w-full rounded bg-gray-800 px-2 py-1 text-xs text-gray-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {branches.map((b) => (
              <option key={b.name} value={b.name}>
                {b.name}
                {b.protected ? " (protected)" : ""}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Filter */}
      {selectedRepo && (
        <div className="border-b border-gray-800 px-2 py-1">
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter files..."
            className="w-full rounded bg-gray-800 px-2 py-1 text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
      )}

      {/* File tree */}
      <div className="flex-1 overflow-y-auto">
        {repoLoading && (
          <div className="flex items-center justify-center py-8">
            <svg className="h-5 w-5 animate-spin text-blue-400" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
          </div>
        )}

        {!repoLoading && !selectedRepo && (
          <p className="px-3 py-6 text-center text-xs text-gray-500">
            Select a repository to browse files
          </p>
        )}

        {!repoLoading && selectedRepo && repoTree.length === 0 && (
          <p className="px-3 py-6 text-center text-xs text-gray-500">
            Empty repository
          </p>
        )}

        {!repoLoading &&
          repoTree.map((node) => (
            <TreeItem
              key={node.path}
              node={node}
              depth={0}
              expanded={expanded}
              onToggle={toggleExpand}
              onSelect={handleSelect}
              selectedPath={selectedPath}
              filter={filter}
              pendingPaths={pendingPaths}
            />
          ))}
      </div>

      {/* Pending changes summary */}
      {pendingChanges.size > 0 && (
        <div className="border-t border-gray-800 px-2 py-1.5">
          <span className="text-xs text-orange-400">
            {pendingChanges.size} pending change{pendingChanges.size !== 1 ? "s" : ""}
          </span>
        </div>
      )}
    </div>
  );
}
