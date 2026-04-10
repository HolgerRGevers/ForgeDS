import { useState, useMemo, useCallback } from "react";
import type { ExtractedFile } from "../lib/zip-utils";
import { formatFileSize } from "../lib/zip-utils";
import { useRepoStore } from "../stores/repoStore";

interface ZipPreviewModalProps {
  files: ExtractedFile[];
  onConfirm: (files: ExtractedFile[]) => void;
  onCancel: () => void;
  isUploading: boolean;
  uploadProgress: number;
}

const CATEGORY_ICONS: Record<string, string> = {
  document: "\u{1F4C4}",
  image: "\u{1F5BC}\uFE0F",
  data: "\u{1F4CA}",
  code: "\u{1F4BB}",
  config: "\u2699\uFE0F",
  other: "\u{1F4E6}",
};

interface GroupedFiles {
  [dir: string]: ExtractedFile[];
}

/** Sanitize a string into a valid GitHub repo name. */
function toRepoName(raw: string): string {
  return raw
    .toLowerCase()
    .replace(/[^a-z0-9._-]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 100);
}

function isValidRepoName(name: string): boolean {
  if (!name || name.length > 100) return false;
  if (name === "." || name === "..") return false;
  return /^[a-zA-Z0-9._-]+$/.test(name);
}

/** Generate up to 3 repo name suggestions from file contents. */
function suggestRepoNames(files: ExtractedFile[]): string[] {
  const suggestions: string[] = [];
  const names = new Set<string>();

  // 1. Try names from document/data files (most likely project names)
  const meaningfulFiles = files.filter(
    (f) => f.category === "document" || f.category === "data" || f.category === "code",
  );

  for (const file of meaningfulFiles) {
    // Strip extension and number suffixes like "(2)"
    const base = file.name
      .replace(/\.[^.]+$/, "")
      .replace(/\s*\(\d+\)\s*$/, "")
      .trim();
    if (base.length >= 3) {
      const candidate = toRepoName(base);
      if (candidate && !names.has(candidate)) {
        names.add(candidate);
        suggestions.push(candidate);
      }
    }
    if (suggestions.length >= 2) break;
  }

  // 2. Try combining keywords from filenames
  if (suggestions.length < 3) {
    const allWords = files
      .flatMap((f) =>
        f.name
          .replace(/\.[^.]+$/, "")
          .replace(/\s*\(\d+\)\s*$/, "")
          .split(/[\s_-]+/),
      )
      .filter((w) => w.length >= 3)
      .map((w) => w.toLowerCase());

    // Get most common word
    const freq = new Map<string, number>();
    for (const w of allWords) freq.set(w, (freq.get(w) ?? 0) + 1);
    const sorted = [...freq.entries()].sort((a, b) => b[1] - a[1]);

    for (const [word] of sorted) {
      const candidate = toRepoName(`${word}-project`);
      if (candidate && !names.has(candidate)) {
        names.add(candidate);
        suggestions.push(candidate);
      }
      if (suggestions.length >= 3) break;
    }
  }

  // 3. Fallback
  if (suggestions.length === 0) {
    suggestions.push("new-project");
  }

  return suggestions.slice(0, 3);
}

