import type { WizardDepth } from "../../types/wizard";

interface DepthPickerProps {
  onPick: (d: WizardDepth) => void;
}

const tiers: Array<{
  id: WizardDepth;
  label: string;
  blurb: string;
  est: string;
}> = [
  { id: "light", label: "Light", blurb: "3 quick A/B picks", est: "~2 min" },
  { id: "mid", label: "Mid", blurb: "1-2 short answers + paired picks", est: "~5 min" },
  { id: "heavy", label: "Heavy", blurb: "Thorough Q&A + parallel-agent synthesis", est: "~10 min" },
  { id: "dev", label: "Dev", blurb: "Heavy + persona round-table critique", est: "~15 min" },
];

export function DepthPicker({ onPick }: DepthPickerProps) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
      {tiers.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onPick(t.id)}
          className="flex flex-col gap-2 rounded-lg border border-gray-800 bg-gray-900 p-4 text-left transition-colors hover:border-[#c2662d] hover:bg-[#c2662d]/5"
        >
          <div className="text-base font-semibold text-white">{t.label}</div>
          <div className="text-xs text-gray-300">{t.blurb}</div>
          <div className="text-[10px] uppercase tracking-wider text-[#c2662d]">{t.est}</div>
        </button>
      ))}
    </div>
  );
}
