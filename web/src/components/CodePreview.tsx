import Editor from "@monaco-editor/react";
import type { CodePreviewProps } from "../types/prompt";
import { useDelugeLanguage } from "../hooks/useMonaco";
import { DELUGE_THEME } from "../lib/deluge-language";

export function CodePreview({
  files,
  activeFileIndex,
  onFileSelect,
}: CodePreviewProps) {
  useDelugeLanguage();

  if (files.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-lg border border-gray-700 bg-gray-900">
        <p className="text-sm text-gray-500">
          Generated code will appear here
        </p>
      </div>
    );
  }

  const activeFile = files[activeFileIndex] ?? files[0];

  // Map .dg files to the registered "deluge" language
  const resolvedLanguage =
    activeFile.name.endsWith(".dg") ? "deluge" : activeFile.language;

  return (
    <div className="overflow-hidden rounded-lg border border-gray-700 bg-gray-900">
      {/* Tab bar */}
      <div className="flex overflow-x-auto border-b border-gray-700 bg-gray-950">
        {files.map((file, i) => (
          <button
            key={file.path}
            type="button"
            onClick={() => onFileSelect(i)}
            className={`shrink-0 border-r border-gray-800 px-4 py-2 text-xs font-medium transition-colors ${
              i === activeFileIndex
                ? "bg-gray-900 text-gray-100"
                : "text-gray-500 hover:bg-gray-900/50 hover:text-gray-300"
            }`}
          >
            {file.name}
          </button>
        ))}
      </div>

      {/* Editor */}
      <Editor
        height="400px"
        language={resolvedLanguage}
        value={activeFile.content}
        theme={DELUGE_THEME}
        options={{
          readOnly: true,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          fontSize: 13,
          lineNumbers: "on",
          renderLineHighlight: "none",
          domReadOnly: true,
        }}
      />
    </div>
  );
}
