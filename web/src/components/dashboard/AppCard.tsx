import { useNavigate } from "react-router-dom";
import { useRepoStore } from "../../stores/repoStore";
import type { DashboardApp } from "../../types/dashboard";

interface AppCardProps {
  app: DashboardApp;
}

export function AppCard({ app }: AppCardProps) {
  const navigate = useNavigate();
  const setSelectedRepoByFullName = useRepoStore(
    (s) => s.setSelectedRepoByFullName,
  );

  const onOpen = async () => {
    await setSelectedRepoByFullName(app.fullName);
    navigate("/ide");
  };

  const meta =
    app.source === "manifest"
      ? `forgeds.yaml · ${formatDate(app.lastUpdated)}`
      : `pinned · ${formatDate(app.lastUpdated)}`;

  return (
    <button
      type="button"
      onClick={onOpen}
      className="flex flex-col gap-2 rounded-lg border border-gray-800 bg-gray-900 p-4 text-left transition-colors hover:border-gray-600 hover:bg-gray-800"
    >
      <div
        className="flex h-9 w-9 items-center justify-center rounded-md font-bold text-white"
        style={{ backgroundColor: app.badgeColor }}
      >
        {app.badge}
      </div>
      <div className="text-sm font-semibold text-white">{app.displayName}</div>
      <div className="text-[10px] text-gray-500">{meta}</div>
    </button>
  );
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}
