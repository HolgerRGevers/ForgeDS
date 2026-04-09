import { useState, useCallback, useRef } from "react";
import type { PromptInputProps } from "../types/prompt";

const ACCEPTED_EXTENSIONS = [".ds", ".dg", ".png", ".jpg"];

function isAcceptedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

export function PromptInput({ onSubmit, isLoading }: PromptInputProps) {
  const [prompt, setPrompt] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback((incoming: FileList | File[]) => {
    const accepted = Array.from(incoming).filter(isAcceptedFile);
    setFiles((prev) => {
      const existingNames = new Set(prev.map((f) => f.name));
      const unique = accepted.filter((f) => !existingNames.has(f.name));
      return [...prev, ...unique];
    });
  }, []);

  const removeFile = useCallback((name: string) => {
    setFiles((prev) => prev.filter((f) => f.name !== name));
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
        addFiles(e.dataTransfer.files);
      }
    },
    [addFiles],
  );

  const handleSubmit = useCallback(() => {
    if (prompt.trim() && !isLoading) {
      onSubmit(prompt.trim(), files);
    }
  }, [prompt, files, isLoading, onSubmit]);

  const isEmpty = prompt.trim().length === 0;

  return (
    <div className="w-full space-y-4">
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
              Drop files here (.ds, .dg, .png, .jpg)
            </p>
          </div>
        )}

        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Describe the Zoho Creator app you want to build..."
          rows={6}
          disabled={isLoading}
          className="w-full resize-y rounded-lg bg-transparent px-4 py-3 text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 disabled:opacity-50"
        />
      </div>

      {/* File chips */}
      {files.length > 0 && (
        <div className="flex flex-wrap gap-2">
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
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="inline-flex items-center gap-1 rounded-full border border-dashed border-gray-600 px-3 py-1 text-xs text-gray-400 hover:border-gray-400 hover:text-gray-300"
          >
            + Add file
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".ds,.dg,.png,.jpg"
            className="hidden"
            onChange={(e) => {
              if (e.target.files) addFiles(e.target.files);
              e.target.value = "";
            }}
          />
        </div>
      )}

      {/* Submit button */}
      <button
        type="button"
        onClick={handleSubmit}
        disabled={isEmpty || isLoading}
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isLoading ? (
          <>
            <svg
              className="h-4 w-4 animate-spin"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
              />
            </svg>
            Refining...
          </>
        ) : (
          "Refine with AI"
        )}
      </button>
    </div>
  );
}
