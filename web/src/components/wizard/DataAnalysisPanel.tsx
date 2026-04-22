import type { DataAnalysis } from "../../types/wizard";

interface DataAnalysisPanelProps {
  analysis: DataAnalysis;
}

export function DataAnalysisPanel({ analysis }: DataAnalysisPanelProps) {
  return (
    <details className="w-full max-w-2xl rounded-md border border-gray-800 bg-gray-900 p-3 text-sm text-gray-300">
      <summary className="cursor-pointer font-semibold text-white">
        What we found in your data ({analysis.entities.length} entities,{" "}
        {analysis.entities.reduce((acc, e) => acc + e.fields.length, 0)} columns)
      </summary>
      <div className="mt-3 space-y-3">
        {analysis.entities.map((e) => (
          <div key={e.name}>
            <div className="font-semibold text-white">{e.name}</div>
            <div className="text-xs text-gray-400">{e.sourceFile}</div>
            <div className="mt-1 text-xs text-gray-300">
              {e.fields.map((f) => f.name).join(", ")}
            </div>
            {e.inferredRules.length > 0 && (
              <ul className="mt-1 list-disc pl-5 text-xs text-gray-400">
                {e.inferredRules.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
        {analysis.gaps.length > 0 && (
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-yellow-400">
              Gaps
            </div>
            <ul className="list-disc pl-5 text-xs text-yellow-200">
              {analysis.gaps.map((g, i) => (
                <li key={i}>{g}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </details>
  );
}
