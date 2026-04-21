import type { RepoActivity } from "../../types/dashboard";

interface RepoActivityGroupProps {
  activity: RepoActivity;
  color: string;
  shortName: string;
}

export function RepoActivityGroup({
  activity,
  color,
  shortName,
}: RepoActivityGroupProps) {
  return (
    <div className="space-y-1">
      <div
        className="flex items-center gap-2 border-b border-white/5 pb-1 text-xs font-semibold"
        style={{ color }}
      >
        <span
          className="inline-block h-1.5 w-1.5 rounded-sm"
          style={{ backgroundColor: color }}
        />
        {shortName}
      </div>
      {activity.events.length === 0 ? (
        <div className="ml-3 text-[10px] italic text-gray-600">
          No recent activity
        </div>
      ) : (
        activity.events.map((ev, i) => (
          <div
            key={`${ev.kind}-${i}`}
            className="ml-1 border-l border-[#c2662d]/20 pl-3 py-1 text-[11px] text-gray-300"
          >
            <div>{ev.summary}</div>
            <div className="text-[9px] text-gray-500">
              {relative(ev.occurredAt)}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function relative(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const min = Math.floor(ms / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}
