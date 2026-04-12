import { useToastStore } from "../stores/toastStore";
import type { Toast } from "../stores/toastStore";

const TYPE_STYLES: Record<string, { bg: string; border: string; icon: string; text: string }> = {
  success: {
    bg: "bg-green-900/90",
    border: "border-green-700/60",
    icon: "\u2713",
    text: "text-green-400",
  },
  error: {
    bg: "bg-red-900/90",
    border: "border-red-700/60",
    icon: "\u2717",
    text: "text-red-400",
  },
  info: {
    bg: "bg-blue-900/90",
    border: "border-blue-700/60",
    icon: "\u2139",
    text: "text-blue-400",
  },
};

function ToastItem({ toast }: { toast: Toast }) {
  const removeToast = useToastStore((s) => s.removeToast);
  const style = TYPE_STYLES[toast.type] ?? TYPE_STYLES.info;

  return (
    <div
      className={`pointer-events-auto flex w-80 max-w-sm items-start gap-3 rounded-lg border ${style.border} ${style.bg} px-4 py-3 shadow-xl backdrop-blur-sm animate-in fade-in slide-in-from-bottom-2`}
    >
      <span className={`mt-0.5 text-lg font-bold ${style.text}`}>{style.icon}</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-100">{toast.title}</p>
        {toast.message && (
          <p className="mt-1 text-xs text-gray-400 break-words select-all">{toast.message}</p>
        )}
      </div>
      <button
        type="button"
        onClick={() => removeToast(toast.id)}
        className="shrink-0 text-gray-500 hover:text-gray-300"
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

export function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts);

  const bottomRight = toasts.filter((t) => t.position === "bottom-right");
  const topCenter = toasts.filter((t) => t.position === "top-center");

  return (
    <>
      {/* Top center — errors */}
      {topCenter.length > 0 && (
        <div className="pointer-events-none fixed inset-x-0 top-0 z-[100] flex flex-col items-center gap-2 px-4 pt-16">
          {topCenter.map((t) => (
            <ToastItem key={t.id} toast={t} />
          ))}
        </div>
      )}

      {/* Bottom right — success/info */}
      {bottomRight.length > 0 && (
        <div className="pointer-events-none fixed bottom-0 right-0 z-[100] flex flex-col items-end gap-2 px-4 pb-4">
          {bottomRight.map((t) => (
            <ToastItem key={t.id} toast={t} />
          ))}
        </div>
      )}
    </>
  );
}
