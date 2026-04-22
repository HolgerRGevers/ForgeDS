import { RepoActivityGroup } from "./RepoActivityGroup";
import type { DashboardApp, RepoActivity } from "../../types/dashboard";
import { useDashboardStore } from "../../stores/dashboardStore";

interface RepoActivityFeedProps {
  apps: DashboardApp[];
  activity: RepoActivity[];
}

export function RepoActivityFeed({ apps, activity }: RepoActivityFeedProps) {
  const legacyPrompts = useDashboardStore((s) => s.legacyPrompts);

  return (
    <div className="flex flex-col gap-3">
      {apps.length === 0 ? (
        <div className="text-xs text-gray-500">
          Activity will appear here once you have apps with <code>forgeds.yaml</code> or pinned repos.
        </div>
      ) : (
        <>
          <div className="text-[10px] font-semibold uppercase tracking-wider text-gray-500">
            Recent activity
          </div>
          {apps.map((app) => {
            const a = activity.find((x) => x.repoFullName === app.fullName);
            return (
              <RepoActivityGroup
                key={app.fullName}
                activity={a ?? { repoFullName: app.fullName, events: [] }}
                color={app.badgeColor}
                shortName={app.displayName}
              />
            );
          })}
        </>
      )}

      {legacyPrompts.length > 0 && (
        <div className="mt-3 border-t border-white/5 pt-3">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-gray-600">
            Local prompts (will disappear after 30 days)
          </div>
          {legacyPrompts.slice(0, 8).map((item) => (
            <div key={item.id} className="mt-1 truncate text-[10px] text-gray-500">
              {new Date(item.timestamp).toLocaleDateString()} — {item.prompt.slice(0, 50)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
