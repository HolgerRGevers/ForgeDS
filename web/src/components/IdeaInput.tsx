import { useState } from "react";
import type { ChangeEvent, FormEvent } from "react";

interface IdeaInputProps {
  initialValue?: string;
  placeholder?: string;
  acceptAttachments?: boolean;
  onSubmit: (text: string, files: File[]) => void;
  isLoading?: boolean;
}

export function IdeaInput({
  initialValue = "",
  placeholder = "Describe your core idea — what does this app do, and for whom?",
  acceptAttachments = false,
  onSubmit,
  isLoading = false,
}: IdeaInputProps) {
  const [text, setText] = useState(initialValue);
  const [files, setFiles] = useState<File[]>([]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (text.trim().length === 0) return;
    onSubmit(text.trim(), files);
  };

  const handleFiles = (e: ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    setFiles(Array.from(e.target.files));
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex w-full max-w-2xl flex-col gap-3 rounded-lg border border-gray-800 bg-gray-900 p-4"
    >
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={placeholder}
        rows={6}
        className="w-full resize-none rounded-md border border-white/10 bg-black/40 p-3 text-sm text-white placeholder-gray-500"
      />

      {acceptAttachments && (
        <div className="flex items-center gap-3 text-xs text-gray-400">
          <input
            type="file"
            multiple
            onChange={handleFiles}
            accept=".csv,.zip,.accdb,.ds,.json"
            className="text-xs text-gray-300 file:mr-3 file:rounded file:border-0 file:bg-white/10 file:px-3 file:py-1.5 file:text-xs file:text-white"
          />
          {files.length > 0 && <span>{files.length} file(s) attached</span>}
        </div>
      )}

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={isLoading || text.trim().length === 0}
          className="rounded-md bg-[#c2662d] px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-[#a8551c] disabled:cursor-not-allowed disabled:opacity-40"
        >
          {isLoading ? "Submitting…" : "Continue →"}
        </button>
      </div>
    </form>
  );
}
