import { useEffect, useRef } from "react";
import type { BuildProgressProps } from "../types/prompt";

const TYPE_COLORS: Record<string, string> = {
  info: "text-gray-400",
  success: "text-green-400",
  error: "text-red-400",
  warning: "text-yellow-400",
};

export function BuildProgress({
  messages,
  isBuilding,
  isComplete,
  onOpenIDE,
}: BuildProgressProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div className="w-full rounded-lg border border-gray-700 bg-gray-900">
      {/* Progress bar */}
      {isBuilding && (
        <div className="h-1 w-full overflow-hidden rounded-t-lg bg-gray-800">
          <div className="h-full w-1/3 animate-[indeterminate_1.5s_ease-in-out_infinite] rounded bg-blue-500" />
        </div>
      )}

      {/* Success banner */}
      {isComplete && (
        <div className="flex items-center justify-between border-b border-gray-700 bg-green-900/30 px-4 py-3">
          <span className="text-sm font-medium text-green-400">
            Build complete
          </span>
          <button
            type="button"
            onClick={onOpenIDE}
            className="rounded-md bg-green-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-green-500"
          >
            Open in IDE
          </button>
        </div>
      )}

      {/* Log area */}
      <div
        ref={scrollRef}
        className="max-h-80 overflow-y-auto p-4 font-mono text-xs leading-relaxed"
      >
        {messages.length === 0 && !isBuilding && (
          <p className="text-gray-600">Waiting for build to start...</p>
        )}
        {messages.map((msg, i) => (
          <div key={i} className="flex gap-2">
            <span className="shrink-0 select-none text-gray-600">
              {msg.timestamp}
            </span>
            <span className={TYPE_COLORS[msg.type] ?? "text-gray-400"}>
              {msg.text}
            </span>
          </div>
        ))}
        {isBuilding && (
          <span className="inline-block animate-pulse text-gray-500">
            ...
          </span>
        )}
      </div>
    </div>
  );
}
