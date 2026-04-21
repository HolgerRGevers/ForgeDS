import { useEffect } from "react";
import { useDashboardStore } from "../stores/dashboardStore";
import { useRepoStore } from "../stores/repoStore";
import { RailWizard } from "../components/dashboard/RailWizard";
import { RepoActivityFeed } from "../components/dashboard/RepoActivityFeed";
import { AppCardGrid } from "../components/dashboard/AppCardGrid";

export default function DashboardPage() {
  const apps = useDashboardStore((s) => s.apps);
  const activity = useDashboardStore((s) => s.activity);
  const loading = useDashboardStore((s) => s.loading);
  const refresh = useDashboardStore((s) => s.refresh);
  const fetchRepos = useRepoStore((s) => s.fetchRepos);

  useEffect(() => {
    fetchRepos();
    refresh();
  }, [fetchRepos, refresh]);

  return (
    <div className="flex h-full">
      <aside className="flex w-[320px] flex-col border-r border-gray-800 bg-black/30">
        <div className="flex-1 border-b border-gray-800 p-4">
          <RailWizard />
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <RepoActivityFeed apps={apps} activity={activity} />
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto p-6">
        <div className="mb-4 flex items-center justify-between">
          <h1 className="text-base font-semibold text-white">My Apps</h1>
          <button
            type="button"
            onClick={() => refresh(true)}
            className="rounded-full bg-white/5 px-3 py-1 text-[11px] text-gray-300 hover:bg-white/10"
          >
            Refresh
          </button>
        </div>
        <AppCardGrid apps={apps} loading={loading} />
      </main>
    </div>
  );
}
