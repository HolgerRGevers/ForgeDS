import type { PairedQuestion as PairedQ } from "../../types/wizard";

interface PairedQuestionProps {
  question: PairedQ;
  onAnswer: (choice: "A" | "B") => void;
  onSkip: () => void;
  onBack: () => void;
  progressLabel: string;          // e.g. "Light · Question 2 of 3"
  totalDots: number;
  currentDot: number;             // 0-indexed
}

export function PairedQuestion({
  question,
  onAnswer,
  onSkip,
  onBack,
  progressLabel,
  totalDots,
  currentDot,
}: PairedQuestionProps) {
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

      <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2">
        {(["A", "B"] as const).map((letter) => {
          const opt = letter === "A" ? question.optionA : question.optionB;
          const accent = letter === "A" ? "#c2662d" : "#7c3aed";
          return (
            <button
              key={letter}
              type="button"
              onClick={() => onAnswer(letter)}
              className="flex flex-col gap-3 rounded-lg border border-white/10 bg-white/5 p-4 text-left transition-colors hover:border-[#c2662d]/50 hover:bg-[#c2662d]/5"
            >
              <div className="flex items-center gap-3">
                <span
                  className="flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold text-white"
                  style={{ backgroundColor: accent }}
                >
                  {letter}
                </span>
                <span className="text-sm font-semibold text-white">
                  {opt.title}
                </span>
              </div>
              <div
                className="rounded-md bg-black/30 px-3 py-2 text-xs text-gray-200"
                style={{ borderLeft: `2px solid ${accent}` }}
              >
                <div className="text-[9px] font-semibold uppercase tracking-wider text-gray-400">
                  Reason
                </div>
                <div>{opt.reason}</div>
              </div>
              <div className="rounded-md bg-black/30 px-3 py-2 text-xs text-gray-200 border-l-2 border-green-500">
                <div className="text-[9px] font-semibold uppercase tracking-wider text-gray-400">
                  Consequence
                </div>
                <div>{opt.consequence}</div>
              </div>
            </button>
          );
        })}
      </div>

      <div className="mt-5 flex items-center justify-between text-xs text-gray-500">
        <button type="button" onClick={onBack} className="hover:text-white">
          ← Back
        </button>
        <button type="button" onClick={onSkip} className="hover:text-white">
          Skip — let AI decide →
        </button>
      </div>
    </div>
  );
}
