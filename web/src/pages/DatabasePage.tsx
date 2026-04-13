import { useCallback, useEffect, useState } from "react";
import { useDatabaseStore } from "../stores/databaseStore";
import { useBridgeStore } from "../stores/bridgeStore";
import {
  SourceTargetPanel,
  FieldMappingTable,
  ValidationConsole,
  UploadWizard,
} from "../components/database";

type BottomTab = "validation" | "upload";

export default function DatabasePage() {
  const status = useBridgeStore((s) => s.status);
  const connect = useBridgeStore((s) => s.connect);
  const send = useBridgeStore((s) => s.send);

  const accessTables = useDatabaseStore((s) => s.accessTables);
  const zohoForms = useDatabaseStore((s) => s.zohoForms);
  const setAccessTables = useDatabaseStore((s) => s.setAccessTables);
  const setZohoForms = useDatabaseStore((s) => s.setZohoForms);
  const setTableMappings = useDatabaseStore((s) => s.setTableMappings);

  const [activeTab, setActiveTab] = useState<BottomTab>("validation");
  const [loading, setLoading] = useState(false);
  const [schemaStatus, setSchemaStatus] = useState<string | null>(null);

  // Load schema from bridge
  const loadSchema = useCallback(async () => {
    setLoading(true);
    setSchemaStatus(null);
    try {
      const response = await send("get_schema", {});
      if (response) {
        if (Array.isArray(response.accessTables)) {
          setAccessTables(response.accessTables as never[]);
        }
        if (Array.isArray(response.zohoForms)) {
          setZohoForms(response.zohoForms as never[]);
        }
        if (Array.isArray(response.tableMappings)) {
          setTableMappings(response.tableMappings as never[]);
        }
        const tableCount = Array.isArray(response.accessTables)
          ? response.accessTables.length
          : 0;
        const formCount = Array.isArray(response.zohoForms)
          ? response.zohoForms.length
          : 0;
        setSchemaStatus(`${tableCount} tables, ${formCount} forms`);
      }
    } catch {
      setSchemaStatus("Failed to load schema");
    } finally {
      setLoading(false);
    }
  }, [send, setAccessTables, setZohoForms, setTableMappings]);

  // Refresh: clear state and reload
  const refreshSchema = useCallback(async () => {
    setAccessTables([]);
    setZohoForms([]);
    setTableMappings([]);
    setSchemaStatus(null);
    await loadSchema();
  }, [loadSchema, setAccessTables, setZohoForms, setTableMappings]);

  // On mount: connect and load schema
  useEffect(() => {
    if (status === "disconnected") {
      connect();
    }
  }, [status, connect]);

  useEffect(() => {
    if (status === "connected" && accessTables.length === 0 && zohoForms.length === 0) {
      loadSchema();
    }
  }, [status, accessTables.length, zohoForms.length, loadSchema]);

  // Connection status badge
  const connectionBadge = (() => {
    switch (status) {
      case "connected":
        return (
          <span className="rounded-full bg-green-900/50 px-2 py-0.5 text-[10px] font-medium text-green-400 sm:text-xs">
            Connected
          </span>
        );
      case "connecting":
        return (
          <span className="rounded-full bg-yellow-900/50 px-2 py-0.5 text-[10px] font-medium text-yellow-400 sm:text-xs">
            Connecting...
          </span>
        );
      default:
        return (
          <span className="rounded-full bg-gray-700 px-2 py-0.5 text-[10px] font-medium text-gray-400 sm:text-xs">
            Offline
          </span>
        );
    }
  })();

  return (
    <div className="flex h-full flex-col bg-gray-900">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-700 px-3 py-2 sm:px-4">
        <div className="flex items-center gap-2">
          <button
            onClick={loadSchema}
            disabled={loading || status !== "connected"}
            className="rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Loading..." : "Load Schema"}
          </button>
          <button
            onClick={refreshSchema}
            disabled={loading || status !== "connected"}
            className="rounded border border-gray-600 bg-gray-800 px-3 py-1.5 text-xs font-medium text-gray-300 transition-colors hover:border-gray-500 hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Refresh
          </button>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          {schemaStatus && (
            <span className="text-[10px] text-gray-400 sm:text-xs">{schemaStatus}</span>
          )}
          {connectionBadge}
        </div>
      </div>

      {/* Scrollable content area — stacks vertically, each section gets a min-height */}
      <div className="min-h-0 flex-1 overflow-y-auto sm:overflow-hidden sm:flex sm:flex-col">
        {/* Source/Target Panel */}
        <div className="min-h-[200px] sm:min-h-0" style={{ flex: "4 1 0%" }}>
          {loading ? (
            <div className="flex h-full min-h-[200px] items-center justify-center">
              <div className="text-center">
                <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-gray-600 border-t-blue-500" />
                <p className="mt-3 text-sm text-gray-400">Loading schema...</p>
              </div>
            </div>
          ) : accessTables.length === 0 && zohoForms.length === 0 ? (
            <div className="flex h-full min-h-[200px] items-center justify-center">
              <div className="text-center px-4">
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
                    d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"
                  />
                </svg>
                <p className="mt-3 text-sm text-gray-400">
                  No schema loaded yet
                </p>
                <p className="mt-1 text-xs text-gray-600">
                  Click "Load Schema" to connect to your databases.
                </p>
              </div>
            </div>
          ) : (
            <SourceTargetPanel />
          )}
        </div>

        {/* Field Mapping Table */}
        <div className="min-h-[180px] border-t border-gray-700 sm:min-h-0" style={{ flex: "3.5 1 0%" }}>
          <FieldMappingTable />
        </div>

        {/* Bottom tabs */}
        <div className="flex min-h-[150px] flex-col border-t border-gray-700 sm:min-h-0" style={{ flex: "2.5 1 0%" }}>
          {/* Tab bar */}
          <div className="flex border-b border-gray-700">
            <button
              onClick={() => setActiveTab("validation")}
              className={`px-3 py-2 text-xs font-medium transition-colors sm:px-4 ${
                activeTab === "validation"
                  ? "border-b-2 border-blue-500 text-blue-400"
                  : "text-gray-400 hover:text-gray-300"
              }`}
            >
              Validation
            </button>
            <button
              onClick={() => setActiveTab("upload")}
              className={`px-3 py-2 text-xs font-medium transition-colors sm:px-4 ${
                activeTab === "upload"
                  ? "border-b-2 border-blue-500 text-blue-400"
                  : "text-gray-400 hover:text-gray-300"
              }`}
            >
              Upload
            </button>
          </div>

          {/* Tab content */}
          <div className="min-h-0 flex-1">
            {activeTab === "validation" ? <ValidationConsole /> : <UploadWizard />}
          </div>
        </div>
      </div>
    </div>
  );
}
