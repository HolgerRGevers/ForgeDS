import { useState, useEffect } from "react";
import { useRepoStore } from "../stores/repoStore";
import type { GitTreeNode } from "../types/github";

interface RepoFilePickerProps {
  onClose: () => void;
  onSelect: (files: Array<{ path: string; content: string }>) => void;
}

/**
 * Modal that lets users browse their GitHub repo and select files
 * to attach as context to the prompt.
 */
export function RepoFilePicker({ onClose, onSelect }: RepoFilePickerProps) {
  const { selectedRepo, repoTree, repoLoading, fetchRepos } = useRepoStore();
  const fetchFileContent = useRepoStore((s) => s.fetchFileContent);

  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selectedRepo) fetchRepos();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleExpand = (path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const toggleSelect = (path: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const handleConfirm = async () => {
    if (selected.size === 0) return;
    setLoading(true);
    try {
      const results: Array<{ path: string; content: string }> = [];
      for (const path of selected) {
        const content = await fetchFileContent(path);
        results.push({ path, content });
      }
      onSelect(results);
      onClose();
    } catch (err) {
      console.error("Failed to fetch selected files:", err);
    } finally {
      setLoading(false);
    }
  };

  function renderNode(node: GitTreeNode, depth: number) {
    const isDir = node.type === "tree";
    const isOpen = expanded.has(node.path);
    const isChecked = selected.has(node.path);

    return (
      <div key={node.path}>
        <button
          type="button"
          onClick={() => (isDir ? toggleExpand(node.path) : toggleSelect(node.path))}
          className="flex w-full items-center gap-1.5 px-2 py-1 text-left text-xs text-gray-300 transition-colors hover:bg-gray-800"
          style={{ paddingLeft: `${depth * 16 + 8}px` }}
        >
          {/* Checkbox for files */}
          {!isDir && (
            <span
              className={`flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded border ${
                isChecked
                  ? "border-blue-500 bg-blue-500 text-white"
                  : "border-gray-600"
              }`}
            >
              {isChecked && (
                <svg className="h-2.5 w-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                </svg>
              )}
            </span>
          )}

          {/* Expand for dirs */}
          {isDir && (
            <span className="w-3 shrink-0 text-gray-500">
              {isOpen ? "\u25BE" : "\u25B8"}
            </span>
          )}

          <span className="shrink-0 text-[11px]">
            {isDir ? (isOpen ? "\u{1F4C2}" : "\u{1F4C1}") : "\u{1F4C4}"}
          </span>
          <span className="truncate">{node.name}</span>
        </button>
        {isDir && isOpen && node.children?.map((c) => renderNode(c, depth + 1))}
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="flex max-h-[80vh] w-full max-w-lg flex-col rounded-xl border border-gray-700 bg-gray-900 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
          <h2 className="text-sm font-semibold text-white">
            Select files from{" "}
            <span className="text-blue-400">
              {selectedRepo?.full_name ?? "repository"}
            </span>
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-500 hover:text-white"
          >
            &times;
          </button>
        </div>

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
          {!repoLoading && repoTree.length === 0 && (
            <p className="py-8 text-center text-xs text-gray-500">
              {selectedRepo ? "Empty repository" : "Select a repository first"}
            </p>
          )}
          {repoTree.map((node) => renderNode(node, 0))}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-gray-800 px-4 py-3">
          <span className="text-xs text-gray-500">
            {selected.size} file{selected.size !== 1 ? "s" : ""} selected
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded border border-gray-700 px-3 py-1.5 text-xs text-gray-400 transition-colors hover:border-gray-500"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={selected.size === 0 || loading}
              className="rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-500 disabled:opacity-50"
            >
              {loading ? "Loading..." : "Add to prompt"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
