import { RepoActivityGroup } from "./RepoActivityGroup";
import type { DashboardApp, RepoActivity } from "../../types/dashboard";

interface RepoActivityFeedProps {
  apps: DashboardApp[];
  activity: RepoActivity[];
}

export function RepoActivityFeed({ apps, activity }: RepoActivityFeedProps) {
  if (apps.length === 0) {
    return (
      <div className="text-xs text-gray-500">
        Activity will appear here once you have apps with <code>forgeds.yaml</code> or pinned repos.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
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
    </div>
  );
}