export function ZipPreviewModal({ files, onConfirm, onCancel, isUploading, uploadProgress }: ZipPreviewModalProps) {
  const selectedRepo = useRepoStore((s) => s.selectedRepo);
  const createNewRepo = useRepoStore((s) => s.createNewRepo);

  const [selected, setSelected] = useState<Set<string>>(() => new Set(files.map((f) => f.targetPath)));
  const [repoName, setRepoName] = useState("");
  const [repoError, setRepoError] = useState<string | null>(null);
  const [isCreatingRepo, setIsCreatingRepo] = useState(false);

  const repoSelected = !!selectedRepo;

  const grouped = useMemo(() => {
    const groups: GroupedFiles = {};
    for (const file of files) {
      const dir = file.targetPath.includes("/")
        ? file.targetPath.substring(0, file.targetPath.lastIndexOf("/"))
        : "(root)";
      if (!groups[dir]) groups[dir] = [];
      groups[dir].push(file);
    }
    return groups;
  }, [files]);

  const suggestions = useMemo(() => suggestRepoNames(files), [files]);

  const selectedFiles = useMemo(() => files.filter((f) => selected.has(f.targetPath)), [files, selected]);
  const totalSize = useMemo(() => selectedFiles.reduce((sum, f) => sum + f.size, 0), [selectedFiles]);
  const allSelected = selected.size === files.length;
  const noneSelected = selected.size === 0;

  const toggleFile = useCallback((targetPath: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(targetPath)) next.delete(targetPath);
      else next.add(targetPath);
      return next;
    });
  }, []);

  const toggleDir = useCallback((dirFiles: ExtractedFile[]) => {
    setSelected((prev) => {
      const next = new Set(prev);
      const allInDir = dirFiles.every((f) => next.has(f.targetPath));
      for (const f of dirFiles) {
        if (allInDir) next.delete(f.targetPath);
        else next.add(f.targetPath);
      }
      return next;
    });
  }, []);

  const toggleAll = useCallback(() => {
    if (allSelected) {
      setSelected(new Set());
    } else {
      setSelected(new Set(files.map((f) => f.targetPath)));
    }
  }, [allSelected, files]);

  const handleCreateRepo = useCallback(async (name: string) => {
    const trimmed = name.trim();
    if (!isValidRepoName(trimmed)) {
      setRepoError("Invalid name. Use letters, numbers, hyphens, underscores, dots only.");
      return;
    }
    setRepoError(null);
    setIsCreatingRepo(true);
    try {
      await createNewRepo(trimmed, "", false, true);
    } catch (err) {
      setRepoError(err instanceof Error ? err.message : "Failed to create repository");
    } finally {
      setIsCreatingRepo(false);
    }
  }, [createNewRepo]);

  const repoNameValid = repoName.trim().length > 0 && isValidRepoName(repoName.trim());

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="mx-4 flex max-h-[85vh] w-full max-w-lg flex-col rounded-xl border border-gray-700 bg-gray-900 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-700 px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-gray-100">Upload ZIP Contents</h2>
            <p className="mt-0.5 text-[11px] text-gray-500">
              {selectedFiles.length}/{files.length} file{files.length !== 1 ? "s" : ""} selected &middot; {formatFileSize(totalSize)}
            </p>
          </div>
          {!isUploading && (
            <button type="button" onClick={onCancel} className="text-gray-500 hover:text-gray-300">
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* Repo creation section (when no repo selected) */}
        {!repoSelected && !isCreatingRepo && (
          <div className="border-b border-gray-700 px-5 py-3 space-y-2.5">
            <p className="text-xs font-medium text-gray-400">Create a repository for these files</p>

            {/* Suggestions */}
            <div className="flex flex-wrap gap-1.5">
              {suggestions.map((name) => (
                <button
                  key={name}
                  type="button"
                  onClick={() => handleCreateRepo(name)}
                  className="rounded-full border border-blue-500/40 bg-blue-500/10 px-3 py-1 text-xs text-blue-400 transition-colors hover:bg-blue-500/20 hover:border-blue-500/60"
                >
                  {name}
                </button>
              ))}
            </div>

            {/* Custom name input */}
            <div className="flex gap-2">
              <input
                type="text"
                value={repoName}
                onChange={(e) => { setRepoName(e.target.value); setRepoError(null); }}
                placeholder="Or type a custom name..."
                className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-xs text-gray-200 placeholder-gray-600 focus:border-blue-500 focus:outline-none"
                onKeyDown={(e) => { if (e.key === "Enter" && repoNameValid) handleCreateRepo(repoName.trim()); }}
              />
              <button
                type="button"
                onClick={() => handleCreateRepo(repoName.trim())}
                disabled={!repoNameValid}
                className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Create
              </button>
            </div>

            {repoError && (
              <p className="text-[11px] text-red-400">{repoError}</p>
            )}

            <p className="text-[10px] text-gray-600">
              Letters, numbers, hyphens, underscores, dots &middot; max 100 chars
            </p>
          </div>
        )}

        {/* Creating repo spinner */}
        {isCreatingRepo && (
          <div className="flex items-center gap-2 border-b border-gray-700 px-5 py-3">
            <svg className="h-4 w-4 animate-spin text-blue-400" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
            <span className="text-xs text-gray-400">Creating repository...</span>
          </div>
        )}

        {/* Repo badge (when selected) */}
        {repoSelected && (
          <div className="flex items-center gap-1.5 border-b border-gray-700 px-5 py-2 text-xs text-green-400">
            <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            Uploading to <span className="font-medium">{selectedRepo.full_name}</span>
          </div>
        )}

        {/* Select all */}
        <div className="flex items-center gap-2 border-b border-gray-800 px-5 py-2">
          <label className="flex cursor-pointer items-center gap-2 text-xs text-gray-400 hover:text-gray-300">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleAll}
              className="rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500/30"
            />
            Select all
          </label>
          <span className="text-[10px] text-gray-600">
            ({selected.size} selected)
          </span>
        </div>

        {/* File tree with checkboxes */}
        <div className="flex-1 overflow-y-auto px-5 py-3">
          {Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b)).map(([dir, dirFiles]) => {
            const allDirSelected = dirFiles.every((f) => selected.has(f.targetPath));
            const someDirSelected = dirFiles.some((f) => selected.has(f.targetPath));

            return (
              <div key={dir} className="mb-3">
                <label className="mb-1 flex cursor-pointer items-center gap-1.5 text-xs font-medium text-blue-400 hover:text-blue-300">
                  <input
                    type="checkbox"
                    checked={allDirSelected}
                    ref={(el) => { if (el) el.indeterminate = someDirSelected && !allDirSelected; }}
                    onChange={() => toggleDir(dirFiles)}
                    className="rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500/30"
                  />
                  <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                  </svg>
                  {dir}/
                </label>
                <div className="ml-5 space-y-0.5">
                  {dirFiles.map((file) => {
                    const isChecked = selected.has(file.targetPath);
                    return (
                      <label
                        key={file.targetPath}
                        className={`flex cursor-pointer items-center justify-between rounded px-2 py-1 text-xs transition-colors hover:bg-gray-800 ${
                          isChecked ? "text-gray-300" : "text-gray-600"
                        }`}
                      >
                        <span className="flex items-center gap-1.5 truncate">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => toggleFile(file.targetPath)}
                            className="rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500/30"
                          />
                          <span>{CATEGORY_ICONS[file.category] ?? "\u{1F4E6}"}</span>
                          <span className="truncate">{file.name}</span>
                        </span>
                        <span className="shrink-0 text-[10px] text-gray-600">{formatFileSize(file.size)}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-700 px-5 py-3">
          {isUploading ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-gray-400">
                <span>Uploading files...</span>
                <span>{uploadProgress}/{selectedFiles.length}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-gray-800">
                <div
                  className="h-full rounded-full bg-blue-500 transition-all"
                  style={{ width: `${(uploadProgress / selectedFiles.length) * 100}%` }}
                />
              </div>
            </div>
          ) : (
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onCancel}
                className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-xs text-gray-400 transition-colors hover:text-gray-200"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => onConfirm(selectedFiles)}
                disabled={!repoSelected || noneSelected}
                className="flex-1 rounded-lg bg-blue-600 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Upload {selectedFiles.length} file{selectedFiles.length !== 1 ? "s" : ""}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
