import { useMemo } from "react";
import type { ExtractedFile } from "../lib/zip-utils";
import { formatFileSize } from "../lib/zip-utils";

interface ZipPreviewModalProps {
  files: ExtractedFile[];
  onConfirm: (files: ExtractedFile[]) => void;
  onCancel: () => void;
  isUploading: boolean;
  uploadProgress: number;
  repoSelected: boolean;
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

export function ZipPreviewModal({ files, onConfirm, onCancel, isUploading, uploadProgress, repoSelected }: ZipPreviewModalProps) {
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

  const totalSize = useMemo(() => files.reduce((sum, f) => sum + f.size, 0), [files]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="mx-4 flex max-h-[80vh] w-full max-w-lg flex-col rounded-xl border border-gray-700 bg-gray-900 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-700 px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-gray-100">Upload ZIP Contents</h2>
            <p className="mt-0.5 text-[11px] text-gray-500">
              {files.length} file{files.length !== 1 ? "s" : ""} &middot; {formatFileSize(totalSize)}
            </p>
          </div>
          {!isUploading && (
            <button
              type="button"
              onClick={onCancel}
              className="text-gray-500 hover:text-gray-300"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* File tree */}
        <div className="flex-1 overflow-y-auto px-5 py-3">
          {!repoSelected && (
            <div className="mb-3 rounded-lg border border-yellow-700/50 bg-yellow-900/20 px-3 py-2 text-xs text-yellow-400">
              Select a repository first to upload files.
            </div>
          )}

          {Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b)).map(([dir, dirFiles]) => (
            <div key={dir} className="mb-3">
              <p className="mb-1 flex items-center gap-1.5 text-xs font-medium text-blue-400">
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
                {dir}/
              </p>
              <div className="ml-5 space-y-0.5">
                {dirFiles.map((file) => (
                  <div
                    key={file.targetPath}
                    className="flex items-center justify-between rounded px-2 py-1 text-xs text-gray-300 hover:bg-gray-800"
                  >
                    <span className="flex items-center gap-1.5 truncate">
                      <span>{CATEGORY_ICONS[file.category] ?? "\u{1F4E6}"}</span>
                      <span className="truncate">{file.name}</span>
                    </span>
                    <span className="shrink-0 text-[10px] text-gray-600">{formatFileSize(file.size)}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-700 px-5 py-3">
          {isUploading ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-gray-400">
                <span>Uploading files...</span>
                <span>{uploadProgress}/{files.length}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-gray-800">
                <div
                  className="h-full rounded-full bg-blue-500 transition-all"
                  style={{ width: `${(uploadProgress / files.length) * 100}%` }}
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
                onClick={() => onConfirm(files)}
                disabled={!repoSelected}
                className="flex-1 rounded-lg bg-blue-600 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Upload to Repository
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
