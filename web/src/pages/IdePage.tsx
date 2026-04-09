import { Link } from "react-router-dom";

export default function IdePage() {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="w-full max-w-md rounded-lg border border-gray-700 bg-gray-800 p-8 text-center shadow-lg">
        <h1 className="text-2xl font-bold text-white">Code Editor</h1>
        <p className="mt-2 text-sm text-blue-400">Coming in Phase 2</p>
        <p className="mt-4 text-sm leading-relaxed text-gray-400">
          Full Monaco-based IDE with file tree, multi-tab editing, integrated
          terminal, and live Deluge linting. Edit generated projects or start
          from scratch.
        </p>
        <Link
          to="/"
          className="mt-6 inline-block rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-500"
        >
          Back to Prompt
        </Link>
      </div>
    </div>
  );
}
