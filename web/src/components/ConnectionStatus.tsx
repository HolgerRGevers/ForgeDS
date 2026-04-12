import { useBridgeStore } from "../stores/bridgeStore";

const dotColor: Record<string, string> = {
  connected: "bg-green-500",
  connecting: "bg-yellow-400 animate-pulse",
  disconnected: "bg-red-500",
};

const labelText: Record<string, string> = {
  connected: "Connected",
  connecting: "Connecting\u2026",
  disconnected: "Disconnected",
};

export function ConnectionStatus() {
  const status = useBridgeStore((s) => s.status);
  const connect = useBridgeStore((s) => s.connect);

  const isClickable = status === "disconnected";

  return (
    <button
      type="button"
      onClick={isClickable ? connect : undefined}
      title={isClickable ? "Click to retry" : undefined}
      className={`inline-flex items-center gap-1.5 rounded px-2 py-1 text-xs font-medium select-none ${
        isClickable
          ? "cursor-pointer hover:bg-zinc-700/50"
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
