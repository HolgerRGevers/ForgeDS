import { useState } from "react";
import type { FreeTextQuestion as FreeQ } from "../../types/wizard";

interface FreeTextQuestionProps {
  question: FreeQ;
  initialValue?: string;
  onAnswer: (text: string) => void;
  onBack: () => void;
  progressLabel: string;
  totalDots: number;
  currentDot: number;
}

export function FreeTextQuestion({
  question,
  initialValue = "",
  onAnswer,
  onBack,
  progressLabel,
  totalDots,
  currentDot,
}: FreeTextQuestionProps) {
  const [text, setText] = useState(initialValue);
  return (
    <div className="mx-auto w-full max-w-3xl rounded-lg border border-gray-800 bg-gray-900 p-6">
      <div className="mb-4 flex items-center gap-3 text-xs text-gray-500">
        <span className="font-semibold text-gray-300">{progressLabel}</span>
        <div className="flex flex-1 justify-end gap-2">
          {Array.from({ length: totalDots }).map((_, i) => (
            <span
              key={i}
              className={`inline-block h-2 w-2 rounded-full ${
                i < currentDot
                  ? "bg-[#c2662d]"
                  : i === currentDot
                    ? "bg-[#c2662d] ring-2 ring-[#c2662d]/30"
                    : "bg-white/15"
              }`}
            />
          ))}
        </div>
      </div>

      <h2 className="text-lg font-semibold text-white">{question.stem}</h2>
      {question.context && (
        <p className="mt-1 text-sm text-gray-400">{question.context}</p>
      )}

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={question.placeholder}
        rows={4}
        className="mt-4 w-full resize-none rounded-md border border-white/10 bg-black/40 p-3 text-sm text-white placeholder-gray-500"
      />

      <div className="mt-4 flex items-center justify-between text-xs text-gray-500">
        <button type="button" onClick={onBack} className="hover:text-white">
          ← Back
        </button>
        <button
          type="button"
          onClick={() => onAnswer(text.trim())}
          disabled={text.trim().length === 0}
          className="rounded-md bg-[#c2662d] px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
        >
          Continue →
        </button>
      </div>
    </div>
  );
}
