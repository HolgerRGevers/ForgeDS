import { useCallback, useEffect, useState } from "react";
import {
  ApiAiPrompt,
  ApiCodePreview,
  ApiList,
  ApiWizard,
} from "../components/api";
import { useApiStore } from "../stores/apiStore";
import { useBridgeStore } from "../stores/bridgeStore";

/* ------------------------------------------------------------------ */
/*  Export modal                                                       */
/* ------------------------------------------------------------------ */

function ExportModal({
  instructions,
  onClose,
}: {
  instructions: string;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="mx-4 w-full max-w-2xl rounded-lg border border-gray-700 bg-gray-900 shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-700 px-6 py-4">
          <h2 className="text-lg font-semibold text-white">
            Export Setup Instructions
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-white"
          >
            &times;
          </button>
        </div>
        <div className="max-h-[60vh] overflow-y-auto px-6 py-4">
          <pre className="whitespace-pre-wrap text-sm text-gray-300">
            {instructions}
          </pre>
        </div>
        <div className="flex justify-end border-t border-gray-700 px-6 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded bg-gray-700 px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-600"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Empty state                                                        */
/* ------------------------------------------------------------------ */

function EmptyState() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="text-center">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="mx-auto h-12 w-12 text-gray-600"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
          />
        </svg>
        <p className="mt-3 text-sm text-gray-400">
          Select an API or create a new one
        </p>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main page                                                          */
/* ------------------------------------------------------------------ */

export default function ApiPage() {
  const selectedApiId = useApiStore((s) => s.selectedApiId);
  const draftApi = useApiStore((s) => s.draftApi);
  const isCreating = useApiStore((s) => s.isCreating);
  const wizardStep = useApiStore((s) => s.wizardStep);
  const setApis = useApiStore((s) => s.setApis);

  const bridgeStatus = useBridgeStore((s) => s.status);
  const connect = useBridgeStore((s) => s.connect);
  const send = useBridgeStore((s) => s.send);

  const [exportInstructions, setExportInstructions] = useState<string | null>(
    null,
  );
  const [exportError, setExportError] = useState<string | null>(null);

  // On mount: connect to bridge and load API list
  useEffect(() => {
    if (bridgeStatus === "disconnected") {
      connect();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch API list once connected
  useEffect(() => {
    if (bridgeStatus !== "connected") return;

    const loadApis = async () => {
      try {
        const response = await send("get_api_list", {});
        if (response.apis && Array.isArray(response.apis)) {
          setApis(
            response.apis as ReturnType<typeof useApiStore.getState>["apis"],
          );
        }
      } catch {
        // Bridge may not support get_api_list yet -- silently ignore
      }
    };

    loadApis();
  }, [bridgeStatus, send, setApis]);

  // Export handler
  const handleExport = useCallback(async () => {
    if (!draftApi) return;

    setExportError(null);
    try {
      const response = await send("export_api", {
        apiId: draftApi.id,
        api: draftApi as unknown as Record<string, unknown>,
      });
      if (response.instructions && typeof response.instructions === "string") {
        setExportInstructions(response.instructions);
      } else {
        setExportInstructions(
          `API "${draftApi.name}" exported successfully.\n\nLink Name: ${draftApi.linkName}\nMethod: ${draftApi.method}\nFunction: ${draftApi.functionName}`,
        );
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Export failed";
      setExportError(message);
    }
  }, [draftApi, send]);

  // Whether we're in edit/create mode (draft exists)
  const hasDraft = draftApi !== null && isCreating;

  return (
    <div className="flex h-full flex-col bg-gray-950">
      {/* Main content area */}
      <div className="flex min-h-0 flex-1">
        {/* Left column: API list (~300px) */}
        <div className="w-[300px] shrink-0 border-r border-gray-800 p-3">
          <ApiList />
        </div>

        {/* Right column (flex-1) */}
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          {hasDraft ? (
            /* Edit/Create mode: wizard on top, code preview on bottom */
            <>
              {/* Export button bar (visible on summary step for existing APIs) */}
              {wizardStep === "summary" && selectedApiId && (
                <div className="flex items-center justify-end border-b border-gray-800 px-4 py-2">
                  <button
                    type="button"
                    onClick={handleExport}
                    disabled={bridgeStatus !== "connected"}
                    className="rounded bg-green-600 px-4 py-1.5 text-xs font-medium text-white transition-colors hover:bg-green-500 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Export
                  </button>
                  {exportError && (
                    <span className="ml-2 text-xs text-red-400">
                      {exportError}
                    </span>
                  )}
                </div>
              )}

              {/* Wizard (top) */}
              <div className="min-h-0 flex-1 overflow-y-auto p-4">
                <ApiWizard />
              </div>

              {/* Code preview (bottom) */}
              <div className="h-[280px] shrink-0 border-t border-gray-800 p-3">
                <ApiCodePreview />
              </div>
            </>
          ) : (
            /* No draft -- show empty state */
            <EmptyState />
          )}
        </div>
      </div>

      {/* Bottom bar: AI prompt (always visible) */}
      <div className="shrink-0 border-t border-gray-800 px-4 py-3">
        <ApiAiPrompt />
      </div>

      {/* Export modal */}
      {exportInstructions && (
        <ExportModal
          instructions={exportInstructions}
          onClose={() => setExportInstructions(null)}
        />
      )}
    </div>
  );
}
