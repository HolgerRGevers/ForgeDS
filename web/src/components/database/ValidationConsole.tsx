import { useCallback, useState } from "react";
import { useDatabaseStore } from "../../stores/databaseStore";
import { useBridgeStore } from "../../stores/bridgeStore";
import type { ValidationResult, ValidationDetail } from "../../types/database";

// --- Severity icon ---

function SeverityIcon({ severity }: { severity: ValidationDetail["severity"] }) {
  switch (severity) {
    case "error":
      return (
        <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-red-900/50 text-[10px] text-red-400">
          &#10005;
        </span>
      );
    case "warning":
      return (
        <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-yellow-900/50 text-[10px] text-yellow-400">
          !
        </span>
      );
    case "info":
      return (
        <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-blue-900/50 text-[10px] text-blue-400">
          i
        </span>
      );
  }
}

// --- Status badge ---

const statusBadgeColors: Record<ValidationResult["status"], string> = {
  pass: "bg-green-900/50 text-green-400",
  warning: "bg-yellow-900/50 text-yellow-400",
  fail: "bg-red-900/50 text-red-400",
};

function StatusBadge({ status }: { status: ValidationResult["status"] }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusBadgeColors[status]}`}
    >
      {status.toUpperCase()}
    </span>
  );
}

// --- Result card ---

function ResultCard({ result }: { result: ValidationResult }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded border border-gray-700 bg-gray-800/50">
      {/* Card header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-3 px-3 py-2 text-left transition-colors hover:bg-gray-800"
      >
        <StatusBadge status={result.status} />
        <span className="rounded bg-gray-700 px-1.5 py-0.5 text-[10px] font-mono text-gray-400">
          {result.tool}
        </span>
        <span className="flex-1 truncate text-xs text-gray-200">
          {result.summary}
        </span>
        <span className="flex-shrink-0 text-[10px] text-gray-500">
          {result.timestamp}
        </span>
        <span className="text-gray-500">{expanded ? "\u25B4" : "\u25BE"}</span>
      </button>

      {/* Expandable details */}
      {expanded && result.details.length > 0 && (
        <div className="border-t border-gray-700 px-3 py-2">
          <div className="space-y-1">
            {result.details.map((detail, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2 rounded px-2 py-1 text-xs hover:bg-gray-800/80"
              >
                <SeverityIcon severity={detail.severity} />
                {detail.rule && (
                  <span className="flex-shrink-0 rounded bg-gray-700 px-1 py-0.5 font-mono text-[10px] text-gray-400">
                    {detail.rule}
                  </span>
                )}
                <span className="flex-1 text-gray-300">{detail.message}</span>
                {detail.source && (
                  <span className="flex-shrink-0 font-mono text-[10px] text-gray-500">
                    {detail.source}
                    {detail.line != null && `:${detail.line}`}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {expanded && result.details.length === 0 && (
        <div className="border-t border-gray-700 px-3 py-2">
          <p className="text-xs text-gray-500">No detail messages</p>
        </div>
      )}
    </div>
  );
}

// --- Main component ---

export function ValidationConsole() {
  const validationResults = useDatabaseStore((s) => s.validationResults);
  const addValidationResult = useDatabaseStore((s) => s.addValidationResult);
  const clearValidationResults = useDatabaseStore(
    (s) => s.clearValidationResults,
  );
  const send = useBridgeStore((s) => s.send);

  const [running, setRunning] = useState<string | null>(null);

  const runValidation = useCallback(
    async (tool: "lint-hybrid" | "validate") => {
      setRunning(tool);
      try {
        const response = await send("run_validation", { tool });
        const result: ValidationResult = {
          id: crypto.randomUUID(),
          timestamp: new Date().toLocaleTimeString(),
          tool,
          status: (response?.status as ValidationResult["status"]) ?? "pass",
          summary: (response?.summary as string) ?? `${tool} completed`,
          details: (response?.details as ValidationDetail[]) ?? [],
        };
        addValidationResult(result);
      } catch {
        const result: ValidationResult = {
          id: crypto.randomUUID(),
          timestamp: new Date().toLocaleTimeString(),
          tool,
          status: "fail",
          summary: `${tool} failed to execute`,
          details: [
            {
              severity: "error",
              message: "Bridge connection error or tool unavailable",
            },
          ],
        };
        addValidationResult(result);
      } finally {
        setRunning(null);
      }
    },
    [send, addValidationResult],
  );

  return (
    <div className="flex h-full flex-col bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-700 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-gray-200">Validation</h3>
          <span className="rounded-full bg-gray-700 px-2 py-0.5 text-xs font-medium text-gray-300">
            {validationResults.length}
          </span>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => runValidation("lint-hybrid")}
            disabled={running !== null}
            className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {running === "lint-hybrid" ? "Running..." : "Schema Check"}
          </button>
          <button
            onClick={() => runValidation("validate")}
            disabled={running !== null}
            className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {running === "validate" ? "Running..." : "Data Validation"}
          </button>
          <button
            onClick={clearValidationResults}
            disabled={validationResults.length === 0}
            className="rounded border border-gray-600 bg-gray-800 px-3 py-1 text-xs font-medium text-gray-300 transition-colors hover:border-gray-500 hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Results list */}
      <div className="flex-1 overflow-y-auto px-3 py-2">
        {validationResults.length === 0 && (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-gray-500">
              No validation results yet. Run a check to get started.
            </p>
          </div>
        )}
        <div className="space-y-2">
          {validationResults.map((result) => (
            <ResultCard key={result.id} result={result} />
          ))}
        </div>
      </div>
    </div>
  );
}
