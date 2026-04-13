import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ApiAiPrompt,
  ApiCodePreview,
  ApiList,
  ApiWizard,
} from "../components/api";
import { useApiStore } from "../stores/apiStore";
import { useBridgeStore } from "../stores/bridgeStore";
import { useIdeStore } from "../stores/ideStore";

/* ------------------------------------------------------------------ */
/*  Export modal                                                       */
/* ------------------------------------------------------------------ */

function ExportModal({
  instructions,
  onClose,
  onOpenInIde,
}: {
  instructions: string;
  onClose: () => void;
  onOpenInIde?: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-2xl rounded-lg border border-gray-700 bg-gray-900 shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-700 px-4 py-3 sm:px-6 sm:py-4">
          <h2 className="text-base font-semibold text-white sm:text-lg">
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
        <div className="max-h-[50vh] overflow-y-auto px-4 py-4 sm:max-h-[60vh] sm:px-6">
          <pre className="whitespace-pre-wrap text-sm text-gray-300">
            {instructions}
          </pre>
        </div>
        <div className="flex flex-wrap justify-end gap-2 border-t border-gray-700 px-4 py-3 sm:px-6">
          {onOpenInIde && (
            <button
              type="button"
              onClick={onOpenInIde}
              className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
            >
              Open in IDE
            </button>
          )}
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
    <div className="flex h-full items-center justify-center p-4">
      <div className="text-center">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="mx-auto h-10 w-10 text-gray-600 sm:h-12 sm:w-12"
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

  const navigate = useNavigate();

  const [exportInstructions, setExportInstructions] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportedFile, setExportedFile] = useState<{
    name: string;
    path: string;
    content: string;
  } | null>(null);
  const [showApiList, setShowApiList] = useState(true);

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
        // silently ignore
      }
    };
    loadApis();
  }, [bridgeStatus, send, setApis]);

  // Export handler
  const handleExport = useCallback(async () => {
    if (!draftApi) return;
    setExportError(null);
    setExportedFile(null);
    try {
      const response = await send("export_api", {
        apiId: draftApi.id,
        api: draftApi as unknown as Record<string, unknown>,
      });
      const file = response.file as { name: string; path: string; content: string } | undefined;
      if (file) setExportedFile(file);

      if (response.instructions && typeof response.instructions === "string") {
        setExportInstructions(response.instructions);
      } else {
        setExportInstructions(
          `API "${draftApi.name}" exported successfully.\n\nLink Name: ${draftApi.linkName}\nMethod: ${draftApi.method}\nFunction: ${draftApi.functionName}`,
        );
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Export failed";
      setExportError(message);
    }
  }, [draftApi, send]);

  // Open exported file in IDE
  const handleOpenInIde = useCallback(() => {
    if (!exportedFile) return;
    useIdeStore.getState().openTab({
      id: exportedFile.path,
      name: exportedFile.name,
      path: exportedFile.path,
      content: exportedFile.content,
      language: "deluge",
      isDirty: false,
    });
    navigate("/ide");
  }, [exportedFile, navigate]);

  const hasDraft = draftApi !== null && isCreating;

  return (
    <div className="flex h-full flex-col bg-gray-950">
      {/* Mobile API list toggle */}
      <button
        type="button"
        onClick={() => setShowApiList((v) => !v)}
        className="flex items-center gap-2 border-b border-gray-800 px-3 py-2 text-xs text-gray-400 hover:text-white md:hidden"
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h7" />
        </svg>
        {showApiList ? "Hide API List" : "Show API List"}
      </button>

      {/* Main content area */}
      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        {/* Left column: API list */}
        <div className={`${showApiList ? "block" : "hidden"} w-full shrink-0 border-b border-gray-800 p-3 md:block md:w-[260px] md:border-b-0 md:border-r lg:w-[300px] ${showApiList ? "max-h-[35vh] overflow-y-auto md:max-h-none md:overflow-visible" : ""}`}>
          <ApiList />
        </div>

        {/* Right column (flex-1) */}
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          {hasDraft ? (
            <>
              {/* Export button bar */}
              {wizardStep === "summary" && selectedApiId && (
                <div className="flex items-center justify-end border-b border-gray-800 px-3 py-2 sm:px-4">
                  <button
                    type="button"
                    onClick={handleExport}
                    disabled={bridgeStatus !== "connected"}
                    className="rounded bg-green-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-green-500 disabled:cursor-not-allowed disabled:opacity-50 sm:px-4"
                  >
                    Export
                  </button>
                  {exportError && (
                    <span className="ml-2 text-xs text-red-400">{exportError}</span>
                  )}
                </div>
              )}

              {/* Wizard (top) */}
              <div className="min-h-0 flex-1 overflow-y-auto p-3 sm:p-4">
                <ApiWizard />
              </div>

              {/* Code preview (bottom) */}
              <div className="h-[200px] shrink-0 border-t border-gray-800 p-2 sm:h-[280px] sm:p-3">
                <ApiCodePreview />
              </div>
            </>
          ) : (
            <EmptyState />
          )}
        </div>
      </div>

      {/* Bottom bar: AI prompt */}
      <div className="safe-bottom shrink-0 border-t border-gray-800 px-3 py-2 sm:px-4 sm:py-3">
        <ApiAiPrompt />
      </div>

      {/* Export modal */}
      {exportInstructions && (
        <ExportModal
          instructions={exportInstructions}
          onClose={() => setExportInstructions(null)}
          onOpenInIde={exportedFile ? handleOpenInIde : undefined}
        />
      )}
    </div>
  );
}
