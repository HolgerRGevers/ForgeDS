import { useState } from "react";
import { AppCard } from "./AppCard";
import { PinRepoCard } from "./PinRepoCard";
import { PinRepoModal } from "./PinRepoModal";
import type { DashboardApp } from "../../types/dashboard";

interface AppCardGridProps {
  apps: DashboardApp[];
  loading: boolean;
}

export function AppCardGrid({ apps, loading }: AppCardGridProps) {
  const [pinModalOpen, setPinModalOpen] = useState(false);

  return (
    <>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {loading && apps.length === 0 ? (
          <div className="col-span-full text-sm text-gray-500">Loading apps…</div>
        ) : (
          <>
            {apps.map((app) => (
              <AppCard key={app.fullName} app={app} />
            ))}
            <PinRepoCard onClick={() => setPinModalOpen(true)} />
          </>
        )}
      </div>
      {pinModalOpen && <PinRepoModal onClose={() => setPinModalOpen(false)} />}
    </>
  );
}
