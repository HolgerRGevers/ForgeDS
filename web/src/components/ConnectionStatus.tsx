import { useBridgeStore } from "../stores/bridgeStore";

const dotColor: Record<string, string> = {
  connected: "bg-green-500",
  connecting: "bg-yellow-400 animate-pulse",
  disconnected: "bg-red-500",
};

const labelText: Record<string, string> = {
  connected: "Local",
  connecting: "Connecting\u2026",
  disconnected: "Offline",
};

const tooltipText: Record<string, string> = {
  connected: "Bridge connected at localhost:9876 \u2014 full write access",
  connecting: "Attempting to reach local bridge\u2026",
  disconnected: "No connection \u2014 cached files only, changes queued locally",
};

export function BridgePill() {
  const status = useBridgeStore((s) => s.status);
  const connect = useBridgeStore((s) => s.connect);

  const isClickable = status === "disconnected";

  return (
    <button
      type="button"
      onClick={isClickable ? connect : undefined}
      title={tooltipText[status]}
      className={`inline-flex items-center gap-1.5 rounded-full bg-gray-700 px-2 py-0.5 text-xs select-none ${
        isClickable
          ? "cursor-pointer hover:bg-gray-600"
          : "cursor-default"
      }`}
    >
      <span
        className={`inline-block h-2 w-2 rounded-full ${dotColor[status]}`}
        aria-hidden="true"
      />
      <span className="text-zinc-300">{labelText[status]}</span>
    </button>
  );
}

export const ConnectionStatus = BridgePill;
