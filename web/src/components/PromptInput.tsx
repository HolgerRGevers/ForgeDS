import { useState, useCallback, useRef } from "react";
import type { PromptInputProps, RepoFile } from "../types/prompt";
import { ModeToggle } from "./ModeToggle";
import { RepoSelector } from "./RepoSelector";
import { RepoFilePicker } from "./RepoFilePicker";
import { SkillPicker } from "./SkillPicker";
import { ZipPreviewModal } from "./ZipPreviewModal";
import { useRepoStore } from "../stores/repoStore";
import { useSkillStore } from "../stores/skillStore";
import { extractZip } from "../lib/zip-utils";
import type { ExtractedFile } from "../lib/zip-utils";

const ACCEPTED_EXTENSIONS = [".ds", ".dg", ".png", ".jpg", ".sql", ".yaml", ".yml", ".json", ".csv", ".md", ".txt", ".zip"];

function isAcceptedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

export function PromptInput({ onSubmit, isLoading, mode, onModeChange }: PromptInputProps) {
  const [prompt, setPrompt] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [repoFiles, setRepoFiles] = useState<RepoFile[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isDropZoneDragOver, setIsDropZoneDragOver] = useState(false);
  const [showRepoPicker, setShowRepoPicker] = useState(false);
  const [showSkillPicker, setShowSkillPicker] = useState(false);
  const [saveToResources, setSaveToResources] = useState(false);
  const [extractedFiles, setExtractedFiles] = useState<ExtractedFile[]>([]);
  const [showZipPreview, setShowZipPreview] = useState(false);
  const [isZipUploading, setIsZipUploading] = useState(false);
  const [zipUploadProgress, setZipUploadProgress] = useState(0);
  const [zipError, setZipError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const selectedRepo = useRepoStore((s) => s.selectedRepo);
  const uploadResource = useRepoStore((s) => s.uploadResource);
  const batchUploadFiles = useRepoStore((s) => s.batchUploadFiles);
  const activeSkillCount = useSkillStore((s) => s.activeSkillIds.length);

  const processFiles = useCallback(async (incoming: FileList | File[]) => {
    const accepted = Array.from(incoming).filter(isAcceptedFile);
    const zipFiles = accepted.filter((f) => f.name.toLowerCase().endsWith(".zip"));
    const regularFiles = accepted.filter((f) => !f.name.toLowerCase().endsWith(".zip"));

    // Add regular files
    if (regularFiles.length > 0) {
      setFiles((prev) => {
        const existingNames = new Set(prev.map((f) => f.name));
        const unique = regularFiles.filter((f) => !existingNames.has(f.name));
        return [...prev, ...unique];
      });
    }

    // Handle ZIP files
    if (zipFiles.length > 0) {
      try {
        setZipError(null);
        const allExtracted: ExtractedFile[] = [];
        for (const zip of zipFiles) {
          const extracted = await extractZip(zip);
          allExtracted.push(...extracted);
        }
        setExtractedFiles(allExtracted);
        setShowZipPreview(true);
      } catch (err) {
        setZipError(err instanceof Error ? err.message : "Failed to extract ZIP");
      }
    }
  }, []);

  const removeFile = useCallback((name: string) => {
    setFiles((prev) => prev.filter((f) => f.name !== name));
  }, []);

  const removeRepoFile = useCallback((path: string) => {
    setRepoFiles((prev) => prev.filter((f) => f.path !== path));
  }, []);

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (!isDragOver) setIsDragOver(true);
    },
    [isDragOver],
  );

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);
      if (e.dataTransfer.files.length > 0) {
        processFiles(e.dataTransfer.files);
      }
    },
    [processFiles],
  );

  const handleDropZoneDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (!isDropZoneDragOver) setIsDropZoneDragOver(true);
    },
    [isDropZoneDragOver],
  );

  const handleDropZoneDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDropZoneDragOver(false);
  }, []);

  const handleDropZoneDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDropZoneDragOver(false);
      if (e.dataTransfer.files.length > 0) {
        processFiles(e.dataTransfer.files);
      }
    },
    [processFiles],
  );

  const handleRepoFilesSelected = useCallback(
    (selected: Array<{ path: string; content: string }>) => {
      const repoName = selectedRepo?.full_name ?? "unknown";
      setRepoFiles((prev) => {
        const existingPaths = new Set(prev.map((f) => f.path));
        const newFiles = selected
          .filter((f) => !existingPaths.has(f.path))
          .map((f) => ({ ...f, repoName }));
        return [...prev, ...newFiles];
      });
    },
    [selectedRepo],
  );

  const handleZipConfirm = useCallback(async (confirmed: ExtractedFile[]) => {
    if (!selectedRepo) return;
    setIsZipUploading(true);
    setZipUploadProgress(0);
    try {
      const filesToUpload = confirmed.map((f) => ({
        path: f.targetPath,
        content: f.content,
        isBinary: f.isBinary,
      }));
      // Upload one at a time so we can track progress
      for (let i = 0; i < filesToUpload.length; i++) {
        await batchUploadFiles([filesToUpload[i]], `Add ${confirmed[i].name}`);
        setZipUploadProgress(i + 1);
      }
      setShowZipPreview(false);
      setExtractedFiles([]);
    } catch (err) {
      setZipError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsZipUploading(false);
    }
  }, [selectedRepo, batchUploadFiles]);

  const handleSubmit = useCallback(async () => {
    if (prompt.trim() && !isLoading) {
      // Upload local files to resources/ if checkbox is checked
      if (saveToResources && selectedRepo && files.length > 0) {
        for (const file of files) {
          const reader = new FileReader();
          const content = await new Promise<string>((resolve) => {
            reader.onload = () => resolve(reader.result as string);
            reader.readAsText(file);
          });
          try {
            await uploadResource(file.name, content);
          } catch (err) {
            console.error(`Failed to upload ${file.name}:`, err);
          }
        }
      }
      onSubmit(prompt.trim(), files, repoFiles);
    }
  }, [prompt, files, repoFiles, isLoading, saveToResources, selectedRepo, uploadResource, onSubmit]);

  const isEmpty = prompt.trim().length === 0;
  const hasAttachments = files.length > 0 || repoFiles.length > 0;

  return (
    <div className="w-full space-y-3">
      {/* Top toolbar: Mode toggle + Repo selector */}
      <div className="flex items-center justify-between">
        <ModeToggle mode={mode} onChange={onModeChange} />
        <RepoSelector compact />
      </div>

      {/* Drop zone wrapper */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`relative rounded-lg border-2 transition-colors ${
          isDragOver
            ? "border-dashed border-blue-500 bg-blue-500/10"
            : "border-gray-700 bg-gray-900"
        }`}
      >
        {/* Drag overlay */}
        {isDragOver && (
          <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-blue-500/10">
            <p className="text-sm font-medium text-blue-400">
              Drop files here
            </p>
          </div>
        )}

        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder={
            mode === "plan"
              ? "Describe what you want to build. I'll analyze and create a plan first..."
              : "Describe the Zoho Creator app you want to build..."
          }
          rows={5}
          disabled={isLoading}
          className="w-full resize-y rounded-lg bg-transparent px-4 py-3 text-gray-100 placeholder-gray-500 focus:outline-none disabled:opacity-50"
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              handleSubmit();
            }
          }}
        />

        {/* Bottom toolbar inside the textarea box */}
        <div className="flex items-center justify-between border-t border-gray-800 px-3 py-2">
          <div className="flex items-center gap-2">
            {/* Code label */}
            <span className="flex items-center gap-1 text-xs text-gray-500">
              <span className="font-mono">&lt;/&gt;</span> Code
            </span>

            {/* Add file from PC */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-1 rounded-md border border-gray-700 px-2 py-1 text-xs text-gray-400 transition-colors hover:border-gray-500 hover:text-gray-300"
              title="Upload files from your computer"
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              File
            </button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept={ACCEPTED_EXTENSIONS.join(",")}
              className="hidden"
              onChange={(e) => {
                if (e.target.files) processFiles(e.target.files);
                e.target.value = "";
              }}
            />

            {/* Add file from repo */}
            {selectedRepo && (
              <button
                type="button"
                onClick={() => setShowRepoPicker(true)}
                className="flex items-center gap-1 rounded-md border border-gray-700 px-2 py-1 text-xs text-gray-400 transition-colors hover:border-gray-500 hover:text-gray-300"
                title="Select files from your GitHub repository"
              >
                <svg className="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                </svg>
                Repo
              </button>
            )}

            {/* Skills button */}
            <button
              type="button"
              onClick={() => setShowSkillPicker(true)}
              className={`flex items-center gap-1 rounded-md border px-2 py-1 text-xs transition-colors ${
                activeSkillCount > 0
                  ? "border-blue-500/50 bg-blue-500/10 text-blue-400 hover:bg-blue-500/20"
                  : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-300"
              }`}
              title="Configure AI skills"
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              Skills
              {activeSkillCount > 0 && (
                <span className="rounded-full bg-blue-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
                  {activeSkillCount}
                </span>
              )}
            </button>
          </div>

          {/* Submit button */}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isEmpty || isLoading}
            className="flex items-center justify-center rounded-full bg-blue-600 p-2 text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
            title={mode === "plan" ? "Start planning" : "Generate code"}
          >
            {isLoading ? (
              <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
              </svg>
            ) : (
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Attached files chips */}
      {hasAttachments && (
        <div className="flex flex-wrap gap-2">
          {/* Local file chips */}
          {files.map((file) => (
            <span
              key={file.name}
              className="inline-flex items-center gap-1.5 rounded-full bg-gray-800 px-3 py-1 text-xs font-medium text-gray-300"
            >
              <span className="max-w-[160px] truncate">{file.name}</span>
              <button
                type="button"
                onClick={() => removeFile(file.name)}
                className="ml-0.5 text-gray-500 hover:text-gray-200"
                aria-label={`Remove ${file.name}`}
              >
                &times;
              </button>
            </span>
          ))}

          {/* Repo file chips */}
          {repoFiles.map((rf) => (
            <span
              key={rf.path}
              className="inline-flex items-center gap-1.5 rounded-full bg-gray-800 px-3 py-1 text-xs font-medium text-blue-300"
              title={`${rf.repoName}/${rf.path}`}
            >
              <svg className="h-3 w-3 shrink-0" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
              </svg>
              <span className="max-w-[160px] truncate">
                {rf.path.split("/").pop()}
              </span>
              <button
                type="button"
                onClick={() => removeRepoFile(rf.path)}
                className="ml-0.5 text-gray-500 hover:text-blue-200"
                aria-label={`Remove ${rf.path}`}
              >
                &times;
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Save to resources checkbox */}
      {files.length > 0 && selectedRepo && (
        <label className="flex items-center gap-2 text-xs text-gray-400">
          <input
            type="checkbox"
            checked={saveToResources}
            onChange={(e) => setSaveToResources(e.target.checked)}
            className="rounded border-gray-600 bg-gray-800"
          />
          Save uploaded files to{" "}
          <span className="font-mono text-blue-400">
            {selectedRepo.full_name}/resources/
          </span>
        </label>
      )}

      {/* Mode hint */}
      <p className="text-center text-[11px] text-gray-600">
        {mode === "plan"
          ? "Plan mode: AI will analyze and outline before generating code"
          : "Code mode: AI will generate Deluge code directly"}
        {" \u00B7 "}
        <kbd className="rounded border border-gray-700 bg-gray-800 px-1 py-0.5 text-[10px]">
          Ctrl+Enter
        </kbd>{" "}
        to submit
      </p>

      {/* Dedicated drag-and-drop zone */}
      <div
        onDragOver={handleDropZoneDragOver}
        onDragLeave={handleDropZoneDragLeave}
        onDrop={handleDropZoneDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed px-4 py-6 transition-colors ${
          isDropZoneDragOver
            ? "border-blue-500 bg-blue-500/10 text-blue-400"
            : "border-gray-700 bg-gray-800/50 text-gray-500 hover:border-gray-600 hover:text-gray-400"
        }`}
      >
        <svg className="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
        <p className="text-sm font-medium">Drag & drop files here</p>
        <p className="text-[11px]">or click to browse &middot; supports .zip files</p>
      </div>

      {/* ZIP error */}
      {zipError && (
        <div className="flex items-center justify-between rounded-lg border border-red-700/50 bg-red-900/20 px-3 py-2 text-xs text-red-400">
          <span>{zipError}</span>
          <button type="button" onClick={() => setZipError(null)} className="text-red-500 hover:text-red-300">&times;</button>
        </div>
      )}

      {/* Repo file picker modal */}
      {showRepoPicker && (
        <RepoFilePicker
          onClose={() => setShowRepoPicker(false)}
          onSelect={handleRepoFilesSelected}
        />
      )}

      {/* Skills picker modal */}
      {showSkillPicker && (
        <SkillPicker onClose={() => setShowSkillPicker(false)} />
      )}

      {/* ZIP preview modal */}
      {showZipPreview && (
        <ZipPreviewModal
          files={extractedFiles}
          onConfirm={handleZipConfirm}
          onCancel={() => { setShowZipPreview(false); setExtractedFiles([]); }}
          isUploading={isZipUploading}
          uploadProgress={zipUploadProgress}
          repoSelected={!!selectedRepo}
        />
      )}
    </div>
  );
}
